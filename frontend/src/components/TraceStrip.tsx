import { formatMs } from '../lib/format'
import type { TraceEvent } from '../api/types'

// Bookkeeping markers with no real duration; the graticule measures work, not the transcript.
const SKIP_STEPS = new Set(['question_received', 'completed'])

function attemptOf(event: TraceEvent): number {
  const attempt = event.detail.attempt
  return typeof attempt === 'number' ? attempt : 1
}

/** A step is redone work — the original failure or anything after it — not forward progress. */
function isRedo(event: TraceEvent): boolean {
  return event.status === 'failed' || attemptOf(event) > 1
}

export function TraceStrip({ trace, retryCount }: { trace: TraceEvent[]; retryCount: number }) {
  const measured = trace.filter((event) => !SKIP_STEPS.has(event.step))
  if (measured.length === 0) return null
  const total = Math.max(measured.reduce((sum, event) => sum + event.duration_ms, 0), 1)
  const hasRedo = measured.some(isRedo)

  return (
    <div className="my-2">
      <div className="flex h-4 items-stretch gap-px border border-line" role="img" aria-label={traceSummary(measured)}>
        {measured.map((event, index) => (
          <div
            key={`${event.step}-${index}`}
            title={`${event.step} · ${formatMs(event.duration_ms)} · ${event.status}`}
            style={{ flexGrow: Math.max(event.duration_ms, total * 0.01), flexBasis: 0 }}
            className={segmentClass(event.status)}
          />
        ))}
      </div>
      {/* The redo overlay: a second, dimmer lane on the same graticule marking the spans that
          were repaired, so the repair shows in the measurement itself, not only in the labels. */}
      {hasRedo && (
        <div className="flex h-1.5 items-stretch gap-px" aria-hidden="true">
          {measured.map((event, index) => (
            <div
              key={`${event.step}-redo-${index}`}
              style={{ flexGrow: Math.max(event.duration_ms, total * 0.01), flexBasis: 0 }}
              className={isRedo(event) ? 'bg-ink-faint/40' : 'bg-transparent'}
            />
          ))}
        </div>
      )}
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 font-mono text-[12px] text-ink-faint">
        {measured.map((event, index) => (
          <span key={`${event.step}-label-${index}`} className={event.status === 'failed' ? 'text-accent' : undefined}>
            {event.step} {formatMs(event.duration_ms)}
          </span>
        ))}
        <span>total {formatMs(total)}</span>
        {retryCount > 0 && <span className="text-accent">retries {retryCount}</span>}
      </div>
    </div>
  )
}

function segmentClass(status: TraceEvent['status']): string {
  if (status === 'failed') return 'bg-accent-soft border-x border-accent'
  if (status === 'skipped') return 'bg-paper'
  return 'bg-paper-raised'
}

function traceSummary(trace: TraceEvent[]): string {
  return `execution trace: ${trace.map((e) => `${e.step} ${e.duration_ms}ms ${e.status}`).join(', ')}`
}
