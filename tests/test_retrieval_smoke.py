"""Tests for the retrieval smoke scoring (no network)."""

from lawbuddy.evaluation.retrieval_smoke import load_questions, score_run
from lawbuddy.kb.loader import load_kb


def hits(*pairs):
    return [{"chunk_id": c, "score": s} for c, s in pairs]


def test_scoring_counts_hits_and_threshold_ranges():
    questions = [{"q": "a", "expect": ["x"]}, {"q": "b", "expect": ["y", "z"]}, {"q": "c", "expect": ["w"]},
                 {"q": "out", "expect": []}]
    results = [hits(("x", 0.9)), hits(("q", 0.5), ("z", 0.4)), hits(("q", 0.3)), hits(("x", 0.2))]
    s = score_run(questions, results)
    assert (s["in_scope"], s["hit@1"], s["hit@3"]) == (3, 1, 2)
    assert s["in_scope_top_min"] == 0.3 and s["out_scope_top_max"] == 0.2 and s["misses"] == ["c"]


def test_fallback_searches_count_for_hits_but_not_for_score_ranges():
    questions = [{"q": "a", "expect": ["x"]}, {"q": "b", "expect": ["y"]}, {"q": "out", "expect": []}]
    results = [hits(("x", 0.5)), hits(("y", 7.2)), hits(("x", 5.9))]       # b and out answered by BM25
    s = score_run(questions, results, ["primary", "fallback", "fallback"])
    assert s["hit@1"] == 2 and s["fallbacks"] == 2
    assert (s["in_scope_top_min"], s["in_scope_n"]) == (0.5, 1)
    assert (s["out_scope_top_max"], s["out_scope_n"]) == (None, 0)         # no primary out-of-scope search left


def test_every_expected_chunk_exists_in_the_kb():
    ids = {c.id for c in load_kb()}
    questions = load_questions()
    assert any(not q["expect"] for q in questions) and any(q["expect"] for q in questions)
    for q in questions:
        assert set(q["expect"]) <= ids, q["q"]
