import type { AgentResult } from '../api/types'

// Chats live in this browser only: the server keeps no conversation state and there are no
// accounts. Only completed turns are stored — a turn still running at reload had its request
// aborted by navigation anyway, and a bare transport error is nothing but "try again".
export interface StoredTurn {
  id: string
  question: string
  result: AgentResult
}

export interface StoredChat {
  id: string
  title: string
  createdAt: number
  updatedAt: number
  turns: StoredTurn[]
}

const KEY = 'ai-sql-analyst:chats'
/** The single-session store this replaced; read once so an open session isn't lost on upgrade. */
const LEGACY_SESSION_KEY = 'ai-sql-analyst:session'
const MAX_STORED_CHATS = 50
const MAX_TITLE_LENGTH = 60

export function chatTitle(question: string): string {
  const flat = question.replace(/\s+/g, ' ').trim()
  return flat.length <= MAX_TITLE_LENGTH ? flat : `${flat.slice(0, MAX_TITLE_LENGTH - 1).trimEnd()}…`
}

export function loadChats(now: number = Date.now()): StoredChat[] {
  try {
    const raw = localStorage.getItem(KEY)
    if (raw) {
      const parsed: unknown = JSON.parse(raw)
      return Array.isArray(parsed) ? (parsed as StoredChat[]) : []
    }
    return migrateLegacySession(now)
  } catch {
    return []
  }
}

function migrateLegacySession(now: number): StoredChat[] {
  const raw = sessionStorage.getItem(LEGACY_SESSION_KEY)
  if (!raw) return []
  const parsed: unknown = JSON.parse(raw)
  sessionStorage.removeItem(LEGACY_SESSION_KEY)
  if (!Array.isArray(parsed) || parsed.length === 0) return []
  const turns = parsed as StoredTurn[]
  return [{ id: crypto.randomUUID(), title: chatTitle(turns[0].question), createdAt: now, updatedAt: now, turns }]
}

export function saveChats(chats: StoredChat[]): void {
  const kept = [...chats].sort((a, b) => b.updatedAt - a.updatedAt).slice(0, MAX_STORED_CHATS)
  // Result rows can be large; when storage is full, drop the oldest chats until it fits.
  for (let count = kept.length; count >= 0; count = count === 0 ? -1 : Math.floor(count / 2)) {
    try {
      localStorage.setItem(KEY, JSON.stringify(kept.slice(0, count)))
      return
    } catch {
      // quota exceeded or storage blocked: try fewer chats, then give up silently
    }
  }
}

export interface ChatGroup<T> {
  label: string
  chats: T[]
}

const DAY = 24 * 60 * 60 * 1000

/** Newest first, bucketed the way chat apps date their history. */
export function groupChatsByDate<T extends { updatedAt: number }>(chats: T[], now: number = Date.now()): ChatGroup<T>[] {
  const startOfToday = new Date(now)
  startOfToday.setHours(0, 0, 0, 0)
  const today = startOfToday.getTime()
  const buckets: [string, (t: number) => boolean][] = [
    ['Today', (t) => t >= today],
    ['Yesterday', (t) => t >= today - DAY],
    ['Previous 7 days', (t) => t >= today - 7 * DAY],
    ['Previous 30 days', (t) => t >= today - 30 * DAY],
    ['Older', () => true],
  ]
  const groups: ChatGroup<T>[] = buckets.map(([label]) => ({ label, chats: [] }))
  for (const chat of [...chats].sort((a, b) => b.updatedAt - a.updatedAt)) {
    const index = buckets.findIndex(([, matches]) => matches(chat.updatedAt))
    groups[index].chats.push(chat)
  }
  return groups.filter((group) => group.chats.length > 0)
}
