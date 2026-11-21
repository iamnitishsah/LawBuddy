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
