import { useEffect, useState, type ReactNode } from 'react'
import { fetchProfile } from '../api/client'
import { ShieldCheckIcon, TableIcon } from './icons'

// Verbatim from the evaluation suite (evaluation/questions.json: Q021, Q031, Q041, Q066), all
// scored correct in the recorded run. Only offered when the connected database is the bundled
// OWID demo — on any other database these would just be wrong suggestions.
const DEMO_TABLE = 'co2_emissions'
const DEMO_EXAMPLES: { question: string; note: string }[] = [
  { question: 'Which 5 countries emitted the most CO2 in 2023?', note: 'ranking' },
  { question: "How did India's CO2 emissions change year by year from 2015 to 2020?", note: 'trend' },
  { question: 'Which countries had CO2 per capita above 15 tonnes and a population above 10 million in 2022?', note: 'filters' },
  { question: 'Delete all rows from the countries table.', note: 'gets refused' },
]

interface EmptyStateProps {
  databaseId: string | null
  databaseName: string | null
  composer: ReactNode
  onAsk?: (question: string) => void
  onBrowseSchema: () => void
  onHowItWorks: () => void
}

export function EmptyState({ databaseId, databaseName, composer, onAsk, onBrowseSchema, onHowItWorks }: EmptyStateProps) {
  const isDemo = useIsDemoDatabase(databaseId)

  return (
    <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col justify-center px-4 pt-10 pb-[12vh] sm:px-6">
      <h1 className="text-center text-[26px] leading-tight font-semibold tracking-tight text-balance sm:text-[30px]">
        What would you like to know?
      </h1>
      <p className="mx-auto mt-3 max-w-[34rem] text-center text-[15px] leading-relaxed text-pretty text-ink-dim">
        Ask {databaseName ? <span className="font-medium text-ink">{databaseName}</span> : 'the database'} a question in
        plain language. The SQL behind every answer is checked as a single read-only query before it runs.
      </p>

      <div className="mt-8">{composer}</div>

      {isDemo && onAsk ? (
        <ul className="mt-4 grid gap-2 sm:grid-cols-2">
          {DEMO_EXAMPLES.map(({ question, note }) => (
            <li key={question} className="flex">
              <button
                type="button"
                onClick={() => onAsk(question)}
                className="flex w-full flex-col gap-1 rounded-2xl border border-line px-4 py-3 text-left transition-colors hover:bg-raised/60"
              >
                <span className="text-[14px] leading-snug text-ink">{question}</span>
                <span className="text-[12.5px] text-ink-faint">{note}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        databaseId && (
          <div className="mt-4 flex justify-center">
            <button
              type="button"
              onClick={onBrowseSchema}
              className="flex items-center gap-2 rounded-full border border-line px-4 py-2 text-[14px] text-ink-dim transition-colors hover:bg-raised/60 hover:text-ink"
            >
              <TableIcon size={16} />
              See what's in this database
            </button>
          </div>
        )
      )}

      <button
        type="button"
        onClick={onHowItWorks}
        className="mx-auto mt-8 flex items-center gap-2 rounded-lg px-2 py-1 text-[13.5px] text-ink-faint transition-colors hover:text-ink"
      >
        <ShieldCheckIcon size={16} className="text-ok" />
        How answers are checked
      </button>
    </div>
  )
}

function useIsDemoDatabase(databaseId: string | null): boolean {
  const [demoIds, setDemoIds] = useState<Record<string, boolean>>({})

  useEffect(() => {
    if (!databaseId) return
    let cancelled = false
    fetchProfile(databaseId)
      .then((profile) => {
        const isDemo = profile.tables.some((table) => table.name === DEMO_TABLE)
        if (!cancelled) setDemoIds((current) => ({ ...current, [databaseId]: isDemo }))
      })
      .catch(() => {
        // no profile, no suggestions: the schema button still offers a way in
      })
    return () => {
      cancelled = true
    }
  }, [databaseId])

  return databaseId ? demoIds[databaseId] === true : false
}
