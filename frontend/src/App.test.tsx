import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import * as client from './api/client'
import { ApiError, type AgentResult, type DatabaseInfo } from './api/types'

vi.mock('./api/client')

const DATABASE: DatabaseInfo = {
  id: 'owid',
  name: 'owid_co2',
  dialect: 'postgresql',
  source: 'config',
  sampling: 'safe',
  status: 'ready',
  issues: [],
}

function successResult(overrides: Partial<AgentResult> = {}): AgentResult {
  return {
    status: 'success',
    question: 'Which country emitted the most CO2 in 2023?',
    resolved_question: null,
    answer: 'China emitted the most CO2 in 2023, at 11,472 Mt.',
    answer_source: 'llm',
    clarification_question: null,
    explanation: null,
    plan: {
      intent: 'ranking',
      tables: ['co2_emissions'],
      metrics: ['co2'],
      filters: ['year = 2023'],
      group_by: [],
      order_by: 'co2 desc',
      limit: 1,
      assumptions: ['latest available year'],
    },
    sql: "SELECT country, co2 FROM co2_emissions WHERE year = 2023 ORDER BY co2 DESC LIMIT 1;",
    columns: ['country', 'co2'],
    rows: [['China', 11472.4]],
    column_units: { co2: 'Mt' },
    chart_suggestion: 'bar',
    chart: null,
    checks: [],
    error: null,
    trace: [
      { step: 'sql_generation', status: 'success', duration_ms: 340, detail: {} },
      { step: 'sql_validation', status: 'success', duration_ms: 2, detail: {} },
      { step: 'query_execution', status: 'success', duration_ms: 41, detail: {} },
    ],
    metadata: {
      database_id: 'owid',
      dialect: 'postgresql',
      model: 'gemini-3.6-flash',
      prompt_version: 'sql-generator/3',
      tables_used: ['co2_emissions'],
      execution_time_ms: 41,
      row_count: 1,
      truncated: false,
      retry_count: 0,
      request_id: 'req-1',
    },
    ...overrides,
  }
}

beforeEach(() => {
  vi.mocked(client.fetchDatabases).mockResolvedValue([DATABASE])
  sessionStorage.clear()
})

describe('App', () => {
  it('shows the mechanism explanation before any question is asked', async () => {
    render(<App />)
    expect(await screen.findByText(/never trusted on its own/i)).toBeInTheDocument()
  })

  it('asks a question and renders the answer, SQL and trace', async () => {
    vi.mocked(client.runQuery).mockResolvedValue(successResult())
    render(<App />)
    await screen.findByPlaceholderText(/ask a question/i)

    await userEvent.type(screen.getByLabelText(/ask a question/i), 'Which country emitted the most CO2 in 2023?{Enter}')

    expect(await screen.findByText(/China emitted the most CO2 in 2023/)).toBeInTheDocument()
    expect(screen.getByText(/SELECT country, co2 FROM co2_emissions/)).toBeInTheDocument()
    expect(screen.getByText('China')).toBeInTheDocument()
    expect(client.runQuery).toHaveBeenCalledWith(
      expect.objectContaining({ question: 'Which country emitted the most CO2 in 2023?', database_id: 'owid' }),
    )
  })

  it('shows a clarification question without SQL or a result grid', async () => {
    vi.mocked(client.runQuery).mockResolvedValue(
      successResult({
        status: 'needs_clarification',
        clarification_question: 'Which year do you mean?',
        sql: null,
        answer: null,
        columns: [],
        rows: [],
        trace: [],
      }),
    )
    render(<App />)
    await screen.findByPlaceholderText(/ask a question/i)
    await userEvent.type(screen.getByLabelText(/ask a question/i), 'Who emits the most?{Enter}')

    expect(await screen.findByText('Which year do you mean?')).toBeInTheDocument()
  })

  it('shows a rate-limit error with a retry affordance', async () => {
    vi.mocked(client.runQuery).mockRejectedValue(new ApiError('Too many questions. Try again in 30 s.', 429, 30, 'req-2'))
    render(<App />)
    await screen.findByPlaceholderText(/ask a question/i)
    await userEvent.type(screen.getByLabelText(/ask a question/i), 'Another question{Enter}')

    expect(await screen.findByText(/rate limited/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /retry in 30s/i })).toBeDisabled()
  })

  it('lets the user switch databases when more than one is configured', async () => {
    const second: DatabaseInfo = { ...DATABASE, id: 'other', name: 'other_db' }
    vi.mocked(client.fetchDatabases).mockResolvedValue([DATABASE, second])
    vi.mocked(client.runQuery).mockResolvedValue(successResult())
    render(<App />)

    const select = await screen.findByLabelText(/connected database/i)
    await userEvent.selectOptions(select, 'other')
    await userEvent.type(screen.getByLabelText(/ask a question/i), 'A question{Enter}')

    await waitFor(() => expect(client.runQuery).toHaveBeenCalledWith(expect.objectContaining({ database_id: 'other' })))
  })

  it('opens and closes the connect, schema and help panels', async () => {
    render(<App />)
    await screen.findByPlaceholderText(/ask a question/i)

    await userEvent.click(screen.getByRole('button', { name: /connect a database/i }))
    expect(await screen.findByLabelText(/connection url/i)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /open help/i }))
    expect(await screen.findByText(/asking questions/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/connection url/i)).not.toBeInTheDocument()

    vi.mocked(client.fetchProfile).mockResolvedValue({
      database_id: 'owid',
      dialect: 'postgresql',
      sampling: 'safe',
      fingerprint: 'x',
      tables: [],
      relationships: [],
      notes: [],
    })
    await userEvent.click(screen.getByRole('button', { name: /browse the active database's schema/i }))
    expect(await screen.findByText(/0 tables, sampling: safe/)).toBeInTheDocument()
  })

  it('restores completed turns from a previous session', async () => {
    const result = successResult()
    sessionStorage.setItem(
      'ai-sql-analyst:session',
      JSON.stringify([{ id: 't1', question: result.question, result }]),
    )
    render(<App />)

    expect(await screen.findByText(/China emitted the most CO2 in 2023/)).toBeInTheDocument()
    expect(client.runQuery).not.toHaveBeenCalled()
  })
})
