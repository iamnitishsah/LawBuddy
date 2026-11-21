"""Automatic checks for one test case (eval/cases/cases.yaml), computed in code from the saved replies.

Every check returns pass / fail with a reason. The checks work on plain dicts (dataclasses.asdict of the engine's
Reply), so a run can be re-scored later from outputs/eval/ without calling any API.

    completed      no reply of kind "error"
    kinds          each turn's reply kind is one the case allows
    category       the problem type LawBuddy settled on
    grounded       every legal reference in every advice reply and notice traces to the registry or the passages
                   shown, re-checked here independently of the guard that ran during the turn
    cited          every advice reply cites at least one passage, and no citation points at a passage not shown
    must_cite      at least one expected KB chunk is cited
    script         LawBuddy's own written replies are in the user's script (fixed templates are not checked)
    mention_any    at least one required phrase appears
    must_not_mention  no forbidden phrase appears
    draft          the last reply is a legal notice with no invented-number warnings
"""

from __future__ import annotations

from dataclasses import dataclass

from lawbuddy.conversation.language import script_of
from lawbuddy.guard.legal_refs import check_answer

WRITTEN_KINDS = ("advice", "follow_up", "clarify")         # written by the model in the user's language

__all__ = ["Check", "run_checks", "script_of"]


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""


def _allowed(kinds_spec, i: int) -> list[str]:
    spec = kinds_spec[i] if i < len(kinds_spec) else kinds_spec[-1]
    return list(spec) if isinstance(spec, (list, tuple)) else [spec]


def _body(reply: dict) -> str:
    """The reply text without a drafted notice (checked separately) and without the fixed footer lines."""
    text = reply.get("text", "")
    return text.split("\n---\n")[0] if reply.get("kind") == "draft" else text


def run_checks(case: dict, replies: list[dict], registry: dict, kb_chunks: dict[str, dict] | None = None) -> list[Check]:
    """`replies`: one dict per turn (asdict of the engine's Reply). `kb_chunks`: id -> {title, text}, for checking
    a drafted notice against the chunks its legal parts come from."""
    exp = case.get("expect", {})
    checks: list[Check] = []

    errors = [i + 1 for i, r in enumerate(replies) if r["kind"] == "error"]
    checks.append(Check("completed", not errors and len(replies) == len(case["turns"]),
                        f"error on turn(s) {errors}" if errors else ""))

    if exp.get("kinds"):
        wrong = [(i + 1, r["kind"], _allowed(exp["kinds"], i)) for i, r in enumerate(replies)
                 if r["kind"] not in _allowed(exp["kinds"], i)]
        checks.append(Check("kinds", not wrong, "; ".join(f"turn {t}: {k}, expected {a}" for t, k, a in wrong)))

    if exp.get("category"):
        cats = [r.get("category") for r in replies if r.get("category")]
        got = cats[-1] if cats else None
        checks.append(Check("category", got == exp["category"], f"got {got}"))

    ungrounded, checked = [], 0
    for i, r in enumerate(replies):
        if r["kind"] == "advice":
            checked += 1
            report = check_answer(r["text"], r.get("passages") or [], registry)
            ungrounded += [f"turn {i + 1}: {p.kind}: {p.text}" for p in report.problems]
        if r["kind"] == "draft" and r.get("draft"):
            checked += 1
            passages = [kb_chunks[c] for c in r["draft"].get("chunks", []) if kb_chunks and c in kb_chunks]
            report = check_answer(r["draft"]["text"], passages, registry)
            ungrounded += [f"turn {i + 1} (notice): {p.kind}: {p.text}" for p in report.problems
                           if p.kind != "invalid_citation"]
    if checked:
        checks.append(Check("grounded", not ungrounded, "; ".join(ungrounded)))

    advice = [(i, r) for i, r in enumerate(replies) if r["kind"] == "advice"]
    if advice:
        problems = []
        for i, r in advice:
            if not r.get("cited"):
                problems.append(f"turn {i + 1}: no citation")
            invalid = [n for n in r.get("cited") or [] if not 1 <= n <= len(r.get("passages") or [])]
            if invalid:
                problems.append(f"turn {i + 1}: invalid {invalid}")
        checks.append(Check("cited", not problems, "; ".join(problems)))

    if exp.get("must_cite"):
        cited_ids = {r["passages"][n - 1]["chunk_id"] for _, r in advice for n in r.get("cited") or []
                     if 1 <= n <= len(r.get("passages") or [])}
        hit = sorted(cited_ids & set(exp["must_cite"]))
        checks.append(Check("must_cite", bool(hit), f"cited {sorted(cited_ids)}" if not hit else f"cited {hit}"))

    if exp.get("script"):
        wrong = [(i + 1, script_of(_body(r))) for i, r in enumerate(replies)
                 if r["kind"] in WRITTEN_KINDS and script_of(_body(r)) != exp["script"]]
        written = [r for r in replies if r["kind"] in WRITTEN_KINDS]
        if written:
            checks.append(Check("script", not wrong, "; ".join(f"turn {t}: {s}" for t, s in wrong)))

    all_text = "\n".join(_body(r) for r in replies).lower()
    if exp.get("mention_any"):
        hit = [m for m in exp["mention_any"] if m.lower() in all_text]
        checks.append(Check("mention_any", bool(hit), f"none of {exp['mention_any']}" if not hit else f"found {hit}"))
    if exp.get("must_not_mention"):
        found = [m for m in exp["must_not_mention"] if m.lower() in all_text]
        checks.append(Check("must_not_mention", not found, f"found {found}" if found else ""))

    if exp.get("draft"):
        last = replies[-1] if replies else {}
        d = last.get("draft") or {}
        ok = last.get("kind") == "draft" and bool(d) and not d.get("warnings")
        detail = (f"last kind {last.get('kind')}" if last.get("kind") != "draft"
                  else f"warnings {d.get('warnings')}" if d.get("warnings")
                  else f"{len(d.get('placeholders', []))} placeholder(s): {d.get('placeholders')}")
        checks.append(Check("draft", ok, detail))
    return checks
