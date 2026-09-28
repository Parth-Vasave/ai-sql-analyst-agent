import type { AgentResult } from '../api/types'

// Only completed turns are worth restoring: a turn still "running" at reload time had its
// request aborted by navigation anyway, and a bare transport error is nothing but "try again".
export interface PersistedTurn {
  id: string
  question: string
  result: AgentResult
}

const KEY = 'ai-sql-analyst:session'

export function loadSession(): PersistedTurn[] {
  try {
    const raw = sessionStorage.getItem(KEY)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    return Array.isArray(parsed) ? (parsed as PersistedTurn[]) : []
  } catch {
    return []
  }
}

export function saveSession(turns: PersistedTurn[]): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(turns))
  } catch {
    // storage unavailable, full, or blocked (private browsing): the session just won't persist
  }
}
