"""Embed the knowledge base and save the search index.

    python -m lawbuddy.kb.build            # validate kb/, embed new or changed chunks, write kb/index/
    python -m lawbuddy.kb.build --force    # re-embed every chunk

The index is two files, small enough to commit, so a deployment needs no embedding step:
    kb/index/vectors.npz   one L2-normalised vector per chunk, in the order of chunks.json
    kb/index/chunks.json   chunk metadata and text, the embedding model, and a content hash per chunk

A chunk is re-embedded only when its text or the embedding model changes (the hash covers both).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml

from lawbuddy.kb.loader import KB_DIR, ROOT, load_kb, load_registry, validate

INDEX_DIR = KB_DIR / "index"


def content_hash(text: str, model: str) -> str:
    return hashlib.sha256(f"{model}\n{text}".encode("utf-8")).hexdigest()[:16]


def load_previous(index_dir: Path) -> dict[str, np.ndarray]:
    """hash -> vector from the existing index, so unchanged chunks are not embedded again."""
    meta, vec = index_dir / "chunks.json", index_dir / "vectors.npz"
    if not (meta.exists() and vec.exists()):
        return {}
    chunks = json.loads(meta.read_text(encoding="utf-8"))["chunks"]
    vectors = np.load(vec)["vectors"]
    return {c["hash"]: vectors[i] for i, c in enumerate(chunks)}


def build(embedder, model: str, index_dir: Path = INDEX_DIR, kb_dir: Path = KB_DIR, force: bool = False) -> dict:
    """-> summary. Raises SystemExit if the KB does not validate."""
    registry = load_registry(kb_dir)
    chunks = load_kb(kb_dir, registry)
    problems = validate(chunks, registry)
    if problems:
        raise SystemExit("knowledge base is not valid:\n" + "\n".join(f"  {p}" for p in problems))

    previous = {} if force else load_previous(index_dir)
    hashes = [content_hash(c.embed_text(), model) for c in chunks]
    todo = [i for i, h in enumerate(hashes) if h not in previous]
    fresh = embedder.encode_docs([chunks[i].embed_text() for i in todo]) if todo else np.zeros((0, 0))
    new = dict(zip(todo, fresh))
    vectors = np.vstack([new[i] if i in new else previous[h] for i, h in enumerate(hashes)]).astype(np.float32)

    index_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(index_dir / "vectors.npz", vectors=vectors)
    meta = {"built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "model": model,
            "dimensions": int(vectors.shape[1]),
            "chunks": [{**asdict(c), "header": c.header, "hash": h} for c, h in zip(chunks, hashes)]}
    (index_dir / "chunks.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"chunks": len(chunks), "embedded": len(todo), "reused": len(chunks) - len(todo),
            "dimensions": meta["dimensions"]}


def main() -> None:  # pragma: no cover - needs the embedding API
    from dotenv import load_dotenv

    from lawbuddy.retrieval.embedder import Embedder

    p = argparse.ArgumentParser(description="Embed the knowledge base and save the index.")
    p.add_argument("--force", action="store_true", help="re-embed every chunk")
    args = p.parse_args()
    load_dotenv(ROOT / ".env")
    cfg = yaml.safe_load(open(ROOT / "configs" / "retrieval.yaml"))["embedding"]
    summary = build(Embedder(cfg), cfg["model"], force=args.force)
    print(f"{summary['chunks']} chunks: {summary['embedded']} embedded, {summary['reused']} reused "
          f"| {summary['dimensions']} dims | {cfg['model']} -> {INDEX_DIR.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
