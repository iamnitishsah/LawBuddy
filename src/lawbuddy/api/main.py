"""HTTP API for LawBuddy.

    uvicorn lawbuddy.api.main:app --reload                 # local: http://localhost:8000/docs
    uvicorn lawbuddy.api.main:app --host 0.0.0.0 --port 8000

Endpoints (all JSON unless noted):
    GET    /health                          is the process up; default model; KB size; retrieval mode
    GET    /backends                        models the client can switch between, and which have a server key
    POST   /sessions                        start a conversation (optionally with a default model)
    GET    /sessions/{id}                   messages, case file, drafts
    DELETE /sessions/{id}                   forget a conversation
    POST   /sessions/{id}/messages          one turn: {"message": "...", "llm": {...}}
    POST   /sessions/{id}/voice             one turn from audio (multipart: audio, language?, backend?, model?)
    POST   /sessions/{id}/draft             draft the legal notice now, from the case so far
    GET    /sessions/{id}/drafts/{n}        download a drafted notice (text/markdown)
    POST   /transcribe                      audio -> text only (multipart: audio, language?)

Model swapping and the user's own key:
    A request may choose the model: "llm": {"backend": "gemini", "model": "..."} in the body (form fields for voice).
    The header X-LLM-API-Key, if present, is used instead of the server's key for that provider, for that request
    only. Keys are never stored, logged or returned. Backend "custom" (any OpenAI-compatible base_url, https only)
    is refused unless ALLOW_CUSTOM_LLM_BASE_URL=1, because it makes the server call a URL the client chooses.
    Retrieval always uses the server's NVIDIA key.

Settings from the environment (.env):
    LAWBUDDY_API_KEY             if set, every /sessions and /transcribe call needs the header X-API-Key: <value>
    CORS_ORIGINS                 comma-separated origins allowed to call the API from a browser
    RATE_LIMIT_PER_MIN           requests per minute per client IP on protected endpoints (default 20; 0 disables)
    ALLOW_CUSTOM_LLM_BASE_URL    1 to allow backend "custom"
    SESSION_TTL_MIN              idle minutes before a conversation is forgotten (default 120)
    MAX_SESSIONS                 conversations kept in memory (default 500; the oldest idle one is dropped)
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
import uuid
from collections import OrderedDict, defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from lawbuddy.api.schemas import (BackendInfo, BackendsResponse, CaseInfo, ChatResponse, DraftInfo, DraftRequest,
                                  GuardInfo, HealthResponse, LLMSettings, Message, MessageRequest, RetrievalInfo,
                                  SessionCreate, SessionInfo, Source, TranscriptionResponse, Usage)

log = logging.getLogger("lawbuddy.api")
KEY_PATTERN_RE = re.compile(r"\b(?:sk|gsk|nvapi|AIza|AQ)[-_.A-Za-z0-9]{12,}")


# --- rate limit and access ---------------------------------------------------------------------------------

class RateLimiter:
    """At most `per_minute` calls per key in any 60-second window (in memory, one process)."""

    def __init__(self, per_minute: int):
        self.per_minute, self.calls = per_minute, defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        if self.per_minute <= 0:
            return True
        now = time.monotonic() if now is None else now
        with self.lock:
            q = self.calls[key]
            while q and now - q[0] >= 60:
                q.popleft()
            if len(q) >= self.per_minute:
                return False
            q.append(now)
            return True


def access_guard(limiter: RateLimiter):
    """FastAPI dependency for protected endpoints: API key (when configured) and rate limit."""

    def guard(request: Request, x_api_key: str | None = Header(default=None)) -> None:
        expected = os.getenv("LAWBUDDY_API_KEY")
        if expected and x_api_key != expected:
            raise HTTPException(status_code=401, detail="missing or wrong X-API-Key header")
        client = request.client.host if request.client else "unknown"
        if not limiter.allow(client):
            raise HTTPException(status_code=429, detail="too many requests; try again in a minute")

    return guard


def redact(text: str, *secrets: str | None) -> str:
    """Error text with any key removed: the user's own key, and anything shaped like a provider key."""
    for s in secrets:
        if s:
            text = text.replace(s, "[key]")
    return KEY_PATTERN_RE.sub("[key]", text)


