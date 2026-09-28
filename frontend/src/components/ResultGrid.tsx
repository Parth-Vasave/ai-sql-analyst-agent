import { downloadCsv, toCsv } from '../lib/csv'
import { columnLabel, formatCell, formatRowCount } from '../lib/format'

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

  return (
    <div className="overflow-x-auto border border-line">
      <table className="w-full min-w-max border-collapse font-mono text-[14px]">
        <thead>
          <tr className="border-b border-line bg-paper-raised text-left">
            {columns.map((column) => (
              <th key={column} scope="col" className="whitespace-nowrap px-2 py-1 font-medium text-ink-dim">
                {columnLabel(column, units)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((row, rowIndex) => (
            <tr key={rowIndex} className="border-b border-line last:border-b-0">
              {row.map((value, columnIndex) => (
                <td key={columnIndex} className="whitespace-nowrap px-2 py-1 tabular-nums">
                  {formatCell(value, units[columns[columnIndex]])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex items-center justify-between border-t border-line bg-paper-raised px-2 py-1 text-[12px] text-ink-faint">
        <span>
          ({formatRowCount(rows.length)}
          {rows.length > MAX_RENDERED_ROWS ? `, showing first ${MAX_RENDERED_ROWS}` : ''}
          {truncated ? ', capped at the row limit' : ''})
        </span>
        <span className="flex items-center gap-2">
          {executionTimeMs !== null && <span>{executionTimeMs}ms</span>}
          <button
            type="button"
            onClick={() => downloadCsv('result.csv', toCsv(columns, rows))}
            className="px-1.5 py-0.5 text-ink-faint transition-colors hover:text-ink-dim"
          >
            export csv
          </button>
        </span>
      </div>
    </div>
  )
}
