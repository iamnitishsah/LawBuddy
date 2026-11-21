"""Tests for the HTTP API with a fake model, retriever and transcriber (no network)."""

import threading

import pytest
from fastapi.testclient import TestClient

from lawbuddy.api.main import AppDeps, PerThreadRetriever, RateLimiter, SessionStore, create_app, redact
from lawbuddy.api.schemas import LLMSettings
from lawbuddy.conversation.engine import load_config
from lawbuddy.kb.loader import load_registry
from lawbuddy.llm.base import MissingKey
from lawbuddy.voice.transcribe import Transcriber, Transcript
from tests.test_engine import DEPOSIT_HITS, FULL_FACTS, GOOD_ADVICE, FakeRetriever, ScriptedLLM, analysis

USER_KEY = "gsk_userkey1234567890abcdef"


class Factory:
    """make_llm for the app: hands out one scripted LLM and records how it was asked for."""

    def __init__(self):
        self.replies, self.requests = [], []

    def __call__(self, settings: LLMSettings, api_key):
        self.requests.append((settings, api_key))
        if settings.backend == "nokey":
            raise MissingKey("no API key for nokey: set NOKEY_API_KEY on the server or send your own key")
        if settings.model == "bad model":
            raise ValueError("invalid model name 'bad model'")
        llm = ScriptedLLM(*self.replies)
        llm.name, llm.model = settings.backend or "groq", settings.model or "default-model"
        self.replies = []
        return llm


class FakeTranscriber:
    max_bytes = 1_000_000
    check = Transcriber.check

    def __init__(self, text="mera deposit wapas nahi mila"):
        self.text, self.calls = text, []

    def transcribe(self, audio, filename, language=None):
        self.check(audio, filename)
        self.calls.append((filename, language))
        return Transcript(self.text, "hindi", 3.2, "whisper-fake", 0.1)


@pytest.fixture()
def app_and_client(monkeypatch):
    monkeypatch.delenv("LAWBUDDY_API_KEY", raising=False)
    monkeypatch.delenv("ALLOW_CUSTOM_LLM_BASE_URL", raising=False)
    monkeypatch.setenv("RATE_LIMIT_PER_MIN", "0")
    factory, transcriber, keys_seen = Factory(), FakeTranscriber(), []

    def make_transcriber(key):
        keys_seen.append(key)
        return transcriber

    deps = AppDeps(registry=load_registry(), conv_cfg=load_config(), retriever=FakeRetriever(DEPOSIT_HITS),
                   min_score=0.035, retrieval_label="rerank", make_llm=factory, make_transcriber=make_transcriber,
                   kb_chunks=32, kb_verified=32, log_turns=False)
    app = create_app(deps)
    with TestClient(app) as c:
        c.factory, c.transcriber, c.transcriber_keys = factory, transcriber, keys_seen
        yield app, c


@pytest.fixture()
def client(app_and_client):
    return app_and_client[1]


def new_session(client, **body):
    r = client.post("/sessions", json=body or None)
    assert r.status_code == 201
    return r.json()["session_id"]


# --- open endpoints ----------------------------------------------------------------------------------------

def test_health_and_backends(client, monkeypatch):
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["kb_chunks"] == 32 and h["retrieval"] == "rerank"
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    b = {x["name"]: x for x in client.get("/backends").json()["backends"]}
    assert b["groq"]["server_key"] and not b["gemini"]["server_key"] and "groq" in b and "nvidia" in b
    assert client.get("/backends").json()["transcription_model"]


# --- a conversation ----------------------------------------------------------------------------------------

def test_a_turn_returns_advice_with_sources_case_guard_and_usage(client):
    sid = new_session(client)
    client.factory.replies = [analysis(facts=FULL_FACTS), GOOD_ADVICE]
    r = client.post(f"/sessions/{sid}/messages", json={"message": "landlord not returning my deposit"})
    body = r.json()
    assert r.status_code == 200 and body["kind"] == "advice" and body["category"] == "deposit"
    assert body["sources"][0]["cited"] and body["sources"][0]["urls"] == ["https://x"]
    assert body["case"]["facts"]["deposit_amount"] == "Rs. 2,00,000" and body["guard"]["checked"]
    assert body["usage"]["llm_calls"] == 2 and body["model"] == "groq / default-model" and body["steps"]
    s = client.get(f"/sessions/{sid}").json()
    assert [m["role"] for m in s["messages"]] == ["user", "assistant"]


