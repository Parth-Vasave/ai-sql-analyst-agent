import type { AgentResult, DatabaseInfo, DatabaseProfile } from "./types";

/** An HTTP error from the API, with the server's own message when it sent one. */
export class ApiError extends Error {
  readonly status: number;
  readonly requestId: string | null;

  constructor(status: number, message: string, requestId: string | null) {
    super(message);
    this.status = status;
    this.requestId = requestId;
  }
}

const BASE = import.meta.env.VITE_API_BASE ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, init);
  } catch {
    throw new ApiError(0, "The API could not be reached. Is the backend running?", null);
  }
  const requestId = response.headers.get("X-Request-ID");
  if (!response.ok) {
    let message = `The API returned HTTP ${response.status}.`;
    try {
      const body: unknown = await response.json();
      const detail = (body as { detail?: unknown }).detail;
      if (typeof detail === "string") message = detail;
      else if (detail && typeof detail === "object" && "message" in detail) {
        message = String((detail as { message: unknown }).message);
      }
    } catch {
      // keep the generic message
    }
    throw new ApiError(response.status, message, requestId);
  }
  return (await response.json()) as T;
}

export function listDatabases(): Promise<DatabaseInfo[]> {
  return request<DatabaseInfo[]>("/api/databases");
}

export function getProfile(databaseId: string): Promise<DatabaseProfile> {
  return request<DatabaseProfile>(`/api/databases/${encodeURIComponent(databaseId)}/profile`);
}

export function ask(question: string, databaseId: string | null, signal?: AbortSignal): Promise<AgentResult> {
  return request<AgentResult>("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, database_id: databaseId }),
    ...(signal ? { signal } : {}),
  });
}
