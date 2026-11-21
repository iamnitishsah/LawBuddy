"""Citation helpers: number the passages, normalise how models cite them, check every citation.

Rules the answer writers rely on:
  - Every factual sentence ends with [n], where n is a passage the model was shown.
  - Retrieved text is untrusted data: it is delimited, and the model is told to ignore
    any instructions inside it (prompt-injection defence).
  - [n] pointing at a passage that was not shown, or a factual sentence with no [n], is flagged.
"""

from __future__ import annotations

import re

CITATION_RE = re.compile(r"\[(\d+)\]")
SENTENCE_RE = re.compile(r"(?<=[.!?।])\s+")                             # । = Devanagari full stop (।)
FULLWIDTH_CITE_RE = re.compile(r"【(\d+)(?:†[^】]*)?】")   # gpt-oss style: 【1】 or 【1†L1-L3】
GROUPED_CITE_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)+)\]")                    # [1, 2] -> [1][2]
ABBREV_RE = re.compile(r"\b(?:Rs|No|Sec|Secs|S|Ss|Art|Arts|Cl|Ch|Sch|Govt|Pvt|Ltd|Co|vs|v|"
                       r"e\.g|i\.e|etc|approx|Mr|Mrs|Ms|Dr|Smt|Shri)\.$")


def split_sentences(text: str) -> list[str]:
    """Split on sentence ends, but not after abbreviations such as 'Rs.' or 'Sec.'."""
    out: list[str] = []
    for part in SENTENCE_RE.split(text):
        if out and ABBREV_RE.search(out[-1]):
            out[-1] += " " + part
        else:
            out.append(part)
    return out


DASHES_RE = re.compile("[‐‑‒–—―−]")      # hyphen-like characters -> "-"
SPACES_RE = re.compile("[   ]")                              # no-break spaces -> " "


def normalize_text(text: str) -> str:
    """Models often write "E‑Commerce" with a no-break hyphen or use no-break spaces; law names in the registry
    use plain ones, so normalise before any matching (and for display, the plain characters look the same)."""
    return SPACES_RE.sub(" ", DASHES_RE.sub("-", text))


def normalize_citations(text: str) -> str:
    """Different models write citations differently; convert them all to [n]."""
    text = FULLWIDTH_CITE_RE.sub(r"[\1]", text)
    return GROUPED_CITE_RE.sub(lambda m: "".join(f"[{x.strip()}]" for x in m.group(1).split(",")), text)


def format_passages(hits: list[dict]) -> str:
    blocks = []
    for n, h in enumerate(hits, start=1):
        blocks.append(f'<passage id="{n}" source="{h["header"]}">\n{h["text"]}\n</passage>')
    return "\n\n".join(blocks)


def check_citations(text: str, n_passages: int) -> tuple[list[int], list[int], list[str]]:
    """-> (valid cited ids, invalid ids, factual-looking sentences with no citation)."""
    ids = [int(x) for x in CITATION_RE.findall(text)]
    valid = sorted({i for i in ids if 1 <= i <= n_passages})
    invalid = sorted({i for i in ids if not 1 <= i <= n_passages})
    uncited = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#") or (s.startswith("**") and s.endswith("**")) or s.endswith(":"):
            continue
        sents = split_sentences(line.strip().lstrip("-*• ").strip())
        cited_at = [i for i, sent in enumerate(sents) if CITATION_RE.search(sent)]
        covered = cited_at[-1] if cited_at else -1      # a citation covers the sentences before it in the same bullet
        for sent in sents[covered + 1:]:
            if len(sent.split()) >= 6:
                uncited.append(sent)
    return valid, invalid, uncited
