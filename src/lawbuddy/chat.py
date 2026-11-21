"""Talk to LawBuddy in the terminal.

    python -m lawbuddy.chat                              # interactive; type 'quit' to stop, 'case' to see the case file
    python -m lawbuddy.chat --debug                      # also show each turn's decisions (trace, retrieval, guard)
    python -m lawbuddy.chat --script convo.txt           # replay one user message per line (blank lines skipped)
    python -m lawbuddy.chat --backend gemini             # any backend in configs/llm.yaml

Every turn is appended to data/logs/chat.jsonl.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lawbuddy.conversation.engine import Reply, Session, build_engine, log_turn


def show(reply: Reply, debug: bool) -> None:
    print(f"\nLawBuddy [{reply.kind}]:\n{reply.text}")
    cited = [p for n, p in enumerate(reply.passages, 1) if n in reply.cited]
    if cited:
        print("\nSources:")
        for n, p in enumerate(reply.passages, 1):
            if n in reply.cited:
                urls = ", ".join(s["url"] for s in p.get("sources", []) if s.get("url"))
                print(f"  [{n}] {p['title']}" + (f"  ({urls})" if urls else ""))
    if debug:
        print("\n-- trace")
        for step in reply.trace:
            print(f"   {step}")
        if reply.draft:
            print(f"   draft legal basis from: {reply.draft['chunks']}")
        if reply.guard.get("problems") or reply.guard.get("first_problems"):
            print(f"   guard first: {[p['kind'] + ': ' + p['text'] for p in reply.guard.get('first_problems', [])]}")
            print(f"   guard final: {[p['kind'] + ': ' + p['text'] for p in reply.guard.get('problems', [])]}")
        u = reply.usage
        print(f"   {u.get('llm_calls', 0)} LLM calls | {u.get('input_tokens', 0)} in / {u.get('output_tokens', 0)} "
              f"out tokens | {reply.latency_s}s total = LLM {u.get('llm_s', 0)}s + retrieval "
              f"{u.get('retrieval_s', 0)}s + other")


def save_draft(session_id: str, text: str, folder: Path | None = None) -> Path:
    """data/drafts/<session>-<n>.md, numbered so a later draft never overwrites an earlier one."""
    folder = folder or Path(__file__).resolve().parents[2] / "data" / "drafts"
    folder.mkdir(parents=True, exist_ok=True)
    n = len(list(folder.glob(f"{session_id}-*.md"))) + 1
    path = folder / f"{session_id}-{n}.md"
    path.write_text(text + "\n", encoding="utf-8")
    return path


def main() -> None:  # pragma: no cover - needs API keys
    p = argparse.ArgumentParser(description="Talk to LawBuddy.")
    p.add_argument("--backend", help="LLM backend from configs/llm.yaml")
    p.add_argument("--script", type=Path, help="file with one user message per line")
    p.add_argument("--debug", action="store_true")
    args = p.parse_args()

    engine = build_engine(args.backend, log=(lambda m: print(f"   ({m})")) if args.debug else None)
    backend = getattr(engine.llm, "name", "")
    print(f"LawBuddy [{backend} / {getattr(engine.llm, 'model', '')}]  -  legal information for Karnataka: "
          "deposits, refunds, unpaid salary. Type 'quit' to stop.")
    session = Session()

    messages = [ln.strip() for ln in args.script.read_text(encoding="utf-8").splitlines() if ln.strip()] \
        if args.script else None
    while True:
        if messages is not None:
            if not messages:
                break
            message = messages.pop(0)
            print(f"\nYou: {message}")
        else:
            try:
                message = input("\nYou: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if message.lower() in ("quit", "exit"):
                break
            if message.lower() == "case":
                print(json.dumps(session.case.to_dict(), indent=2, ensure_ascii=False))
                continue
            if not message:
                continue
        reply = engine.turn(session, message)
        show(reply, args.debug)
        if reply.kind == "draft":
            path = save_draft(session.id, reply.draft["text"])
            print(f"\n(notice saved to {path}; edit the [● fill: ...] parts before sending)")
        log_turn(session, message, reply, backend)
    print(f"\n(session {session.id} saved to data/logs/chat.jsonl)")


if __name__ == "__main__":
    main()
