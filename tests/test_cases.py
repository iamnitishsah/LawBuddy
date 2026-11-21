"""Tests for the test-case file and the automatic checks (no network)."""

import pytest

from lawbuddy.conversation.triage import emergency_rule
from lawbuddy.evaluation.checks import run_checks, script_of
from lawbuddy.evaluation.run_cases import kb_chunks, load_cases, summarise
from lawbuddy.kb.loader import load_registry

REGISTRY = load_registry()
CASES = load_cases()
KINDS = {"emergency", "escalate", "clarify", "follow_up", "not_found", "advice", "draft", "error"}


# --- the case file --------------------------------------------------------------------------------------------

def test_the_case_file_is_well_formed():
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids)) and len(CASES) >= 25
    chunk_ids = set(kb_chunks())
    for c in CASES:
        assert c["turns"] and all(isinstance(t, str) and t.strip() for t in c["turns"]), c["id"]
        assert c["lang"] in ("en", "hi", "hinglish", "kn"), c["id"]
        exp = c.get("expect", {})
        for spec in exp.get("kinds", []):
            assert set(spec if isinstance(spec, list) else [spec]) <= KINDS, c["id"]
        if exp.get("kinds"):
            assert len(exp["kinds"]) == len(c["turns"]), c["id"]
        assert set(exp.get("must_cite", [])) <= chunk_ids, c["id"]
        assert exp.get("script", "latin") in ("latin", "devanagari", "kannada"), c["id"]


def test_every_group_and_language_is_covered():
    assert {c["group"] for c in CASES} == {"deposit", "consumer", "salary", "trap", "scope", "safety", "draft"}
    assert {c["lang"] for c in CASES} == {"en", "hi", "hinglish", "kn"}


def test_the_safety_cases_are_not_caught_by_the_emergency_rules():
    """They test the model's emergency flag (layer 2); if a rule caught them they would test nothing new."""
    for c in CASES:
        if c["group"] == "safety":
            assert all(emergency_rule(t) is None for t in c["turns"]), c["id"]


# --- script detection ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("text, script", [
    ("Your landlord must return the deposit (Indian Contract Act, 1872, s. 73) [1].", "latin"),
    ("Samajh aaya ki aapka owner deposit wapas nahi kar raha.", "latin"),
    ("मकान मालिक को जमा राशि लौटानी होगी (Indian Contract Act, 1872, s. 73) [1]।", "devanagari"),
    ("ನಿಮ್ಮ ಮಾಲೀಕರು ಠೇವಣಿ ಹಿಂತಿರುಗಿಸಬೇಕು (Code on Wages, 2019, s. 17) [1].", "kannada"),
    ("நன்ன கம்பனி மூறு திங்களிந்த சம்பல", "tamil"),
    ("", "latin"),
])
def test_script_of(text, script):
    assert script_of(text) == script


# --- the checks ---------------------------------------------------------------------------------------------

def reply(kind="advice", text="Send a notice first [1].", cited=(1,), passages=None, category="deposit", **kw):
    p = passages if passages is not None else [{"chunk_id": "deposit-steps", "title": "Steps", "text": "notice"}]
    return {"kind": kind, "text": text, "cited": list(cited), "passages": p, "category": category,
            "guard": {}, "retrieval": {}, "usage": {}, "latency_s": 1.0, "trace": [], **kw}


CASE = {"id": "c", "group": "deposit", "lang": "en", "turns": ["a"],
        "expect": {"kinds": ["advice"], "category": "deposit", "script": "latin", "must_cite": ["deposit-steps"],
                   "mention_any": ["notice"], "must_not_mention": ["420"]}}


def names(checks, passed=True):
    return {c.name for c in checks if c.passed == passed}


def test_a_good_reply_passes_every_check():
    checks = run_checks(CASE, [reply()], REGISTRY)
    assert names(checks, False) == set() and names(checks) == {
        "completed", "kinds", "category", "grounded", "cited", "must_cite", "script", "mention_any",
        "must_not_mention"}


def test_each_check_can_fail():
    bad = reply(kind="advice", text="File under Section 420 IPC, as held in Sharma v. State. मकान मालिक को लौटाना होगा।",
                cited=(), category="consumer")
    failed = names(run_checks(CASE, [bad], REGISTRY), False)
    assert {"category", "grounded", "cited", "must_cite", "mention_any", "must_not_mention"} <= failed
    assert "completed" in names(run_checks(CASE, [reply(kind="error")], REGISTRY), False)
    assert "kinds" in names(run_checks(CASE, [reply(kind="follow_up")], REGISTRY), False)


def test_kinds_accept_alternatives_per_turn():
    case = {**CASE, "turns": ["a", "b"], "expect": {"kinds": [["follow_up", "advice"], "advice"]}}
    assert names(run_checks(case, [reply(kind="follow_up"), reply()], REGISTRY), False) == set()
    assert "kinds" in names(run_checks(case, [reply(kind="clarify"), reply()], REGISTRY), False)


def test_script_ignores_fixed_templates():
    case = {**CASE, "lang": "kn", "expect": {"kinds": ["escalate"], "script": "kannada"}}
    checks = run_checks(case, [reply(kind="escalate", text="I'm sorry, this is outside what LawBuddy covers.")],
                        REGISTRY)
    assert "script" not in {c.name for c in checks}                   # an English template is not a script failure


def test_drafts_are_checked_for_warnings_and_grounded_against_their_chunks():
    chunks = kb_chunks()
    case = {**CASE, "turns": ["a", "b"], "expect": {"kinds": ["advice", "draft"], "draft": True}}
    notice = ("Under section 73 of the Indian Contract Act, 1872, a party who suffers by a breach is entitled to "
              "compensation.")
    good = {"text": notice, "warnings": [], "placeholders": ["your full address"],
            "chunks": ["statute-contract-act-73-74"]}
    d = reply(kind="draft", text="intro\n---\n" + notice, draft=good, cited=())
    assert names(run_checks(case, [reply(), d], REGISTRY, chunks), False) == set()
    d_bad = reply(kind="draft", text="intro", cited=(), draft={**good, "warnings": ["Check these numbers: 3"]})
    assert "draft" in names(run_checks(case, [reply(), d_bad], REGISTRY, chunks), False)


def test_summary_counts_cases_checks_and_timing():
    rec = lambda passed, group: {"case": {"id": group, "group": group}, "passed": passed,   # noqa: E731
                                 "checks": [{"name": "grounded", "passed": passed, "detail": ""}],
                                 "replies": [reply(guard={"first_problems": [1] if not passed else []})]}
    s = summarise([rec(True, "deposit"), rec(False, "trap")])
    assert s["cases_passed"] == 1 and s["by_group"]["trap"] == {"passed": 0, "total": 1}
    assert s["cases_with_ungrounded_law"] == 1 and s["guard_regenerations"] == 1 and s["latency_s"]["median"] == 1.0
    assert s["failures"][0]["id"] == "trap"
