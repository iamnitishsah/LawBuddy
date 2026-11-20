"""Retrieval smoke test: do realistic questions bring back the right KB chunks, with each search mode?

    python -m lawbuddy.evaluation.retrieval_smoke                    # keyword, dense and rerank
    python -m lawbuddy.evaluation.retrieval_smoke --modes keyword    # no API needed

For each mode it prints hit@1 and hit@3 on the in-scope questions (eval/retrieval_smoke.yaml), and the best score
of in-scope vs out-of-scope questions. A good refusal threshold (search.min_score) sits between the lowest in-scope
top score and the highest out-of-scope top score; if those overlap, the threshold alone cannot separate them.
The full results are saved to outputs/retrieval_smoke/<mode>.json (raw, unedited).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
MODES = ("keyword", "dense", "rerank")


def load_questions(path: Path = ROOT / "eval" / "retrieval_smoke.yaml") -> list[dict]:
    return yaml.safe_load(open(path, encoding="utf-8"))["questions"]


def score_run(questions: list[dict], results: list[list[dict]]) -> dict:
    """results[i] = hits for questions[i], best first. -> hit rates and the score ranges for the threshold."""
    in_scope = [(q, r) for q, r in zip(questions, results) if q["expect"]]
    out_scope = [(q, r) for q, r in zip(questions, results) if not q["expect"]]
    hit1 = sum(bool(r) and r[0]["chunk_id"] in q["expect"] for q, r in in_scope)
    hit3 = sum(any(h["chunk_id"] in q["expect"] for h in r[:3]) for q, r in in_scope)
    top = lambda r: r[0]["score"] if r else 0.0                     # noqa: E731
    return {"in_scope": len(in_scope), "hit@1": hit1, "hit@3": hit3,
            "in_scope_top_min": min((top(r) for _, r in in_scope), default=0.0),
            "out_scope_top_max": max((top(r) for _, r in out_scope), default=0.0),
            "misses": [q["q"] for q, r in in_scope if not any(h["chunk_id"] in q["expect"] for h in r[:3])]}


def get_searcher(mode: str):  # pragma: no cover - dense and rerank need the API
    if mode == "keyword":
        from lawbuddy.retrieval.lexical import LexicalIndex
        return LexicalIndex()
    from lawbuddy.retrieval.factory import get_retriever
    return get_retriever(mode)


def main() -> None:  # pragma: no cover - needs the API for dense and rerank
    from dotenv import load_dotenv

    p = argparse.ArgumentParser(description="Retrieval smoke test over eval/retrieval_smoke.yaml.")
    p.add_argument("--modes", nargs="+", default=list(MODES), choices=MODES)
    args = p.parse_args()
    load_dotenv(ROOT / ".env")
    questions = load_questions()
    out_dir = ROOT / "outputs" / "retrieval_smoke"
    out_dir.mkdir(parents=True, exist_ok=True)

    for mode in args.modes:
        searcher, results, fallbacks, t0 = get_searcher(mode), [], 0, time.monotonic()
        for q in questions:
            results.append(searcher.search(q["q"], k=5))
            fallbacks += getattr(searcher, "last_mode", "primary") == "fallback"
        s = score_run(questions, results)
        print(f"\n== {mode}  ({time.monotonic() - t0:.1f}s{f', {fallbacks} searches fell back to keyword' if fallbacks else ''})")
        print(f"hit@1 {s['hit@1']}/{s['in_scope']}   hit@3 {s['hit@3']}/{s['in_scope']}")
        print(f"lowest in-scope top score {s['in_scope_top_min']:.3f} | highest out-of-scope top score "
              f"{s['out_scope_top_max']:.3f}")
        for m in s["misses"]:
            print(f"  miss: {m}")
        record = {"mode": mode, "summary": s, "fallbacks": fallbacks,
                  "results": [{"q": q["q"], "expect": q["expect"],
                               "hits": [{"chunk_id": h["chunk_id"], "score": round(h["score"], 4)} for h in r]}
                              for q, r in zip(questions, results)]}
        (out_dir / f"{mode}.json").write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nraw results: {out_dir.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
