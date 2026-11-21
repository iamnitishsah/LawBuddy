# LawBuddy

**An AI lawyer that an ordinary person in India can talk to about a legal problem.**

Most people never get legal help for everyday problems: a deposit the landlord won't return, a refund that
never came, salary that stopped. LawBuddy takes the problem by text or voice, in the person's language, turns
it into a case (what happened, when, what proof exists), explains where they stand in plain language, and
prepares what they need to act, such as a legal notice.

**Design principle: the model never supplies law from memory.** Every legal statement must cite a passage from a
small, hand-verified knowledge base, and code checks every Act and section the answer names. When the knowledge
base does not cover a question, or the matter needs a real lawyer, LawBuddy says so.

> Status: **Phase 5** (HTTP API with voice, model swapping and user API keys; conversation engine with grounded
> advice and a legal-reference guard; legal-notice drafts; terminal chat). Web UI next. See [docs/ROADMAP.md](docs/ROADMAP.md) for the plan and [docs/SOURCES.md](docs/SOURCES.md) for
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

## API

`make api` starts the FastAPI service; interactive docs at http://localhost:8000/docs.

| Endpoint | What it does |
|---|---|
| `GET /health`, `GET /backends` | status; the models a client can switch between, and which have a server key |
| `POST /sessions`, `GET` / `DELETE /sessions/{id}` | a conversation: messages, case file, drafts |
| `POST /sessions/{id}/messages` | one turn: reply, kind, sources, case file, guard result, decision trace, usage |
| `POST /sessions/{id}/voice` | one turn from an audio file (Whisper), in any language Whisper hears |
| `POST /sessions/{id}/draft`, `GET /sessions/{id}/drafts/{n}` | draft the legal notice now; download it as Markdown |
| `POST /transcribe` | audio to text only |

**Model swapping:** each request may choose `{"llm": {"backend": "gemini", "model": "..."}}` (form fields for voice).
**Your own key:** the header `X-LLM-API-Key` replaces the server's key for that provider, for that request only; keys
are never stored, logged or returned. Backend `custom` (any https OpenAI-compatible endpoint) is off unless
`ALLOW_CUSTOM_LLM_BASE_URL=1`. Search always uses the server's NVIDIA key.

`make api-smoke` (with the server running) calls every endpoint, switches model, tries a bad key and sends the test
recordings in `eval/audio/` (English, Hindi, Kannada); raw responses go to `outputs/api_smoke/`.

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
  voice/            speech to text (Whisper through an OpenAI-compatible API)
  drafting/         legal notices: legal parts written in code, facts by the model, checked
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
