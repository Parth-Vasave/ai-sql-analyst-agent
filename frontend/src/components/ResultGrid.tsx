import { downloadCsv, toCsv } from '../lib/csv'
import { columnDecimals, columnLabel, formatCell, formatRowCount, isYearColumn } from '../lib/format'
import { DownloadIcon } from './icons'

const MAX_RENDERED_ROWS = 200

interface ResultGridProps {
  columns: string[]
  rows: unknown[][]
  units: Record<string, string>
  executionTimeMs: number | null
  truncated: boolean
}

export function ResultGrid({ columns, rows, units, executionTimeMs, truncated }: ResultGridProps) {
  if (columns.length === 0) return null
  const shown = rows.slice(0, MAX_RENDERED_ROWS)
  // Years are labels, not magnitudes: they stay left-aligned with the text columns.
  const numeric = columns.map((column, index) => !isYearColumn(column) && isNumericColumn(rows, index))
  // Fixed fraction digits per numeric column, so right-aligned decimal points line up.
  const digits = columns.map((_, index) => (numeric[index] ? columnDecimals(rows, index) : undefined))

  return (
    <div className="overflow-hidden rounded-xl border border-line">
      <div className="scroll-shadow-x max-h-[26rem] overflow-auto">
        <table className="w-full min-w-max border-collapse text-[13.5px] tabular-nums sm:text-[14px]">
          <thead className="sticky top-0 z-10 bg-code">
            <tr className="text-left">
              {columns.map((column, index) => (
                <th
                  key={column}
                  scope="col"
                  className={`border-b border-line px-2.5 py-2 text-[13px] font-medium whitespace-nowrap sm:px-3 text-ink-dim ${numeric[index] ? 'text-right' : ''}`}
                >
                  {columnLabel(column, units)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((row, rowIndex) => (
              <tr key={rowIndex} className="border-b border-line last:border-b-0 hover:bg-code/60">
                {row.map((value, columnIndex) => (
                  <td
                    key={columnIndex}
                    className={`px-2.5 py-1.5 whitespace-nowrap sm:px-3 ${numeric[columnIndex] ? 'text-right' : ''} ${value === null ? 'text-ink-faint' : ''}`}
                  >
                    {formatCell(value, units[columns[columnIndex]], columns[columnIndex], digits[columnIndex])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between gap-3 border-t border-line px-3 py-1.5 text-[13px] text-ink-faint">
        <span>
          {formatRowCount(rows.length)}
          {rows.length > MAX_RENDERED_ROWS ? `, showing first ${MAX_RENDERED_ROWS}` : ''}
          {truncated ? ' · capped at the row limit' : ''}
          {executionTimeMs !== null && ` · ${executionTimeMs} ms`}
        </span>
        <button
          type="button"
          onClick={() => downloadCsv('result.csv', toCsv(columns, rows))}
          className="-mr-1.5 flex items-center gap-1.5 rounded-lg px-1.5 py-1 transition-colors hover:bg-raised hover:text-ink"
        >
          <DownloadIcon size={15} />
          CSV
        </button>
      </div>
    </div>
  )
}

/** Numbers align right so magnitudes compare at a glance; a column of only NULLs stays left. */
function isNumericColumn(rows: unknown[][], index: number): boolean {
  let seen = false
  for (const row of rows) {
    const value = row[index]
    if (value === null || value === undefined) continue
    if (typeof value !== 'number') return false
    seen = true
  }
  return seen
}
