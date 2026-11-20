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
| Jurisdiction | All-India central law; tenancy is state law, so ask the user's state and flag the difference |
| Grounding rule | Only law present in the curated knowledge base may be cited; no case law ever; code checks every legal reference |

---

## Phase 0: Clean slate and LawBuddy skeleton ✅

- [x] Delete the parts specific to the previous project: ingestion, parsing, SQL analyst, MySQL/Qdrant storage, research graph, evals, data, docs, notebooks, scripts
- [x] Rename the package to `lawbuddy`; keep `llm/` (swappable backends), `retrieval/` embedder + reranker, `guard/citations.py`, API shell (health, auth, rate limit)
- [x] Add empty `kb/`, `conversation/`, `drafting/`, `evaluation/` packages; `kb/`, `eval/cases/`, `outputs/` folders
- [x] Trim dependencies; new `.env.example`, Makefile, Dockerfile, README
- [x] Frontend rebranded; hard-coded server IP and default API key removed
- [x] Checks: `pytest` (15 pass), `/health` serves, `npm run build` + lint pass, no traces of the old project

## Phase 1: Legal knowledge base

**Goal:** a small, hand-checked law base. Every fact in it has a source; nothing outside it can be cited.

- [ ] Download the official sources (bare acts from India Code, portal FAQs) into `data/sources/` (see *Sources* below)
- [ ] `kb/<category>/*.md` with frontmatter `id, title, category, applies_to (central | state), source_url, source_ref (Act + section / page), verified_on`
- [ ] Per category: which law applies · rights · first steps (written demand → legal notice) · which forum and its money limits · time limits · fees · documents needed · online portals and helplines · when you need a lawyer
- [ ] Cross-cutting: free legal aid (who qualifies, DLSA), Lok Adalat, legal notice basics, repealed-law trap list (IPC → BNS, CrPC → BNSS, Evidence Act → BSA, CPA 1986 → 2019, Payment of Wages Act → Code on Wages)
- [ ] Statute chunks: the exact text of the few sections the guides rely on, extracted from the bare acts, so answers can quote them
- [ ] `kb/registry.yaml`: the only Acts and sections the bot may name (used by the guard)
- [ ] **Human check:** every chunk verified against its official source and dated (`verified_on`)
- [ ] `python -m lawbuddy.kb.build`: chunk, embed and save the index to `data/kb_index.npz`; in-memory search with a category filter, then reranking
- [ ] Calibrate `min_score` on a few in-scope and out-of-scope questions

**Done when:** about 60–120 chunks, 100% with a source, the index builds, and smoke queries return the right chunks.

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

Official sources go in `data/sources/` (gitignored). KB chunks cite them by URL and section.

| Source | Use | Status |
|---|---|---|
| Constitution of India (Legislative Dept., as on 10 Sep 2026) | Art. 39A (free legal aid) and a few cross-cutting rights; **not indexed in bulk** | ✅ have |
| Consumer Protection Act, 2019 | Consumer rights, complaints, Commissions | ⬜ |
| CP (Jurisdiction of District, State and National Commissions) Rules, 2021 | Money limits per forum | ⬜ |
| CP (E-Commerce) Rules, 2020 | Online purchase refunds, seller duties | ⬜ |
| e-Jagriti / National Consumer Helpline (1915) guides | Filing steps, fees, helpline | ⬜ |
| Code on Wages, 2019 (+ Industrial Relations Code for dues/disputes) | Wage payment deadlines, claims authority | ⬜ verify commencement and state rules |
| Model Tenancy Act, 2021 + rent law of 1–2 target states | Deposit caps, refund on vacating, Rent Authority | ⬜ pick states |
| Indian Contract Act, 1872 | Breach of agreement, compensation (deposit refund as a contract claim) | ⬜ |
| Limitation Act, 1963 | Time limits for civil money claims | ⬜ |
| Code of Civil Procedure, 1908 (Order XXXVII) | Summary suits for money recovery | ⬜ optional |
| Legal Services Authorities Act, 1987 (s. 12) + NALSA/DLSA pages | Who gets free legal aid, how to apply; Lok Adalat | ⬜ |
| BNS / BNSS / BSA, 2023 (titles only) | Repealed-law trap list, so the bot never cites IPC/CrPC as current | ⬜ |
