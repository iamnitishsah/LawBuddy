"""Check every legal reference in an answer against the registry and the passages the model was shown.

This is the main defence against invented law. The model is told to use only the passages, but a model can still
write "Section 420 IPC" or "as held in Sharma v. State". This module finds such references with patterns, not with
another model, and reports each one that cannot be traced:

    case_law            any case citation ("X v. Y", AIR 2019 SC ..., (2020) 3 SCC ...). LawBuddy never cites cases.
    unknown_law         an Act / Code / Rules name that is neither in kb/registry.yaml nor in the passages shown
    wrong_year          a known law with the wrong year ("Limitation Act, 1908")
    repealed_law        a repealed law used as if current (no "replaced" / "repealed" nearby), or a section of it
    unlisted_section    a section / article / rule of a known law that the registry does not list and the passages
                        do not mention
    unanchored_section  a section number with no law it could belong to
    invalid_citation    [n] pointing at a passage that was not shown

A law or section that appears in the passages shown is accepted even if the registry does not list it: the
passages come from the verified KB, so repeating them is grounded.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from lawbuddy.guard.citations import check_citations, normalize_text, split_sentences

YEAR_RE = re.compile(r"\b(1[89]\d\d|20\d\d)\b")

CASE_LAW_RES = [
    re.compile(r"\b[A-Z][\w.&'-]*(?:\s+[A-Z][\w.&'-]*){0,5}\s+(?:v\.|vs\.?|versus)\s+(?:The\s+)?[A-Z][\w.&'-]*"),
    re.compile(r"\bAIR\s+\d{4}\b"),
    re.compile(r"\(\d{4}\)\s*\d+\s*SCC\b"),
    re.compile(r"\b\d{4}\s+SCC\b"),
    re.compile(r"\b(?:Supreme Court|High Court|Hon'?ble Court)\s+(?:has\s+)?(?:held|ruled|observed|decided)\b", re.I),
]

# section-like references: (kind, keyword pattern). The numbers follow the keyword.
NUM = r"\d+[A-Z]?(?:\s*\([0-9a-z]+\))*"
NUM_LIST = rf"{NUM}(?:\s*(?:,|and|to|&|-|–)\s*{NUM})*"
REF_RES = [
    ("section", re.compile(rf"(?:\b(?:sections?|secs?\.?|ss?\.|u/s\.?)|धारा)\s*({NUM_LIST})", re.I)),
    ("article", re.compile(rf"(?:\b(?:articles?|arts?\.)|अनुच्छेद)\s*({NUM_LIST})", re.I)),
    ("rule", re.compile(rf"\b(?:rules?|rr?\.)\s*({NUM_LIST})", re.I)),
]
BARE_SECTION_RE = re.compile(r"\b(\d+[A-Z]?)\s+(?:of\s+(?:the\s+)?)?(IPC|CrPC|Cr\.P\.C\.|BNS|BNSS)\b")
LAW_NAME_RE = re.compile(r"\b((?:[A-Z][A-Za-z'()&-]*\s+){1,8}(?:Act|Code|Rules|Regulations|Sanhita|Adhiniyam))\b"
                         r"(?:,?\s*(\d{4}))?")
LEADING_WORDS = {"The", "This", "That", "These", "Under", "Each", "Every", "Such", "Your", "Any", "Both", "Our",
                 "Its", "Their", "Per", "As", "By", "In", "Of", "From", "And", "Or", "If", "When", "A", "An"}
REPLACED_WORDS = re.compile(r"replac|repeal|no longer|old law|earlier law|supersed|instead|बदल|जगह|निरस्त", re.I)
ANCHOR_WINDOW = 160                     # characters: a section belongs to the nearest law name within this distance


@dataclass
class LawMention:
    start: int
    end: int
    raw: str
    doc: str | None                     # registry id, or None if unknown
    repealed: bool = False
    year: str | None = None


@dataclass
class Problem:
    kind: str
    text: str                           # the offending text, as written in the answer
    detail: str = ""


@dataclass
class GuardReport:
    problems: list[Problem] = field(default_factory=list)
    uncited_sentences: list[str] = field(default_factory=list)
    cited: list[int] = field(default_factory=list)
    refs: list[dict] = field(default_factory=list)          # every reference found: {kind, text, doc, section}

    @property
    def ok(self) -> bool:
        return not self.problems

    def summary(self) -> str:
        return "; ".join(f"{p.kind}: {p.text}" + (f" ({p.detail})" if p.detail else "") for p in self.problems)


class LawIndex:
    """Every name a known law can be written as, from the registry (in-force and repealed)."""

    def __init__(self, registry: dict):
        self.docs = registry.get("documents", {})
        names: list[tuple[str, str, bool]] = []
        for doc_id, d in self.docs.items():
            for name in [d["title"], *d.get("aliases", [])]:
                names.append((name, doc_id, False))
        for r in registry.get("repealed", []):
            for name in [r["title"], *r.get("aliases", [])]:
                names.append((name, f"repealed:{r['title']}", True))
        # Longest names first, so "Consumer Protection Act, 1986" wins over "Consumer Protection Act".
        names.sort(key=lambda n: -len(n[0]))
        self.names = [(re.compile(r"(?<![\w])" + re.escape(name).replace(r"\ ", r"\s+") + r"(?![\w])"
                                  + r"(?:,?\s*(\d{4}))?", re.I if len(name) > 5 else 0), name, doc, rep)
                      for name, doc, rep in names]
        self.repealed_titles = {f"repealed:{r['title']}": r for r in registry.get("repealed", [])}

    def doc_year(self, doc: str) -> str | None:
        title = self.docs[doc]["title"] if doc in self.docs else self.repealed_titles[doc]["title"]
        m = YEAR_RE.search(title)
        return m.group(1) if m else None

    def find(self, text: str) -> list[LawMention]:
        mentions: list[LawMention] = []
        taken = [False] * len(text)
        for rx, _name, doc, repealed in self.names:
            for m in rx.finditer(text):
                if any(taken[m.start():m.end()]):
                    continue
                for i in range(m.start(), m.end()):
                    taken[i] = True
                mentions.append(LawMention(m.start(), m.end(), m.group(0), doc, repealed, m.group(1)))
        for m in LAW_NAME_RE.finditer(text):                    # capitalised "... Act" names not in the registry
            words = m.group(1).split()
            while words and words[0] in LEADING_WORDS:
                words.pop(0)
            if len(words) < 2:                                  # "the Act", "This Code": a back-reference
                continue
            start = m.start(1) + m.group(1).index(words[0])
            if any(taken[start:m.end()]):
                continue
            mentions.append(LawMention(start, m.end(), text[start:m.end()], None, False, m.group(2)))
        return sorted(mentions, key=lambda x: x.start)


def _numbers(span: str) -> list[str]:
    """'2(3)(e) to 5' -> ['2', '3', '4', '5']; '73 and 74' -> ['73', '74']; '39A' -> ['39A']."""
    span = re.sub(r"\([0-9a-z]+\)", "", span)
    out: list[str] = []
    tokens = re.findall(r"\d+[A-Z]?|to|-|–", span)
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in ("to", "-", "–") and out and i + 1 < len(tokens) and out[-1].isdigit() and tokens[i + 1].isdigit():
            a, b = int(out[-1]), int(tokens[i + 1])
            if 0 < b - a <= 20:
                out += [str(n) for n in range(a + 1, b + 1)]
                i += 2
                continue
        if t not in ("to", "-", "–"):
            out.append(t)
        i += 1
    return [n for n in out if not (n.isdigit() and int(n) >= 1000)]        # years are not sections


def find_refs(text: str, laws: LawIndex) -> tuple[list[LawMention], list[dict]]:
    """-> (law mentions, section-like references with the law each one is anchored to)."""
    mentions = laws.find(text)
    refs: list[dict] = []
    for kind, rx in REF_RES:
        for m in rx.finditer(text):
            law = _anchor(m.start(), m.end(), mentions, text)
            for n in _numbers(m.group(1)):
                refs.append({"kind": kind, "text": m.group(0).strip(), "section": n,
                             "doc": law.doc if law else None, "law": law})
    for m in BARE_SECTION_RE.finditer(text):                  # "420 IPC"
        law = next((x for x in mentions if x.start <= m.start(2) < x.end), None) or \
            _anchor(m.start(), m.end(), mentions, text)
        refs.append({"kind": "section", "text": m.group(0), "section": m.group(1),
                     "doc": law.doc if law else None, "law": law})
    return mentions, refs


OF_LAW_RE = re.compile(r"\s*(?:of|under|in)\s+(?:the\s+)?", re.I)


def _anchor(start: int, end: int, mentions: list[LawMention], text: str = "") -> LawMention | None:
    """The law a reference belongs to:
    1. "section 17 of the Code on Wages": the law right after "of";
    2. else the nearest law before it within ANCHOR_WINDOW ("Code on Wages, 2019, s. 17" is the citation style);
    3. else the nearest law after it within the window;
    4. else the last law mentioned anywhere before it.
    (Nearest-in-either-direction tied "Consumer Protection Act, 2019, s. 2(10)" to an E-Commerce Rules mention that
    followed it: chat smoke run 3.)"""
    of = OF_LAW_RE.match(text, end) if text else None
    if of:
        nxt = next((m for m in mentions if m.start == of.end()), None)
        if nxt:
            return nxt
    before = [m for m in mentions if m.end <= start]
    if before and start - before[-1].end <= ANCHOR_WINDOW:
        return before[-1]
    after = [m for m in mentions if m.start >= end and m.start - end <= ANCHOR_WINDOW]
    if after:
        return after[0]
    return before[-1] if before else None


def _name_key(raw: str) -> str:
    """'The Karnataka Municipal Corporation Act, 1976' -> 'karnataka municipal corporation act'"""
    s = YEAR_RE.sub("", raw.lower()).replace(",", " ")
    return re.sub(r"\s+", " ", re.sub(r"^the\s+", "", s.strip())).strip()


def _ref_key(ref: dict) -> str:
    return f"Article {ref['section']}" if ref["kind"] == "article" else ref["section"]


BLOCK_START_RE = re.compile(r"\n\s*\n|\n\s*(?:[-*•]|\d+\.)\s")


def _block_at(text: str, pos: int) -> str:
    """The paragraph or list item around `pos`: wrapped lines belong together, a blank line or a new bullet ends it."""
    starts = [m.end() for m in BLOCK_START_RE.finditer(text) if m.end() <= pos]
    start = starts[-1] if starts else 0
    nxt = BLOCK_START_RE.search(text, pos)
    return text[start:nxt.start() if nxt else len(text)]


def check_answer(answer: str, passages: list[dict], registry: dict) -> GuardReport:
    """Every problem with the legal references and [n] citations in `answer`.
    Pass text already put through normalize_text() if you will use remove_problem_sentences() on it."""
    answer = normalize_text(answer)
    passages = [{**p, "title": normalize_text(p.get("title", "")), "text": normalize_text(p.get("text", ""))}
                for p in passages]
    laws = LawIndex(registry)
    report = GuardReport()

    for rx in CASE_LAW_RES:
        for m in rx.finditer(answer):
            report.problems.append(Problem("case_law", m.group(0), "LawBuddy does not cite court cases"))

    # What the passages themselves mention is grounded, even if the registry does not list it.
    passage_text = "\n\n".join(f"{p.get('title', '')}\n{p.get('text', '')}" for p in passages)
    p_mentions, p_refs = find_refs(passage_text, laws)
    grounded_names = {_name_key(m.raw) for m in p_mentions}
    grounded_refs = {(r["doc"], _ref_key(r)) for r in p_refs if r["doc"]}

    mentions, refs = find_refs(answer, laws)
    for m in mentions:
        if m.doc is None:
            if _name_key(m.raw) not in grounded_names:
                report.problems.append(Problem("unknown_law", m.raw, "not in the registry or the passages"))
            continue
        if m.year and laws.doc_year(m.doc) and m.year != laws.doc_year(m.doc):
            report.problems.append(Problem("wrong_year", m.raw, f"the law is from {laws.doc_year(m.doc)}"))
        if m.repealed and not REPLACED_WORDS.search(_block_at(answer, m.start)):
            rep = laws.repealed_titles[m.doc]
            report.problems.append(Problem("repealed_law", m.raw, f"repealed: {rep['authority']}"))

    for r in refs:
        report.refs.append({"kind": r["kind"], "text": r["text"], "doc": r["doc"], "section": r["section"]})
        law, key = r["law"], _ref_key(r)
        if law is None:
            report.problems.append(Problem("unanchored_section", r["text"], "no law named for this reference"))
        elif law.doc is None:
            continue                                        # already reported (or grounded) as a law name
        elif law.repealed:
            report.problems.append(Problem("repealed_law", r["text"], f"a section of {law.raw}, which is repealed"))
        elif key not in [str(s) for s in laws.docs[law.doc].get("sections", [])] and \
                (law.doc, key) not in grounded_refs:
            report.problems.append(Problem("unlisted_section", r["text"],
                                           f"{laws.docs[law.doc]['title']} {key} is not in LawBuddy's sources"))

    cited, invalid, uncited = check_citations(answer, len(passages))
    report.cited, report.uncited_sentences = cited, uncited
    for n in invalid:
        report.problems.append(Problem("invalid_citation", f"[{n}]", f"only {len(passages)} passages were shown"))

    seen, unique = set(), []                                # one entry per (kind, text)
    for p in report.problems:
        if (p.kind, p.text) not in seen:
            seen.add((p.kind, p.text))
            unique.append(p)
    report.problems = unique
    return report


UNVERIFIED_NOTE = ("(Some statements were removed because LawBuddy could not trace them to its legal sources. "
                   "Please confirm the exact law with a lawyer or your District Legal Services Authority.)")


def remove_problem_sentences(answer: str, report: GuardReport) -> str:
    """The answer without any sentence that contains a problem, plus a note saying so. Lines are kept in order."""
    bad = [p.text for p in report.problems]
    lines = []
    for line in answer.splitlines():
        prefix = re.match(r"^\s*(?:[-*•]|\d+\.)?\s*", line).group(0)
        sentences = [s for s in split_sentences(line[len(prefix):]) if s.strip()]
        kept = [s for s in sentences if not any(b in s for b in bad)]
        if kept:
            lines.append(prefix + " ".join(kept))
        elif not sentences or not line.strip():
            lines.append(line)
    return "\n".join(lines).strip() + "\n\n" + UNVERIFIED_NOTE
