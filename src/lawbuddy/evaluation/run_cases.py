"""Run the test cases (eval/cases/cases.yaml) and score them in code.

    python -m lawbuddy.evaluation.run_cases                         # all cases on the default backend
    python -m lawbuddy.evaluation.run_cases --backend gemini        # another backend (and --model)
    python -m lawbuddy.evaluation.run_cases --group trap scope      # some groups (or --cases id1 id2)
    python -m lawbuddy.evaluation.run_cases --rescore groq          # re-score a saved run (no API calls)
    python -m lawbuddy.evaluation.run_cases --compare groq gemini   # compare two saved runs

Each case runs as a fresh conversation through the same engine as the API. Raw results, unedited, go to
outputs/eval/<run>/<case_id>.json (every reply with its passages, guard result, trace and usage, the case file, and
the checks); outputs/eval/<run>/summary.md and summary.json hold the scores. If a provider rate-limits a case, the
case is rerun once from the start after a pause, and the retry is recorded.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

from lawbuddy.evaluation.checks import Check, run_checks

ROOT = Path(__file__).resolve().parents[3]
CASES = ROOT / "eval" / "cases" / "cases.yaml"
OUT = ROOT / "outputs" / "eval"


def load_cases(path: Path = CASES) -> list[dict]:
    return yaml.safe_load(open(path, encoding="utf-8"))["cases"]


def kb_chunks() -> dict[str, dict]:
    from lawbuddy.kb.loader import load_kb
    return {c.id: {"title": c.title, "text": c.text} for c in load_kb()}


# --- running ------------------------------------------------------------------------------------------------

def rate_limited(replies: list[dict]) -> bool:
    return any(r["kind"] == "error" and any("RateLimit" in t or "429" in t for t in r.get("trace", []))
               for r in replies)


def run_case(engine, case: dict, pause: float) -> list[dict]:  # pragma: no cover - needs the APIs
    from lawbuddy.conversation.engine import Session
    session, replies = Session(), []
    for message in case["turns"]:
        replies.append(asdict(engine.turn(session, message)))
        time.sleep(pause)
    replies[-1]["_case_file"] = session.case.to_dict()
    return replies


def score(case: dict, replies: list[dict], registry: dict, chunks: dict) -> dict:
    checks = run_checks(case, replies, registry, chunks)
    return {"checks": [asdict(c) for c in checks], "passed": all(c.passed for c in checks)}


def save_case(run_dir: Path, case: dict, replies: list[dict], result: dict, meta: dict) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    case_file = replies[-1].pop("_case_file", None) if replies else None
    record = {"case": case, **meta, "case_file": case_file, **result, "replies": replies}
    (run_dir / f"{case['id']}.json").write_text(json.dumps(record, indent=1, ensure_ascii=False, default=str),
                                                encoding="utf-8")


# --- summarising --------------------------------------------------------------------------------------------

def summarise(records: list[dict]) -> dict:
    """Scores across cases. `records`: the saved per-case dicts."""
    by_check, by_group = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    kinds, latencies, llm_s, retr_s, tok_in, tok_out = Counter(), [], [], [], [], []
    legal_replies = guard_fixed = guard_removed = fallbacks = 0
    failures = []
    for rec in records:
        g = by_group[rec["case"]["group"]]
        g[0] += rec["passed"]
        g[1] += 1
        for c in rec["checks"]:
            by_check[c["name"]][0] += c["passed"]
            by_check[c["name"]][1] += 1
        failed = [c for c in rec["checks"] if not c["passed"]]
        if failed:
            failures.append({"id": rec["case"]["id"], "failed": [f"{c['name']}: {c['detail']}" for c in failed]})
        for r in rec["replies"]:
            kinds[r["kind"]] += 1
            latencies.append(r.get("latency_s", 0))
            u = r.get("usage") or {}
            llm_s.append(u.get("llm_s", 0))
            retr_s.append(u.get("retrieval_s", 0))
            tok_in.append(u.get("input_tokens", 0))
            tok_out.append(u.get("output_tokens", 0))
            if r["kind"] in ("advice", "draft"):
                legal_replies += 1
            gd = r.get("guard") or {}
            guard_fixed += bool(gd.get("first_problems"))
            guard_removed += bool(gd.get("removed"))
            fallbacks += (r.get("retrieval") or {}).get("mode") == "fallback"
    ordered = sorted(latencies)
    p90 = ordered[min(len(ordered) - 1, int(round(0.9 * (len(ordered) - 1))))] if ordered else 0
    grounded = by_check.get("grounded", [0, 0])
    return {
        "cases": len(records), "cases_passed": sum(r["passed"] for r in records),
        "by_group": {k: {"passed": v[0], "total": v[1]} for k, v in sorted(by_group.items())},
        "by_check": {k: {"passed": v[0], "total": v[1]} for k, v in sorted(by_check.items())},
        "turns": sum(kinds.values()), "kinds": dict(kinds),
        "legal_replies": legal_replies, "cases_with_ungrounded_law": grounded[1] - grounded[0],
        "guard_regenerations": guard_fixed, "guard_removals": guard_removed, "fallback_searches": fallbacks,
        "latency_s": {"median": round(statistics.median(latencies), 2) if latencies else 0, "p90": round(p90, 2),
                      "max": round(max(latencies), 2) if latencies else 0},
        "llm_s_median": round(statistics.median(llm_s), 2) if llm_s else 0,
        "retrieval_s_median": round(statistics.median(retr_s), 2) if retr_s else 0,
        "tokens_per_turn": {"input": round(statistics.mean(tok_in)) if tok_in else 0,
                            "output": round(statistics.mean(tok_out)) if tok_out else 0},
        "tokens_total": {"input": sum(tok_in), "output": sum(tok_out)},
        "rate_limit_retries": sum(r.get("attempts", 1) - 1 for r in records),
        "failures": failures,
    }


def summary_markdown(run: str, s: dict, records: list[dict], meta: dict) -> str:
    pct = lambda p, t: f"{p}/{t} ({100 * p / t:.0f}%)" if t else "n/a"        # noqa: E731
    lines = [f"# Evaluation: {run}", "",
             f"Model: `{meta.get('model', '')}` · run {meta.get('at', '')} · cases from `eval/cases/cases.yaml`", "",
             "## Scores", "",
             f"- **Cases passing every check: {pct(s['cases_passed'], s['cases'])}**",
             f"- Cases with untraceable law in an answer or notice (after the guard): "
             f"**{s['cases_with_ungrounded_law']}** of {s['by_check'].get('grounded', {}).get('total', 0)} with legal content",
             f"- Guard rewrote {s['guard_regenerations']} of {s['turns']} replies and removed sentences in "
             f"{s['guard_removals']}; {s['fallback_searches']} searches fell back to keyword",
             f"- Turn time: median {s['latency_s']['median']} s, 90th percentile {s['latency_s']['p90']} s, max "
             f"{s['latency_s']['max']} s (median LLM {s['llm_s_median']} s, search {s['retrieval_s_median']} s)",
             f"- Tokens per turn: {s['tokens_per_turn']['input']} in / {s['tokens_per_turn']['output']} out; total "
             f"{s['tokens_total']['input']:,} / {s['tokens_total']['output']:,} over {s['turns']} turns",
             f"- Rate-limit reruns: {s['rate_limit_retries']}", "",
             "| Check | Passed |", "|---|---|"]
    lines += [f"| {k} | {pct(v['passed'], v['total'])} |" for k, v in s["by_check"].items()]
    lines += ["", "| Group | Cases passed |", "|---|---|"]
    lines += [f"| {k} | {pct(v['passed'], v['total'])} |" for k, v in s["by_group"].items()]
    lines += ["", "## Failures", ""]
    lines += [f"- **{f['id']}**: " + "; ".join(f["failed"]) for f in s["failures"]] or ["None."]
    lines += ["", "## Every case", "", "| Case | Lang | Reply kinds | Checks | Seconds | Last reply (start) |",
              "|---|---|---|---|---|---|"]
    for rec in records:
        c, reps = rec["case"], rec["replies"]
        ok = sum(x["passed"] for x in rec["checks"])
        text = reps[-1]["text"].split("\n---\n")[0] if reps else ""
        excerpt = " ".join(text.split())[:140].replace("|", "/")
        lines.append(f"| {c['id']} | {c.get('lang', '')} | {' → '.join(r['kind'] for r in reps)} | "
                     f"{ok}/{len(rec['checks'])}{'' if rec['passed'] else ' ✗'} | "
                     f"{round(sum(r.get('latency_s', 0) for r in reps), 1)} | {excerpt} |")
    return "\n".join(lines) + "\n"


def write_summary(run_dir: Path, run: str, meta: dict) -> dict:
    records = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(run_dir.glob("*.json"))
               if p.name != "summary.json"]
    s = summarise(records)
    (run_dir / "summary.json").write_text(json.dumps({**meta, **s}, indent=1, ensure_ascii=False), encoding="utf-8")
    (run_dir / "summary.md").write_text(summary_markdown(run, s, records, meta), encoding="utf-8")
    return s


def compare(runs: list[str]) -> str:
    sums = {r: json.loads((OUT / r / "summary.json").read_text(encoding="utf-8")) for r in runs}
    pct = lambda d: f"{d['passed']}/{d['total']}"                         # noqa: E731
    rows = [("Model", lambda s: f"`{s.get('model', '')}`"),
            ("Cases passing every check", lambda s: f"{s['cases_passed']}/{s['cases']}"),
            ("Cases with untraceable law", lambda s: str(s["cases_with_ungrounded_law"])),
            ("Guard rewrites / removals", lambda s: f"{s['guard_regenerations']} / {s['guard_removals']}"),
            ("Median turn time (s)", lambda s: str(s["latency_s"]["median"])),
            ("90th percentile turn time (s)", lambda s: str(s["latency_s"]["p90"])),
            ("Tokens per turn (in / out)", lambda s: f"{s['tokens_per_turn']['input']} / {s['tokens_per_turn']['output']}")]
    checks = sorted({k for s in sums.values() for k in s["by_check"]})
    rows += [(f"check: {k}", lambda s, k=k: pct(s["by_check"][k]) if k in s["by_check"] else "n/a") for k in checks]
    lines = ["# Comparison: " + " vs ".join(runs), "", "| | " + " | ".join(runs) + " |",
             "|---|" + "---|" * len(runs)]
    lines += [f"| {name} | " + " | ".join(f(sums[r]) for r in runs) + " |" for name, f in rows]
    return "\n".join(lines) + "\n"


def main() -> None:  # pragma: no cover - needs the APIs (except --rescore and --compare)
    p = argparse.ArgumentParser(description="Run and score the LawBuddy test cases.")
    p.add_argument("--backend", help="LLM backend from configs/llm.yaml (default: the configured one)")
    p.add_argument("--model", help="another model of that backend")
    p.add_argument("--group", nargs="+", help="only these groups")
    p.add_argument("--cases", nargs="+", help="only these case ids")
    p.add_argument("--pause", type=float, default=1.0, help="seconds between turns (free-tier rate limits)")
    p.add_argument("--run-name", help="output folder name (default: the backend)")
    p.add_argument("--rescore", metavar="RUN", help="re-score a saved run with the current cases.yaml, no API calls")
    p.add_argument("--compare", nargs="+", metavar="RUN", help="compare saved runs")
    args = p.parse_args()

    if args.compare:
        text = compare(args.compare)
        (OUT / "comparison.md").write_text(text, encoding="utf-8")
        print(text + f"\nwritten to {(OUT / 'comparison.md').relative_to(ROOT)}")
        return

    from lawbuddy.kb.loader import load_registry
    registry, chunks, cases = load_registry(), kb_chunks(), load_cases()
    if args.rescore:
        run_dir = OUT / args.rescore
        by_id = {c["id"]: c for c in cases}
        meta = {}
        for path in sorted(run_dir.glob("*.json")):
            if path.name == "summary.json":
                meta = {k: v for k, v in json.loads(path.read_text()).items() if k in ("model", "backend", "at")}
                continue
            rec = json.loads(path.read_text(encoding="utf-8"))
            case = by_id.get(rec["case"]["id"], rec["case"])
            rec.update(case=case, **score(case, rec["replies"], registry, chunks))
            path.write_text(json.dumps(rec, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
        s = write_summary(run_dir, args.rescore, meta)
        print(f"re-scored {args.rescore}: {s['cases_passed']}/{s['cases']} cases pass -> {run_dir.relative_to(ROOT)}/summary.md")
        return

    from lawbuddy.conversation.engine import build_engine
    from lawbuddy.llm.base import get_llm
    engine = build_engine(args.backend)
    if args.model:
        engine.llm = get_llm(args.backend, model=args.model)
    run = args.run_name or engine.llm.name
    run_dir = OUT / run
    meta = {"backend": engine.llm.name, "model": engine.llm.model,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    selected = [c for c in cases if (not args.group or c["group"] in args.group)
                and (not args.cases or c["id"] in args.cases)]
    print(f"{len(selected)} cases on {engine.llm.name} / {engine.llm.model} -> {run_dir.relative_to(ROOT)}/")
    for case in selected:
        t0, attempts = time.monotonic(), 1
        replies = run_case(engine, case, args.pause)
        if rate_limited(replies):
            print(f"   {case['id']}: rate limited, waiting 60 s and rerunning the case")
            time.sleep(60)
            replies, attempts = run_case(engine, case, args.pause), 2
        result = score(case, replies, registry, chunks)
        save_case(run_dir, case, replies, result, {**meta, "attempts": attempts,
                                                   "seconds": round(time.monotonic() - t0, 1)})
        failed = [f"{c['name']}" for c in result["checks"] if not c["passed"]]
        print(f"{'ok ' if result['passed'] else '!! '} {case['id']:<28} {' → '.join(r['kind'] for r in replies):<30}"
              f"{'' if not failed else 'failed: ' + ', '.join(failed)}")
    s = write_summary(run_dir, run, meta)
    print(f"\n{s['cases_passed']}/{s['cases']} cases pass every check · untraceable law in "
          f"{s['cases_with_ungrounded_law']} case(s) · median turn {s['latency_s']['median']} s"
          f"\nsummary: {(run_dir / 'summary.md').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
