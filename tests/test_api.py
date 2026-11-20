"""Tests for the HTTP API (no services, no network)."""

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from lawbuddy.api.main import RateLimiter, create_app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.delenv("LAWBUDDY_API_KEY", raising=False)
    monkeypatch.setenv("RATE_LIMIT_PER_MIN", "0")
    monkeypatch.setenv("LLM_BACKEND", "groq")
    app = create_app()

    @app.post("/protected", dependencies=[Depends(app.state.guard)])
    def protected() -> dict:                    # stands in for the chat endpoints until Phase 5
        return {"ok": True}

    with TestClient(app) as c:
        yield c


def test_health_reports_the_configured_backend(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["backend"] == "groq" and body["llm"]


def test_api_key_is_required_when_configured(client, monkeypatch):
    assert client.post("/protected").status_code == 200                 # no key configured: open
    monkeypatch.setenv("LAWBUDDY_API_KEY", "secret")
    assert client.post("/protected").status_code == 401
    assert client.post("/protected", headers={"X-API-Key": "secret"}).status_code == 200
    assert client.get("/health").status_code == 200                     # health needs no key


def test_rate_limiter_window():
    lim = RateLimiter(2)
    assert lim.allow("a", 0) and lim.allow("a", 1) and not lim.allow("a", 2)
    assert lim.allow("b", 2)                                              # another client is unaffected
    assert lim.allow("a", 61)                                             # the first call has left the window
    assert RateLimiter(0).allow("a", 0)
