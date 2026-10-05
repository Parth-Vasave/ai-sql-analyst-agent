import { useState } from 'react'
import type { FormEvent } from 'react'
import { addDatabase } from '../api/client'
import { ApiError, type DatabaseInfo, type SamplingMode } from '../api/types'
import { Dialog } from './Dialog'
import { AlertIcon } from './icons'

const SAMPLING_OPTIONS: { value: SamplingMode; label: string; hint: string }[] = [
  {
    value: 'safe',
    label: 'Safe — numeric/date ranges and short category values',
    hint: 'Numeric/date ranges and the complete set of values of short categorical columns leave the database. Free text and sensitive-looking columns (email, password, phone, token, ...) are never sampled.',
  },
  {
    value: 'off',
    label: 'Off — structure only, no values leave the database',
    hint: 'Only table/column names, types and comments leave the database. No row values at all.',
  },
  {
    value: 'full',
    label: 'Full — safe, plus a few example text values',
    hint: 'Adds a few truncated example values from other text columns (still never sensitive-looking ones), sent to the LLM provider as schema context. Avoid this on databases with free text you would not want leaving the database.',
  },
]

// A loose sanity check, not a URL parser: catches empty scheme/host typos before a round trip
// to the backend, which does the real validation.
const URL_PATTERN = /^[a-z][a-z0-9+.-]*:\/\/[^\s]+$/i

function urlLooksValid(url: string): boolean {
  return URL_PATTERN.test(url)
}

interface ConnectDatabaseFormProps {
  onConnected: (database: DatabaseInfo) => void
  onCancel: () => void
}

export function ConnectDatabaseForm({ onConnected, onCancel }: ConnectDatabaseFormProps) {
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [sampling, setSampling] = useState<SamplingMode>('safe')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  const trimmedUrl = url.trim()
  const urlTouched = trimmedUrl.length > 0
  const urlValid = urlLooksValid(trimmedUrl)
  const selectedSampling = SAMPLING_OPTIONS.find((option) => option.value === sampling)!

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (pending) return
    const trimmedName = name.trim()
    if (!trimmedName || !urlValid) return
    setPending(true)
    setError(null)
    addDatabase({ name: trimmedName, url: trimmedUrl, sampling })
      .then((database) => onConnected(database))
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err : new ApiError('Could not add the database.', 0))
        setPending(false)
      })
  }

  return (
    <Dialog
      title="Connect a database"
      description="Read-only accounts only: an account that can write data is refused after connecting, with the privileges that disqualified it."
      onClose={pending ? () => {} : onCancel}
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4 text-[14px]">
        <label className="flex flex-col gap-1.5">
          <span className="font-medium">Name</span>
          <input
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value.slice(0, 100))}
            placeholder="My shop database"
            autoFocus
            maxLength={100}
            className={FIELD}
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="font-medium">Connection URL</span>
          <input
            type="password"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="postgresql://user:password@host:5432/dbname"
            aria-invalid={urlTouched && !urlValid}
            autoComplete="off"
            className={`${FIELD} font-mono text-[13px] aria-invalid:border-accent`}
          />
          {urlTouched && !urlValid ? (
            <span className="text-[13px] text-accent">Expected scheme://user:password@host:port/database</span>
          ) : (
            <span className="text-[13px] text-ink-faint">Sent to the API server to connect; not saved in this browser.</span>
          )}
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="font-medium">Sampling</span>
          <select value={sampling} onChange={(event) => setSampling(event.target.value as SamplingMode)} className={FIELD}>
            {SAMPLING_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <span className="text-[13px] leading-relaxed text-ink-faint">{selectedSampling.hint}</span>
        </label>
        {error && (
          <p className="flex items-start gap-2 rounded-xl border border-accent/40 bg-accent-soft px-3 py-2.5 text-ink" role="alert">
            <AlertIcon className="mt-0.5 shrink-0 text-accent" size={16} />
            {error.message}
          </p>
        )}
        <div className="flex justify-end gap-2 pt-1">
          <button
            type="button"
            onClick={onCancel}
            disabled={pending}
            className="rounded-full px-4 py-2 font-medium text-ink-dim transition-colors hover:bg-raised hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={pending || !name.trim() || !urlValid}
            className="rounded-full bg-ink px-4 py-2 font-medium text-surface transition-opacity hover:opacity-85 disabled:cursor-not-allowed disabled:opacity-30"
          >
            {pending ? 'Connecting…' : 'Connect'}
          </button>
        </div>
      </form>
    </Dialog>
  )
}

const FIELD =
  'rounded-xl border border-line bg-surface px-3 py-2 text-ink outline-none transition-colors placeholder:text-ink-faint focus-visible:border-ink-faint focus-visible:outline-none'
