"""Tests for the knowledge base, its loader, the index build and in-memory search (no network)."""

import json

import numpy as np
import pytest

from lawbuddy.kb.build import build, content_hash
from lawbuddy.kb.extract import decode_glyphs
from lawbuddy.kb.loader import CATEGORIES, load_kb, load_registry, parse_file, validate
from lawbuddy.retrieval.index import KBIndex

CHUNK = """---
id: {id}
title: "{title}"
category: {category}
kind: {kind}
jurisdiction: central
cites:
{cites}
verified_on: null
---
{body}
"""


def write_chunk(kb, id, category="deposit", kind="guide", cites='  - {doc: act, section: "1"}', body="Body text.",
                title="A title"):
    (kb / category).mkdir(parents=True, exist_ok=True)
    (kb / category / f"{id}.md").write_text(CHUNK.format(id=id, title=title, category=category, kind=kind,
                                                         cites=cites, body=body))


@pytest.fixture()
def kb(tmp_path):
    (tmp_path / "registry.yaml").write_text(
        "documents:\n  act: {title: Some Act, status: in_force, sections: ['1', '2'], url: https://x}\n"
        "  old: {title: Old Act, status: repealed, sections: ['1']}\n")
    return tmp_path


class FakeEmbedder:
    """Maps each text to a fixed direction by keyword, so search results are predictable."""
    WORDS = ("deposit", "refund", "salary")

    def __init__(self):
        self.doc_calls = 0

    def _vec(self, text):
        v = np.array([text.lower().count(w) for w in self.WORDS], dtype=np.float32) + 0.01
        return v / np.linalg.norm(v)

    def encode_docs(self, texts):
        self.doc_calls += len(texts)
        return np.vstack([self._vec(t) for t in texts])

    def encode_query(self, query):
        return self._vec(query)


# --- the real knowledge base -------------------------------------------------------------------------------

def test_the_real_kb_is_valid_and_covers_every_category():
    registry = load_registry()
    chunks = load_kb(registry=registry)
    assert validate(chunks, registry) == []
    assert {c.category for c in chunks} == set(CATEGORIES)
    assert all(c.sources for c in chunks if c.kind != "practice")       # every legal chunk links to a source


def test_registry_documents_are_complete_and_repeals_point_somewhere_real():
    registry = load_registry()
    docs = registry["documents"]
    for name, d in docs.items():
        assert {"title", "status", "sections", "url", "aliases"} <= set(d), name
    for r in registry["repealed"]:
        assert r["replaced_by"] is None or r["replaced_by"] in docs, r["title"]


def test_the_committed_index_matches_the_kb():
    chunks = load_kb()
    meta = json.loads(open("kb/index/chunks.json", encoding="utf-8").read())
    assert [c["id"] for c in meta["chunks"]] == [c.id for c in chunks]
    assert [c["hash"] for c in meta["chunks"]] == [content_hash(c.embed_text(), meta["model"]) for c in chunks], \
        "the KB changed since the index was built; run: python -m lawbuddy.kb.build"
    assert np.load("kb/index/vectors.npz")["vectors"].shape == (len(chunks), meta["dimensions"])


# --- loader and validation ---------------------------------------------------------------------------------

def test_frontmatter_errors_name_the_file(kb):
    (kb / "deposit").mkdir()
    bad = kb / "deposit" / "bad.md"
    bad.write_text("no frontmatter here")
    with pytest.raises(ValueError, match="bad.md: missing frontmatter"):
        parse_file(bad)
    bad.write_text("---\ntitle: Colon: breaks yaml\n---\nbody")
    with pytest.raises(ValueError, match="bad.md: frontmatter is not valid YAML"):
        parse_file(bad)


