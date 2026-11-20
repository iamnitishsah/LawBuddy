"""Load the curated knowledge base (kb/) and check it against the registry of allowed laws.

Each kb/<category>/*.md file is one chunk: YAML frontmatter, then a short plain-language body.

    ---
    id: deposit-overview
    title: Getting your security deposit back
    category: deposit            # deposit | consumer | salary | general
    kind: guide                  # guide (plain language) | statute (verbatim text) | practice (no legal provision)
    jurisdiction: karnataka      # karnataka | central
    cites:                       # every law the body relies on; each must be in kb/registry.yaml
      - {doc: contract-act-1872, section: "73"}
    verified_on: null            # date a person checked the chunk against its sources
    ---
    Body text ...

    python -m lawbuddy.kb.loader          # validate the KB and print a summary
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
KB_DIR = ROOT / "kb"
CATEGORIES = ("deposit", "consumer", "salary", "general")
KINDS = ("guide", "statute", "practice")
JURISDICTIONS = ("karnataka", "central")
REQUIRED = ("id", "title", "category", "kind", "jurisdiction", "cites")
MAX_WORDS = 450                  # a chunk is read whole by the model; keep each one short


@dataclass
class Chunk:
    id: str
    title: str
    category: str
    kind: str
    jurisdiction: str
    cites: list[dict]
    text: str
    path: str                                       # relative to the repo root
    verified_on: str | None = None
    sources: list[dict] = field(default_factory=list)   # filled from the registry: {doc, title, url}

    @property
    def header(self) -> str:
        return f"{self.title} | {self.category} | {self.kind}"

    def embed_text(self) -> str:
        return f"{self.title}\n\n{self.text}"


def parse_file(path: Path) -> tuple[dict, str]:
    """-> (frontmatter, body). Raises ValueError if the frontmatter is missing or malformed."""
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---\n"):
        raise ValueError(f"{path.name}: missing frontmatter")
    end = raw.find("\n---\n", 4)
    if end < 0:
        raise ValueError(f"{path.name}: frontmatter is not closed with ---")
    try:
        meta = yaml.safe_load(raw[4:end]) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"{path.name}: frontmatter is not valid YAML ({exc})") from None
    if not isinstance(meta, dict):
        raise ValueError(f"{path.name}: frontmatter is not a mapping")
    return meta, raw[end + 5:].strip()


def load_registry(kb_dir: Path = KB_DIR) -> dict:
    return yaml.safe_load(open(kb_dir / "registry.yaml", encoding="utf-8"))


def load_kb(kb_dir: Path = KB_DIR, registry: dict | None = None) -> list[Chunk]:
    """All chunks, sorted by id. Raises ValueError on a file that cannot be parsed at all."""
    registry = registry or load_registry(kb_dir)
    docs = registry.get("documents", {})
    chunks = []
    for path in sorted(kb_dir.glob("*/*.md")):
        meta, body = parse_file(path)
        missing = [k for k in REQUIRED if k not in meta]
        if missing:
            raise ValueError(f"{path.name}: missing {missing}")
        cites = meta.get("cites") or []
        sources, seen = [], set()
        for c in cites:
            d = docs.get(c.get("doc"))
            if d and c["doc"] not in seen:
                seen.add(c["doc"])
                sources.append({"doc": c["doc"], "title": d["title"], "url": d.get("url")})
        chunks.append(Chunk(id=meta["id"], title=meta["title"], category=meta["category"], kind=meta["kind"],
                            jurisdiction=meta["jurisdiction"], cites=cites, text=body,
                            path=str(path.relative_to(kb_dir.parent)),
                            verified_on=str(meta["verified_on"]) if meta.get("verified_on") else None,
                            sources=sources))
    return sorted(chunks, key=lambda c: c.id)


def validate(chunks: list[Chunk], registry: dict) -> list[str]:
    """Every problem that should stop the index from being built. Empty list = valid."""
    docs = registry.get("documents", {})
    problems, ids = [], {}
    for c in chunks:
        where = f"{c.path} ({c.id})"
        if c.id in ids:
            problems.append(f"{where}: duplicate id, also in {ids[c.id]}")
        ids[c.id] = c.path
        if c.category not in CATEGORIES:
            problems.append(f"{where}: unknown category {c.category!r}")
        if Path(c.path).parent.name != c.category:
            problems.append(f"{where}: category {c.category!r} does not match its folder")
        if c.kind not in KINDS:
            problems.append(f"{where}: unknown kind {c.kind!r}")
        if c.jurisdiction not in JURISDICTIONS:
            problems.append(f"{where}: unknown jurisdiction {c.jurisdiction!r}")
        if not c.text:
            problems.append(f"{where}: empty body")
        if len(c.text.split()) > MAX_WORDS:
            problems.append(f"{where}: {len(c.text.split())} words, more than {MAX_WORDS}; split it")
        if c.kind in ("guide", "statute") and not c.cites:
            problems.append(f"{where}: a {c.kind} must cite at least one law")
        for cite in c.cites:
            doc, section = cite.get("doc"), str(cite.get("section", ""))
            if doc not in docs:
                problems.append(f"{where}: cites {doc!r}, which is not in the registry")
            elif docs[doc].get("status") != "in_force":
                problems.append(f"{where}: cites {doc!r}, which is not in force")
            elif section not in [str(s) for s in docs[doc].get("sections", [])]:
                problems.append(f"{where}: cites {doc} section {section!r}, which the registry does not list")
    return problems


if __name__ == "__main__":
    from collections import Counter

    reg = load_registry()
    kb = load_kb(registry=reg)
    issues = validate(kb, reg)
    by_cat = Counter(c.category for c in kb)
    by_kind = Counter(c.kind for c in kb)
    print(f"{len(kb)} chunks | " + ", ".join(f"{k} {v}" for k, v in sorted(by_cat.items()))
          + " | " + ", ".join(f"{k} {v}" for k, v in sorted(by_kind.items())))
    print(f"{sum(len(c.text.split()) for c in kb)} words | verified {sum(bool(c.verified_on) for c in kb)}/{len(kb)}")
    print("\n".join(f"!! {p}" for p in issues) or "valid")
    raise SystemExit(1 if issues else 0)
