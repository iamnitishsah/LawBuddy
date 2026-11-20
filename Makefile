.DEFAULT_GOAL := help

.PHONY: help install test api frontend docker-build docker-run

help:
	@echo "make install       install the package and dev tools into the active environment"
	@echo "make test          unit tests (no network)"
	@echo "make api           run the FastAPI backend on http://localhost:8000"
	@echo "make frontend      run the Vite React frontend on http://localhost:5173"
	@echo "make docker-build  build the API image"
	@echo "make docker-run    run the API image on port 8000 with .env"

install:
	pip install -e ".[dev]"

test:
	pytest -q

api:
	uvicorn lawbuddy.api.main:app --reload

frontend:
	cd frontend && npm run dev

docker-build:
	docker build -t lawbuddy-api .

docker-run:
	docker run --rm -p 8000:8000 --env-file .env lawbuddy-api
