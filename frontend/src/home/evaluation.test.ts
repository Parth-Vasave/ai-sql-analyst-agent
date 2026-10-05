import { describe, expect, it } from 'vitest'
import questionsJsonl from '../../../evaluation/results/20261004-061307-questions.jsonl?raw'
import safetyJsonl from '../../../evaluation/results/20261004-060622-sql-safety.jsonl?raw'
import { BLOCKED_STATEMENTS, LATENCY_MEDIAN_MS, MISSES, QUESTION_METRICS, QUESTION_RUN, SAFETY_RUN, SAFETY_VIOLATIONS } from './evaluation'

interface EvalRecord {
  id: string
  run_id: string
  model: string
  recorded_at: string
  expected_behavior: string
  status: string
  correct: boolean | null
  sql: string | null
  error: string | null
  latency_ms: number
  safety_violation?: boolean
}

/** Latest record per id, like evaluation/run.py load_records; unscored records are dropped. */
function scored(jsonl: string): EvalRecord[] {
  const latest = new Map<string, EvalRecord>()
  for (const line of jsonl.split('\n')) {
    if (!line.trim()) continue
    const record = JSON.parse(line) as EvalRecord
    if (record.id) latest.set(record.id, record)
  }
  return [...latest.values()].filter((r) => r.correct !== null)
}

const ratio = (records: EvalRecord[], hit: (r: EvalRecord) => boolean) => ({ correct: records.filter(hit).length, total: records.length })
const metric = (label: string) => QUESTION_METRICS.find((m) => m.label === label)!.value

// The homepage's numbers are recomputed from the recorded results the same way
// evaluation/report.py computes them, so the page cannot claim what the run did not record.
describe('recorded evaluation shown on the homepage', () => {
  const questions = scored(questionsJsonl)
  const safety = scored(safetyJsonl)
  const of = (behaviour: string) => questions.filter((r) => r.expected_behavior === behaviour)

  it('matches the question run metadata', () => {
    expect(new Set(questions.map((r) => r.run_id))).toEqual(new Set([QUESTION_RUN.runId]))
    expect(new Set(questions.map((r) => r.model))).toEqual(new Set([QUESTION_RUN.model]))
    expect(questions.every((r) => r.recorded_at.startsWith(QUESTION_RUN.date))).toBe(true)
  })

  it('matches every question metric', () => {
    expect(metric('Answer accuracy')).toEqual(ratio(questions, (r) => r.correct === true))
    expect(metric('SQL execution success')).toEqual(
      ratio(questions.filter((r) => ['query', 'empty'].includes(r.expected_behavior)), (r) => r.status === 'success'),
    )
    expect(metric('Result correctness (query questions)')).toEqual(ratio(of('query'), (r) => r.correct === true))
    expect(metric('Empty-result accuracy')).toEqual(ratio(of('empty'), (r) => r.correct === true))
    expect(metric('Clarification accuracy (ambiguous questions)')).toEqual(ratio(of('clarify'), (r) => r.correct === true))
    expect(metric('Refusals (safety questions)')).toEqual(ratio(of('refuse'), (r) => r.status !== 'success'))
    expect(SAFETY_VIOLATIONS).toBe(questions.filter((r) => r.safety_violation).length)

    const latencies = questions.map((r) => r.latency_ms).sort((a, b) => a - b)
    const mid = latencies.length / 2
    const median = latencies.length % 2 ? latencies[Math.floor(mid)] : (latencies[mid - 1] + latencies[mid]) / 2
    expect(LATENCY_MEDIAN_MS).toBe(Math.round(median))
  })

  it('lists exactly the questions the run got wrong', () => {
    expect(MISSES.map((m) => m.id).sort()).toEqual(questions.filter((r) => !r.correct).map((r) => r.id).sort())
  })

  it('shows every adversarial statement with the validator response it recorded', () => {
    expect(new Set(safety.map((r) => r.run_id))).toEqual(new Set([SAFETY_RUN.runId]))
    expect(safety.every((r) => r.correct === true && r.status === 'error')).toBe(true)
    expect(BLOCKED_STATEMENTS).toHaveLength(safety.length)
    for (const statement of BLOCKED_STATEMENTS) {
      const record = safety.find((r) => r.id === statement.id)
      expect(record, statement.id).toBeDefined()
      expect(record!.sql).toBe(statement.sql)
      expect(record!.error).toBe(statement.response)
    }
  })
})
