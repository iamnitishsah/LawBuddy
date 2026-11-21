# Findings

What the measurements showed, including what did not work. Raw results are in `outputs/`.

## Retrieval (Phase 1, 2026-11-21)

Setup: 32 KB chunks; `make smoke` over two question sets.
- **Original:** 17 in-scope and 4 out-of-scope questions, written by the same author as the KB.
- **Paraphrased:** the same questions reworded as people type them (median 5% word overlap with the original),
  plus 3 in Hindi (Devanagari) and 4 out-of-scope questions close to a covered topic.

Hit@k = an expected chunk is among the top k results. Raw: `outputs/retrieval_smoke/<set>_<mode>.json`.

| Mode | Original hit@1 | Original hit@3 | Paraphrased hit@1 | Paraphrased hit@3 | Hindi hit@3 |
|---|---|---|---|---|---|
| keyword (BM25, no API) | 14/17 | 17/17 | 4/20 | 8/20 | 0/3 |
| dense (embeddings) | 16/17 | 17/17 | 16/20 | 18/20 | 3/3 |
| rerank (dense + cross-encoder) | 16/17 | 17/17 | **19/20** | **20/20** | 3/3 |

**1. Keyword search worked only because the questions reused the KB's wording.** On the original set it looked as
good as the others (17/17 hit@3); on paraphrases it fell to 8/20, and to 0/3 in Hindi (its tokenizer keeps only
a-z and 0-9). The keyword fallback for API outages is therefore weak on real messages unless the message is first
rewritten into an English query in the KB's vocabulary, which Phase 2 adds.

