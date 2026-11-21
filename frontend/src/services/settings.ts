import { useSyncExternalStore } from 'react';
import type { LLMSettings } from '../types/api';

// Client settings. The server access key and the model choice are kept in localStorage (convenience, not secret
// from the user). The user's own LLM provider key is kept ONLY in memory: it is never written to storage, so a
// page reload forgets it.

export type LanguageHint = '' | 'en' | 'hi' | 'kn';

export interface Settings {
  serverKey: string;          // sent as X-API-Key (only needed if the server sets LAWBUDDY_API_KEY)
  llm: LLMSettings;           // backend / model; empty = server default
  llmKey: string;             // sent as X-LLM-API-Key; memory only
  language: LanguageHint;     // hint for voice transcription; '' = detect
  showSteps: boolean;         // show "why this answer" details open by default
}

const STORAGE_KEY = 'lawbuddy_settings';

function load(): Settings {
  const base: Settings = {
    serverKey: import.meta.env.VITE_API_KEY || '',
    llm: {},
    llmKey: '',
    language: '',
    showSteps: false,
  };
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    return {
      ...base,
      serverKey: typeof saved.serverKey === 'string' ? saved.serverKey : base.serverKey,
      llm: saved.llm && typeof saved.llm === 'object' ? saved.llm : {},
      language: ['', 'en', 'hi', 'kn'].includes(saved.language) ? saved.language : '',
      showSteps: saved.showSteps === true,
    };
  } catch {
    return base;
  }
}

let state: Settings = load();
const listeners = new Set<() => void>();

export function getSettings(): Settings {
  return state;
}

export function updateSettings(patch: Partial<Settings>): void {
  state = { ...state, ...patch };
  try {
    const { llmKey: _secret, ...persisted } = state; // the provider key is never persisted
    void _secret;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(persisted));
  } catch {
    // storage unavailable (private mode): settings still work for this page
  }
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useSettings(): Settings {
  return useSyncExternalStore(subscribe, getSettings, getSettings);
}

export function activeLLM(): LLMSettings | undefined {
  const { backend, model } = state.llm;
  if (!backend && !model) return undefined;
  return { backend: backend || null, model: model || null };
}
