import type { DatabaseInfo } from '../api/types'

const STATUS_LABEL: Record<DatabaseInfo['status'], string> = {
  ready: 'ready',
  rejected: 'rejected: not read-only',
  unavailable: 'unavailable',
}

interface SessionHeaderProps {
  databases: DatabaseInfo[]
  activeId: string | null
  onSelect: (id: string) => void
  theme: 'light' | 'dark'
  onToggleTheme: () => void
  onConnect: () => void
  onSchema: () => void
  onLlmKey: () => void
  onHelp: () => void
  onRemove: (id: string) => void
  removing: boolean
}

export function SessionHeader({
  databases,
  activeId,
  onSelect,
  theme,
  onToggleTheme,
  onConnect,
  onSchema,
  onLlmKey,
  onHelp,
  onRemove,
  removing,
}: SessionHeaderProps) {
  const active = databases.find((d) => d.id === activeId) ?? databases[0]

  return (
    <header className="border-b border-line px-4 py-3 sm:px-6">
      <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-x-3 gap-y-2">
        <div className="flex min-w-0 items-center gap-2 font-mono text-[14px] leading-none whitespace-nowrap">
          <span className="text-accent" aria-hidden="true">
            {'>_'}
          </span>
          <h1 className="m-0 font-mono text-[14px] leading-none font-medium">ai-sql-analyst</h1>
          <span className="text-ink-faint" aria-hidden="true">
            ·
          </span>
          {active ? (
            <>
              {databases.length > 1 ? (
                <select
                  aria-label="Connected database"
                  value={active.id}
                  onChange={(event) => onSelect(event.target.value)}
                  className="max-w-[9rem] truncate rounded-none border-none bg-transparent p-0 font-mono text-[14px] text-ink underline decoration-line decoration-1 underline-offset-4 outline-none focus-visible:ring-1 focus-visible:ring-accent sm:max-w-none"
                >
                  {databases.map((db) => (
                    <option key={db.id} value={db.id}>
                      {db.name}
                    </option>
                  ))}
                </select>
              ) : (
                <span className="truncate">{active.name}</span>
              )}
              <span className="hidden text-ink-faint sm:inline">
                ({active.dialect}, read-only, sampling: {active.sampling})
              </span>
              <StatusDot status={active.status} />
              <span className="hidden text-ink-dim sm:inline">{STATUS_LABEL[active.status]}</span>
              {active.source === 'ui' && (
                <button
                  type="button"
                  onClick={() => onRemove(active.id)}
                  disabled={removing}
                  className="text-ink-faint underline decoration-line decoration-1 underline-offset-4 transition-colors hover:text-accent disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {removing ? 'removing…' : 'remove'}
                </button>
              )}
            </>
          ) : (
            <span className="text-ink-faint">no database configured</span>
          )}
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onSchema}
            disabled={!active}
            className="rounded-none border border-line px-2 py-1 font-mono text-[12px] text-ink-dim transition-colors hover:border-ink-faint hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="Browse the active database's schema"
          >
            :schema
          </button>
          <button
            type="button"
            onClick={onConnect}
            className="rounded-none border border-line px-2 py-1 font-mono text-[12px] text-ink-dim transition-colors hover:border-ink-faint hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
            aria-label="Connect a database"
          >
            :connect
          </button>
          <button
            type="button"
            onClick={onLlmKey}
            className="rounded-none border border-line px-2 py-1 font-mono text-[12px] text-ink-dim transition-colors hover:border-ink-faint hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
            aria-label="Configure the LLM key"
          >
            :llm-key
          </button>
          <button
            type="button"
            onClick={onHelp}
            className="rounded-none border border-line px-2 py-1 font-mono text-[12px] text-ink-dim transition-colors hover:border-ink-faint hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
            aria-label="Open help"
          >
            :help
          </button>
          <button
            type="button"
            onClick={onToggleTheme}
            className="rounded-none border border-line px-2 py-1 font-mono text-[12px] text-ink-dim transition-colors hover:border-ink-faint hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
            aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
          >
            <span className="sm:hidden">{theme === 'dark' ? ':theme light' : ':theme dark'}</span>
            <span className="hidden sm:inline">{theme === 'dark' ? ':set theme light' : ':set theme dark'}</span>
          </button>
        </div>
      </div>
    </header>
  )
}

function StatusDot({ status }: { status: DatabaseInfo['status'] }) {
  // "ready" is the unremarkable case, reported in plain ink. "rejected" (not read-only) is a
  // genuine alert and reuses the one reserved accent rather than introducing a second hue.
  const color = status === 'ready' ? 'bg-ink-dim' : status === 'rejected' ? 'bg-accent' : 'bg-ink-faint'
  return <span className={`inline-block h-[7px] w-[7px] rounded-full ${color}`} aria-hidden="true" />
}
