import { useEffect, useRef, useState } from 'react'
import { fetchDatabases, runQuery } from './api/client'
import { ApiError, type AgentResult, type DatabaseInfo, type Turn } from './api/types'
import { ChatTurn } from './components/ChatTurn'
import { Composer } from './components/Composer'
import { ConnectDatabaseForm } from './components/ConnectDatabaseForm'
import { EmptyState } from './components/EmptyState'
import { HelpPanel } from './components/HelpPanel'
import { MenuIcon, NewChatIcon, SidebarIcon } from './components/icons'
import { SchemaBrowser } from './components/SchemaBrowser'
import { SettingsMenu } from './components/SettingsMenu'
import { Sidebar } from './components/Sidebar'
import { useMediaQuery } from './hooks/useMediaQuery'
import { useTheme } from './hooks/useTheme'
import { chatTitle, loadChats, saveChats } from './lib/chats'

interface LocalTurn {
  id: string
  question: string
  running: boolean
  stopped?: boolean
  result?: AgentResult
  transportError?: ApiError
}

interface Chat {
  id: string
  title: string
  createdAt: number
  updatedAt: number
  turns: LocalTurn[]
}

const MAX_HISTORY_TURNS = 3

/** Prior turns sent as context — only those asked against the same database. */
function toHistory(turns: LocalTurn[], databaseId: string | undefined): Turn[] {
  return turns
    .filter((t) => t.result && (!databaseId || t.result.metadata.database_id === databaseId))
    .slice(-MAX_HISTORY_TURNS)
    .map((t) => ({
      question: t.result!.resolved_question ?? t.result!.question,
      sql: t.result!.sql,
      answer: t.result!.answer,
    }))
}

type DialogName = 'connect' | 'schema' | 'help' | null

