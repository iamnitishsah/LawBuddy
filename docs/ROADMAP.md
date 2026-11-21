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

## Phase 1: Legal knowledge base ✅

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
- [x] **Human check:** every chunk read against its source; `verified_on: 2026-11-21` set with `python -m lawbuddy.kb.verify --all`
- [x] Retrieval smoke sets: `eval/retrieval_smoke.yaml` (17 in scope, 4 out) and `eval/retrieval_smoke_paraphrased.yaml` (same ids reworded as people type them, + 3 Hindi, + 4 near-scope out-of-scope); a test enforces ≤ 30% word overlap with the original
- [x] `make smoke` on both sets ([findings.md](findings.md)): rerank hit@3 20/20 on paraphrases (Hindi 3/3), keyword 8/20; `search.min_score` set as a safety floor (rerank 0.035, dense 0.28), since near-topic out-of-scope questions score like real ones and scope must be decided by triage

**Result:** 32 chunks (deposit 10, consumer 10, salary 6, general 6; 18 guides, 9 statute extracts, 5 practice
notes), ~5,800 words, every legal chunk linked to a registered source. Fewer chunks than the 60–120 first planned:
each chunk covers one question fully, and more can be added where the Phase 6 test cases show gaps.

## Phase 2: Conversation engine ✅

**Goal:** a multi-turn CLI chat that understands the case, asks for what's missing and advises using only the KB.

- [x] LLM layer: `chat(messages)` with history; `chat_json()` parses the reply and retries once if it is not JSON; model switching stays a config change
- [x] Pipeline (`conversation/engine.py`, plain functions instead of LangGraph: five steps, each testable alone): emergency rule → analysis → follow-up decision → rerank retrieval → advice + guard
- [x] Classification in three layers: (1) emergency rules in code (English, Hinglish, Hindi; no API); (2) one LLM analysis call returning category, emergency, intent, language and facts as JSON; (3) rerank as the evidence check: in-scope advice only if a chunk clears the score floor, and for unclear messages a whole-KB rerank search suggests the topic to confirm
- [x] Fixed replies written in code (English and Hindi): emergency helplines, out-of-scope referral (DLSA, NALSA 15100), "not in my sources"
- [x] `CaseFile` (`conversation/case.py`): facts per category, timeline, evidence held and missing, other party, goal, state; code decides which critical facts are missing; at most 2 follow-up turns, 3 questions each; general questions are answered without follow-ups
- [x] Query rewriting: the analysis returns an English search query in legal terms
- [x] Advice: retrieval within {category, general}; answer only from the passages with `[n]` citations; sections "Where you stand / What you can do / Next step"; reply in the user's language (no separate localize call); note when the state is not Karnataka; disclaimer
- [x] Guard (`guard/legal_refs.py`): every law, section, article and rule is traced to the registry or the passages shown; case law, unknown laws, wrong years, repealed laws used as current, unlisted or unanchored sections and invalid citations are caught; regenerate once with the problems named, then remove the offending sentences and add a note
- [x] CLI `python -m lawbuddy.chat` (interactive or `--script`, `--debug` trace); every turn logged to `data/logs/chat.jsonl`
- [x] Offline tests: 106, with a scripted fake model (every branch of a turn, guard regeneration and removal, API failure)
- [x] `make chat-smoke`, two runs reviewed ([findings.md](findings.md)): run 1 exposed 5 failures (empty reply, an invented user fact, wrong script for Hinglish, a guard false alarm, 27-60 s turns); all fixed with regression tests; run 2 clean on traps, scope and safety; raw transcripts in `outputs/chat_smoke/run1/` and `run2/` (reconstructed from the turn log after the originals were deleted)

**Done when:** the Hinglish deposit script ends in grounded advice, and the 420 / judgment / deposit-cap traps produce no untraceable law.

## Phase 3: Documents ✅

- [x] Legal notice for all three problem types (`drafting/notice.py`): layout, legal basis, demand (15-day deadline) and consequence written in code; the model writes only the facts, as JSON paragraphs that code numbers
- [x] Legal basis chosen per case (salary: s. 17(2) if the user left, s. 17(1) if still employed, both if unknown, plus s. 45; consumer: e-commerce rule 6(3) only for online purchases); every legal sentence is tested against the KB chunks it names with the guard
- [x] Facts checked in code: no law at all, and every number must appear in what the user said ("2 lakh" = "Rs. 2,00,000"); regenerated once with the problems named, then law is removed and unsupported numbers are listed as warnings
- [x] Unknown details become visible `[● fill: ...]` placeholders, listed to the user; the salary total is never computed (placeholder)
- [x] Triggered by asking ("draft the notice", "notice bana do": analysis intent `draft`); every advice reply offers it; intro in the user's language (English / Hindi / Hinglish offer), notice in English; CLI saves to `data/drafts/`
- [x] `make chat-smoke` run 3 (scripts 06 and 07) reviewed ([findings.md](findings.md)): both notices correct in structure, law and numbers; fixed: unformatted amounts, embellished facts (prompt), two guard false alarms (anchoring direction; Hindi law names added to the registry)
- [ ] Optional: consumer-complaint draft (e-Jagriti structure); .docx / PDF export (Phase 5 download)

