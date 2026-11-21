"""Tests for picking the LLM backend (no network)."""

import pytest

from lawbuddy.llm.base import (LLMResponse, MissingKey, chat_json, get_llm, load_config, parse_json,
                                resolve_backend)


def test_parse_json_tolerates_fences_and_surrounding_text():
    assert parse_json('Here you go:\n```json\n{"a": 1, "b": {"c": [2]}}\n```\nDone.') == {"a": 1, "b": {"c": [2]}}
    for bad in ["no json here", '{"a": 1,,}', "[1, 2]"]:
        with pytest.raises(ValueError):
            parse_json(bad)


def test_chat_json_retries_once_with_a_reminder():
    class Twice:
        def __init__(self):
            self.replies, self.calls = ["not json", '{"ok": true}'], []

        def chat(self, messages, temperature=0.0, max_tokens=800):
            self.calls.append(messages)
            return LLMResponse(self.replies.pop(0), "m", 1, 1, 0.0)

    llm = Twice()
    value, responses = chat_json(llm, [{"role": "user", "content": "x"}])
    assert value == {"ok": True} and len(responses) == 2
    assert "only the JSON object" in llm.calls[1][-1]["content"]


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
    with pytest.raises(MissingKey, match="set GROQ_API_KEY on the server or send your own key"):
        get_llm("groq")


def test_a_user_key_replaces_the_server_key_and_models_can_be_swapped(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "server-key")
    llm = get_llm("groq", api_key="user-key")
    assert llm.client.api_key == "user-key"
    assert get_llm("groq").client.api_key == "server-key"
    cfg = load_config()["backends"]["groq"]
    assert get_llm("groq").extra_body == cfg.get("extra_body", {}) and get_llm("groq").model == cfg["model"]
    other = get_llm("groq", model="llama-3.3-70b-versatile")
    assert other.model == "llama-3.3-70b-versatile" and other.extra_body == {}    # extra_body is model-specific


def test_custom_backend_needs_url_model_and_key_and_model_names_are_validated():
    with pytest.raises(ValueError, match="custom backend needs"):
        get_llm("custom", model="m")
    llm = get_llm("custom", model="their-model", api_key="k", base_url="https://llm.example.com/v1")
    assert llm.name == "custom" and llm.model == "their-model" and str(llm.client.base_url).startswith("https://llm")
    with pytest.raises(ValueError, match="invalid model name"):
        get_llm("groq", model="bad model; rm -rf")


def test_chat_json_doubles_the_budget_when_the_reply_was_cut_off():
    class CutOff:
        def __init__(self):
            self.replies = [("", "length"), ('{"ok": 1}', "stop")]
            self.budgets = []

        def chat(self, messages, temperature=0.0, max_tokens=800):
            self.budgets.append(max_tokens)
            text, finish = self.replies.pop(0)
            return LLMResponse(text, "m", 1, 1, 0.0, finish_reason=finish)

    llm = CutOff()
    assert chat_json(llm, [{"role": "user", "content": "x"}], max_tokens=1000)[0] == {"ok": 1}
    assert llm.budgets == [1000, 2000]
