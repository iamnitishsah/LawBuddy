"""One interface for every LLM provider.

The rest of the code calls get_llm().chat(messages) (or .complete(system, user)) and never knows
which provider or model is behind it. Backends are defined in configs/llm.yaml;
LLM_BACKEND (env) or the `backend` argument picks one. chat_json() asks for a JSON object and
retries once if the reply does not parse.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


@dataclass
class LLMResponse:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_s: float
    finish_reason: str = "stop"


class OpenAICompatibleLLM:
    """Any provider with an OpenAI-style /chat/completions endpoint (Groq, Gemini, OpenAI...)."""

    def __init__(self, name: str, base_url: str, api_key_env: str, model: str,
                 extra_body: dict | None = None, max_retries: int = 4, timeout: float = 60.0):
        from openai import OpenAI
        key = os.getenv(api_key_env)
        if not key:
            raise RuntimeError(f"{api_key_env} is not set (add it to .env)")
        self.name, self.model, self.extra_body = name, model, extra_body or {}
        # The SDK retries 429 (rate limit) and 5xx errors itself, with exponential backoff.
        self.client = OpenAI(api_key=key, base_url=base_url, max_retries=max_retries, timeout=timeout)

    def complete(self, system: str, user: str, temperature: float = 0.0, max_tokens: int = 800) -> LLMResponse:
        return self.chat([{"role": "system", "content": system}, {"role": "user", "content": user}],
                         temperature, max_tokens)

    def chat(self, messages: list[dict], temperature: float = 0.0, max_tokens: int = 800) -> LLMResponse:
        """messages: [{"role": "system" | "user" | "assistant", "content": str}, ...]"""
        t0 = time.monotonic()
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **({"extra_body": self.extra_body} if self.extra_body else {}),
        )
        usage = resp.usage
        return LLMResponse(
            text=(resp.choices[0].message.content or "").strip(),
            model=resp.model or self.model,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            latency_s=time.monotonic() - t0,
            finish_reason=resp.choices[0].finish_reason or "stop",
        )

    def list_models(self) -> list[str]:
        return sorted(m.id for m in self.client.models.list())


JSON_BLOCK_RE = re.compile(r"\{.*\}", re.S)


def parse_json(text: str) -> dict:
    """The first JSON object in a model reply, tolerating ```json fences and text around it. Raises ValueError."""
    m = JSON_BLOCK_RE.search(text or "")
    if not m:
        raise ValueError("no JSON object in the reply")
    try:
        value = json.loads(m.group(0))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in the reply: {exc}") from None
    if not isinstance(value, dict):
        raise ValueError("the reply's JSON is not an object")
    return value


def chat_json(llm, messages: list[dict], temperature: float = 0.0, max_tokens: int = 1500) -> tuple[dict, list]:
    """-> (parsed object, [LLMResponse, ...]). One retry if the first reply is not valid JSON: with double the token
    budget if it was cut off (reasoning models can spend the budget before answering), else with a reminder."""
    responses = [llm.chat(messages, temperature, max_tokens)]
    try:
        return parse_json(responses[0].text), responses
    except ValueError as exc:
        if responses[0].finish_reason == "length" or not responses[0].text.strip():
            responses.append(llm.chat(messages, temperature, max_tokens * 2))
        else:
            retry = messages + [{"role": "assistant", "content": responses[0].text},
                                {"role": "user", "content": f"That was not valid JSON ({exc}). "
                                                            "Reply with only the JSON object."}]
            responses.append(llm.chat(retry, temperature, max_tokens))
        return parse_json(responses[1].text), responses


def load_config() -> dict:
    return yaml.safe_load(open(ROOT / "configs" / "llm.yaml"))


def resolve_backend(backend: str | None = None) -> tuple[str, str]:
    """-> (backend name, where the choice came from). Precedence: flag > env var > config."""
    if backend:
        return backend, "--backend flag"
    if os.getenv("LLM_BACKEND"):
        return os.environ["LLM_BACKEND"].strip(), "LLM_BACKEND env var"
    return load_config()["default_backend"], "configs/llm.yaml"


def get_llm(backend: str | None = None) -> OpenAICompatibleLLM:
    cfg = load_config()
    name, source = resolve_backend(backend)
    if name not in cfg["backends"]:
        raise ValueError(f"Unknown LLM backend {name!r} (from {source}); choose from {list(cfg['backends'])}")
    b = cfg["backends"][name]
    llm = OpenAICompatibleLLM(name, b["base_url"], b["api_key_env"], b["model"], b.get("extra_body"))
    llm.source = source
    return llm


if __name__ == "__main__":   # python -m lawbuddy.llm.base groq  -> lists that provider's models
    import sys

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    llm = get_llm(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"{llm.name}: configured model = {llm.model}")
    print("\n".join(f"  {m}" for m in llm.list_models()))