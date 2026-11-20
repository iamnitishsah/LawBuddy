import type { HealthResponse } from '../types/api';

// The API base URL comes from the environment (Vercel env or frontend/.env).
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '');
const DEFAULT_API_KEY = import.meta.env.VITE_API_KEY || '';

export function getStoredApiKey(): string {
  const savedKey = localStorage.getItem('lawbuddy_api_key');
  return savedKey !== null ? savedKey : DEFAULT_API_KEY;
}

export function saveStoredApiKey(apiKey: string): void {
  localStorage.setItem('lawbuddy_api_key', apiKey.trim());
}

export function resetStoredApiKey(): string {
  localStorage.removeItem('lawbuddy_api_key');
  return DEFAULT_API_KEY;
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const apiKey = getStoredApiKey();
  const url = `${API_BASE_URL}${endpoint}`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (apiKey) {
    headers['X-API-Key'] = apiKey;
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = response.statusText;
    try {
      const errorJson = await response.json();
      if (errorJson && errorJson.detail) {
        errorDetail = errorJson.detail;
      }
    } catch {
      // use default statusText
    }
    throw new Error(`API error (${response.status}): ${errorDetail}`);
  }

  return response.json();
}

export async function checkHealth(): Promise<{ data: HealthResponse; pingMs: number }> {
  const t0 = performance.now();
  const data = await request<HealthResponse>('/health');
  const pingMs = Math.round(performance.now() - t0);
  return { data, pingMs };
}
