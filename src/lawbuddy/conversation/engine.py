"""One conversation turn, step by step. Each step is a plain function; `trace` records what happened and why.

    message
      1. emergency rule (code)          -> emergency reply
      2. analysis (LLM, JSON)           -> emergency reply | escalate (out of scope) | clarify (unclear)
         category, facts, search query
      3. follow-up decision (code)      -> follow_up, if critical facts are missing and the user told a story,
                                           for at most max_followup_turns turns
      4. retrieval (rerank, evidence)   -> not_found, if nothing in the KB clears the score floor
      5. advice (LLM) + guard (code)    -> advice; regenerated once if the guard finds untraceable law,
                                           then the offending sentences are removed

Layer 3 of classification is step 4: the model's category is only acted on if the knowledge base has evidence for
it. For an unclear message, a rerank search over the whole KB suggests the likely topic for the clarifying question.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

from lawbuddy.conversation import respond
from lawbuddy.conversation.case import IN_SCOPE, CaseFile
from lawbuddy.conversation.triage import Analysis, analyze, emergency_rule
from lawbuddy.guard.legal_refs import check_answer, remove_problem_sentences
from lawbuddy.guard.citations import normalize_citations, normalize_text

ROOT = Path(__file__).resolve().parents[3]
KINDS = ("emergency", "escalate", "clarify", "follow_up", "not_found", "advice", "error")


@dataclass
class Session:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    messages: list[dict] = field(default_factory=list)       # {"role": "user" | "assistant", "content": str}
    case: CaseFile = field(default_factory=CaseFile)
    language: str = "English"
    followup_turns: int = 0


@dataclass
class Reply:
    kind: str
    text: str
    language: str = "English"
    category: str | None = None
    passages: list[dict] = field(default_factory=list)        # what the model was shown, in [n] order
    cited: list[int] = field(default_factory=list)
    guard: dict = field(default_factory=dict)                 # {"problems": [...], "regenerated": bool, ...}
    retrieval: dict = field(default_factory=dict)             # {"query", "mode", "top_score", "floor"}
    trace: list[str] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    latency_s: float = 0.0


def load_config() -> dict:
    return yaml.safe_load(open(ROOT / "configs" / "conversation.yaml", encoding="utf-8"))


class Engine:
    def __init__(self, llm, retriever, registry: dict, cfg: dict, min_score: float | None = None):
        self.llm, self.retriever, self.registry, self.cfg = llm, retriever, registry, cfg
        self.min_score = min_score                     # rerank / dense floor; not applied to keyword fallback
        self.h = cfg["helplines"]

    # -- the turn ---------------------------------------------------------------------------------------------

    def turn(self, session: Session, message: str) -> Reply:
        t0 = time.monotonic()
        session.messages.append({"role": "user", "content": message})
        usage = {"input_tokens": 0, "output_tokens": 0, "llm_calls": 0, "llm_s": 0.0, "retrieval_s": 0.0}
        try:
            reply = self._turn(session, message, usage)
        except Exception as exc:                                     # an upstream API failure: say so, don't crash
            reply = Reply("error", "Sorry, something went wrong on my side. Please try again in a minute.",
                          language=session.language, trace=[f"error: {type(exc).__name__}: {str(exc)[:200]}"])
        reply.usage, reply.latency_s = usage, round(time.monotonic() - t0, 2)
        session.messages.append({"role": "assistant", "content": reply.text})
        return reply

    def _turn(self, s: Session, message: str, usage: dict) -> Reply:
        trace: list[str] = []

        # 1. emergency rule
        hit = emergency_rule(message)
        if hit:
            trace.append(f"emergency rule matched {hit!r}")
            return Reply("emergency", respond.emergency_reply(s.language, self.h), s.language,
                         s.case.category, trace=trace)

        # 2. analysis
        a = analyze(self.llm, s.messages, s.case, self.cfg["temperature"], self.cfg["analyze_max_tokens"])
        self._add_usage(usage, a.usage)
        s.language = a.language or s.language
        trace.append(f"analysis: category={a.category} intent={a.intent} language={a.language} "
                     f"emergency={a.emergency} query={a.search_query!r}")
        if a.emergency:
            trace.append("emergency flagged by the analysis")
            return Reply("emergency", respond.emergency_reply(s.language, self.h), s.language, s.case.category,
                         trace=trace)
        if a.category == "out_of_scope":
            trace.append(f"out of scope: {a.out_of_scope_topic or 'unspecified'}")
            return Reply("escalate", respond.escalate_reply(s.language, a.out_of_scope_topic, self.h), s.language,
                         s.case.category, trace=trace)
        if a.category == "unclear" and not s.case.category:
            return self._clarify(s, a, trace, usage)

        category = a.category if a.category in IN_SCOPE else s.case.category
        if category != s.case.category:
            trace.append(f"case category: {s.case.category} -> {category}")
            s.followup_turns = 0
        s.case.set_category(category)
        s.case.merge(a.update)

        # 3. follow-up questions
        missing = s.case.missing(critical_only=True)
        if missing and a.intent == "story" and s.followup_turns < self.cfg["max_followup_turns"]:
            s.followup_turns += 1
            asks = s.case.missing()                                  # critical first, then useful extras
            trace.append(f"follow-up {s.followup_turns}/{self.cfg['max_followup_turns']}: missing {missing}")
            msgs = respond.follow_up_messages(s.case, asks, s.language, s.messages, self.cfg["max_questions_per_turn"])
            return Reply("follow_up", self._generate(msgs, usage, trace), s.language, category, trace=trace)
        if missing:
            trace.append(f"advising without {missing} ({'question' if a.intent != 'story' else 'follow-up limit'})")

        # 4. retrieval (rerank) as the evidence check
        query = a.search_query or s.case.summary or message
        hits, retrieval = self._search(query, [category, "general"], usage=usage)
        trace.append(f"retrieval: {retrieval['mode']} top={retrieval['top_score']} floor={retrieval['floor']} "
                     f"ids={[h['chunk_id'] for h in hits]}")
        if not hits or (retrieval["floor"] is not None and retrieval["top_score"] < retrieval["floor"]):
            trace.append("no evidence above the floor: not answering")
            return Reply("not_found", respond.not_found_reply(s.language, self.h), s.language, category,
                         retrieval=retrieval, trace=trace)

        # 5. advice + guard
        text, guard = self._advise(s, hits, message, trace, usage)
        if s.case.outside_karnataka():
            text += respond.outside_karnataka_note(s.language, s.case.state)
            trace.append(f"note added: state is {s.case.state}")
        text += respond.disclaimer(s.language)
        return Reply("advice", text, s.language, category, passages=hits, cited=guard["cited"], guard=guard,
                     retrieval=retrieval, trace=trace)

    # -- steps ------------------------------------------------------------------------------------------------

    def _clarify(self, s: Session, a: Analysis, trace: list[str], usage: dict) -> Reply:
        hint, retrieval = None, {}
        if a.search_query:                       # "hi" has nothing to search for: don't spend an API call on it
            hits, retrieval = self._search(a.search_query, None, k=3, usage=usage)
            if hits and (retrieval["floor"] is None or retrieval["top_score"] >= retrieval["floor"]):
                hint = next((h["category"] for h in hits if h["category"] in IN_SCOPE), None)
            trace.append(f"unclear: rerank hint={hint} (top={retrieval['top_score']})")
        else:
            trace.append("unclear: no search query, asking what happened")
        text = self._generate(respond.clarify_messages(s.language, s.messages, hint), usage, trace)
        return Reply("clarify", text, s.language, None, retrieval=retrieval, trace=trace)

    def _search(self, query: str, categories: list[str] | None, k: int | None = None,
                usage: dict | None = None) -> tuple[list[dict], dict]:
        t0 = time.monotonic()
        hits = self.retriever.search(query, k=k or self.cfg["top_k"], category=categories)
        seconds = round(time.monotonic() - t0, 2)
        if usage is not None:
            usage["retrieval_s"] = round(usage["retrieval_s"] + seconds, 2)
        mode = getattr(self.retriever, "last_mode", "primary")
        floor = self.min_score if mode == "primary" else None          # keyword scores are on another scale
        top = round(hits[0]["score"], 4) if hits else None
        return hits, {"query": query, "mode": mode, "top_score": top, "floor": floor, "seconds": seconds,
                      "error": getattr(self.retriever, "last_error", "")}

    def _advise(self, s: Session, hits: list[dict], message: str, trace: list[str], usage: dict) -> tuple[str, dict]:
        text = normalize_citations(
            self._generate(respond.advise_messages(s.case, hits, s.language, message), usage, trace))
        report = check_answer(text, hits, self.registry)
        guard = {"first_problems": [asdict(p) for p in report.problems], "regenerated": False, "removed": False}
        if not report.ok:
            trace.append(f"guard: {report.summary()} -> regenerating once")
            guard["regenerated"] = True
            text = normalize_citations(self._generate(
                respond.advise_messages(s.case, hits, s.language, message, feedback=report.summary()), usage, trace))
            report = check_answer(text, hits, self.registry)
            if not report.ok:
                trace.append(f"guard: still {report.summary()} -> removing those sentences")
                text = remove_problem_sentences(text, report)
                guard["removed"] = True
                report = check_answer(text, hits, self.registry)
        else:
            trace.append("guard: all legal references traced")
        if report.uncited_sentences:
            trace.append(f"guard: {len(report.uncited_sentences)} sentence(s) without a citation (warning only)")
        guard.update({"problems": [asdict(p) for p in report.problems], "cited": report.cited,
                      "uncited_sentences": report.uncited_sentences, "refs": report.refs})
        return text, guard

    def _generate(self, messages: list[dict], usage: dict, trace: list[str]) -> str:
        """The model's reply text. Reasoning models (gpt-oss) spend hidden tokens before answering; if the budget runs
        out the reply is empty or cut off (chat smoke 01 returned an empty answer), so retry once with double."""
        max_tokens = self.cfg["respond_max_tokens"]
        for attempt in (1, 2):
            r = self.llm.chat(messages, self.cfg["temperature"], max_tokens)
            self._add_usage(usage, {"input_tokens": r.input_tokens, "output_tokens": r.output_tokens, "calls": 1,
                                    "latency_s": r.latency_s})
            text = normalize_text(r.text).strip()
            if text and r.finish_reason != "length":
                return text
            if attempt == 1:
                trace.append(f"generation {'empty' if not text else 'cut off'} at {max_tokens} tokens -> retrying "
                             f"with {max_tokens * 2}")
                max_tokens *= 2
        if text:
            trace.append("generation still cut off: using the partial reply")
            return text
        raise RuntimeError("the model returned an empty reply twice")

    @staticmethod
    def _add_usage(usage: dict, u: dict) -> None:
        usage["input_tokens"] += u.get("input_tokens", 0)
        usage["output_tokens"] += u.get("output_tokens", 0)
        usage["llm_calls"] += u.get("calls", 1)
        usage["llm_s"] = round(usage["llm_s"] + u.get("latency_s", 0.0), 2)


def build_engine(backend: str | None = None, log=None) -> Engine:  # pragma: no cover - needs API keys
    from dotenv import load_dotenv

    from lawbuddy.kb.loader import load_registry
    from lawbuddy.llm.base import get_llm
    from lawbuddy.retrieval.factory import get_retriever, load_config as load_retrieval_config

    load_dotenv(ROOT / ".env")
    cfg = load_config()
    floors = load_retrieval_config()["search"].get("min_score") or {}
    return Engine(get_llm(backend), get_retriever(cfg["retriever"], log=log), load_registry(), cfg,
                  min_score=floors.get(cfg["retriever"]))


def log_turn(session: Session, message: str, reply: Reply, backend: str, path: Path | None = None) -> None:
    path = path or ROOT / "data" / "logs" / "chat.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "session": session.id,
              "backend": backend, "message": message, "reply": asdict(reply), "case": session.case.to_dict()}
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
