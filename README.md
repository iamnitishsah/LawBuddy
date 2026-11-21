# LawBuddy

**An AI lawyer that an ordinary person in India can talk to about a legal problem.**

Most people never get legal help for everyday problems: a deposit the landlord won't return, a refund that
never came, salary that stopped. LawBuddy takes the problem by text or voice, in the person's language, turns
it into a case (what happened, when, what proof exists), explains where they stand in plain language, and
prepares what they need to act, such as a legal notice.

**Design principle: the model never supplies law from memory.** Every legal statement must cite a passage from a
small, hand-verified knowledge base, and code checks every Act and section the answer names. When the knowledge
base does not cover a question, or the matter needs a real lawyer, LawBuddy says so.

> Status: **Phase 2** (conversation engine: classification, case intake, grounded advice, legal-reference guard;
> terminal chat). See [docs/ROADMAP.md](docs/ROADMAP.md) for the plan and [docs/SOURCES.md](docs/SOURCES.md) for
> the legal sources.

---

## Running locally

```bash
python -m venv .venv && source .venv/bin/activate
make install                 # pip install -e ".[dev]"
cp .env.example .env         # add at least the key for LLM_BACKEND
make test                    # unit tests, no network
make kb                      # validate the knowledge base (no network)
make kb-build                # re-embed changed KB chunks into kb/index/ (only after editing kb/)
make smoke                   # retrieval smoke test (keyword, dense, rerank)
make chat                    # talk to LawBuddy in the terminal (shows each turn's decisions)
make chat-smoke              # replay the scripted conversations in eval/chat_smoke/
make api                     # http://localhost:8000/health
make frontend                # http://localhost:5173 (first time: cd frontend && npm install)
```

## Switching the model

Every LLM call goes through `lawbuddy.llm.base.get_llm()`. Backends are OpenAI-compatible endpoints listed in
[`configs/llm.yaml`](configs/llm.yaml); pick one with `LLM_BACKEND=<name>` in `.env`. Adding a provider is a
config entry, not a code change. List a provider's models with `python -m lawbuddy.llm.base <backend>`.

## Repository structure

```
configs/            llm.yaml (providers), retrieval.yaml (embedding, rerank, search)
src/lawbuddy/
  llm/              one interface for every LLM provider
  retrieval/        in-memory dense search, reranking, keyword (BM25) fallback
  guard/            citation checks and the legal-reference guard (every law named must be traceable)
  kb/               knowledge-base loading, validation and index build
  conversation/     classification (triage), case file, replies, the turn engine
  chat.py           terminal chat
  drafting/         legal notices and complaints (Phase 3)
  api/              FastAPI service
  evaluation/       test-case runner and scoring (Phase 6)
kb/                 the curated legal knowledge base: <category>/*.md chunks, registry.yaml, index/
eval/               retrieval_smoke.yaml; cases/ for the test cases (Phase 6)
outputs/            raw, unedited outputs of the test cases (Phase 6)
frontend/           React + Vite web client
tests/              unit tests (no network)
docs/               roadmap and notes
```

## Disclaimer

LawBuddy gives legal information, not legal advice, and does not replace a lawyer. For free legal aid, contact
your District Legal Services Authority (DLSA).
