"""Build a retriever by name, with settings from configs/retrieval.yaml.

    python -m lawbuddy.retrieval.factory "landlord is not returning my deposit" --category deposit
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
VARIANTS = ("dense", "rerank")


def load_config() -> dict:
    return yaml.safe_load(open(ROOT / "configs" / "retrieval.yaml"))


class KeywordOnly:
    """Keyword search alone, for a server with no embedding API key. Reports itself as a fallback, so the
    dense / rerank score floor is not applied to its BM25 scores."""

    def __init__(self, reason: str):
        from lawbuddy.retrieval.lexical import LexicalIndex
        self.index, self.last_mode, self.last_error = LexicalIndex(), "fallback", reason

    def search(self, query: str, k: int | None = None, **filters) -> list[dict]:
        return self.index.search(query, k=k or 5, **filters)


def get_retriever(variant: str = "rerank", log=None):
    """dense: embedding search over the KB index. rerank: the dense candidates re-sorted by a cross-encoder.

    Either way the result is wrapped in a FallbackRetriever: if the hosted API fails, keyword search answers.
    The embedding and rerank APIs always use the server's key (NVIDIA_API_KEY). Without it, the result is keyword
    search only (KeywordOnly), so the service still starts.
    """
    if variant not in VARIANTS:
        raise SystemExit(f"unknown retrieval variant {variant!r}; choose from {VARIANTS}")
    from lawbuddy.retrieval.embedder import Embedder
    from lawbuddy.retrieval.index import KBIndex
    from lawbuddy.retrieval.lexical import FallbackRetriever, LexicalIndex

    cfg = load_config()
    e = cfg["embedding"]
    try:
        embedder = Embedder(e, max_retries=e.get("max_retries", 2), timeout=e.get("timeout_s", 15))
    except RuntimeError as exc:
        return KeywordOnly(f"keyword search only: {exc}")
    dense = KBIndex(embedder)
    if dense.model != e["model"]:
        raise SystemExit(f"the index was built with {dense.model}, but configs/retrieval.yaml uses "
                         f"{e['model']}; rebuild it with: python -m lawbuddy.kb.build")
    primary = dense
    if variant == "rerank":
        from lawbuddy.retrieval.reranker import Reranker, RerankRetriever
        r = cfg["rerank"]
        reranker = Reranker(r["url"], r["model"], r["api_key_env"], max_retries=r.get("max_retries", 2),
                            timeout=r.get("timeout_s", 15))
        primary = RerankRetriever(dense, reranker, candidates=r["candidates"], default_k=cfg["search"].get("top_k", 5))
    return FallbackRetriever(primary, LexicalIndex(), log=log,
                             cooldown_s=cfg["search"].get("fallback_cooldown_s", 120))


def main() -> None:  # pragma: no cover - needs the embedding API
    from dotenv import load_dotenv

    p = argparse.ArgumentParser(description="Search the knowledge base.")
    p.add_argument("query")
    p.add_argument("--category", help="deposit | consumer | salary | general")
    p.add_argument("--variant", default="rerank", choices=VARIANTS)
    p.add_argument("-k", type=int, default=5)
    p.add_argument("--keyword", action="store_true", help="keyword (BM25) search only, no API")
    args = p.parse_args()
    load_dotenv(ROOT / ".env")
    if args.keyword:
        from lawbuddy.retrieval.lexical import LexicalIndex
        retriever, mode = LexicalIndex(), "keyword"
    else:
        retriever = get_retriever(args.variant, log=print)
    hits = retriever.search(args.query, k=args.k, category=args.category)
    mode = mode if args.keyword else ("keyword fallback" if retriever.last_mode == "fallback" else args.variant)
    print(f"({mode})")
    for n, h in enumerate(hits, 1):
        print(f"[{n}] {h['score']:.3f}  {h['chunk_id']:<34} {h['title']}")


if __name__ == "__main__":
    main()
