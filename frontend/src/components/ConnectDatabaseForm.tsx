import { useState } from 'react'
import type { FormEvent } from 'react'
import { addDatabase } from '../api/client'
import { ApiError, type DatabaseInfo, type SamplingMode } from '../api/types'

const SAMPLING_OPTIONS: { value: SamplingMode; label: string; hint: string }[] = [
  {
    value: 'safe',
    label: 'safe — numeric/date ranges + short category values',
    hint: 'Numeric/date ranges and the complete set of values of short categorical columns leave the database. Free text and sensitive-looking columns (email, password, phone, token, ...) are never sampled.',
  },
  {
    value: 'off',
    label: 'off — structure only, no values leave the database',
    hint: 'Only table/column names, types and comments leave the database. No row values at all.',
  },
  {
    value: 'full',
    label: 'full — safe + a few example text values',
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
    <form onSubmit={handleSubmit} className="border-b border-line bg-paper-raised px-4 py-4 sm:px-6">
      <div className="mx-auto flex max-w-4xl flex-col gap-3 font-mono text-[14px]">
        <p className="text-ink-dim">
          <span className="text-accent">{':connect'}</span> add a database — read-only accounts only; a
          writable account is refused after connecting
        </p>
        <label className="flex flex-col gap-1">
          <span className="text-[12px] text-ink-faint">name</span>
          <input
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value.slice(0, 100))}
            placeholder="my shop database"
            autoFocus
            maxLength={100}
            className="border border-line bg-transparent px-2 py-1.5 text-ink outline-none placeholder:text-ink-faint focus-visible:ring-1 focus-visible:ring-accent"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-[12px] text-ink-faint">connection url</span>
          <input
            type="password"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="postgresql://user:password@host:5432/dbname"
            aria-invalid={urlTouched && !urlValid}
            className="border border-line bg-transparent px-2 py-1.5 text-ink outline-none placeholder:text-ink-faint focus-visible:ring-1 focus-visible:ring-accent aria-invalid:border-accent"
          />
          {urlTouched && !urlValid && (
            <span className="text-[12px] text-accent">expected scheme://user:password@host:port/database</span>
          )}
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-[12px] text-ink-faint">sampling</span>
          <select
            value={sampling}
            onChange={(event) => setSampling(event.target.value as SamplingMode)}
            className="border border-line bg-transparent px-2 py-1.5 text-ink outline-none focus-visible:ring-1 focus-visible:ring-accent"
          >
            {SAMPLING_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <span className="text-[12px] text-ink-faint">{selectedSampling.hint}</span>
        </label>
        {error && (
          <p className="text-accent">
            [error] {error.message}
          </p>
        )}
        <div className="flex gap-2">
          <button
            type="submit"
            disabled={pending || !name.trim() || !urlValid}
            className="border border-line px-3 py-1.5 text-ink-dim transition-colors hover:border-ink-faint hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? 'connecting…' : 'connect'}
          </button>
          <button
            type="button"
            onClick={onCancel}
            disabled={pending}
            className="px-3 py-1.5 text-ink-faint transition-colors hover:text-ink-dim disabled:cursor-not-allowed disabled:opacity-50"
          >
            cancel
          </button>
        </div>
      </div>
    </form>
  )
}
