.DEFAULT_GOAL := help

.PHONY: help install test kb kb-build smoke chat chat-smoke api api-smoke frontend docker-build docker-run

help:
	@echo "make install       install the package and dev tools into the active environment"
	@echo "make test          unit tests (no network)"
	@echo "make kb            validate the knowledge base against kb/registry.yaml (no network)"
	@echo "make kb-build      embed new or changed KB chunks into kb/index/ (embedding API)"
	@echo "make smoke         retrieval smoke test: keyword, dense and rerank (API for dense and rerank)"
	@echo "make chat          talk to LawBuddy in the terminal, with the decision trace (LLM + retrieval APIs)"
	@echo "make chat-smoke    replay eval/chat_smoke/*.txt; raw transcripts to outputs/chat_smoke/ (APIs)"
	@echo "make api           run the FastAPI backend on http://localhost:8000 (docs at /docs)"
	@echo "make api-smoke     call every endpoint of a running API (APIs); raw responses to outputs/api_smoke/"
	@echo "make frontend      run the Vite React frontend on http://localhost:5173"
	@echo "make docker-build  build the API image"
	@echo "make docker-run    run the API image on port 8000 with .env"

install:
	pip install -e ".[dev]"

test:
	pytest -q

kb:
	python -m lawbuddy.kb.loader

kb-build:
	python -m lawbuddy.kb.build

smoke:
	python -m lawbuddy.evaluation.retrieval_smoke

chat:
	python -m lawbuddy.chat --debug

chat-smoke:
	mkdir -p outputs/chat_smoke
	for f in eval/chat_smoke/*.txt; do \
		python -m lawbuddy.chat --debug --script $$f | tee outputs/chat_smoke/$$(basename $$f); \
	done

api:
	uvicorn lawbuddy.api.main:app --reload

api-smoke:
	python -m lawbuddy.evaluation.api_smoke

frontend:
	cd frontend && npm run dev

docker-build:
	docker build -t lawbuddy-api .

docker-run:
	docker run --rm -p 8000:8000 --env-file .env lawbuddy-api
