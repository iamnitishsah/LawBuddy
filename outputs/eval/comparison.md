# Comparison: groq-run1 vs groq

| | groq-run1 | groq |
|---|---|---|
| Model | `openai/gpt-oss-120b` | `openai/gpt-oss-120b` |
| Cases passing every check | 28/31 | 30/31 |
| Cases with untraceable law | 0 | 0 |
| Guard rewrites / removals | 1 / 0 | 0 / 0 |
| Median turn time (s) | 21.32 | 21.6 |
| 90th percentile turn time (s) | 31.95 | 31.61 |
| Tokens per turn (in / out) | 2729 / 651 | 2852 / 651 |
| check: category | 22/22 | 22/22 |
| check: cited | 22/22 | 23/23 |
| check: completed | 31/31 | 31/31 |
| check: draft | 2/2 | 2/2 |
| check: grounded | 22/22 | 23/23 |
| check: kinds | 29/31 | 31/31 |
| check: mention_any | 4/5 | 4/5 |
| check: must_cite | 16/16 | 15/16 |
| check: must_not_mention | 2/2 | 2/2 |
| check: script | 19/20 | 20/20 |
