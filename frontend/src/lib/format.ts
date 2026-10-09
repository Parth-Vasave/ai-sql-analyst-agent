export function formatMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(ms < 10_000 ? 2 : 1)}s`
}

/** A year is an identifier, not a quantity: 2015, never 2,015. */
export function isYearColumn(column: string): boolean {
  return /(^|_)year$/i.test(column)
}

/** A non-numeric value as text. JSON values (json_build_object, jsonb_agg) arrive as objects and
 * arrays, which String() would turn into "[object Object]" or a bare comma list. */
export function cellText(value: unknown): string {
  return typeof value === 'object' && value !== null ? JSON.stringify(value) : String(value)
}

/**
 * `digits` fixes the fraction digits so a right-aligned column's decimal points line up
 * (see `columnDecimals`); without it, a number shows up to 3 decimals as it comes.
 */
export function formatCell(value: unknown, unit?: string, column?: string, digits?: number): string {
  if (value === null || value === undefined) return '∅'
  if (typeof value === 'number' && column && isYearColumn(column) && Number.isInteger(value)) return String(value)
  if (typeof value === 'number') {
    const formatted =
      digits !== undefined
        ? value.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })
        : Number.isInteger(value)
          ? value.toLocaleString('en-US')
          : value.toLocaleString('en-US', { maximumFractionDigits: 3 })
    return unit ? `${formatted} ${unit}` : formatted
  }
  return cellText(value)
}

export function formatRowCount(n: number): string {
  return n === 1 ? '1 row' : `${n.toLocaleString('en-US')} rows`
}

/** A stable, readable label for a column, e.g. "co2 (Mt)". */
export function columnLabel(column: string, units: Record<string, string>): string {
  const unit = units[column]
  return unit ? `${column} (${unit})` : column
}

/** The most fraction digits any value in a numeric column needs, capped at 3. */
export function columnDecimals(rows: unknown[][], index: number): number {
  let digits = 0
  for (const row of rows) {
    const value = row[index]
    if (typeof value !== 'number' || Number.isInteger(value)) continue
    const fraction = value.toFixed(3).replace(/0+$/, '').split('.')[1] ?? ''
    digits = Math.max(digits, fraction.length)
    if (digits === 3) break
  }
  return digits
}
