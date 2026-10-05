import { useEffect, useState, type ReactNode } from 'react'
import { fetchProfile } from '../api/client'
import { ApiError, type ColumnProfile, type DatabaseProfile, type TableProfile } from '../api/types'
import { Dialog } from './Dialog'
import { AlertIcon, ChevronIcon } from './icons'

interface SchemaBrowserProps {
  databaseId: string
  databaseName: string
  onClose: () => void
}

export function SchemaBrowser({ databaseId, databaseName, onClose }: SchemaBrowserProps) {
  const [loaded, setLoaded] = useState<{
    databaseId: string
    profile: DatabaseProfile | null
    error: ApiError | null
  } | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchProfile(databaseId)
      .then((profile) => !cancelled && setLoaded({ databaseId, profile, error: null }))
      .catch((err: unknown) => {
        if (cancelled) return
        const error = err instanceof ApiError ? err : new ApiError('Could not load the schema.', 0)
        setLoaded({ databaseId, profile: null, error })
      })
    return () => {
      cancelled = true
    }
  }, [databaseId])

  const current = loaded?.databaseId === databaseId ? loaded : null
  const profile = current?.profile ?? null
  const error = current?.error ?? null
  const loading = current === null

  const summary = profile
    ? `${profile.tables.length} table${profile.tables.length === 1 ? '' : 's'}, sampling: ${profile.sampling}`
    : null

  return (
    <Dialog
      title={`Schema · ${databaseName}`}
      description={
        <>
          What the profiler found{summary && <span className="text-ink-faint"> — {summary}</span>}. This is exactly
          the context the model is given, so it is also what it can and can't answer about.
        </>
      }
      onClose={onClose}
      wide
    >
      <div className="flex flex-col gap-2 text-[14px]">
        {loading && <p className="py-6 text-center text-ink-faint">Loading schema…</p>}
        {error && <Callout>{error.message}</Callout>}

        {profile &&
          profile.tables.map((table) => <TableDisclosure key={`${table.schema_name}.${table.name}`} table={table} />)}
        {profile && profile.relationships.length > 0 && (
          <details className="group rounded-xl border border-line">
            <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2.5 text-ink-dim hover:text-ink">
              <ChevronIcon size={16} className="transition-transform group-open:rotate-90" />
              Joins ({profile.relationships.length})
            </summary>
            <ul className="space-y-1 border-t border-line px-3 py-2.5 font-mono text-[13px] text-ink-dim">
              {profile.relationships.map((rel, i) => (
                <li key={i}>
                  {rel.from_table}.{rel.from_columns.join(', ')} → {rel.to_table}.{rel.to_columns.join(', ')}
                  {rel.inferred && <span className="text-ink-faint"> (inferred)</span>}
                </li>
              ))}
            </ul>
          </details>
        )}
        {profile && profile.notes.length > 0 && <p className="text-[13px] text-ink-faint">{profile.notes.join(' ')}</p>}
      </div>
    </Dialog>
  )
}

function Callout({ children }: { children: ReactNode }) {
  return (
    <p className="flex items-start gap-2 rounded-xl border border-accent/40 bg-accent-soft px-3 py-2.5 text-ink">
      <AlertIcon className="mt-0.5 shrink-0 text-accent" size={16} />
      {children}
    </p>
  )
}

function TableDisclosure({ table }: { table: TableProfile }) {
  return (
    <details className="group rounded-xl border border-line" open={table.columns.length <= 6}>
      <summary className="flex cursor-pointer list-none items-start gap-2 rounded-xl px-3 py-2.5 hover:bg-raised/60">
        <ChevronIcon size={16} className="mt-0.5 shrink-0 text-ink-faint transition-transform group-open:rotate-90" />
        <span className="min-w-0">
          <span className="font-mono text-[13.5px] font-medium">
            {table.schema_name}.{table.name}
          </span>
          <span className="text-[13px] text-ink-faint">
            {' '}
            · {table.columns.length} column{table.columns.length === 1 ? '' : 's'}
            {table.estimated_rows != null && ` · ~${table.estimated_rows.toLocaleString()} rows`}
          </span>
          {table.comment && <span className="block text-[13px] text-ink-dim">{table.comment}</span>}
        </span>
      </summary>
      <table className="w-full border-t border-line text-left text-[13px]">
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
      <td className="py-1.5 pr-3 pl-9 font-mono whitespace-nowrap text-ink">
        {column.name}
        {column.primary_key && <span className="ml-1.5 font-sans text-[11px] text-ink-faint uppercase">pk</span>}
        {column.sensitive && <span className="ml-1.5 font-sans text-[11px] text-accent uppercase">sensitive</span>}
      </td>
      <td className="py-1.5 pr-3 font-mono whitespace-nowrap text-ink-faint">{column.type.toLowerCase()}</td>
      <td className="w-full py-1.5 pr-3 text-ink-dim">
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
