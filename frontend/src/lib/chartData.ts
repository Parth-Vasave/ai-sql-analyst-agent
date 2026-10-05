import type { ChartSpec } from '../api/types'

/**
 * Charts get their own quiet, non-alert palette: the accent color (amber) means focus, warning
 * or error everywhere else and must never appear here, or a routine chart would read as an alert. Mid-tone hues, none in the amber/orange/red range, legible on both
 * near-white and near-black grounds.
 */
export const SERIES_COLORS = [
  '#3b6e8c', // steel blue
  '#6e5a9c', // violet
  '#3b8c6e', // teal green
  '#8c3b6e', // wine
  '#6e8c3b', // olive
  '#3b4f8c', // indigo
  '#7a3b8c', // purple
  '#3b8c9e', // cyan-teal
]

export type Row = Record<string, unknown>

export function toRecords(columns: string[], rows: unknown[][]): Row[] {
  return rows.map((row) => {
    const record: Row = {}
    columns.forEach((column, index) => {
      record[column] = row[index]
    })
    return record
  })
}

/** For a line chart with `series`: one row per x value, one numeric key per series value. */
export function pivotBySeries(
  records: Row[],
  x: string,
  y: string,
  series: string,
): { data: Row[]; seriesKeys: string[] } {
  const byX = new Map<unknown, Row>()
  const seriesKeys: string[] = []
  for (const record of records) {
    const xValue = record[x]
    const seriesValue = String(record[series])
    if (!seriesKeys.includes(seriesValue)) seriesKeys.push(seriesValue)
    if (!byX.has(xValue)) byX.set(xValue, { [x]: xValue })
    byX.get(xValue)![seriesValue] = record[y]
  }
  return { data: Array.from(byX.values()), seriesKeys }
}

export function statValue(spec: ChartSpec, columns: string[], rows: unknown[][]): { value: unknown; label: string } {
  const column = spec.y[0] ?? columns[0]
  const value = rows[0]?.[columns.indexOf(column)]
  const label = spec.label ? String(rows[0]?.[columns.indexOf(spec.label)] ?? column) : column
  return { value, label }
}
