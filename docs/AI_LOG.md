# AI tools log

The solution doc must say which AI tools were used and one place where they got it wrong. Log each case here
as it happens: date, tool, what it produced, what was wrong, how it was caught, what changed.

| Date | Tool | What went wrong | How it was caught | Fix |
|---|---|---|---|---|
| 2026-11-21 | Claude Code | While checking `.env` for leftover variable names, it printed commented-out lines that contained real API keys | Noticed in the command output | Keys to be rotated; only variable names are printed from `.env` from now on |
