import type { TraceEvent } from '../api/types'

// Bookkeeping markers with no real duration; the strip measures work, not the transcript.
const SKIP_STEPS = new Set(['question_received', 'completed'])

export function measuredSteps(trace: TraceEvent[]): TraceEvent[] {
  return trace.filter((event) => !SKIP_STEPS.has(event.step))
}

export function totalMs(trace: TraceEvent[]): number {
  return measuredSteps(trace).reduce((sum, event) => sum + event.duration_ms, 0)
}
