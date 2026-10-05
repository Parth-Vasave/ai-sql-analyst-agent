import { lazy, Suspense, useEffect, useState, type ReactNode } from 'react'
import { ApiError, type AgentResult } from '../api/types'
import { CopyButton } from './CopyButton'
import { ErrorBanner } from './ErrorBanner'
import { QuestionBubbleIcon } from './icons'
import { ResultGrid } from './ResultGrid'
import { CheckWarnings, Verification } from './Verification'

const ResultChart = lazy(() => import('./ResultChart').then((m) => ({ default: m.ResultChart })))

interface ChatTurnProps {
  id?: string
  question: string
  result?: AgentResult
  transportError?: ApiError
  running: boolean
  stopped?: boolean
  onRetry?: () => void
}

export function ChatTurn({ id, question, result, transportError, running, stopped = false, onRetry }: ChatTurnProps) {
  return (
    <article id={id} className="scroll-mt-4 py-5">
      <div className="flex justify-end">
        <p className="max-w-[85%] rounded-3xl bg-raised px-4 py-2.5 text-[15px] leading-relaxed whitespace-pre-wrap text-ink sm:max-w-[75%]">
          {question}
        </p>
      </div>
      <div className="mt-5 flex flex-col gap-4">
        {running && <Working />}
        {stopped && (
          <p className="flex items-center gap-3 text-[14px] text-ink-faint">
            Stopped before an answer came back.
            {onRetry && (
              <button type="button" onClick={onRetry} className="font-medium text-ink-dim underline underline-offset-4 hover:text-ink">
                Ask again
              </button>
            )}
          </p>
        )}
        {transportError && <ErrorBanner error={transportError} onRetry={onRetry} />}
        {result && <Answer result={result} onRetry={onRetry} />}
      </div>
    </article>
  )
}

function Answer({ result, onRetry }: { result: AgentResult; onRetry?: () => void }) {
  if (result.status === 'error') {
    return (
      <>
        <ErrorBanner {...describeAgentError(result.error?.message ?? 'The query failed.', result.metadata.request_id)} onRetry={onRetry} />
        {(result.plan || result.sql || result.trace.length > 0) && <Verification result={result} />}
      </>
    )
  }

  if (result.status === 'needs_clarification') {
    return (
      <div className="flex flex-col gap-2">
        <Label>Needs a little more detail</Label>
        <Prose>{result.clarification_question}</Prose>
      </div>
    )
  }

  if (result.status === 'unanswerable') {
    return (
      <div className="flex flex-col gap-2">
        <Label>Not answerable from this database</Label>
        <Prose>{result.answer ?? result.explanation}</Prose>
      </div>
    )
  }

  const assumptions = result.plan?.assumptions ?? []

  return (
    <>
      <Verification result={result} />
      {result.answer && (
        <div>
          <Prose>{result.answer}</Prose>
          {assumptions.length > 0 && (
            <p className="mt-2 text-[13.5px] text-ink-faint">Assumed: {joinSentences(assumptions)}</p>
          )}
        </div>
      )}
      <CheckWarnings checks={result.checks} />
      <ResultGrid
        columns={result.columns}
        rows={result.rows}
        units={result.column_units}
        executionTimeMs={result.metadata.execution_time_ms}
        truncated={result.metadata.truncated}
      />
      {result.chart && result.chart.type !== 'none' && (
        <Suspense fallback={<div className="h-72 rounded-xl border border-line" aria-hidden="true" />}>
          <ResultChart chart={result.chart} columns={result.columns} rows={result.rows} units={result.column_units} />
        </Suspense>
      )}
      {result.answer && (
        <div className="-mt-1 -ml-2 flex">
          <CopyButton text={result.answer} label="Copy answer" />
        </div>
      )}
    </>
  )
}

export function Prose({ children }: { children: ReactNode }) {
  return <p className="max-w-[42rem] text-[15.5px] leading-7 text-ink">{children}</p>
}

function Label({ children }: { children: ReactNode }) {
  return (
    <p className="flex items-center gap-2 text-[13.5px] font-medium text-ink-dim">
      <QuestionBubbleIcon size={16} className="text-ink-faint" />
      {children}
    </p>
  )
}

/** Elapsed seconds, so a slow model call reads as progress rather than a hang. */
export function Working() {
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    const interval = setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => clearInterval(interval)
  }, [])

  return (
    <p className="flex items-center gap-2.5 text-[14px] text-ink-dim" role="status">
      <span className="flex gap-1" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <span key={i} className="pulse-dot size-1.5 rounded-full bg-ink-dim" style={{ animationDelay: `${i * 160}ms` }} />
        ))}
      </span>
      Writing and validating SQL
      <span className="text-ink-faint tabular-nums">{seconds}s</span>
    </p>
  )
}

/** Model-written assumptions arrive as loose sentences; join them without doubled punctuation. */
function joinSentences(parts: string[]): string {
  return `${parts.map((part) => part.trim().replace(/[.;\s]+$/, '')).join('; ')}.`
}

/** Agent failures in product language, with the recovery; the raw message stays when it is already specific. */
function describeAgentError(message: string, requestId: string | null): { title: string; error: ApiError } {
  if (/provider returned HTTP 429/i.test(message)) {
    return {
      title: 'The model provider is rate-limiting requests',
      error: new ApiError('Wait a minute, then retry.', 0, null, requestId),
    }
  }
  if (/LLM provider/i.test(message)) {
    return { title: 'The model provider had a problem', error: new ApiError(`${message}. Retry in a moment.`, 0, null, requestId) }
  }
  return { title: 'The question could not be answered', error: new ApiError(message, 0, null, requestId) }
}
