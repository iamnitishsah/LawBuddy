"""Tests for picking the LLM backend (no network)."""

import pytest

from lawbuddy.llm.base import get_llm, load_config, resolve_backend


def test_backend_precedence_flag_then_env_then_config(monkeypatch):
    monkeypatch.delenv("LLM_BACKEND", raising=False)
    assert resolve_backend() == (load_config()["default_backend"], "configs/llm.yaml")
    monkeypatch.setenv("LLM_BACKEND", "gemini")
    assert resolve_backend() == ("gemini", "LLM_BACKEND env var")
    assert resolve_backend("nvidia") == ("nvidia", "--backend flag")


def test_every_backend_is_complete():
    for name, b in load_config()["backends"].items():
        assert {"base_url", "api_key_env", "model"} <= set(b), name


def test_unknown_backend_and_missing_key_fail_clearly(monkeypatch):
    with pytest.raises(ValueError, match="Unknown LLM backend"):
        get_llm("no-such-backend")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GROQ_API_KEY is not set"):
        get_llm("groq")
