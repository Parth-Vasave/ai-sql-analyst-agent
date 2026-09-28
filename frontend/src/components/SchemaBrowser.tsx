import { useEffect, useState } from 'react'
import { fetchProfile } from '../api/client'
import { ApiError, type ColumnProfile, type DatabaseProfile, type TableProfile } from '../api/types'

interface SchemaBrowserProps {
  databaseId: string
  databaseName: string
  onClose: () => void
}

export function SchemaBrowser({ databaseId, databaseName, onClose }: SchemaBrowserProps) {
  const [profile, setProfile] = useState<DatabaseProfile | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    setError(null)
    fetchProfile(databaseId)
      .then(setProfile)
      .catch((err: unknown) => setError(err instanceof ApiError ? err : new ApiError('Could not load the schema.', 0)))
      .finally(() => setLoading(false))
  }, [databaseId])

  return (
    <div className="border-b border-line bg-paper-raised px-4 py-4 sm:px-6">
      <div className="mx-auto flex max-w-4xl flex-col gap-3 font-mono text-[14px]">
        <div className="flex items-center justify-between gap-2">
          <p className="text-ink-dim">
            <span className="text-accent">{':schema'}</span> {databaseName}
            {profile && (
              <span className="text-ink-faint">
                {' '}
                — {profile.tables.length} table{profile.tables.length === 1 ? '' : 's'}, sampling: {profile.sampling}
              </span>
            )}
          </p>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 px-2 py-0.5 text-ink-faint transition-colors hover:text-ink-dim"
          >
            close
          </button>
        </div>

        {loading && <p className="text-ink-faint">loading schema…</p>}
        {error && <p className="text-accent">[error] {error.message}</p>}

        {profile && (
          <div className="flex flex-col gap-2">
            {profile.tables.map((table) => (
              <TableDisclosure key={`${table.schema_name}.${table.name}`} table={table} />
            ))}
            {profile.relationships.length > 0 && (
              <details className="border border-line">
                <summary className="cursor-pointer px-2 py-1.5 text-ink-dim hover:text-ink">
                  joins ({profile.relationships.length})
                </summary>
                <ul className="border-t border-line px-2 py-1.5 text-ink-faint">
                  {profile.relationships.map((rel, i) => (
                    <li key={i}>
                      {rel.from_table}.{rel.from_columns.join(', ')} → {rel.to_table}.{rel.to_columns.join(', ')}
                      {rel.inferred && <span className="text-ink-faint"> (inferred)</span>}
                    </li>
                  ))}
                </ul>
              </details>
            )}
            {profile.notes.length > 0 && (
              <p className="text-ink-faint">{profile.notes.join(' ')}</p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function TableDisclosure({ table }: { table: TableProfile }) {
  return (
    <details className="border border-line" open={table.columns.length <= 6}>
      <summary className="cursor-pointer px-2 py-1.5 text-ink hover:bg-paper">
        {table.schema_name}.{table.name}
        <span className="text-ink-faint">
          {' '}
          · {table.columns.length} column{table.columns.length === 1 ? '' : 's'}
          {table.estimated_rows != null && ` · ~${table.estimated_rows.toLocaleString()} rows`}
        </span>
        {table.comment && <span className="block text-[13px] text-ink-faint">{table.comment}</span>}
      </summary>
      <table className="w-full border-t border-line text-left text-[13.5px]">
        <tbody>
          {table.columns.map((column) => (
            <ColumnRow key={column.name} column={column} />
          ))}
        </tbody>
      </table>
    </details>
  )
}

function ColumnRow({ column }: { column: ColumnProfile }) {
  return (
    <tr className="border-t border-line first:border-t-0">
      <td className="px-2 py-1 whitespace-nowrap text-ink">
        {column.name}
        {column.primary_key && <span className="text-ink-faint"> pk</span>}
        {column.sensitive && <span className="text-accent"> sensitive</span>}
      </td>
      <td className="px-2 py-1 whitespace-nowrap text-ink-faint">{column.type.toLowerCase()}</td>
      <td className="w-full px-2 py-1 text-ink-faint">
        {column.comment}
        {hintSummary(column) && <span>{column.comment ? ' — ' : ''}{hintSummary(column)}</span>}
      </td>
    </tr>
  )
}

function hintSummary(column: ColumnProfile): string | null {
  const hints = column.hints
  if (!hints) return null
  if (hints.categories) return hints.categories.slice(0, 6).join(', ') + (hints.categories.length > 6 ? ', …' : '')
  if (hints.min != null && hints.max != null) return `${hints.min}–${hints.max}`
  return null
}
