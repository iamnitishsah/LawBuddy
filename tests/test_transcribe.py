"""Tests for speech to text with a fake Whisper client (no network)."""

from types import SimpleNamespace

import pytest

from lawbuddy.llm.base import load_config
from lawbuddy.voice.transcribe import Transcriber


def transcriber(*responses, retry=("tamil", "telugu", "malayalam")):
    t = Transcriber.__new__(Transcriber)
    t.model, t.max_bytes, t.retry_as_kannada = "whisper-fake", 1_000_000, set(retry)
    calls = []

    def create(**kw):
        calls.append(kw.get("language"))
        return responses[len(calls) - 1]

    t.client = SimpleNamespace(audio=SimpleNamespace(transcriptions=SimpleNamespace(create=create)))
    t.calls = calls
    return t


TAMIL = SimpleNamespace(text="நன்ன கம்பனி மூறு திங்களிந்த சம்பல", language="tamil", duration=4.5)
KANNADA = SimpleNamespace(text="ನನ್ನ ಕಂಪನಿ ಮೂರು ತಿಂಗಳಿಂದ ಸಂಬಳ ಕೊಟ್ಟಿಲ್ಲ", language="kannada", duration=4.5)
HINDI = SimpleNamespace(text="कंपनी ने तनख्वाह नहीं दी", language="hindi", duration=3.0)


def test_kannada_heard_as_tamil_is_transcribed_again_as_kannada():
    """api smoke 2026-11-21: synthetic Kannada speech came back in Tamil script, and the reply was in Tamil."""
    t = transcriber(TAMIL, KANNADA)
    out = t.transcribe(b"x", "a.wav")
    assert out.text.startswith("ನನ್ನ") and t.calls == [None, "kn"] and "detected Tamil" in out.note


def test_other_languages_and_explicit_choices_are_left_alone():
    t = transcriber(HINDI)
    assert t.transcribe(b"x", "a.wav").note == "" and t.calls == [None]
    t = transcriber(TAMIL)
    assert t.transcribe(b"x", "a.wav", language="ta").text.startswith("நன்ன") and t.calls == ["ta"]


def test_language_hint_and_file_checks():
    t = transcriber(HINDI)
    with pytest.raises(ValueError, match="two-letter code"):
        t.transcribe(b"x", "a.wav", language="hindi")
    with pytest.raises(ValueError, match="unsupported audio type"):
        t.transcribe(b"x", "a.txt")
    with pytest.raises(ValueError, match="limit"):
        t.transcribe(b"x" * 2_000_000, "a.wav")
    assert t.calls == []                                                   # nothing reached the API


def test_the_retry_list_is_configured():
    assert "tamil" in load_config()["transcription"]["retry_as_kannada_when_detected"]
