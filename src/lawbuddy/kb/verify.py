"""Record that a person has checked KB chunks against their sources: sets `verified_on` in the frontmatter.

    python -m lawbuddy.kb.verify --all                        # every chunk, today's date
    python -m lawbuddy.kb.verify deposit-no-cap salary-claim  # only these chunks
    python -m lawbuddy.kb.verify --all --date 2026-11-21

Only the `verified_on:` line changes, so the chunk's text hash (and its embedding) stays the same. Run
`make kb-build` afterwards: it re-embeds nothing and only refreshes the metadata in kb/index/chunks.json.
"""

from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path

from lawbuddy.kb.loader import KB_DIR, parse_file

VERIFIED_RE = re.compile(r"^verified_on:.*$", re.M)


def set_verified(path: Path, on: str) -> bool:
    """-> True if the file changed. The line must already exist in the frontmatter."""
    raw = path.read_text(encoding="utf-8")
    end = raw.find("\n---\n", 4)
    head, rest = raw[:end], raw[end:]
    if not VERIFIED_RE.search(head):
        raise ValueError(f"{path.name}: no verified_on line in the frontmatter")
    new_head = VERIFIED_RE.sub(f"verified_on: {on}", head, count=1)
    if new_head == head:
        return False
    path.write_text(new_head + rest, encoding="utf-8")
    return True


def verify(ids: list[str] | None, on: str, kb_dir: Path = KB_DIR) -> list[str]:
    """Set verified_on for the given chunk ids (None = all). -> ids changed. Unknown ids raise ValueError."""
    files = {parse_file(p)[0]["id"]: p for p in sorted(kb_dir.glob("*/*.md"))}
    unknown = sorted(set(ids or []) - set(files))
    if unknown:
        raise ValueError(f"unknown chunk ids: {unknown}")
    return [i for i in (ids or list(files)) if set_verified(files[i], on)]


def main() -> None:
    p = argparse.ArgumentParser(description="Mark KB chunks as checked against their sources.")
    p.add_argument("ids", nargs="*", help="chunk ids to mark")
    p.add_argument("--all", action="store_true", help="mark every chunk")
    p.add_argument("--date", default=date.today().isoformat(), help="YYYY-MM-DD (default: today)")
    args = p.parse_args()
    if not args.all and not args.ids:
        p.error("give chunk ids or --all")
    date.fromisoformat(args.date)                                  # reject a malformed date early
    changed = verify(None if args.all else args.ids, args.date)
    print(f"verified_on: {args.date} set on {len(changed)} chunk(s)")
    print("now run: make kb-build   (re-embeds nothing; refreshes kb/index/chunks.json)")


if __name__ == "__main__":
    main()
