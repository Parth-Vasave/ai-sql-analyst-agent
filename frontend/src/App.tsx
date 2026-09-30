import { useEffect, useRef, useState } from 'react'
import { fetchDatabases, runQuery } from './api/client'
import { ApiError, type AgentResult, type DatabaseInfo, type Turn } from './api/types'
import { ConnectDatabaseForm } from './components/ConnectDatabaseForm'
import { HelpPanel } from './components/HelpPanel'
import { IntroBlock } from './components/IntroBlock'
import { PromptForm } from './components/PromptForm'
import { QueryBlock } from './components/QueryBlock'
import { SchemaBrowser } from './components/SchemaBrowser'
import { SessionHeader } from './components/SessionHeader'
import { useTheme } from './hooks/useTheme'
import { loadSession, saveSession } from './lib/session'

interface LocalTurn {
  id: string
  question: string
  running: boolean
  result?: AgentResult
  transportError?: ApiError
}

const MAX_HISTORY_TURNS = 3

function toHistory(turns: LocalTurn[]): Turn[] {
  return turns
    .filter((t) => t.result)
    .slice(-MAX_HISTORY_TURNS)
    .map((t) => ({
      question: t.result!.resolved_question ?? t.result!.question,
      sql: t.result!.sql,
      answer: t.result!.answer,
    }))
}

type Panel = 'connect' | 'schema' | 'help' | null

export default function App() {
  const { theme, toggle } = useTheme()
  const [databases, setDatabases] = useState<DatabaseInfo[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [databasesError, setDatabasesError] = useState<ApiError | null>(null)
  const [panel, setPanel] = useState<Panel>(null)
  const [turns, setTurns] = useState<LocalTurn[]>(() =>
    loadSession().map((t) => ({ id: t.id, question: t.question, running: false, result: t.result })),
  )
  const transcriptEnd = useRef<HTMLDivElement>(null)

  function loadDatabases() {
    fetchDatabases()
      .then((list) => {
        setDatabasesError(null)
        setDatabases(list)
        setActiveId((current) => current ?? list.find((d) => d.status === 'ready')?.id ?? list[0]?.id ?? null)
      })
      .catch((error: unknown) => setDatabasesError(error instanceof ApiError ? error : new ApiError('Could not load databases.', 0)))
  }

  useEffect(() => {
    loadDatabases()
  }, [])

  useEffect(() => {
    transcriptEnd.current?.scrollIntoView({ block: 'end' })
    saveSession(
      turns.filter((t): t is LocalTurn & { result: AgentResult } => t.result != null).map((t) => ({ id: t.id, question: t.question, result: t.result })),
    )
  }, [turns])

  function submit(question: string, retryOf?: string) {
    const id = retryOf ?? crypto.randomUUID()
    const historyBefore = toHistory(turns.filter((t) => t.id !== id))
    setTurns((current) => {
      const withoutRetried = current.filter((t) => t.id !== id)
      return [...withoutRetried, { id, question, running: true }]
    })
    runQuery({ question, database_id: activeId ?? undefined, history: historyBefore })
      .then((result) => {
        setTurns((current) => current.map((t) => (t.id === id ? { ...t, running: false, result } : t)))
      })
      .catch((error: unknown) => {
        const transportError = error instanceof ApiError ? error : new ApiError('Something went wrong.', 0)
        setTurns((current) => current.map((t) => (t.id === id ? { ...t, running: false, transportError } : t)))
      })
  }

  function handleConnected(database: DatabaseInfo) {
    setDatabases((current) => [...current.filter((d) => d.id !== database.id), database])
    setActiveId(database.id)
    setDatabasesError(null)
    setPanel(null)
  }

  const active = databases.find((d) => d.id === activeId)
  const anyRunning = turns.some((t) => t.running)
  const disabled = anyRunning || (databases.length > 0 && !active) || active?.status === 'rejected'
  const disabledReason =
    active?.status === 'rejected'
      ? 'this database account is not read-only; queries are disabled'
      : anyRunning
        ? 'waiting on the previous question…'
        : undefined

  return (
    <div className="flex h-dvh flex-col">
      <SessionHeader
        databases={databases}
        activeId={activeId}
        onSelect={setActiveId}
        theme={theme}
        onToggleTheme={toggle}
        onConnect={() => setPanel(panel === 'connect' ? null : 'connect')}
        onSchema={() => setPanel(panel === 'schema' ? null : 'schema')}
        onHelp={() => setPanel(panel === 'help' ? null : 'help')}
      />
      {panel === 'connect' && <ConnectDatabaseForm onConnected={handleConnected} onCancel={() => setPanel(null)} />}
      {panel === 'schema' && active && (
        <SchemaBrowser databaseId={active.id} databaseName={active.name} onClose={() => setPanel(null)} />
      )}
      {panel === 'help' && <HelpPanel onClose={() => setPanel(null)} />}
      <main className="flex-1 overflow-y-auto px-4 sm:px-6">
        <div className="mx-auto max-w-4xl">
          {databasesError && (
            <p className="py-6 font-mono text-[14px] text-accent">
              [error] could not load databases: {databasesError.message}
            </p>
          )}
          {turns.length === 0 && !databasesError && <IntroBlock />}
          {turns.map((turn) => (
            <QueryBlock
              key={turn.id}
              question={turn.question}
              result={turn.result}
              transportError={turn.transportError}
              running={turn.running}
              onRetry={turn.transportError || turn.result?.status === 'error' ? () => submit(turn.question, turn.id) : undefined}
            />
          ))}
          <div ref={transcriptEnd} />
        </div>
      </main>
      <PromptForm
        onSubmit={submit}
        disabled={disabled}
        disabledReason={disabledReason}
        history={turns.map((t) => t.question)}
      />
      <Footer />
    </div>
  )
}

function Footer() {
  return (
    <footer className="border-t border-line px-4 py-2 sm:px-6">
      <p className="mx-auto max-w-4xl font-mono text-[12px] text-ink-faint">
        read-only always · SQL validated before it runs · demo data:{' '}
        <a href="https://github.com/owid/co2-data" className="underline decoration-line hover:text-ink-dim">
          Our World in Data, CO2 &amp; GHG emissions
        </a>{' '}
        (CC BY 4.0)
      </p>
    </footer>
  )
}