def test_a_drafted_notice_is_stored_and_downloadable(client):
    sid = new_session(client)
    client.factory.replies = [analysis(facts=FULL_FACTS, intent="draft"),
                              '{"paragraphs": ["I paid a deposit of Rs. 2,00,000."]}']
    body = client.post(f"/sessions/{sid}/messages", json={"message": "draft the notice"}).json()
    assert body["kind"] == "draft" and body["draft"]["n"] == 1 and "your full name" in body["draft"]["placeholders"]
    r = client.get(f"/sessions/{sid}/drafts/1")
    assert r.status_code == 200 and r.text.startswith("**LEGAL NOTICE**")
    assert r.headers["content-type"].startswith("text/markdown")
    assert 'filename="legal-notice-deposit-1.md"' in r.headers["content-disposition"]
    assert client.get(f"/sessions/{sid}/drafts/2").status_code == 404
    assert len(client.get(f"/sessions/{sid}").json()["drafts"]) == 1


def test_the_draft_button_needs_a_case_first(client):
    sid = new_session(client)
    assert client.post(f"/sessions/{sid}/draft").status_code == 409
    client.factory.replies = [analysis(facts=FULL_FACTS), GOOD_ADVICE]
    client.post(f"/sessions/{sid}/messages", json={"message": "deposit not returned"})
    client.factory.replies = ['{"paragraphs": ["I paid a deposit of Rs. 2,00,000."]}']
    body = client.post(f"/sessions/{sid}/draft").json()
    assert body["kind"] == "draft" and body["draft"]["category"] == "deposit"


def test_unknown_and_deleted_sessions(client):
    assert client.get("/sessions/nope").status_code == 404
    sid = new_session(client)
    assert client.delete(f"/sessions/{sid}").status_code == 204
    assert client.post(f"/sessions/{sid}/messages", json={"message": "hi"}).status_code == 404


def test_bad_input_is_rejected(client):
    sid = new_session(client)
    assert client.post(f"/sessions/{sid}/messages", json={"message": ""}).status_code == 422
    assert client.post(f"/sessions/{sid}/messages", json={}).status_code == 422
    assert client.post(f"/sessions/{sid}/messages", json={"message": "x" * 5000}).status_code == 422


# --- model swapping and the user's key ---------------------------------------------------------------------

def test_model_can_be_swapped_per_session_and_per_message(client):
    sid = new_session(client, llm={"backend": "gemini"})
    client.factory.replies = [analysis(category="out_of_scope")]
    r = client.post(f"/sessions/{sid}/messages", json={"message": "divorce"})
    assert r.json()["model"] == "gemini / default-model"
    client.factory.replies = [analysis(category="out_of_scope")]
    client.post(f"/sessions/{sid}/messages", json={"message": "divorce", "llm": {"model": "gemini-pro-x"}})
    settings, _ = client.factory.requests[-1]
    assert settings.backend == "gemini" and settings.model == "gemini-pro-x"           # session backend kept


def test_the_users_key_is_passed_through_and_never_returned(client):
    sid = new_session(client)
    client.factory.replies = [analysis(category="out_of_scope")]
    r = client.post(f"/sessions/{sid}/messages", json={"message": "divorce"}, headers={"X-LLM-API-Key": USER_KEY})
    assert client.factory.requests[-1][1] == USER_KEY
    assert USER_KEY not in r.text and USER_KEY not in client.get(f"/sessions/{sid}").text


def test_missing_key_and_invalid_model_are_clear_errors(client):
    sid = new_session(client)
    r = client.post(f"/sessions/{sid}/messages", json={"message": "hi", "llm": {"backend": "nokey"}})
    assert r.status_code == 400 and "send your own key" in r.json()["detail"]
    r = client.post(f"/sessions/{sid}/messages", json={"message": "hi", "llm": {"model": "bad model"}})
    assert r.status_code == 422


def test_custom_backend_is_off_by_default_and_needs_https(client, monkeypatch):
    sid = new_session(client)
    custom = {"backend": "custom", "model": "m", "base_url": "http://10.0.0.1/v1"}
    assert client.post(f"/sessions/{sid}/messages", json={"message": "hi", "llm": custom}).status_code == 403
    monkeypatch.setenv("ALLOW_CUSTOM_LLM_BASE_URL", "1")
    assert client.post(f"/sessions/{sid}/messages", json={"message": "hi", "llm": custom}).status_code == 422
    client.factory.replies = [analysis(category="out_of_scope")]
    custom["base_url"] = "https://llm.example.com/v1"
    assert client.post(f"/sessions/{sid}/messages", json={"message": "hi", "llm": custom}).status_code == 200


def test_a_rejected_key_is_a_401(client):
    class AuthenticationError(Exception):
        pass

    sid = new_session(client)

    def boom(settings, key):
        llm = ScriptedLLM()
        llm.name, llm.model = "groq", "m"
        llm.chat = lambda *a, **k: (_ for _ in ()).throw(AuthenticationError(f"Invalid API Key {key}"))
        return llm

    client.app.state.deps.make_llm = boom
    r = client.post(f"/sessions/{sid}/messages", json={"message": "hi"}, headers={"X-LLM-API-Key": USER_KEY})
    assert r.status_code == 401 and "rejected the API key" in r.json()["detail"] and USER_KEY not in r.text


