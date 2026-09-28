export function formatMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(ms < 10_000 ? 2 : 1)}s`
}

export function formatCell(value: unknown, unit?: string): string {
  if (value === null || value === undefined) return '∅'
  if (typeof value === 'number') {
    const formatted = Number.isInteger(value) ? value.toLocaleString('en-US') : value.toLocaleString('en-US', { maximumFractionDigits: 3 })
    return unit ? `${formatted} ${unit}` : formatted
  }
  return String(value)
}

export function formatRowCount(n: number): string {
  return n === 1 ? '1 row' : `${n.toLocaleString('en-US')} rows`
}

/** A stable, readable label for a column, e.g. "co2 (Mt)". */
export function columnLabel(column: string, units: Record<string, string>): string {
  const unit = units[column]
  return unit ? `${column} (${unit})` : column
}
