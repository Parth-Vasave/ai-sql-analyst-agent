import {
  ApiError,
  type AddDatabaseRequest,
  type AgentResult,
  type DatabaseInfo,
  type DatabaseProfile,
  type HealthResponse,
  type QueryRequest,
} from './types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''
const REQUEST_ID_HEADER = 'X-Request-ID'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError('Could not reach the API. Is the backend running?', 0)
  }
  const requestId = response.headers.get(REQUEST_ID_HEADER)
  if (!response.ok) {
    const retryAfter = response.headers.get('Retry-After')
    let message = `Request failed with status ${response.status}.`
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') message = body.detail
      else if (body.detail && typeof body.detail === 'object' && 'message' in body.detail) {
        const detail = body.detail as { message: unknown; issues?: unknown }
        message = String(detail.message)
        if (Array.isArray(detail.issues) && detail.issues.length > 0) {
          message = `${message} (${detail.issues.join('; ')})`
        }
      }
    } catch {
      // body wasn't JSON; keep the generic message
    }
    throw new ApiError(message, response.status, retryAfter ? Number(retryAfter) : null, requestId)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/api/health')
}

export function fetchDatabases(): Promise<DatabaseInfo[]> {
  return request<DatabaseInfo[]>('/api/databases')
}

export function runQuery(body: QueryRequest): Promise<AgentResult> {
  return request<AgentResult>('/api/query', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function addDatabase(body: AddDatabaseRequest): Promise<DatabaseInfo> {
  return request<DatabaseInfo>('/api/databases', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function fetchProfile(databaseId: string, refresh = false): Promise<DatabaseProfile> {
  const query = refresh ? '?refresh=true' : ''
  return request<DatabaseProfile>(`/api/databases/${encodeURIComponent(databaseId)}/profile${query}`)
}