class PerThreadRetriever:
    """One retriever shared by all requests, but `last_mode` / `last_error` (read by the engine right after a
    search) belong to the calling thread: otherwise two conversations searching at once could see each other's
    mode, and the rerank score floor could be applied to keyword scores."""

    def __init__(self, inner):
        self.inner, self.lock, self.local = inner, threading.Lock(), threading.local()

    def search(self, query: str, k: int | None = None, **filters) -> list[dict]:
        with self.lock:
            hits = self.inner.search(query, k=k, **filters)
            self.local.mode = getattr(self.inner, "last_mode", "primary")
            self.local.error = getattr(self.inner, "last_error", "")
        return hits

    @property
    def last_mode(self) -> str:
        return getattr(self.local, "mode", "primary")

    @property
    def last_error(self) -> str:
        return getattr(self.local, "error", "")


# --- dependencies (built once at startup; faked in tests) --------------------------------------------------

@dataclass
class AppDeps:
    registry: dict
    conv_cfg: dict
    retriever: object
    min_score: float | None
    retrieval_label: str
    make_llm: Callable                  # (LLMSettings, api_key | None) -> LLM; raises MissingKey / ValueError
    make_transcriber: Callable          # (api_key | None) -> Transcriber; raises MissingKey
    kb_chunks: int = 0
    kb_verified: int = 0
    log_turns: bool = True


def build_deps() -> AppDeps:  # pragma: no cover - needs the server's keys and the KB index
    from dotenv import load_dotenv

    from lawbuddy.conversation.engine import ROOT, load_config as load_conv_config
    from lawbuddy.kb.loader import load_kb, load_registry
    from lawbuddy.llm.base import get_llm
    from lawbuddy.retrieval.factory import get_retriever, load_config as load_retrieval_config
    from lawbuddy.voice.transcribe import get_transcriber

    from lawbuddy.retrieval.factory import KeywordOnly

    load_dotenv(ROOT / ".env")
    conv = load_conv_config()
    retriever = get_retriever(conv["retriever"], log=log.warning)
    label = retriever.last_error if isinstance(retriever, KeywordOnly) else conv["retriever"]
    retriever = PerThreadRetriever(retriever)
    floors = load_retrieval_config()["search"].get("min_score") or {}
    kb = load_kb()

    def make_llm(s: LLMSettings, api_key: str | None):
        return get_llm(s.backend, model=s.model, api_key=api_key, base_url=s.base_url)

    return AppDeps(registry=load_registry(), conv_cfg=conv, retriever=retriever, min_score=floors.get(conv["retriever"]),
                   retrieval_label=label, make_llm=make_llm, make_transcriber=get_transcriber,
                   kb_chunks=len(kb), kb_verified=sum(bool(c.verified_on) for c in kb))


# --- sessions ----------------------------------------------------------------------------------------------

@dataclass
class Entry:
    session: object                                 # conversation.engine.Session
    llm: LLMSettings
    created_at: str
    last_used: float
    drafts: list[DraftInfo] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)


class SessionStore:
    """Conversations in memory, dropped after `ttl_s` idle or when more than `max_sessions` exist (oldest first).
    One process only: a multi-worker deployment would need a shared store."""

    def __init__(self, ttl_s: float, max_sessions: int, clock=time.monotonic):
        self.ttl_s, self.max_sessions, self.clock = ttl_s, max_sessions, clock
        self.entries: OrderedDict[str, Entry] = OrderedDict()
        self.lock = threading.Lock()

    def _expire(self) -> None:
        now = self.clock()
        for sid in [sid for sid, e in self.entries.items() if now - e.last_used > self.ttl_s]:
            del self.entries[sid]
        while len(self.entries) > self.max_sessions:
            self.entries.popitem(last=False)

    def create(self, llm: LLMSettings) -> Entry:
        from lawbuddy.conversation.engine import Session
        with self.lock:
            self._expire()
            s = Session(id=uuid.uuid4().hex)
            e = Entry(s, llm, datetime.now(timezone.utc).isoformat(timespec="seconds"), self.clock())
            self.entries[s.id] = e
            self._expire()
            return e

    def get(self, sid: str) -> Entry:
        with self.lock:
            self._expire()
            e = self.entries.get(sid)
            if e is None:
                raise HTTPException(status_code=404, detail="no such conversation (it may have expired)")
            e.last_used = self.clock()
            self.entries.move_to_end(sid)
            return e

    def delete(self, sid: str) -> None:
        with self.lock:
            if self.entries.pop(sid, None) is None:
                raise HTTPException(status_code=404, detail="no such conversation")

    def __len__(self) -> int:
        return len(self.entries)


