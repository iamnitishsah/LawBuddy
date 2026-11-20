"""Tests for keyword (BM25) search and the API-failure fallback (no network)."""

import pytest

from lawbuddy.retrieval.lexical import FallbackRetriever, LexicalIndex, tokenize


def test_tokenize_lowercases_and_drops_stopwords():
    assert tokenize("My Landlord is NOT returning the deposit!") == ["landlord", "returning", "deposit"]


def test_keyword_search_on_the_real_index_finds_the_obvious_chunk():
    index = LexicalIndex()
    assert index.search("is there a 2 month limit on deposit in karnataka", k=1)[0]["chunk_id"] == "deposit-no-cap"
    assert index.search("can I get free legal aid", k=1)[0]["chunk_id"] == "general-legal-aid"
    hits = index.search("wages not paid", k=10, category="salary")
    assert hits and all(h["category"] == "salary" for h in hits)
    assert index.search("deposit", k=10, category="salary") == []            # the filter is strict: no leakage
    assert index.search("zzzz qqqq", k=3) == []                             # no matching word: nothing, not noise


class Boom:
    def search(self, query, **kw):
        raise RuntimeError("embedding API still failing after 2 attempts")


class Fixed:
    def __init__(self, hits):
        self.hits, self.calls = hits, []

    def search(self, query, **kw):
        self.calls.append(kw)
        return self.hits


def test_fallback_answers_when_the_primary_fails_and_says_so():
    logged = []
    r = FallbackRetriever(Boom(), Fixed([{"chunk_id": "kw"}]), log=logged.append)
    assert r.search("q", k=3, category="deposit") == [{"chunk_id": "kw"}]
    assert r.last_mode == "fallback" and "embedding API" in r.last_error and logged
    assert r.fallback.calls == [{"k": 3, "category": "deposit"}]


def test_primary_is_used_when_it_works():
    r = FallbackRetriever(Fixed([{"chunk_id": "dense"}]), Fixed([{"chunk_id": "kw"}]))
    assert r.search("q", k=2)[0]["chunk_id"] == "dense" and r.last_mode == "primary" and r.last_error == ""


def test_missing_index_says_how_to_build_it(tmp_path):
    with pytest.raises(RuntimeError, match="python -m lawbuddy.kb.build"):
        LexicalIndex(tmp_path)
