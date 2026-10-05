import { formatMs } from '../lib/format'
import { measuredSteps, totalMs } from '../lib/trace'
import type { TraceEvent } from '../api/types'

function attemptOf(event: TraceEvent): number {
  const attempt = event.detail.attempt
  return typeof attempt === 'number' ? attempt : 1
}

/** A step is redone work — the original failure or anything after it — not forward progress. */
function isRedo(event: TraceEvent): boolean {
  return event.status === 'failed' || attemptOf(event) > 1
}

/** Each backend step plotted to scale on one bar, so where the time went is visible at a glance. */
export function TraceStrip({ trace, retryCount }: { trace: TraceEvent[]; retryCount: number }) {
  const measured = measuredSteps(trace)
  if (measured.length === 0) return null
  const total = Math.max(totalMs(trace), 1)
  const hasRedo = measured.some(isRedo)
  const grow = (event: TraceEvent) => Math.max(event.duration_ms, total * 0.012)

  return (
    <div>
      <div className="flex h-2 items-stretch gap-0.5 overflow-hidden rounded-full" role="img" aria-label={traceSummary(measured)}>
        {measured.map((event, index) => (
          <div
            key={`${event.step}-${index}`}
            title={`${event.step} · ${formatMs(event.duration_ms)} · ${event.status}`}
            style={{ flexGrow: grow(event), flexBasis: 0 }}
            className={segmentClass(event.status)}
          />
        ))}
      </div>
      {/* The redo lane: marks the spans that were repaired, so a retry shows in the measurement itself. */}
      {hasRedo && (
        <div className="mt-0.5 flex h-1 items-stretch gap-0.5" aria-hidden="true">
          {measured.map((event, index) => (
            <div
              key={`${event.step}-redo-${index}`}
              style={{ flexGrow: grow(event), flexBasis: 0 }}
              className={isRedo(event) ? 'rounded-full bg-accent/40' : ''}
            />
          ))}
        </div>
      )}
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12.5px] text-ink-faint">
        {measured.map((event, index) => (
          <li key={`${event.step}-label-${index}`} className={event.status === 'failed' ? 'text-accent' : undefined}>
            <span className="font-mono">{event.step}</span> <span className="tabular-nums">{formatMs(event.duration_ms)}</span>
            {event.status === 'failed' && ' · failed'}
          </li>
        ))}
        {retryCount > 0 && <li className="text-accent">retries {retryCount}</li>}
      </ul>
    </div>
  )
}

function segmentClass(status: TraceEvent['status']): string {
  if (status === 'failed') return 'bg-accent'
  if (status === 'skipped') return 'bg-line'
  return 'bg-ink-faint/45'
}

function traceSummary(trace: TraceEvent[]): string {
  return `execution trace: ${trace.map((e) => `${e.step} ${e.duration_ms}ms ${e.status}`).join(', ')}`
}
