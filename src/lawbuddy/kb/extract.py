"""Extract the text of the source PDFs, for reading and quoting while writing KB chunks.

    python -m lawbuddy.kb.extract          # data/sources/*.pdf -> data/text/*.txt

Each page starts with a `<<<PAGE n>>>` marker, so a quote can be traced back to its page. Some PDFs (the Karnataka
Rent Act) encode their text as glyph names like /G75/G65/G82, which are decimal character codes ("KAR"); these are
decoded. The Constitution (400+ pages) is skipped: the KB uses only Article 39A from it.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCES, TEXT = ROOT / "data" / "sources", ROOT / "data" / "text"
SKIP = ("IndianConstitution",)
GLYPH_RE = re.compile(r"/G(\d{2,3})")


def decode_glyphs(text: str) -> str:
    return GLYPH_RE.sub(lambda m: chr(int(m.group(1))), text) if "/G" in text else text


def extract(pdf: Path) -> str:
    from pypdf import PdfReader
    pages = [decode_glyphs(p.extract_text() or "") for p in PdfReader(pdf).pages]
    return "".join(f"\n<<<PAGE {i}>>>\n{t}" for i, t in enumerate(pages, start=1))


def main() -> None:
    logging.disable(logging.WARNING)            # pypdf warns about fonts it cannot fully parse; the text is fine
    TEXT.mkdir(parents=True, exist_ok=True)
    for pdf in sorted(SOURCES.glob("*.pdf")):
        if pdf.stem.startswith(SKIP):
            continue
        text = extract(pdf)
        (TEXT / f"{pdf.stem}.txt").write_text(text, encoding="utf-8")
        print(f"{pdf.name}: {text.count('<<<PAGE')} pages, {len(text):,} chars")


if __name__ == "__main__":
    main()
