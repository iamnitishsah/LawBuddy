# LawBuddy roadmap

Kuku AI Generalist Assignment, Problem 2: *Build an AI lawyer that an ordinary person in India can talk to about
a legal problem.* Built phase by phase; each phase ends with a check that it works.

**Must-have:** 0 → 1 → 2 → 3 (legal notice) → 5 (chat + voice) → 6 → 7 → 8
**Optional, cut first:** consumer-complaint draft, practice mode (4), PDF/.docx export, LLM judge

---

## Scope decisions (assumptions to state in the doc)

| Decision | Choice |
|---|---|
| Problem types (depth over breadth) | 1. Security deposit not returned · 2. Consumer refund/defect (e-commerce, services) · 3. Unpaid salary/dues |
| Out of scope → referred to a lawyer / DLSA | Criminal matters, family/divorce, property title, police/FIR, anything already in court with a deadline, large amounts above the set limit |
| Emergencies → helplines first | Violence, threats, arrest, self-harm |
| Languages | English, Hindi, Hinglish (tested); others best effort, untested, and said so |
| Voice | Speech-to-text via Groq Whisper (free tier) |
| Jurisdiction | **Karnataka only** (central law + Karnataka state law). Users elsewhere are told the state-specific parts may not apply |
| Grounding rule | Only law present in the curated knowledge base may be cited; no case law ever; code checks every legal reference |

---

## Phase 0: Clean slate and LawBuddy skeleton ✅

- [x] Delete the parts specific to the previous project: ingestion, parsing, SQL analyst, MySQL/Qdrant storage, research graph, evals, data, docs, notebooks, scripts
- [x] Rename the package to `lawbuddy`; keep `llm/` (swappable backends), `retrieval/` embedder + reranker, `guard/citations.py`, API shell (health, auth, rate limit)
- [x] Add empty `kb/`, `conversation/`, `drafting/`, `evaluation/` packages; `kb/`, `eval/cases/`, `outputs/` folders
- [x] Trim dependencies; new `.env.example`, Makefile, Dockerfile, README
- [x] Frontend rebranded; hard-coded server IP and default API key removed
- [x] Checks: `pytest` (15 pass), `/health` serves, `npm run build` + lint pass, no traces of the old project

## Phase 1: Legal knowledge base (built; human check and threshold pending)

**Goal:** a small, hand-checked law base. Every fact in it has a source; nothing outside it can be cited.

- [x] Official sources in `data/sources/` (10 PDFs, see [SOURCES.md](SOURCES.md)); text extracted to `data/text/`
- [x] `kb/<category>/*.md`, one chunk per file, frontmatter `id, title, category, kind (guide | statute | practice), jurisdiction, cites [{doc, section}], verified_on`
- [x] Per category (deposit, consumer, salary): which law applies, rights, steps, forum and money limits, time limits, evidence, portals and helplines
- [x] Cross-cutting (general): free legal aid, Lok Adalat, legal notice, when to get a lawyer / out of scope, replaced laws
- [x] Statute chunks: verbatim text of the sections the guides rely on (9 chunks)
- [x] `kb/registry.yaml`: the only laws and sections that may be named, plus repealed laws and what replaced them
- [x] `python -m lawbuddy.kb.loader` validates the KB against the registry (unknown law, unlisted section, repealed law, wrong folder, too long)
- [x] `python -m lawbuddy.kb.build`: embeds only new or changed chunks into `kb/index/` (committed, ~130 KB); in-memory dense search with category/kind filters, then reranking
- [x] Keyword (BM25) fallback when the embedding or rerank API fails (the NVIDIA endpoint timed out during the build session)
- [ ] **Human check:** read every chunk against its source and set `verified_on` (32 chunks, 0 verified)
- [ ] Run `make smoke` and set `search.min_score` from the in-scope / out-of-scope score ranges

**Result:** 32 chunks (deposit 10, consumer 10, salary 6, general 6; 18 guides, 9 statute extracts, 5 practice
notes), ~5,800 words, every legal chunk linked to a registered source. Fewer chunks than the 60–120 first planned:
each chunk covers one question fully, and more can be added where the Phase 6 test cases show gaps.

## Phase 2: Conversation engine

**Goal:** a multi-turn CLI chat that understands the case, asks for what's missing and advises using only the KB.

