# AI tools log

The solution doc must say which AI tools were used and one place where they got it wrong. Log each case here
as it happens: date, tool, what it produced, what was wrong, how it was caught, what changed.

| Date | Tool | What went wrong | How it was caught | Fix |
|---|---|---|---|---|
| 2026-11-21 | Claude Code | While checking `.env` for leftover variable names, it printed commented-out lines that contained real API keys | Noticed in the command output | Keys to be rotated; only variable names are printed from `.env` from now on |
| 2026-11-21 | Web search (via Claude Code) | A search result (a property blog) stated that the Karnataka Rent (Amendment) Act, 2025 caps security deposits at 2 months' rent | Read the Rent Act and the amendment text: no deposit limit exists; the amendment only changes offences and penalties | KB chunk `deposit-no-cap` states the correct position; the claim is a test case |
| 2026-11-21 | Claude Code | While drafting KB chunks it added facts not found in any downloaded source: that the Model Tenancy Act has a 2-month cap, and that wage claims in Karnataka are heard "through the Labour Department" | Self-review of each chunk against the source texts before indexing | Sentences removed or reworded to what the sources support ("ask the Labour Department which officer hears claims") |
| 2026-11-21 | Claude Code | Wrote KB titles containing a colon without quotes, which is invalid YAML; the loader crashed | The KB validator failed on load | Titles quoted; the loader now names the file in the error |
| 2026-11-21 | Claude Code | A keyword-search test assumed salary articles mention "deposit"; they do not, so the test failed | Test run | Test corrected to search for "wages" and to assert the category filter returns nothing for "deposit" |
| 2026-11-21 | gpt-oss-120b (LawBuddy's own model, via Groq) | Told a user they had no written rental agreement, which the user never said | Reading the chat smoke transcript | The case file is shown to the model as "what the user told us" / "not discussed yet", with no nulls |
| 2026-11-21 | gpt-oss-120b | Returned an empty answer after spending its token budget on hidden reasoning | Chat smoke transcript (advice was only the disclaimer) | Low reasoning effort; empty or cut-off replies retried with a bigger budget |
| 2026-11-21 | Claude Code | Wrote the engine to pass the model's text straight through, with no check for an empty reply, and showed unknown facts as `null` in the prompt | The first real run exposed both | Fixes above, with regression tests named after the smoke run |
| 2026-11-21 | gpt-oss-120b | Told a xerox-shop owner "you are not a consumer", leaving out the self-employment exception in the Consumer Protection Act, s. 2(7); also pointed to "the Sale of Goods law", which is in none of LawBuddy's sources | Reading eval replies by hand (every automatic check had passed) | Prompt: include exceptions; the case now measures it; the guard's blind spot for names not ending in "Act" is recorded |
| 2026-11-21 | gpt-oss-120b | Rewrote "printers for my xerox shop" as the search query "faulty printers purchased in October", dropping the fact that decides the answer; the reply then said "you are a consumer" | Eval run 2 (expected article not cited) | Prompt: the search query must keep every fact that could change the legal answer |
| 2026-11-21 | Claude Code | Wrote a test-case expectation (con-04) that a reply must be advice, when asking for the business's name is the better behaviour | Reviewing the eval failure | Expectation corrected; both runs re-scored with the same case file |