# --- converting engine output to API models ----------------------------------------------------------------

def merge_llm(base: LLMSettings, override: LLMSettings | None) -> LLMSettings:
    if override is None:
        return base
    return LLMSettings(**{**base.model_dump(), **override.model_dump(exclude_none=True)})


def case_info(case) -> CaseInfo:
    d = case.to_dict()
    return CaseInfo(**{k: d[k] for k in CaseInfo.model_fields if k in d}, missing=case.missing())


def error_of(reply, *secrets) -> str | None:
    if reply.kind != "error":
        return None
    line = next((t for t in reply.trace if t.startswith("error:")), "error: unknown")
    return redact(line.removeprefix("error: "), *secrets)


def to_response(entry: Entry, reply, llm, draft: DraftInfo | None, transcript: str | None, api_key: str | None,
                latency_s: float) -> ChatResponse:
    cited = set(reply.cited)
    sources = [Source(n=n, cited=n in cited, chunk_id=p["chunk_id"], title=p.get("title", ""),
                      category=p.get("category", ""), kind=p.get("kind", ""), score=round(float(p["score"]), 4),
                      urls=[s["url"] for s in p.get("sources", []) if s.get("url")], verified_on=p.get("verified_on"))
               for n, p in enumerate(reply.passages, start=1)]
    g = reply.guard or {}
    fmt = lambda ps: [f"{p['kind']}: {p['text']}" for p in ps or []]          # noqa: E731
    guard = GuardInfo(checked=bool(g), regenerated=g.get("regenerated", False), removed=g.get("removed", False),
                      first_problems=fmt(g.get("first_problems")), problems=fmt(g.get("problems")),
                      uncited_sentences=len(g.get("uncited_sentences") or []))
    r = reply.retrieval or {}
    retrieval = RetrievalInfo(**{k: r.get(k) for k in RetrievalInfo.model_fields}) if r else None
    u = reply.usage or {}
    return ChatResponse(session_id=entry.session.id, kind=reply.kind, text=reply.text, language=reply.language,
                        category=reply.category, sources=sources, case=case_info(entry.session.case), guard=guard,
                        retrieval=retrieval, draft=draft, transcript=transcript,
                        model=f"{llm.name} / {llm.model}" if llm else "", steps=[redact(t, api_key) for t in reply.trace],
                        error=error_of(reply, api_key),
                        usage=Usage(**{k: u.get(k, 0) for k in Usage.model_fields}),
                        latency_ms=int(latency_s * 1000))


# --- the app -----------------------------------------------------------------------------------------------

