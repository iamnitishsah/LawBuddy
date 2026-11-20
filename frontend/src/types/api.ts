export interface HealthResponse {
  status: string;
  backend: string;
  llm: string | null;
}
