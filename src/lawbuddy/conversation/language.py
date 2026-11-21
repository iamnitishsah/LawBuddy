"""Which script a text is written in, and a code-level correction of the model's language label.

The analysis model labels the user's language, but on short messages it can get the script wrong: "kal raat order
kiya tha" (Hindi in Latin letters) was labelled "Hindi" and answered in Devanagari (eval, con-06). The user's own
script is a fact code can read, so it wins over the label.
"""

from __future__ import annotations

SCRIPT_RANGES = {"devanagari": (0x0900, 0x097F), "kannada": (0x0C80, 0x0CFF), "tamil": (0x0B80, 0x0BFF),
                 "telugu": (0x0C00, 0x0C7F), "malayalam": (0x0D00, 0x0D7F)}


def script_of(text: str) -> str:
    """The main script of a text: latin, devanagari, kannada, tamil, telugu or malayalam. A reply in Hindi still
    contains Latin law names and numbers, so an Indic script wins at 30% of the letters."""
    counts = {name: 0 for name in SCRIPT_RANGES}
    latin = 0
    for ch in text:
        if ch.isascii() and ch.isalpha():
            latin += 1
            continue
        cp = ord(ch)
        for name, (lo, hi) in SCRIPT_RANGES.items():
            if lo <= cp <= hi:
                counts[name] += 1
                break
    letters = latin + sum(counts.values())
    if not letters:
        return "latin"
    best = max(counts, key=counts.get)
    return best if counts[best] / letters >= 0.3 else "latin"


def correct_language(label: str, message: str, previous: str = "") -> str:
    """The language to reply in, given the model's label, the user's latest message and the conversation's language
    so far. Only the script is corrected; the model's judgement of the language itself is kept."""
    label = (label or "").strip() or previous or "English"
    low = label.lower()
    script = script_of(message)
    if script == "kannada":
        return "Kannada"
    if script == "devanagari" and ("hinglish" in low or "english" in low):
        return "Hindi"
    if script == "latin" and "hindi" in low and "hinglish" not in low:
        return "Hinglish"
    return label