def create_app(deps: AppDeps | None = None) -> FastAPI:
    """`deps` is passed by tests; in production it is built at startup from .env and configs/."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.deps = deps or build_deps()
        log.info("ready: %d KB chunks, retrieval %s", app.state.deps.kb_chunks, app.state.deps.retrieval_label)
        yield

    app = FastAPI(title="LawBuddy", version="0.5.0", lifespan=lifespan,
                  description="An AI lawyer that an ordinary person in India can talk to about a legal problem: "
                              "security deposits, consumer refunds and unpaid salary, under central and Karnataka law.")
    origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
               if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST", "DELETE"],
                       allow_headers=["*"], expose_headers=["Content-Disposition"])
    guard = access_guard(RateLimiter(int(os.getenv("RATE_LIMIT_PER_MIN", "20"))))
    app.state.guard = guard
    store = SessionStore(ttl_s=float(os.getenv("SESSION_TTL_MIN", "120")) * 60,
                         max_sessions=int(os.getenv("MAX_SESSIONS", "500")))
    app.state.store = store
    protected = [Depends(guard)]

    def get_llm_for(request: Request, settings: LLMSettings, api_key: str | None):
        from lawbuddy.llm.base import CUSTOM, MissingKey
        if settings.backend == CUSTOM:
            if os.getenv("ALLOW_CUSTOM_LLM_BASE_URL", "").strip() not in ("1", "true", "yes"):
                raise HTTPException(status_code=403, detail="the custom backend is disabled on this server")
            if not (settings.base_url or "").startswith("https://"):
                raise HTTPException(status_code=422, detail="the custom backend needs an https:// base_url")
        try:
            return request.app.state.deps.make_llm(settings, api_key)
        except MissingKey as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None

    def engine_for(request: Request, llm):
        from lawbuddy.conversation.engine import Engine
        d = request.app.state.deps
        return Engine(llm, d.retriever, d.registry, d.conv_cfg, min_score=d.min_score)

    def provider_rejected_key(reply) -> bool:
        return reply.kind == "error" and any("AuthenticationError" in t or "PermissionDenied" in t
                                             for t in reply.trace)

    def finish(request: Request, entry: Entry, reply, llm, message: str, api_key: str | None, t0: float,
               transcript: str | None = None) -> ChatResponse:
        if provider_rejected_key(reply):
            raise HTTPException(status_code=401, detail=f"the {llm.name} API rejected the API key "
                                                        "(check X-LLM-API-Key, or the server's key)")
        draft = None
        if reply.kind == "draft" and reply.draft:
            draft = DraftInfo(n=len(entry.drafts) + 1, **{k: reply.draft[k] for k in
                                                          ("category", "text", "placeholders", "warnings", "chunks")})
            entry.drafts.append(draft)
        if request.app.state.deps.log_turns:
            from lawbuddy.conversation.engine import log_turn
            try:
                log_turn(entry.session, message, reply, f"{llm.name} / {llm.model}")
            except OSError:
                log.warning("could not write the turn log")
        return to_response(entry, reply, llm, draft, transcript, api_key, time.monotonic() - t0)

    # -- open endpoints ---------------------------------------------------------------------------------------

    @app.get("/health", response_model=HealthResponse)
    def health(request: Request) -> HealthResponse:
        from lawbuddy.llm.base import load_config, resolve_backend
        d = request.app.state.deps
        backend, _ = resolve_backend()
        model = load_config()["backends"].get(backend, {}).get("model")
        return HealthResponse(status="ok", backend=backend, llm=model, kb_chunks=d.kb_chunks,
                              kb_verified=d.kb_verified, retrieval=d.retrieval_label, sessions=len(store))

    @app.get("/backends", response_model=BackendsResponse)
    def backends() -> BackendsResponse:
        from lawbuddy.llm.base import load_config, resolve_backend
        cfg = load_config()
        default, _ = resolve_backend()
        items = [BackendInfo(name=n, model=b["model"], base_url=b["base_url"], server_key=bool(os.getenv(b["api_key_env"])),
                             default=n == default) for n, b in cfg["backends"].items()]
        t = cfg["transcription"]
        return BackendsResponse(backends=items,
                                custom_allowed=os.getenv("ALLOW_CUSTOM_LLM_BASE_URL", "") in ("1", "true", "yes"),
                                transcription_model=t["model"],
                                transcription_server_key=bool(os.getenv(cfg["backends"][t["backend"]]["api_key_env"])))

    # -- sessions ---------------------------------------------------------------------------------------------

    @app.post("/sessions", response_model=SessionInfo, dependencies=protected, status_code=201)
    def create_session(body: SessionCreate | None = None) -> SessionInfo:
        return session_info(store.create((body.llm if body and body.llm else None) or LLMSettings()))

    def session_info(e: Entry) -> SessionInfo:
        s = e.session
        return SessionInfo(session_id=s.id, created_at=e.created_at, language=s.language, llm=e.llm,
                           messages=[Message(**m) for m in s.messages], case=case_info(s.case), drafts=e.drafts)

    @app.get("/sessions/{session_id}", response_model=SessionInfo, dependencies=protected)
    def get_session(session_id: str) -> SessionInfo:
        return session_info(store.get(session_id))

    @app.delete("/sessions/{session_id}", status_code=204, dependencies=protected)
    def delete_session(session_id: str) -> Response:
        store.delete(session_id)
        return Response(status_code=204)

    @app.post("/sessions/{session_id}/messages", response_model=ChatResponse, dependencies=protected)
    def send_message(session_id: str, body: MessageRequest, request: Request,
                     x_llm_api_key: str | None = Header(default=None)) -> ChatResponse:
        entry = store.get(session_id)
        llm = get_llm_for(request, merge_llm(entry.llm, body.llm), x_llm_api_key)
        t0 = time.monotonic()
        with entry.lock:                                  # one turn at a time per conversation
            reply = engine_for(request, llm).turn(entry.session, body.message.strip())
            return finish(request, entry, reply, llm, body.message, x_llm_api_key, t0)

    @app.post("/sessions/{session_id}/voice", response_model=ChatResponse, dependencies=protected)
    def send_voice(session_id: str, request: Request, audio: UploadFile = File(...),
                   language: str | None = Form(None), backend: str | None = Form(None),
                   model: str | None = Form(None), x_llm_api_key: str | None = Header(default=None)) -> ChatResponse:
        entry = store.get(session_id)
        settings = merge_llm(entry.llm, LLMSettings(backend=backend, model=model))
        llm = get_llm_for(request, settings, x_llm_api_key)
        t0 = time.monotonic()
        text, t = transcribe_upload(request, audio, language, settings, x_llm_api_key)
        if not text:
            raise HTTPException(status_code=422, detail="no speech was recognised in the audio")
        with entry.lock:
            reply = engine_for(request, llm).turn(entry.session, text)
            reply.trace.insert(0, f"voice: {t.model} heard {t.language or 'unknown language'} in {t.latency_s}s"
                                  + (f" ({t.note})" if t.note else ""))
            return finish(request, entry, reply, llm, text, x_llm_api_key, t0, transcript=text)

    @app.post("/sessions/{session_id}/draft", response_model=ChatResponse, dependencies=protected)
    def draft_now(session_id: str, request: Request, body: DraftRequest | None = None,
                  x_llm_api_key: str | None = Header(default=None)) -> ChatResponse:
        entry = store.get(session_id)
        llm = get_llm_for(request, merge_llm(entry.llm, body.llm if body else None), x_llm_api_key)
        t0 = time.monotonic()
        with entry.lock:
            try:
                reply = engine_for(request, llm).draft(entry.session)
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from None
            return finish(request, entry, reply, llm, "(draft requested)", x_llm_api_key, t0)

    @app.get("/sessions/{session_id}/drafts/{n}", dependencies=protected,
             responses={200: {"content": {"text/markdown": {}}}})
    def download_draft(session_id: str, n: int) -> Response:
        entry = store.get(session_id)
        if not 1 <= n <= len(entry.drafts):
            raise HTTPException(status_code=404, detail="no such draft")
        d = entry.drafts[n - 1]
        return Response(d.text + "\n", media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="legal-notice-{d.category}-{n}.md"'})

    # -- voice ------------------------------------------------------------------------------------------------

    def transcribe_upload(request: Request, audio: UploadFile, language: str | None, settings: LLMSettings,
                          user_key: str | None):
        """-> (text, Transcript). The user's key is used only if their chosen LLM backend is also the transcription
        backend (a Gemini key cannot call Groq's Whisper)."""
        from lawbuddy.llm.base import MissingKey, load_config, resolve_backend
        t_backend = load_config()["transcription"]["backend"]
        chosen, _ = resolve_backend(settings.backend)
        key = user_key if chosen == t_backend else None
        try:
            transcriber = request.app.state.deps.make_transcriber(key)
        except MissingKey as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        data = audio.file.read()
        try:
            t = transcriber.transcribe(data, audio.filename or "audio", language)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        except Exception as exc:                          # the transcription API failed
            name = type(exc).__name__
            status = 401 if "Authentication" in name or "PermissionDenied" in name else 502
            raise HTTPException(status_code=status,
                                detail=f"transcription failed: {redact(f'{name}: {exc}', key)[:200]}") from None
        return t.text, t

    @app.post("/transcribe", response_model=TranscriptionResponse, dependencies=protected)
    def transcribe(request: Request, audio: UploadFile = File(...), language: str | None = Form(None),
                   x_llm_api_key: str | None = Header(default=None)) -> TranscriptionResponse:
        from lawbuddy.llm.base import load_config
        t0 = time.monotonic()
        backend = load_config()["transcription"]["backend"]
        _, t = transcribe_upload(request, audio, language, LLMSettings(backend=backend), x_llm_api_key)
        return TranscriptionResponse(text=t.text, language=t.language, duration_s=t.duration_s, model=t.model,
                                     latency_ms=int((time.monotonic() - t0) * 1000), note=t.note)

    return app


app = create_app()
