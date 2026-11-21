"""Tests for the retrieval smoke sets and scoring (no network)."""

import pytest

from lawbuddy.evaluation.retrieval_smoke import SETS, load_questions, score_run
from lawbuddy.kb.loader import load_kb
from lawbuddy.retrieval.lexical import tokenize

MAX_OVERLAP = 0.3        # a paraphrase may share at most 30% of its words with the original (Jaccard)


def hits(*pairs):
    return [{"chunk_id": c, "score": s} for c, s in pairs]


def jaccard(a: str, b: str) -> float:
    x, y = set(tokenize(a)), set(tokenize(b))
    return len(x & y) / len(x | y) if x | y else 0.0


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


def test_hits_are_broken_down_by_language():
    questions = [{"q": "a", "expect": ["x"], "lang": "en"}, {"q": "b", "expect": ["y"], "lang": "hi"},
                 {"q": "c", "expect": ["z"], "lang": "hi"}]
    s = score_run(questions, [hits(("x", 1)), hits(("y", 1)), hits(("q", 1))])
    assert s["hit@3_by_lang"] == {"en": (1, 1), "hi": (1, 2)}


@pytest.mark.parametrize("set_name", list(SETS))
def test_every_set_is_well_formed(set_name):
    ids = {c.id for c in load_kb()}
    questions = load_questions(SETS[set_name])
    assert any(not q["expect"] for q in questions) and any(q["expect"] for q in questions)
    assert len({q["id"] for q in questions}) == len(questions), "duplicate question ids"
    for q in questions:
        assert set(q["expect"]) <= ids, q["q"]


def test_paraphrases_cover_every_original_with_the_same_answer_and_new_wording():
    original = {q["id"]: q for q in load_questions(SETS["original"])}
    paraphrased = {q["id"]: q for q in load_questions(SETS["paraphrased"])}
    assert set(original) <= set(paraphrased), f"not paraphrased: {sorted(set(original) - set(paraphrased))}"
    for qid, orig in original.items():
        para = paraphrased[qid]
        assert para["expect"] == orig["expect"], qid
        overlap = jaccard(orig["q"], para["q"])
        assert overlap <= MAX_OVERLAP, f"{qid}: shares {overlap:.0%} of its words with the original"
