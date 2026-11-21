"""API smoke test against a running server: every endpoint, model swapping, a rejected key, and voice.

    make api                                         # terminal 1: start the server
    python -m lawbuddy.evaluation.api_smoke          # terminal 2 (calls the real LLM, search and Whisper APIs)
    python -m lawbuddy.evaluation.api_smoke --base-url http://localhost:8000 --swap-to nvidia

Every response is saved unedited to outputs/api_smoke/<nn>-<step>.json; a one-line summary per step is printed.
If LAWBUDDY_API_KEY is set, it is sent as X-API-Key. Your own provider key can be tested with USER_LLM_API_KEY
(sent as X-LLM-API-Key for the default backend); it is never written to the output files.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "outputs" / "api_smoke"
AUDIO = ROOT / "eval" / "audio"


class Run:
    def __init__(self, base_url: str):
        headers = {"X-API-Key": os.environ["LAWBUDDY_API_KEY"]} if os.getenv("LAWBUDDY_API_KEY") else {}
        self.http = httpx.Client(base_url=base_url, headers=headers, timeout=180)
        self.n = 0
        OUT.mkdir(parents=True, exist_ok=True)

    def call(self, step: str, method: str, path: str, expect: int = 200, **kw) -> httpx.Response:
        self.n += 1
        r = self.http.request(method, path, **kw)
        try:
            body = r.json()
        except ValueError:
            body = {"text": r.text, "content_type": r.headers.get("content-type")}
        (OUT / f"{self.n:02d}-{step}.json").write_text(
            json.dumps({"request": f"{method} {path}", "status": r.status_code, "body": body}, indent=1,
                       ensure_ascii=False), encoding="utf-8")
        ok = "ok " if r.status_code == expect else "!! "
        print(f"{ok}{self.n:02d} {step:<28} {r.status_code}  {summary(body)}")
        return r


def summary(body) -> str:
    if not isinstance(body, dict):
        return ""
    if "kind" in body:
        s = f"kind={body['kind']} lang={body['language']} model={body['model']} " \
            f"{body['latency_ms']} ms (LLM {body['usage']['llm_s']}s, search {body['usage']['retrieval_s']}s)"
        if body.get("transcript"):
            s += f"\n      heard: {body['transcript'][:110]}"
        if body.get("guard", {}).get("first_problems"):
            s += f"\n      guard: {body['guard']['first_problems']}"
        if body.get("error"):
            s += f"\n      error: {body['error'][:150]}"
        return s
    if "detail" in body:
        return f"detail: {str(body['detail'])[:120]}"
    if "text" in body and "model" in body:
        return f"heard ({body.get('language')}): {body['text'][:110]}"
    return ", ".join(f"{k}={v}" for k, v in list(body.items())[:5] if not isinstance(v, (list, dict)))


def main() -> None:  # pragma: no cover - needs a running server and the APIs
    p = argparse.ArgumentParser(description="Smoke-test a running LawBuddy API.")
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--swap-to", default="gemini", help="backend to switch to in the model-swap step")
    args = p.parse_args()
    run = Run(args.base_url)

    run.call("health", "GET", "/health")
    backends = run.call("backends", "GET", "/backends").json()

    # one conversation on the default model: advice, the draft button, the download
    sid = run.call("session-default", "POST", "/sessions", expect=201).json()["session_id"]
    run.call("message-deposit", "POST", f"/sessions/{sid}/messages", json={"message": (
        "My name is Asha Rao. My landlord Mr. R. Kumar in HSR Layout, Bengaluru has not returned my deposit of "
        "Rs. 1,50,000. I moved out on 31 October and handed over the keys.")})
    run.call("draft-button", "POST", f"/sessions/{sid}/draft")
    run.call("draft-download", "GET", f"/sessions/{sid}/drafts/1")
    run.call("session-state", "GET", f"/sessions/{sid}")

    # model swap: the same question on another backend, chosen per message
    swap = next((b for b in backends["backends"] if b["name"] == args.swap_to), None)
    if swap and swap["server_key"]:
        sid2 = run.call("session-swap", "POST", "/sessions", expect=201).json()["session_id"]
        run.call(f"message-{args.swap_to}", "POST", f"/sessions/{sid2}/messages", json={
            "message": "Is there a 2 month limit on security deposits in Karnataka?",
            "llm": {"backend": args.swap_to}})
    else:
        print(f"-- skipped model swap: no server key for {args.swap_to!r}")

    # a key the provider rejects must be a clear 401, and must not appear in the response
    sid3 = run.call("session-badkey", "POST", "/sessions", expect=201).json()["session_id"]
    run.call("message-bad-key", "POST", f"/sessions/{sid3}/messages", expect=401,
             json={"message": "My employer has not paid my salary"},
             headers={"X-LLM-API-Key": "invalid-key-for-testing-0000000000"})
    if os.getenv("USER_LLM_API_KEY"):
        run.call("message-user-key", "POST", f"/sessions/{sid3}/messages",
                 json={"message": "My employer has not paid my salary"},
                 headers={"X-LLM-API-Key": os.environ["USER_LLM_API_KEY"]})

    # voice: English, Hindi and Kannada recordings, each in a new conversation
    for wav in sorted(AUDIO.glob("*.wav")):
        sid4 = run.call(f"session-{wav.stem}", "POST", "/sessions", expect=201).json()["session_id"]
        with open(wav, "rb") as fh:
            run.call(f"voice-{wav.stem}", "POST", f"/sessions/{sid4}/voice", files={"audio": (wav.name, fh,
                                                                                             "audio/wav")})
    kn = AUDIO / "salary-kn.wav"
    if kn.exists():
        with open(kn, "rb") as fh:
            run.call("transcribe-kn-hint", "POST", "/transcribe", files={"audio": (kn.name, fh, "audio/wav")},
                     data={"language": "kn"})
    print(f"\nraw responses: {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
