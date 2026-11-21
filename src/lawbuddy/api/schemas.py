"""Request and response models for the HTTP API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ReplyKind = Literal["emergency", "escalate", "clarify", "follow_up", "not_found", "advice", "draft", "error"]


class LLMSettings(BaseModel):
    """Which model answers. Every field is optional: omitted fields use the server's configuration.
    The API key is never part of the body; send it in the X-LLM-API-Key header."""
    backend: str | None = Field(None, examples=["groq"], description="a backend from GET /backends, or 'custom'")
    model: str | None = Field(None, max_length=120, examples=["openai/gpt-oss-120b"],
                              description="another model of the same provider")
    base_url: str | None = Field(None, max_length=300, examples=["https://llm.example.com/v1"],
                                 description="only for backend 'custom' (an OpenAI-compatible endpoint)")


class SessionCreate(BaseModel):
    llm: LLMSettings | None = Field(None, description="default model for this conversation")


class MessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000, examples=["My landlord in Bengaluru is not returning my "
                                                                   "deposit of 1.5 lakh"])
    llm: LLMSettings | None = Field(None, description="overrides the session's model for this message")


class DraftRequest(BaseModel):
    llm: LLMSettings | None = None


class Source(BaseModel):
    n: int                              # the number used in [n] citations
    cited: bool
    chunk_id: str
    title: str
    category: str
    kind: str                           # guide | statute | practice
    score: float
    urls: list[str] = []                # official sources of the law the chunk relies on
    verified_on: str | None = None


class GuardInfo(BaseModel):
    checked: bool = False               # True when an answer with legal content was checked
    regenerated: bool = False
    removed: bool = False               # sentences were removed after a second failed check
    first_problems: list[str] = []      # what the first answer got wrong ("kind: text")
    problems: list[str] = []            # what remains (empty unless removal also failed)
    uncited_sentences: int = 0


class RetrievalInfo(BaseModel):
    query: str | None = None
    mode: str | None = None             # primary (rerank/dense) | fallback (keyword)
    top_score: float | None = None
    floor: float | None = None
    seconds: float | None = None


class Usage(BaseModel):
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    llm_s: float = 0.0
    retrieval_s: float = 0.0


class DraftInfo(BaseModel):
    n: int                              # 1-based number within the session: GET /sessions/{id}/drafts/{n}
    category: str
    text: str                           # the notice, Markdown
    placeholders: list[str] = []        # what the user must fill in, shown as [● fill: ...]
    warnings: list[str] = []
    chunks: list[str] = []              # KB chunks the legal parts come from


class CaseInfo(BaseModel):
    category: str | None = None
    facts: dict[str, str | None] = {}
    missing: list[str] = []             # fact keys still unknown, critical first
    timeline: list[dict] = []
    evidence_have: list[str] = []
    evidence_missing: list[str] = []
    other_party: str | None = None
    user_goal: str | None = None
    state: str | None = None
    summary: str = ""
    parties: dict[str, str] = {}


class ChatResponse(BaseModel):
    session_id: str
    kind: ReplyKind
    text: str                           # Markdown, in the user's language
    language: str
    category: str | None = None
    sources: list[Source] = []
    case: CaseInfo
    guard: GuardInfo
    retrieval: RetrievalInfo | None = None
    draft: DraftInfo | None = None
    transcript: str | None = None       # for voice messages: what was heard
    model: str = ""                     # "backend / model" that answered
    steps: list[str] = []               # the turn's decision trace
    error: str | None = None            # for kind "error": what failed (no secrets)
    usage: Usage
    latency_ms: int


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class SessionInfo(BaseModel):
    session_id: str
    created_at: str
    language: str
    llm: LLMSettings
    messages: list[Message]
    case: CaseInfo
    drafts: list[DraftInfo] = []


class BackendInfo(BaseModel):
    name: str
    model: str
    base_url: str
    server_key: bool                    # the server has a key; if False the user must send X-LLM-API-Key
    default: bool


class BackendsResponse(BaseModel):
    backends: list[BackendInfo]
    custom_allowed: bool                # whether backend "custom" (any OpenAI-compatible URL) is enabled
    transcription_model: str
    transcription_server_key: bool


class TranscriptionResponse(BaseModel):
    text: str
    language: str | None = None
    duration_s: float | None = None
    model: str
    latency_ms: int
    note: str = ""                      # e.g. "Whisper detected Tamil; transcribed again as Kannada"


class HealthResponse(BaseModel):
    status: str
    backend: str
    llm: str | None
    kb_chunks: int
    kb_verified: int
    retrieval: str                      # e.g. "rerank" or "keyword search only: ..."
    sessions: int
