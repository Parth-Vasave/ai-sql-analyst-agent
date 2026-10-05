import { beforeEach, describe, expect, it } from 'vitest'
import { chatTitle, groupChatsByDate, loadChats, saveChats, type StoredChat } from './chats'

const NOW = new Date('2026-10-04T15:00:00').getTime()
const HOUR = 60 * 60 * 1000

function chat(id: string, updatedAt: number): StoredChat {
  return { id, title: id, createdAt: updatedAt, updatedAt, turns: [] }
}

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
})

describe('chatTitle', () => {
  it('flattens whitespace and keeps short questions whole', () => {
    expect(chatTitle('  Top 5   countries\nby CO2 ')).toBe('Top 5 countries by CO2')
  })
  it('truncates long questions with an ellipsis', () => {
    const title = chatTitle('a'.repeat(100))
    expect(title).toHaveLength(60)
    expect(title.endsWith('…')).toBe(true)
  })
})

describe('loadChats / saveChats', () => {
  it('round-trips chats through localStorage, newest first', () => {
    saveChats([chat('old', NOW - 5 * HOUR), chat('new', NOW)])
    expect(loadChats().map((c) => c.id)).toEqual(['new', 'old'])
  })

  it('migrates the previous single-session store into one chat', () => {
    sessionStorage.setItem(
      'ai-sql-analyst:session',
      JSON.stringify([{ id: 't1', question: 'Which country emitted the most?', result: {} }]),
    )
    const chats = loadChats(NOW)
    expect(chats).toHaveLength(1)
    expect(chats[0].title).toBe('Which country emitted the most?')
    expect(chats[0].turns).toHaveLength(1)
    expect(sessionStorage.getItem('ai-sql-analyst:session')).toBeNull()
  })

  it('returns nothing for corrupt storage', () => {
    localStorage.setItem('ai-sql-analyst:chats', '{not json')
    expect(loadChats()).toEqual([])
  })
})

describe('groupChatsByDate', () => {
  it('buckets by calendar day and drops empty groups', () => {
    const groups = groupChatsByDate(
      [chat('today', NOW - HOUR), chat('yesterday', NOW - 20 * HOUR), chat('lastweek', NOW - 4 * 24 * HOUR), chat('ancient', NOW - 90 * 24 * HOUR)],
      NOW,
    )
    expect(groups.map((g) => [g.label, g.chats.map((c) => c.id)])).toEqual([
      ['Today', ['today']],
      ['Yesterday', ['yesterday']],
      ['Previous 7 days', ['lastweek']],
      ['Older', ['ancient']],
    ])
  })
})