export default function App() {
  const { preference, setPreference } = useTheme()
  const isMobile = useMediaQuery('(max-width: 767.98px)')
  const [sidebarOpen, setSidebarOpen] = useState(() => !window.matchMedia('(max-width: 767.98px)').matches)
  const [databases, setDatabases] = useState<DatabaseInfo[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [databasesError, setDatabasesError] = useState<ApiError | null>(null)
  const [dialog, setDialog] = useState<DialogName>(null)
  const [chats, setChats] = useState<Chat[]>(() =>
    loadChats().map((c) => ({ ...c, turns: c.turns.map((t) => ({ ...t, running: false })) })),
  )
  const [currentId, setCurrentId] = useState<string | null>(null)
  const scroller = useRef<HTMLElement>(null)
  // A freshly asked question scrolls to the top of the pane so its answer reads downward from it.
  const followTurn = useRef<string | null>(null)
  // In-flight requests by turn, so Stop can abandon one. The server may still finish it; the
  // answer is simply not waited for.
  const inFlight = useRef(new Map<string, AbortController>())

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

  // The mobile drawer closes on Escape like any other overlay.
  useEffect(() => {
    if (!isMobile || !sidebarOpen) return
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && setSidebarOpen(false)
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [isMobile, sidebarOpen])

  useEffect(() => {
    saveChats(
      chats
        .map((c) => ({
          id: c.id,
          title: c.title,
          createdAt: c.createdAt,
          updatedAt: c.updatedAt,
          turns: c.turns.filter((t): t is LocalTurn & { result: AgentResult } => t.result != null).map((t) => ({ id: t.id, question: t.question, result: t.result })),
        }))
        .filter((c) => c.turns.length > 0),
    )
  }, [chats])

  const current = chats.find((c) => c.id === currentId) ?? null

  useEffect(() => {
    const followed = current?.turns.find((t) => t.id === followTurn.current)
    if (followed) {
      document.getElementById(`turn-${followed.id}`)?.scrollIntoView({ block: 'start' })
      if (!followed.running) followTurn.current = null
    }
  }, [current])

  // Opening an existing chat lands at its latest answer, like returning to a conversation.
  useEffect(() => {
    if (followTurn.current) return
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight })
  }, [currentId])

  function updateTurn(chatId: string, turnId: string, patch: Partial<LocalTurn>) {
    setChats((all) =>
      all.map((c) =>
        c.id === chatId ? { ...c, updatedAt: Date.now(), turns: c.turns.map((t) => (t.id === turnId ? { ...t, ...patch } : t)) } : c,
      ),
    )
  }

  function submit(question: string, retryOf?: string) {
    const now = Date.now()
    const chatId = currentId ?? crypto.randomUUID()
    const turnId = retryOf ?? crypto.randomUUID()
    const priorTurns = (current?.turns ?? []).filter((t) => t.id !== turnId)
    const history = toHistory(priorTurns, activeId ?? undefined)
    const turn: LocalTurn = { id: turnId, question, running: true }
    followTurn.current = turnId

    setChats((all) => {
      const existing = all.find((c) => c.id === chatId)
      if (!existing) return [{ id: chatId, title: chatTitle(question), createdAt: now, updatedAt: now, turns: [turn] }, ...all]
      return all.map((c) => (c.id === chatId ? { ...c, updatedAt: now, turns: [...c.turns.filter((t) => t.id !== turnId), turn] } : c))
    })
    setCurrentId(chatId)
    if (isMobile) setSidebarOpen(false)

    const controller = new AbortController()
    inFlight.current.set(turnId, controller)
    runQuery({ question, database_id: activeId ?? undefined, history }, controller.signal)
      .then((result) => updateTurn(chatId, turnId, { running: false, stopped: false, result, transportError: undefined }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          updateTurn(chatId, turnId, { running: false, stopped: true })
          return
        }
        const transportError = error instanceof ApiError ? error : new ApiError('Something went wrong.', 0)
        updateTurn(chatId, turnId, { running: false, transportError })
      })
      .finally(() => inFlight.current.delete(turnId))
  }

  function stopCurrent() {
    current?.turns.filter((t) => t.running).forEach((t) => inFlight.current.get(t.id)?.abort())
  }

  function newChat() {
    setCurrentId(null)
    if (isMobile) setSidebarOpen(false)
  }

  function selectChat(id: string) {
    setCurrentId(id)
    if (isMobile) setSidebarOpen(false)
  }

  function deleteChat(id: string) {
    setChats((all) => all.filter((c) => c.id !== id))
    if (id === currentId) setCurrentId(null)
  }

  function handleConnected(database: DatabaseInfo) {
    setDatabases((all) => [...all.filter((d) => d.id !== database.id), database])
    setActiveId(database.id)
    setDatabasesError(null)
    setDialog(null)
  }

  const active = databases.find((d) => d.id === activeId)
  const currentRunning = current?.turns.some((t) => t.running) ?? false
  const noReadyDatabase = databases.length > 0 && !active
  const disabled = currentRunning || noReadyDatabase || active?.status === 'rejected'
  const disabledReason =
    active?.status === 'rejected'
      ? 'This database account is not read-only, so questions are disabled'
      : currentRunning
        ? 'Waiting for the answer…'
        : undefined

  const composer = (
    <Composer
      onSubmit={submit}
      disabled={disabled}
      disabledReason={disabledReason}
      placeholder={current ? 'Ask a follow-up' : undefined}
      history={current?.turns.map((t) => t.question) ?? []}
      onStop={currentRunning ? stopCurrent : undefined}
    />
  )

  const settings = (
    <SettingsMenu
      databases={databases}
      activeId={activeId}
      onSelectDatabase={setActiveId}
      onConnect={() => setDialog('connect')}
      onSchema={() => setDialog('schema')}
      onHelp={() => setDialog('help')}
      theme={preference}
      onTheme={setPreference}
    />
  )

  const sidebar = (
    <Sidebar
      chats={chats.map((c) => ({ id: c.id, title: c.title, updatedAt: c.updatedAt, running: c.turns.some((t) => t.running) }))}
      currentId={currentId}
      onSelect={selectChat}
      onNewChat={newChat}
      onDelete={deleteChat}
      onClose={() => setSidebarOpen(false)}
      closeLabel={isMobile ? 'Close menu' : 'Collapse sidebar'}
      footer={settings}
    />
  )

  return (
    <div className="flex h-dvh overflow-hidden">
      {isMobile ? (
        sidebarOpen && (
          <div className="fixed inset-0 z-40 flex" role="dialog" aria-modal="true" aria-label="Chats">
            <div className="absolute inset-0 bg-black/40" onClick={() => setSidebarOpen(false)} aria-hidden="true" />
            <div className="rise-in relative h-full shadow-[var(--shadow-menu)]">{sidebar}</div>
          </div>
        )
      ) : (
        sidebarOpen && <div className="h-full shrink-0 border-r border-line">{sidebar}</div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-13 shrink-0 items-center gap-1 px-2 sm:px-3">
          {(isMobile || !sidebarOpen) && (
            <>
              <button
                type="button"
                onClick={() => setSidebarOpen(true)}
                aria-label="Open sidebar"
                className="rounded-lg p-2 text-ink-dim transition-colors hover:bg-raised hover:text-ink"
              >
                {isMobile ? <MenuIcon /> : <SidebarIcon />}
              </button>
              <button
                type="button"
                onClick={newChat}
                aria-label="New chat"
                className="rounded-lg p-2 text-ink-dim transition-colors hover:bg-raised hover:text-ink"
              >
                <NewChatIcon />
              </button>
            </>
          )}
          {current && <p className="ml-2 min-w-0 truncate text-[14px] text-ink-dim">{current.title}</p>}
        </header>

        <main ref={scroller} className="flex-1 overflow-y-auto">
          {current && (
            <div className="pointer-events-none sticky top-0 z-10 -mb-5 h-5 bg-linear-to-b from-surface to-transparent" aria-hidden="true" />
          )}
          {databasesError && (
            <div className="mx-auto max-w-3xl px-4 pt-4 sm:px-6">
              <p className="rounded-xl border border-accent/40 bg-accent-soft px-4 py-3 text-[14px]" role="alert">
                Could not load databases: {databasesError.message}{' '}
                <button type="button" onClick={loadDatabases} className="font-medium underline underline-offset-4">
                  Try again
                </button>
              </p>
            </div>
          )}
          {current ? (
            <div className="mx-auto max-w-3xl px-4 pb-10 sm:px-6">
              {current.turns.map((turn) => (
                <ChatTurn
                  key={turn.id}
                  id={`turn-${turn.id}`}
                  question={turn.question}
                  result={turn.result}
                  transportError={turn.transportError}
                  running={turn.running}
                  stopped={turn.stopped}
                  onRetry={turn.transportError || turn.stopped || turn.result?.status === 'error' ? () => submit(turn.question, turn.id) : undefined}
                />
              ))}
            </div>
          ) : (
            <EmptyState
              databaseId={active?.id ?? null}
              databaseName={active?.name ?? null}
              composer={composer}
              onAsk={disabled ? undefined : submit}
              onBrowseSchema={() => setDialog('schema')}
              onHowItWorks={() => setDialog('help')}
            />
          )}
        </main>

        {current && (
          <div className="mx-auto w-full max-w-3xl px-3 pb-2 sm:px-6">
            {composer}
            <p className="px-2 pt-2 text-center text-[12px] text-ink-faint">
              {active ? `${active.name} · ` : ''}read-only · SQL is validated before it runs ·{' '}
              <a href="https://github.com/owid/co2-data" className="underline decoration-line underline-offset-2 hover:text-ink-dim">
                demo data: Our World in Data
              </a>{' '}
              (CC BY 4.0)
            </p>
          </div>
        )}
      </div>

      {dialog === 'connect' && <ConnectDatabaseForm onConnected={handleConnected} onCancel={() => setDialog(null)} />}
      {dialog === 'schema' && active && <SchemaBrowser databaseId={active.id} databaseName={active.name} onClose={() => setDialog(null)} />}
      {dialog === 'help' && <HelpPanel onClose={() => setDialog(null)} />}
    </div>
  )
}