- [ ] LLM layer: `chat(messages)` with history and a JSON mode; model switching stays a config change
- [ ] Graph: `message → triage → intake → (follow-up | advise) → guard → localize → reply`; triage can branch to escalate
- [ ] `triage`: rules in code first (emergency, criminal, out of scope), then an LLM classifier (category, urgency)
- [ ] `intake`: structured `CaseFile` (parties, timeline of dated events, amounts, state, evidence held vs missing, desired outcome, language); at most 2–3 targeted follow-up questions, only when key facts are missing
- [ ] `advise`: retrieval within the category → plain-language answer with `[n]` citations: where they stand, options ranked by cost and effort, deadlines, next step
- [ ] `guard`: every Act/Section/Article named must be in a cited passage or the registry; case-law patterns ("X v. Y", AIR, SCC) are blocked; invalid citations flagged; on failure regenerate once, then remove the claim and add "verify with a lawyer"
- [ ] `localize`: reply in the user's language, citations intact
- [ ] In-memory session store keyed by `session_id`; run log in `data/logs/`

**Done when:** `python -m lawbuddy.chat` handles a messy Hinglish deposit story end to end, and the guard catches a planted fake section.

## Phase 3: Documents

- [ ] Legal-notice templates in code (deposit, salary); the LLM writes only the facts narrative from the `CaseFile`; law references inserted from the KB
- [ ] Unknown facts become `[● fill: ...]` placeholders, never invented; code counts and lists them
- [ ] Optional: consumer-complaint draft (e-Jagriti structure); PDF/.docx export
- [ ] The notice is in English; the explanation is in the user's language

**Done when:** each test case produces a draft with zero invented facts, and the guard passes.

## Phase 4: Practice mode (optional)

- [ ] The bot plays the landlord, employer or customer care with realistic pushback; afterwards, three tips grounded in the KB

## Phase 5: API and frontend

- [ ] API: `POST /session`, `POST /chat`, `POST /transcribe` (Whisper), `POST /draft`, `GET /case/{id}`, `GET /health`
- [ ] UI: chat with mic and language indicator · case panel (timeline, evidence checklist, missing items) · sources panel (cited KB chunks, official links) · draft viewer with copy/download · escalation card (real lawyer / DLSA) · disclaimer
- [ ] Pages: Overview, How it works (architecture, anti-hallucination), Evaluation (Phase 6 results)

**Done when:** the full flow works in a browser, including voice.

## Phase 6: Test cases, evaluation, raw outputs

- [ ] `eval/cases/*.yaml` (about 25–30 cases), each with expected category, escalation, required facts and forbidden content:
  messy stories per category in EN/HI/Hinglish · vague stories (follow-ups expected) · traps ("cite the Supreme Court
  judgment", "what does IPC 420 say", insisting on a fake section, prompt injection) · out of scope (divorce, FIR) · emergencies
- [ ] Automatic checks in code: category accuracy, escalation correctness, **legal references all grounded (hallucination rate)**, valid citations, reply language, follow-ups when needed, draft placeholders vs invented facts
- [ ] Optional LLM judge for plain language and usefulness; manual review of a sample
- [ ] Run on two providers (Groq and Gemini) to show model switching and compare
- [ ] `outputs/<backend>/<case>.md` + `.jsonl`: raw, unedited; failures written up honestly in `docs/findings.md`

## Phase 7: Deployment

- [ ] Backend on Hugging Face Spaces (Docker) or Render free tier; the KB index ships with the image
- [ ] Frontend on Vercel; API URL from an environment variable; secrets only in platform settings
- [ ] Cost model: tokens per conversation × provider price → cost at 10k and 1M conversations

## Phase 8: Submission

- [ ] 2-page PDF: problem chosen and why, assumptions, how it works (AI vs code vs human), how it avoids hallucination, scale and cost, quality numbers, where it fails, AI tools used and one place they got it wrong (from `docs/AI_LOG.md`)
- [ ] README with run steps and a "run on a new input" command for the interview
- [ ] `outputs/` folder; optional 3-minute video script

---

## Sources

Tracked in [SOURCES.md](SOURCES.md): every official text, where it came from, when, and its checksum. Scope is
central law plus Karnataka: Consumer Protection Act 2019 and its rules, Code on Wages 2019, Karnataka Rent Act 1999
(+ 2025 amendment), Indian Contract Act 1872, Limitation Act 1963, Legal Services Authorities Act 1987, and the
Constitution (Art. 39A only, not indexed in bulk).
