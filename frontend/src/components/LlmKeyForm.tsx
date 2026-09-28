import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { fetchLlmKeyStatus, removeLlmKey, setLlmKey } from '../api/client'
import { ApiError, type LlmKeyStatus } from '../api/types'

const SOURCE_LABEL: Record<LlmKeyStatus['source'], string> = {
  env: 'set in the server environment',
  ui: 'set through this UI',
  none: 'not set',
}

interface LlmKeyFormProps {
  onClose: () => void
}

export function LlmKeyForm({ onClose }: LlmKeyFormProps) {
  const [status, setStatus] = useState<LlmKeyStatus | null>(null)
  const [statusError, setStatusError] = useState<ApiError | null>(null)
  const [apiKey, setApiKey] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    fetchLlmKeyStatus()
      .then(setStatus)
      .catch((err: unknown) => setStatusError(err instanceof ApiError ? err : new ApiError('Could not load the LLM key status.', 0)))
  }, [])

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const trimmed = apiKey.trim()
    if (pending || !trimmed) return
    setPending(true)
    setError(null)
    setLlmKey(trimmed)
      .then((next) => {
        setStatus(next)
        setApiKey('')
      })
      .catch((err: unknown) => setError(err instanceof ApiError ? err : new ApiError('Could not set the LLM key.', 0)))
      .finally(() => setPending(false))
  }

  function handleRemove() {
    if (pending) return
    setPending(true)
    setError(null)
    removeLlmKey()
      .then(() => fetchLlmKeyStatus())
      .then(setStatus)
      .catch((err: unknown) => setError(err instanceof ApiError ? err : new ApiError('Could not remove the LLM key.', 0)))
      .finally(() => setPending(false))
  }

  return (
    <div className="border-b border-line bg-paper-raised px-4 py-4 sm:px-6">
      <div className="mx-auto flex max-w-4xl flex-col gap-3 font-mono text-[14px]">
        <div className="flex items-center justify-between gap-2">
          <p className="text-ink-dim">
            <span className="text-accent">{':llm-key'}</span> set or remove the API key used to answer
            questions
          </p>
          <button type="button" onClick={onClose} className="shrink-0 px-2 py-0.5 text-ink-faint transition-colors hover:text-ink-dim">
            close
          </button>
        </div>

        {statusError && <p className="text-accent">[error] {statusError.message}</p>}

        {status && (
          <p className="text-ink-faint">
            status: <span className="text-ink">{status.configured ? 'configured' : 'not configured'}</span> (
            {SOURCE_LABEL[status.source]}) · model <span className="text-ink">{status.model}</span> · provider{' '}
            <span className="text-ink">{status.base_url}</span>
          </p>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-[12px] text-ink-faint">api key</span>
            <input
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder={status?.configured ? 'replace the current key…' : 'paste your LLM provider key'}
              autoFocus
              className="border border-line bg-transparent px-2 py-1.5 text-ink outline-none placeholder:text-ink-faint focus-visible:ring-1 focus-visible:ring-accent"
            />
          </label>
          {error && <p className="text-accent">[error] {error.message}</p>}
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={pending || !apiKey.trim()}
              className="border border-line px-3 py-1.5 text-ink-dim transition-colors hover:border-ink-faint hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
            >
              {pending ? 'saving…' : status?.configured ? 'replace key' : 'set key'}
            </button>
            {status?.configured && (
              <button
                type="button"
                onClick={handleRemove}
                disabled={pending}
                className="px-3 py-1.5 text-ink-faint transition-colors hover:text-accent disabled:cursor-not-allowed disabled:opacity-50"
              >
                remove key
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  )
}
