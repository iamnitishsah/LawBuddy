"""HTTP API for LawBuddy.

    uvicorn lawbuddy.api.main:app --reload                 # local: http://localhost:8000/docs
    uvicorn lawbuddy.api.main:app --host 0.0.0.0 --port 8000

Endpoints:
    GET  /health      is the process up, and which LLM backend and model are configured
    (chat, transcription and drafting endpoints arrive in Phase 5)

Settings come from the environment (.env):
    LAWBUDDY_API_KEY     if set, protected endpoints require the header  X-API-Key: <value>
    CORS_ORIGINS         comma-separated origins allowed to call the API from a browser
    RATE_LIMIT_PER_MIN   requests per minute per client IP on protected endpoints (default 20; 0 disables)
"""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

log = logging.getLogger("lawbuddy.api")


class RateLimiter:
    """At most `per_minute` calls per key in any 60-second window (in memory, one process)."""

    def __init__(self, per_minute: int):
        self.per_minute, self.calls = per_minute, defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        if self.per_minute <= 0:
            return True
        now = time.monotonic() if now is None else now
        q = self.calls[key]
        while q and now - q[0] >= 60:
            q.popleft()
        if len(q) >= self.per_minute:
            return False
        q.append(now)
        return True


def access_guard(limiter: RateLimiter):
    """FastAPI dependency for protected endpoints: API key (when configured) and rate limit."""

    def guard(request: Request, x_api_key: str | None = Header(default=None)) -> None:
        expected = os.getenv("LAWBUDDY_API_KEY")
        if expected and x_api_key != expected:
            raise HTTPException(status_code=401, detail="missing or wrong X-API-Key header")
        client = request.client.host if request.client else "unknown"
        if not limiter.allow(client):
            raise HTTPException(status_code=429, detail="too many requests; try again in a minute")

    return guard


def create_app() -> FastAPI:
    from dotenv import load_dotenv

    from lawbuddy.llm.base import ROOT, load_config, resolve_backend

    load_dotenv(ROOT / ".env")
    app = FastAPI(title="LawBuddy", version="0.1.0",
                  description="An AI lawyer that an ordinary person in India can talk to about a legal problem.")
    origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
               if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"], allow_headers=["*"])
    app.state.guard = access_guard(RateLimiter(int(os.getenv("RATE_LIMIT_PER_MIN", "20"))))

    @app.get("/health")
    def health() -> dict:
        backend, _ = resolve_backend()
        model = load_config()["backends"].get(backend, {}).get("model")
        return {"status": "ok", "backend": backend, "llm": model}

    return app


app = create_app()
