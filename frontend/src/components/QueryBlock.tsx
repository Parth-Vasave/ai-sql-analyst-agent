import { lazy, Suspense } from 'react'
import { ApiError, type AgentResult } from '../api/types'
import { ChecksRow } from './ChecksRow'
import { CopyButton } from './CopyButton'
import { ErrorBanner } from './ErrorBanner'
import { PlanBlock } from './PlanBlock'
import { ResultGrid } from './ResultGrid'
import { TraceStrip } from './TraceStrip'

const ResultChart = lazy(() => import('./ResultChart').then((m) => ({ default: m.ResultChart })))

interface QueryBlockProps {
  question: string
  result?: AgentResult
  transportError?: ApiError
  running: boolean
  onRetry?: () => void
}

export function QueryBlock({ question, result, transportError, running, onRetry }: QueryBlockProps) {
  return (
    <div className="border-b border-line py-4">
      <p className="font-mono text-[14px]">
        <span className="text-accent">{'>'}</span> {question}
      </p>
      <div className="mt-2 space-y-2 pl-[1.4rem]">
        {running && (
          <p className="font-mono text-[14px] text-ink-faint">
            running <span className="cursor-blink text-accent">▌</span>
          </p>
        )}
        {transportError && <ErrorBanner error={transportError} onRetry={onRetry} />}
        {result && <ResultBody result={result} onRetry={onRetry} />}
      </div>
    </div>
  )
}

function ResultBody({ result, onRetry }: { result: AgentResult; onRetry?: () => void }) {
  if (result.status === 'error') {
    return (
      <>
        {result.plan && <PlanBlock plan={result.plan} />}
        {result.sql && <SqlBlock sql={result.sql} />}
        <ErrorBanner
          error={new ApiError(result.error?.message ?? 'the query failed', 0)}
          onRetry={onRetry}
        />
      </>
    )
  }

  if (result.status === 'needs_clarification') {
    return (
      <p className="font-mono text-[14px] text-ink">
        <span className="text-accent">[clarify]</span> {result.clarification_question}
      </p>
    )
  }

  if (result.status === 'unanswerable') {
    return (
      <p className="font-mono text-[14px] text-ink">
        <span className="text-accent">[unanswerable]</span> {result.answer ?? result.explanation}
      </p>
    )
  }

  return (
    <>
      {result.plan && <PlanBlock plan={result.plan} />}
      {result.sql && <SqlBlock sql={result.sql} />}
      <TraceStrip trace={result.trace} retryCount={result.metadata.retry_count} />
      <ChecksRow checks={result.checks} />
      <ResultGrid
        columns={result.columns}
        rows={result.rows}
        units={result.column_units}
        executionTimeMs={result.metadata.execution_time_ms}
        truncated={result.metadata.truncated}
      />
      {result.chart && (
        <Suspense fallback={<div className="h-72 border border-line" aria-hidden="true" />}>
          <ResultChart chart={result.chart} columns={result.columns} rows={result.rows} units={result.column_units} />
        </Suspense>
      )}
      {result.answer && (
        <p className="max-w-[36rem] pt-1 text-[15px] leading-relaxed text-ink">
          {result.answer}
          {result.answer_source === 'template' && (
            <span className="ml-1.5 font-mono text-[12px] text-ink-faint">[answer_source: template]</span>
          )}
        </p>
      )}
    </>
  )
}

function SqlBlock({ sql }: { sql: string }) {
  return (
    <div className="flex items-start justify-between gap-2 border border-line bg-paper-raised px-2 py-1.5">
      <pre className="overflow-x-auto font-mono text-[13.5px] leading-relaxed whitespace-pre-wrap text-ink">
        <span className="text-accent">[sql] </span>
        {sql}
      </pre>
      <CopyButton text={sql} />
    </div>
  )
}