**2. Reranking recovers what dense search misses.** Dense missed two paraphrases ("owner still sitting on the 2L I
gave when moving in" ranked a salary chunk first; "xerox shop ... machines faulty"); reranking ranked both correctly.
Rerank is the default retriever.

**3. Dense and rerank handle Hindi without translation** (3/3 hit@3), so the embedding model is usable for
Hindi input. Hinglish (1 question) also worked. Kannada was not tested.

**4. A similarity threshold cannot decide what is in scope.**

| Rerank top score | Original set | Paraphrased set |
|---|---|---|
| Lowest in-scope question | 0.059 | 0.043 |
| Out-of-scope, unrelated (tax, land, FIR, divorce, bank) | 0.037 - 0.045 | 0.022 - 0.040 |
| Out-of-scope, near a covered topic (eviction, PF, bounced cheque) | n/a | 0.049 - 0.057 |

Near-topic questions score like real ones, and on the original set even unrelated ones score within 0.015 of the
lowest real question. The threshold (`search.min_score`, rerank 0.035, dense 0.28) is kept only as a safety floor
that rejects no real question in either set; it would stop 4 of the 9 paraphrased out-of-scope questions (rerank)
and none of the 4 original ones. Deciding scope is the job of the Phase 2 triage step.

**5. The free embedding API is unreliable.** During the build session the NVIDIA embedding endpoint timed out on
every request for several minutes; in one smoke run 5-6 of 21 searches failed and fell back to keyword search, and
one dense run took 165 s for 21 questions (later runs: 31-39 s, slowest single search 5-12 s). Timeouts were cut to
15 s with 2 retries, and the keyword fallback keeps the product answering during an outage.

Limits of this evaluation: 20 in-scope paraphrases and 9 out-of-scope questions, all written by one person (with
AI help); no Kannada; scores from one run of each mode.

## Conversation, first end-to-end run (Phase 2, 2026-11-21)

Setup: `make chat-smoke`, 5 scripted conversations (11 user turns), Groq `openai/gpt-oss-120b`, rerank retrieval.
Raw transcripts: `outputs/chat_smoke/run1/` (reconstructed from the turn log; see `outputs/README.md`).

**What worked**
- **Traps.** "2-month deposit cap in Karnataka": "there is no legal limit ... a two-month deposit cap is not found
  in the current statutes". "Which Supreme Court judgment says ...": "We do not have reliable information on any
  Supreme Court judgment". "Section 420 IPC": referral reply, no criminal-law content. No untraceable law reached
  a user.
- **Scope and safety.** "hi" got a clarifying question; custody got the fixed referral (DLSA, 15100); "threatened to
  kill me" got the emergency reply from the rule in 0.0 s with no model call.
- **Hindi.** The salary conversation in Devanagari asked only for the missing fact, then gave correct rules in Hindi
  (pay by the 7th; within 2 working days of resigning; 3-year claim; compensation up to 10x).
- **Keyword fallback with query rewriting.** The embedding API failed during the run; keyword search over the
  rewritten English query still returned the right chunks.

**What failed, and the fix**

| # | Failure | Cause | Fix |
|---|---|---|---|
| 1 | An advice reply was empty (only the disclaimer) | gpt-oss spent its whole token budget on hidden reasoning (2,239 output tokens) | `reasoning_effort: low`; budgets 2000; an empty or cut-off reply is retried once with double the budget, and twice empty becomes an error reply, never a blank one |
| 2 | Told the user "you don't have a written rental agreement", which they never said | The prompt showed `"written_agreement": null`; the model read null as "no" | The case is shown as "what the user told us" and "not discussed yet", with no nulls; the prompt forbids saying the user lacks anything not discussed |
| 3 | Hinglish (Latin script) message answered in Devanagari | Analysis labelled it "Hindi" | Analysis must label Hindi in Latin letters "Hinglish"; reply prompts state the script explicitly |
| 4 | Guard flagged "Commerce) Rules"; the regeneration made the turn take 60 s | The model writes "E‑Commerce" with a no-break hyphen, which did not match the registry name | All model text is normalised (hyphens, no-break spaces) before checking and display |
| 5 | Turns took 27-60 s | Reasoning tokens, and every search during the embedding outage waited ~30 s on timeouts | Low reasoning effort; after one API failure, keyword search is used directly for 120 s; no search for messages like "hi" |

**Model mistakes the guard does not catch** (it checks references to law, not every claim):
- "you have up to 21 days for admission": the Act says the *Commission* should decide admission within 21 days.
- "The law does not specify a statutory right to interest on a delayed refund": not stated in any passage. The guard
  logged it as an uncited sentence (a warning, not a block).
- Law names written in Devanagari ("कर्नाटक रेंट एक्ट") are not checked; only "धारा" section references are.

## Conversation, second run after the fixes (Phase 2, 2026-11-21)

Same 5 scripts. Raw transcripts: `outputs/chat_smoke/run2/` (reconstructed from the turn log).

| Check | Run 1 | Run 2 |
|---|---|---|
| Hinglish message answered in Latin script | no (Devanagari) | yes |
| Empty advice replies | 1 of 5 advice turns | 0 of 6 |
| Facts about the user that the user never gave | 1 ("you don't have a written agreement") | 0 |
| Guard regenerations / removals | 1 / 1 (a false alarm on "E-Commerce") | 0 / 0 |
| Untraceable law shown to a user | 0 | 0 |
| Output tokens, deposit turns 2 and 3 | 1,468 and 2,239 | 831 and 961 |
| Deduction question answered from the deductions chunk | no (empty reply) | yes |

Still wrong in run 2 (not caught by the guard):
- Hindi salary advice: "civil suit within three years (according to the Code on Wages)". The three years is right,
  but it comes from the Limitation Act (Art. 7). The law name was written in Devanagari, which the guard does not read.
- "The commission will admit the complaint within 21 days": the Act says it should decide *whether* to admit within
  21 days.
- "There is no passage that records a Supreme Court judgment": internal wording shown to the user (prompt fixed:
  the model must say "my sources").
- Latency varied from 2 s to 32 s per turn; "hi" took 10 s with no retrieval, so Groq free-tier response time
  varies on its own. The trace now splits each turn into LLM time and retrieval time.

## Legal notices, first run (Phase 3, 2026-11-21)

Scripts 06 (deposit, names and address given) and 07 (Flipkart phone, online). Raw transcripts and the two drafts:
`outputs/chat_smoke/run3/` and `run3/drafts/`.

**What worked**
- Both notices: correct layout; legal position only from code (Contract Act ss. 73-74 for the deposit; CPA s. 2,
  E-Commerce rule 6(3) and CPA s. 39 for the online phone); demand with a 15-day deadline; the right forum.
- Names and addresses the user gave filled the header (Asha Rao, Mr. R. Kumar, his address; Flipkart); unknown
  details stayed as placeholders and were listed (the user's address; the order date, which the user never gave).
- The number check passed on both: every amount and date in the facts came from the user.

**What failed, and the fix**

| Failure | Cause | Fix |
|---|---|---|
| "refund the security deposit of 150000" / "refund 24999" | The analysis stored bare digits | Code formats amounts as rupees with Indian grouping ("Rs. 1,50,000") |
| Deposit facts said "returned the premises in good condition" and "thereby fulfilling my obligations"; consumer facts added "promptly" and "replacement" | The model embellished; the number check cannot see invented wording | The facts prompt forbids descriptions, conclusions and requests the user did not give. Not checkable in code: the intro asks the user to check every fact before sending |
| Advice (script 02) regenerated over "Consumer Protection Act, 2019 (s. 2(10))" | The guard tied the section to the nearest law in either direction, an E-Commerce Rules mention after it | Anchoring: "section N of <law>" binds forward; otherwise the nearest law before the section |
| Hindi advice (script 03) regenerated over "कोड ऑन वेजेज, 2019 ... s. 45(6)" | The guard could not read law names in Devanagari | Hindi names for the registered laws added as aliases; Hindi answers are now checked (a "धारा 50" of the Code on Wages is now caught) |

Latency: the turn time is now split. LLM time was 1.6-54 s per turn and retrieval 0-6 s, so the slow turns are
the Groq free tier, not search.

## API and voice, first live run (Phase 5, 2026-11-21)

`make api-smoke` against a local server: 18 calls. Raw responses: `outputs/api_smoke/run1/`.

**What worked**
- Every endpoint answered as designed: health, backends, sessions, a grounded deposit answer (4.9 s), the draft
  button (0.9 s, facts passed the number check), the Markdown download, session state.
- Model swap: the same question on Gemini (`llm.backend = gemini`) gave the correct "no deposit cap" answer.
- A key the provider rejects returned **401** with a clear message and no key in the response.
- Voice in English: transcript exact ("1 lakh 50 thousand rupees ... 31st of October"), grounded answer in 5.1 s.
- Voice in Hindi: transcript slightly misspelt ("तंवाह", "इस तीफा") but understood; correct Hindi advice
  (2 working days after resigning, 3-year claim, up to 10x compensation) in 5.4 s.

**What failed, and the fix**

| Failure | Cause | Fix |
|---|---|---|
| Kannada speech transcribed in **Tamil script**; the analysis then labelled the language Tamil and the advice was written in Tamil | Whisper's language detection confused Kannada with Tamil (synthetic voice). With the hint `kn` the transcript was correct Kannada | When no language is chosen and Whisper reports Tamil, Telugu or Malayalam, the audio is transcribed again as Kannada (`transcription.retry_as_kannada_when_detected`); the step is recorded in the trace. The UI will offer a language choice |
| A Gemini turn took **101 s** (Groq: 4.9 s) | Most likely Gemini's own reasoning | `reasoning_effort: low` for Gemini, as for Groq |
| The Tamil reply contained stray Chinese characters ("欠薪") | Model glitch | Not fixed; recorded. With the Kannada fix this reply would not be produced |

Not yet tested: real (non-synthetic) voices, noisy phone audio, a Kannada conversation beyond one message.

## API and voice, second live run (Phase 5, 2026-11-21)

Raw responses: `outputs/api_smoke/run2/`.
- **Kannada fixed:** the trace shows "Whisper detected Tamil; transcribed again as Kannada"; the transcript was correct
  Kannada and the advice was written in Kannada, citing Code on Wages, 2019, s. 17(1) (pay by the 7th). 5.2 s.
- **Gemini:** accepted `reasoning_effort: low` but still took 73 s (LLM time 71.6 s) against 4.3 s on Groq for the same
  kind of turn; the answer was correct. Groq stays the default; Gemini is usable but slow on the free tier.
- Everything else unchanged and passing: deposit advice 4.3 s, draft 1.4 s, English voice 5.7 s, Hindi voice 8.4 s,
  rejected key 401.
