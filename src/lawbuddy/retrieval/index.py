"""In-memory dense search over the knowledge-base index (kb/index/).

The KB is a few dozen chunks, so a vector database is unnecessary: the vectors live in one numpy array and a
search is a single matrix-vector product. Vectors are L2-normalised, so the dot product is cosine similarity.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from lawbuddy.kb.build import INDEX_DIR


class KBIndex:
    def __init__(self, embedder, index_dir: Path = INDEX_DIR):
        meta_path, vec_path = index_dir / "chunks.json", index_dir / "vectors.npz"
        if not (meta_path.exists() and vec_path.exists()):
            raise RuntimeError(f"no index in {index_dir}; build it with: python -m lawbuddy.kb.build")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        self.embedder, self.model, self.chunks = embedder, meta["model"], meta["chunks"]
        self.vectors = np.load(vec_path)["vectors"]
        if len(self.chunks) != len(self.vectors):
            raise RuntimeError(f"index is inconsistent: {len(self.chunks)} chunks but {len(self.vectors)} vectors")

    def search(self, query: str, k: int = 5, category: str | list[str] | None = None,
               kinds: list[str] | None = None) -> list[dict]:
        """Top-k chunks, best first. `category` and `kinds` restrict which chunks are searched."""
        cats = [category] if isinstance(category, str) else category
        allowed = [i for i, c in enumerate(self.chunks)
                   if (not cats or c["category"] in cats) and (not kinds or c["kind"] in kinds)]
        if not allowed:
            return []
        scores = self.vectors[allowed] @ self.embedder.encode_query(query)
        order = np.argsort(-scores)[:k]
        return [self._hit(allowed[j], float(scores[j])) for j in order]

    def _hit(self, i: int, score: float) -> dict:
        c = self.chunks[i]
        return {"chunk_id": c["id"], "score": score, "header": c["header"], "title": c["title"], "text": c["text"],
                "category": c["category"], "kind": c["kind"], "jurisdiction": c["jurisdiction"],
                "cites": c["cites"], "sources": c["sources"], "path": c["path"], "verified_on": c["verified_on"]}
