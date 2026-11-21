"""Speech to text through an OpenAI-compatible /audio/transcriptions endpoint (Whisper on Groq by default).

The provider and model come from the `transcription` section of configs/llm.yaml; the API key is the configured
backend's key, or the caller's own key. Whisper detects the language itself; a language hint ("hi", "kn", "en")
can be passed when the user has chosen one.

    python -m lawbuddy.voice.transcribe recording.m4a [--language hi]
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

from lawbuddy.llm.base import MissingKey, load_config

AUDIO_TYPES = {".flac", ".m4a", ".mp3", ".mp4", ".mpeg", ".mpga", ".oga", ".ogg", ".wav", ".webm"}
LANGUAGE_RE_CHARS = set("abcdefghijklmnopqrstuvwxyz")


@dataclass
class Transcript:
    text: str
    language: str | None = None          # as detected by the model, e.g. "hindi" or "hi"
    duration_s: float | None = None      # length of the audio
    model: str = ""
    latency_s: float = 0.0
    note: str = ""                       # e.g. "Whisper detected Tamil; transcribed again as Kannada"


class Transcriber:
    def __init__(self, base_url: str, model: str, api_key: str, max_mb: float = 20, timeout: float = 60.0,
                 retry_as_kannada: list[str] | tuple[str, ...] = ()):
        from openai import OpenAI
        self.model, self.max_bytes = model, int(max_mb * 1024 * 1024)
        self.retry_as_kannada = {x.lower() for x in retry_as_kannada}
        self.client = OpenAI(api_key=api_key, base_url=base_url, max_retries=2, timeout=timeout)

    def check(self, audio: bytes, filename: str) -> None:
        """Raises ValueError for an upload that would be refused, before any API call."""
        ext = os.path.splitext(filename or "")[1].lower()
        if ext not in AUDIO_TYPES:
            raise ValueError(f"unsupported audio type {ext or '(none)'}; use one of {sorted(AUDIO_TYPES)}")
        if not audio:
            raise ValueError("the audio file is empty")
        if len(audio) > self.max_bytes:
            raise ValueError(f"the audio is {len(audio) / 1e6:.1f} MB; the limit is {self.max_bytes / 1e6:.0f} MB")

    def transcribe(self, audio: bytes, filename: str, language: str | None = None) -> Transcript:
        self.check(audio, filename)
        if language and (len(language) != 2 or not set(language.lower()) <= LANGUAGE_RE_CHARS):
            raise ValueError("language must be a two-letter code such as 'hi', 'kn' or 'en'")
        t0 = time.monotonic()
        resp = self._call(audio, filename, language)
        note = ""
        detected = str(getattr(resp, "language", "") or "").lower()
        if not language and detected in self.retry_as_kannada:
            note = f"Whisper detected {detected.title()}; transcribed again as Kannada"
            resp = self._call(audio, filename, "kn")
        return Transcript(text=(getattr(resp, "text", "") or "").strip(), language=getattr(resp, "language", None),
                          duration_s=getattr(resp, "duration", None), model=self.model,
                          latency_s=round(time.monotonic() - t0, 2), note=note)

    def _call(self, audio: bytes, filename: str, language: str | None):
        return self.client.audio.transcriptions.create(
            model=self.model, file=(filename, audio), response_format="verbose_json",
            **({"language": language.lower()} if language else {}))


def get_transcriber(api_key: str | None = None) -> Transcriber:
    cfg = load_config()
    t = cfg["transcription"]
    b = cfg["backends"][t["backend"]]
    key = api_key or os.getenv(b["api_key_env"])
    if not key:
        raise MissingKey(f"no API key for transcription: set {b['api_key_env']} on the server or send your own key")
    return Transcriber(b["base_url"], t["model"], key, t.get("max_mb", 20),
                       retry_as_kannada=t.get("retry_as_kannada_when_detected", []))


if __name__ == "__main__":  # pragma: no cover - needs the API
    import argparse
    from pathlib import Path

    from dotenv import load_dotenv

    from lawbuddy.llm.base import ROOT

    p = argparse.ArgumentParser(description="Transcribe an audio file.")
    p.add_argument("audio", type=Path)
    p.add_argument("--language")
    args = p.parse_args()
    load_dotenv(ROOT / ".env")
    t = get_transcriber().transcribe(args.audio.read_bytes(), args.audio.name, args.language)
    print(f"[{t.model} | language {t.language} | {t.duration_s}s audio | {t.latency_s}s]"
          + (f" ({t.note})" if t.note else "") + f"\n{t.text}")