def test_other_errors_come_back_redacted():
    assert redact(f"failed with {USER_KEY}", USER_KEY) == "failed with [key]"
    assert redact("Incorrect API key provided: sk-abcdefghijklmnopqrstu") == "Incorrect API key provided: [key]"


# --- voice -------------------------------------------------------------------------------------------------

def test_voice_message_is_transcribed_then_answered(client):
    sid = new_session(client)
    client.factory.replies = [analysis(facts=FULL_FACTS), GOOD_ADVICE]
    r = client.post(f"/sessions/{sid}/voice", files={"audio": ("note.webm", b"fake-audio", "audio/webm")},
                    data={"language": "hi"})
    body = r.json()
    assert r.status_code == 200 and body["transcript"] == "mera deposit wapas nahi mila" and body["kind"] == "advice"
    assert client.transcriber.calls == [("note.webm", "hi")]


def test_the_users_key_is_used_for_transcription_only_on_the_same_provider(client):
    sid = new_session(client)
    files = {"audio": ("a.wav", b"x", "audio/wav")}
    client.factory.replies = [analysis(category="out_of_scope")]
    client.post(f"/sessions/{sid}/voice", files=files, headers={"X-LLM-API-Key": USER_KEY})
    client.factory.replies = [analysis(category="out_of_scope")]
    client.post(f"/sessions/{sid}/voice", files=files, data={"backend": "gemini"}, headers={"X-LLM-API-Key": "g"})
    assert client.transcriber_keys == [USER_KEY, None]          # groq key reused; a gemini key is not sent to groq


def test_bad_audio_is_refused_before_any_call(client):
    r = client.post("/transcribe", files={"audio": ("notes.txt", b"hello", "text/plain")})
    assert r.status_code == 422 and "unsupported audio type" in r.json()["detail"]
    r = client.post("/transcribe", files={"audio": ("a.wav", b"", "audio/wav")})
    assert r.status_code == 422


def test_transcribe_only(client):
    r = client.post("/transcribe", files={"audio": ("a.m4a", b"x", "audio/mp4")})
    assert r.status_code == 200 and r.json()["text"] and r.json()["model"] == "whisper-fake"


# --- access, limits and the session store ------------------------------------------------------------------

def test_api_key_is_required_when_configured(client, monkeypatch):
    monkeypatch.setenv("LAWBUDDY_API_KEY", "secret")
    assert client.post("/sessions").status_code == 401
    assert client.post("/sessions", headers={"X-API-Key": "secret"}).status_code == 201
    assert client.get("/health").status_code == 200 and client.get("/backends").status_code == 200


def test_rate_limiter_window():
    lim = RateLimiter(2)
    assert lim.allow("a", 0) and lim.allow("a", 1) and not lim.allow("a", 2)
    assert lim.allow("b", 2)                                              # another client is unaffected
    assert lim.allow("a", 61)                                             # the first call has left the window
    assert RateLimiter(0).allow("a", 0)


def test_sessions_expire_when_idle_and_the_oldest_is_dropped_when_full():
    now = [0.0]
    store = SessionStore(ttl_s=60, max_sessions=2, clock=lambda: now[0])
    a, b = store.create(LLMSettings()), store.create(LLMSettings())
    now[0] = 30
    store.get(a.session.id)                                               # a is used again
    c = store.create(LLMSettings())                                       # full: b (oldest idle) is dropped
    assert set(store.entries) == {a.session.id, c.session.id}
    now[0] = 200
    with pytest.raises(Exception):
        store.get(a.session.id)                                           # idle too long


def test_each_thread_sees_its_own_retrieval_mode():
    class Flip:
        last_mode, last_error = "primary", ""

        def search(self, query, k=None, **kw):
            self.last_mode = "fallback" if query == "down" else "primary"
            return []

    r = PerThreadRetriever(Flip())
    seen = {}

    def run(q):
        r.search(q)
        seen[q] = r.last_mode

    threads = [threading.Thread(target=run, args=(q,)) for q in ("down", "up")]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert seen == {"down": "fallback", "up": "primary"}


def test_the_voice_turn_records_what_was_heard_in_its_steps(client):
    sid = new_session(client)
    client.factory.replies = [analysis(category="out_of_scope")]
    body = client.post(f"/sessions/{sid}/voice", files={"audio": ("a.wav", b"x", "audio/wav")}).json()
    assert body["steps"][0].startswith("voice: whisper-fake heard hindi")
