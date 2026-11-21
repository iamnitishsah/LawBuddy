"""Keyword (BM25) search over the knowledge-base index: no API, no network.

Used as the fallback when the hosted embedding or rerank API fails, so the product keeps working during a
provider outage. Dense search is better on paraphrased questions; with a few dozen chunks and a category filter,
keyword search is an acceptable stand-in. Scores are BM25 scores, not comparable to cosine similarity.
"""

from __future__ import annotations

import json
import math
import re
import time
from collections import Counter
from pathlib import Path

from lawbuddy.kb.build import INDEX_DIR

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = frozenset("""a an and are as at be by can do does for from has have how i if in is it its my me of on or
the their them there they this to was what when where which who will with you your not no""".split())


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS]


class LexicalIndex:
    def __init__(self, index_dir: Path = INDEX_DIR, k1: float = 1.5, b: float = 0.75):
        meta_path = index_dir / "chunks.json"
        if not meta_path.exists():
            raise RuntimeError(f"no index in {index_dir}; build it with: python -m lawbuddy.kb.build")
        self.chunks = json.loads(meta_path.read_text(encoding="utf-8"))["chunks"]
        self.k1, self.b = k1, b
        # The title is counted twice: it states the topic of the whole chunk.
        self.docs = [Counter(tokenize(f"{c['title']} {c['title']} {c['text']}")) for c in self.chunks]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg_len = sum(self.lengths) / max(len(self.lengths), 1)
        df = Counter(t for d in self.docs for t in d)
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def _score(self, i: int, terms: list[str]) -> float:
        d, length, s = self.docs[i], self.lengths[i], 0.0
        for t in terms:
            if t in d:
                tf = d[t]
                s += self.idf[t] * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * length / self.avg_len))
        return s

    def search(self, query: str, k: int = 5, category: str | list[str] | None = None,
               kinds: list[str] | None = None) -> list[dict]:
        cats = [category] if isinstance(category, str) else category
        terms = tokenize(query)
        scored = [(self._score(i, terms), i) for i, c in enumerate(self.chunks)
                  if (not cats or c["category"] in cats) and (not kinds or c["kind"] in kinds)]
        scored.sort(key=lambda pair: (-pair[0], self.chunks[pair[1]]["id"]))
        return [self._hit(i, s) for s, i in scored[:k] if s > 0]

    def _hit(self, i: int, score: float) -> dict:
        c = self.chunks[i]
        return {"chunk_id": c["id"], "score": score, "header": c["header"], "title": c["title"], "text": c["text"],
                "category": c["category"], "kind": c["kind"], "jurisdiction": c["jurisdiction"],
                "cites": c["cites"], "sources": c["sources"], "path": c["path"], "verified_on": c["verified_on"]}


class FallbackRetriever:
    """Tries `primary` (dense or reranked search); on any API failure, answers from `fallback` (keyword search).

    After a failure the primary is skipped for `cooldown_s` seconds: during an outage every attempt costs the full
    timeout-and-retry time (about 30 s in the chat smoke run), so trying again on every message makes each turn slow.

    `last_mode` says which one answered the last search ("primary" or "fallback"), so callers can log it and the
    refusal threshold can be skipped for fallback scores, which are on a different scale.
    """

    def __init__(self, primary, fallback, log=None, cooldown_s: float = 120.0, clock=time.monotonic):
        self.primary, self.fallback, self.log = primary, fallback, log
        self.cooldown_s, self.clock, self.down_until = cooldown_s, clock, 0.0
        self.last_mode, self.last_error = "primary", ""

    def search(self, query: str, k: int | None = None, **filters) -> list[dict]:
        if self.clock() < self.down_until:
            self.last_mode = "fallback"
            self.last_error = f"primary skipped for {self.down_until - self.clock():.0f}s more after a failure"
            return self.fallback.search(query, k=k or 5, **filters)
        try:
            hits = self.primary.search(query, k=k, **filters) if k else self.primary.search(query, **filters)
            self.last_mode, self.last_error = "primary", ""
            return hits
        except Exception as exc:                             # network, timeout, quota or API error
            self.last_mode, self.last_error = "fallback", f"{type(exc).__name__}: {exc}"[:200]
            self.down_until = self.clock() + self.cooldown_s
            if self.log:
                self.log(f"retrieval fell back to keyword search for {self.cooldown_s:.0f}s ({self.last_error})")
            return self.fallback.search(query, k=k or 5, **filters)