**Done when:** each test case produces a draft with zero invented facts, and the guard passes.

## Phase 4: Practice mode (skipped)

Skipped to keep within the time budget; the prototype link (Phase 5) is a required deliverable and practice mode is not.

## Phase 5: API and frontend ✅

- [x] FastAPI service with Pydantic models (`api/main.py`, `api/schemas.py`): health, backends, sessions, messages, voice, draft button, draft download, transcription
- [x] Model swapping per session or per message (`backend`, `model`); backend `custom` for any https OpenAI-compatible endpoint, off unless `ALLOW_CUSTOM_LLM_BASE_URL=1`
- [x] User's own LLM key in `X-LLM-API-Key`, replacing the server key for that request; never stored, logged or returned (error text redacted); a key the provider rejects is a 401. Retrieval keeps the server's NVIDIA key
- [x] Voice: Whisper (`whisper-large-v3-turbo` on Groq) via the OpenAI-compatible audio API; type and size checked before any call; test recordings in English, Hindi and Kannada (`eval/audio/`, made with macOS `say`)
- [x] In-memory sessions with idle expiry and a cap; one turn at a time per conversation; per-thread retrieval mode so concurrent turns cannot mix score scales; rate limit and optional server key kept
- [x] 177 offline tests (API with fake model, retriever and transcriber); `make api-smoke` for the live check
- [x] `make api-smoke` runs 1-2 reviewed ([findings.md](findings.md)): all endpoints, model swap and 401 on a bad key work; Kannada voice was heard as Tamil (fixed: re-transcribe as Kannada); Gemini 101 s (low reasoning effort)
- [x] UI (React + Vite + Tailwind): chat with mic (MediaRecorder; webm/mp4/ogg) and a voice-language picker (Auto/EN/HI/KN) · reply cards by kind (emergency, referral, not found, error, draft) · clickable [n] citations · "Why this answer?" (steps, search, guard, timings) · side panel: case file, sources with official links, notice viewer with blanks highlighted, download and copy · Settings: model picker from /backends, model name, own API key (memory only), server access key · safe Markdown renderer (React elements only)
- [x] UI checked in a browser by the user
- [x] Pages: Overview, How it works, Evaluation (from findings.md; Phase 6 adds the full test-case results)

## Phase 6: Test cases, evaluation, raw outputs ✅

- [x] `eval/cases/cases.yaml`: 31 cases, ~45 turns, written fresh: deposit 6, consumer 6, salary 5 (each in English plus Hinglish, Hindi and Kannada variants), traps 5 (deposit cap, 420 IPC, fake judgment, repealed law, prompt injection), scope 5 (divorce, eviction, cheque bounce, PF, unclear), safety 2 (threat and despair the emergency rules do not match), drafts 2
- [x] Automatic checks in code (`evaluation/checks.py`): completed, reply kinds per turn, category, **grounded** (every legal reference in advice and notices re-checked independently of the guard), citations, expected article cited, reply script (Latin / Devanagari / Kannada), required and forbidden phrases, notices without invented numbers
- [x] Runner (`evaluation/run_cases.py`): fresh conversation per case through the same engine as the API; raw results per case to `outputs/eval/<run>/`; `summary.md` / `summary.json` (pass rates per check and group, guard interventions, fallbacks, latency, tokens, failures, every case with its reply); rerun after a rate limit; `--rescore` (no API) and `--compare`
- [x] Offline tests for the case file, the checks and every fix (209 in total)
- [x] `make eval` on Groq, twice: run 1 28/31, run 2 (after fixes) 30/31; untraceable law in 0 cases both times ([findings.md](findings.md)); `outputs/eval/comparison.md`
- [ ] `make eval-gemini` + `make eval-compare` (postponed: Gemini is 73-101 s per turn on the free tier)
- [x] Failures and a sample of replies reviewed by hand: 3 bugs fixed in code (repeat follow-ups, language by script) and prompts (PF, exceptions, search query keeps outcome-changing facts), 1 wrong expectation corrected, limits recorded
- [ ] Optional: re-run con-05 to confirm the search-query fix (`python -m lawbuddy.evaluation.run_cases --cases con-05-commercial-buyer`)

## Phase 7: Deployment

- [x] Frontend on Vercel; `/api/*` rewritten to the API, so the browser talks only to the Vercel origin
- [x] API on AWS EC2 (t3.micro) with Docker Compose; image built by GitHub Actions and pulled from GHCR
- [x] CI/CD (`.github/workflows/ci-cd.yml`): tests and frontend build on every push and PR; on `main`: image to GHCR, SSH deploy, health check with automatic rollback, public health check
- [x] Secrets stay on the server (`/opt/lawbuddy/lawbuddy.env`); GitHub holds only the deploy SSH key
- [x] Real client IP through `X-Forwarded-For` (uvicorn `--proxy-headers`), so the rate limit is per user
- [x] Cost and scale: [ARCHITECTURE.md](ARCHITECTURE.md#10-scale-and-cost); runbook: [DEPLOYMENT.md](DEPLOYMENT.md)
- [ ] One-time setup (Elastic IP, security group, `setup-ec2.sh`, GitHub secrets, Vercel `VITE_API_BASE_URL=/api`) and the first deploy

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
