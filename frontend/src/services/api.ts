import type {
  BackendsResponse,
  ChatResponse,
  HealthResponse,
  SessionInfo,
} from '../types/api';
import { activeLLM, getSettings } from './settings';

// The API base URL comes from the environment (Vercel env or frontend/.env).
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '');

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function headers(json: boolean): Record<string, string> {
  const s = getSettings();
  const h: Record<string, string> = {};
  if (json) h['Content-Type'] = 'application/json';
  if (s.serverKey) h['X-API-Key'] = s.serverKey;
  if (s.llmKey) h['X-LLM-API-Key'] = s.llmKey;
  return h;
}

async function request<T>(endpoint: string, init: RequestInit = {}, json = true): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...init,
      headers: { ...headers(json && !(init.body instanceof FormData)), ...(init.headers as Record<string, string>) },
    });
  } catch {
    throw new ApiError(0, `Cannot reach the LawBuddy server at ${API_BASE_URL}.`);
  }
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    } catch {
      // keep statusText
    }
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export async function checkHealth(): Promise<{ data: HealthResponse; pingMs: number }> {
  const t0 = performance.now();
  const data = await request<HealthResponse>('/health');
  return { data, pingMs: Math.round(performance.now() - t0) };
}

export function getBackends(): Promise<BackendsResponse> {
  return request<BackendsResponse>('/backends');
}

export function createSession(): Promise<SessionInfo> {
  const llm = activeLLM();
  return request<SessionInfo>('/sessions', { method: 'POST', body: JSON.stringify(llm ? { llm } : {}) });
}

export function getSession(id: string): Promise<SessionInfo> {
  return request<SessionInfo>(`/sessions/${id}`);
}

export function sendMessage(sessionId: string, message: string): Promise<ChatResponse> {
  const llm = activeLLM();
  return request<ChatResponse>(`/sessions/${sessionId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ message, ...(llm ? { llm } : {}) }),
  });
}

export function sendVoice(sessionId: string, audio: Blob, filename: string): Promise<ChatResponse> {
  const form = new FormData();
  form.append('audio', audio, filename);
  const s = getSettings();
  if (s.language) form.append('language', s.language);
  if (s.llm.backend) form.append('backend', s.llm.backend);
  if (s.llm.model) form.append('model', s.llm.model);
  return request<ChatResponse>(`/sessions/${sessionId}/voice`, { method: 'POST', body: form }, false);
}

export function draftNow(sessionId: string): Promise<ChatResponse> {
  const llm = activeLLM();
  return request<ChatResponse>(`/sessions/${sessionId}/draft`, {
    method: 'POST',
    body: JSON.stringify(llm ? { llm } : {}),
  });
}

// Downloads go through fetch (not a plain link) so the access-key header is sent.
export async function downloadDraft(sessionId: string, n: number): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/drafts/${n}`, { headers: headers(false) });
  } catch {
    throw new ApiError(0, 'Cannot reach the LawBuddy server.');
  }
  if (!response.ok) throw new ApiError(response.status, 'The notice could not be downloaded.');
  const disposition = response.headers.get('Content-Disposition') || '';
  const name = /filename="([^"]+)"/.exec(disposition)?.[1] || `legal-notice-${n}.md`;
  const url = URL.createObjectURL(await response.blob());
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
