# Raw outputs

Unedited outputs of every evaluation run, kept as evidence. What each run showed, and what was changed because of
it, is written up in [docs/findings.md](../docs/findings.md).

| Folder | Produced by | Contents |
|---|---|---|
| `retrieval_smoke/<set>_<mode>.json` | `make smoke` | For the `original` and `paraphrased` question sets and the `keyword`, `dense` and `rerank` modes: every question, the expected articles, the returned articles with scores, which mode answered, timing, and the summary (hit@1, hit@3, by language, score ranges) |
| `chat_smoke/run1/` | `make chat-smoke`, first run (Phase 2) | 5 conversations. Shows the failures fixed afterwards: an empty answer, an invented user fact, a Devanagari reply to Hinglish, a guard false alarm |
| `chat_smoke/run2/` | second run (Phase 2) | The same 5 conversations after the fixes |
| `chat_smoke/run-partial-0102/` | an interrupted run | 3 conversations |
| `chat_smoke/run3/` | third run (Phase 3) | 7 conversations including two legal notices; `drafts/` holds the two notices as saved |
| `eval/groq-run1/`, `eval/groq/` | `make eval` (Phase 6), Groq, before and after the fixes | One JSON per test case (every reply with passages, guard result, trace, usage; the case file; the checks) and `summary.md` / `summary.json`. Both scored with the final `cases.yaml` |
| `eval/comparison.md` | `run_cases --compare groq-run1 groq` | The two runs side by side |
| `api_smoke/run1/`, `run2/` | `make api-smoke` (Phase 5) | Every API response: health, backends, sessions, advice, draft button, download, model swap to Gemini, a rejected key (401), voice in English, Hindi and Kannada. run1 shows Kannada heard as Tamil; run2 the fix |

`chat_smoke/run1/`, `run2/` and `run-partial-0102/` were reconstructed from the turn log (`data/logs/chat.jsonl`)
after the original transcripts were deleted: each `.jsonl` line is the unedited log record of one turn (message,
full reply with trace and guard result, case file). `run3/` holds the original terminal transcripts.

The scripts and questions behind these runs: `eval/retrieval_smoke*.yaml`, `eval/chat_smoke/*.txt`,
`eval/audio/*.wav`.
