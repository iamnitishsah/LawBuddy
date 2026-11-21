// Mirrors src/lawbuddy/api/schemas.py. Keep the two in step.

export type ReplyKind =
  | 'emergency'
  | 'escalate'
  | 'clarify'
  | 'follow_up'
  | 'not_found'
  | 'advice'
  | 'draft'
  | 'error';

export interface LLMSettings {
  backend?: string | null;
  model?: string | null;
  base_url?: string | null;
}

export interface Source {
  n: number;
  cited: boolean;
  chunk_id: string;
  title: string;
  category: string;
  kind: string;
  score: number;
  urls: string[];
  verified_on?: string | null;
}

export interface GuardInfo {
  checked: boolean;
  regenerated: boolean;
  removed: boolean;
  first_problems: string[];
  problems: string[];
  uncited_sentences: number;
}

export interface RetrievalInfo {
  query?: string | null;
  mode?: string | null;
  top_score?: number | null;
  floor?: number | null;
  seconds?: number | null;
}

export interface Usage {
  llm_calls: number;
  input_tokens: number;
  output_tokens: number;
  llm_s: number;
  retrieval_s: number;
}

export interface DraftInfo {
  n: number;
  category: string;
  text: string;
  placeholders: string[];
  warnings: string[];
  chunks: string[];
}

export interface CaseInfo {
  category: string | null;
  facts: Record<string, string | null>;
  missing: string[];
  timeline: { date: string; event: string }[];
  evidence_have: string[];
  evidence_missing: string[];
  other_party: string | null;
  user_goal: string | null;
  state: string | null;
  summary: string;
  parties: Record<string, string>;
}

export interface ChatResponse {
  session_id: string;
  kind: ReplyKind;
  text: string;
  language: string;
  category: string | null;
  sources: Source[];
  case: CaseInfo;
  guard: GuardInfo;
  retrieval: RetrievalInfo | null;
  draft: DraftInfo | null;
  transcript: string | null;
  model: string;
  steps: string[];
  error: string | null;
  usage: Usage;
  latency_ms: number;
}

export interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export interface SessionInfo {
  session_id: string;
  created_at: string;
  language: string;
  llm: LLMSettings;
  messages: Message[];
  case: CaseInfo;
  drafts: DraftInfo[];
}

export interface BackendInfo {
  name: string;
  model: string;
  base_url: string;
  server_key: boolean;
  default: boolean;
}

export interface BackendsResponse {
  backends: BackendInfo[];
  custom_allowed: boolean;
  transcription_model: string;
  transcription_server_key: boolean;
}

export interface HealthResponse {
  status: string;
  backend: string;
  llm: string | null;
  kb_chunks: number;
  kb_verified: number;
  retrieval: string;
  sessions: number;
}

// What the chat keeps per turn: the user's message plus, once it arrives, LawBuddy's reply.
export interface Turn {
  id: string;
  user: string;
  viaVoice: boolean;
  reply?: ChatResponse;
  failed?: string;
}