def test_validation_catches_bad_citations_and_metadata(kb):
    write_chunk(kb, "ok")
    write_chunk(kb, "unknown-law", cites='  - {doc: nope, section: "1"}')
    write_chunk(kb, "unlisted-section", cites='  - {doc: act, section: "9"}')
    write_chunk(kb, "repealed-law", cites='  - {doc: old, section: "1"}')
    write_chunk(kb, "guide-without-law", cites="  []")
    write_chunk(kb, "wrong-folder", category="salary", body="x")
    (kb / "salary" / "wrong-folder.md").write_text((kb / "salary" / "wrong-folder.md").read_text()
                                                   .replace("category: salary", "category: deposit"))
    write_chunk(kb, "too-long", body="word " * 500)
    registry = load_registry(kb)
    problems = "\n".join(validate(load_kb(kb, registry), registry))
    assert "'nope', which is not in the registry" in problems
    assert "section '9', which the registry does not list" in problems
    assert "'old', which is not in force" in problems
    assert "a guide must cite at least one law" in problems
    assert "does not match its folder" in problems
    assert "500 words" in problems
    assert "(ok)" not in problems


def test_practice_chunks_may_cite_nothing_and_sources_come_from_the_registry(kb):
    write_chunk(kb, "tips", kind="practice", cites="  []")
    write_chunk(kb, "law", cites='  - {doc: act, section: "1"}\n  - {doc: act, section: "2"}')
    registry = load_registry(kb)
    chunks = {c.id: c for c in load_kb(kb, registry)}
    assert validate(list(chunks.values()), registry) == []
    assert chunks["law"].sources == [{"doc": "act", "title": "Some Act", "url": "https://x"}]   # one per document


# --- build and search --------------------------------------------------------------------------------------

def test_build_refuses_an_invalid_kb(kb, tmp_path):
    write_chunk(kb, "broken", cites='  - {doc: nope, section: "1"}')
    with pytest.raises(SystemExit, match="not valid"):
        build(FakeEmbedder(), "fake-model", index_dir=tmp_path / "index", kb_dir=kb)


def test_build_reuses_unchanged_chunks(kb, tmp_path):
    write_chunk(kb, "a", body="deposit deposit")
    write_chunk(kb, "b", body="refund")
    emb, out = FakeEmbedder(), tmp_path / "index"
    assert build(emb, "m", index_dir=out, kb_dir=kb)["embedded"] == 2
    write_chunk(kb, "b", body="refund refund")                          # only b changes
    summary = build(emb, "m", index_dir=out, kb_dir=kb)
    assert summary["embedded"] == 1 and summary["reused"] == 1 and emb.doc_calls == 3
    assert build(emb, "other-model", index_dir=out, kb_dir=kb)["embedded"] == 2     # a new model re-embeds all


def test_search_ranks_and_filters_by_category_and_kind(kb, tmp_path):
    write_chunk(kb, "dep", category="deposit", body="deposit deposit")
    write_chunk(kb, "ref", category="consumer", body="refund refund")
    write_chunk(kb, "sal", category="salary", body="salary")
    write_chunk(kb, "sal-tips", category="salary", kind="practice", cites="  []", body="salary salary")
    build(FakeEmbedder(), "m", index_dir=tmp_path / "index", kb_dir=kb)
    index = KBIndex(FakeEmbedder(), tmp_path / "index")

    hits = index.search("where is my deposit", k=2)
    assert hits[0]["chunk_id"] == "dep" and len(hits) == 2 and hits[0]["score"] > hits[1]["score"]
    assert {"header", "text", "sources", "cites", "category", "kind"} <= set(hits[0])
    assert {h["chunk_id"] for h in index.search("deposit", category="salary")} == {"sal", "sal-tips"}
    assert [h["chunk_id"] for h in index.search("salary", category="salary", kinds=["guide"])] == ["sal"]
    assert {h["chunk_id"] for h in index.search("x", category=["deposit", "consumer"])} == {"dep", "ref"}
    assert index.search("x", category="general") == []


def test_glyph_codes_from_the_rent_act_pdf_are_decoded():
    assert decode_glyphs("/G75/G65/G82/G78/G65/G84/G65/G75/G65/G32/G65/G67/G84") == "KARNATAKA ACT"
    assert decode_glyphs("plain text, no glyphs") == "plain text, no glyphs"


def test_missing_index_says_how_to_build_it(tmp_path):
    with pytest.raises(RuntimeError, match="python -m lawbuddy.kb.build"):
        KBIndex(FakeEmbedder(), tmp_path / "nothing-here")
