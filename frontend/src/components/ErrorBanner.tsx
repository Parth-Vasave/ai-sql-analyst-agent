import { useEffect, useState } from 'react'
import { ApiError } from '../api/types'
import { AlertIcon, RetryIcon } from './icons'

export function ErrorBanner({ error, onRetry, title }: { error: ApiError; onRetry?: () => void; title?: string }) {
  const [countdown, setCountdown] = useState({ error, elapsed: 0 })
  if (countdown.error !== error) setCountdown({ error, elapsed: 0 })
  const remaining = Math.max(0, (error.retryAfterSeconds ?? 0) - countdown.elapsed)

  useEffect(() => {
    if (!error.retryAfterSeconds) return
    const interval = setInterval(() => setCountdown((c) => ({ ...c, elapsed: c.elapsed + 1 })), 1000)
    return () => clearInterval(interval)
  }, [error])

  return (
    <div className="flex items-start gap-3 rounded-xl border border-accent/40 bg-accent-soft px-4 py-3 text-[14px]" role="alert">
      <AlertIcon size={18} className="mt-px shrink-0 text-accent" />
      <div className="min-w-0 flex-1">
        <p className="font-medium text-ink">{title ?? kindLabel(error.httpStatus)}</p>
        <p className="mt-0.5 leading-relaxed text-ink-dim">{error.message}</p>
        {error.requestId && <p className="mt-1 font-mono text-[12px] text-ink-faint">request {error.requestId}</p>}
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            disabled={remaining > 0}
            className="mt-2.5 flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 text-[13px] font-medium text-ink transition-colors hover:bg-raised disabled:cursor-not-allowed disabled:opacity-60"
          >
            <RetryIcon size={14} />
            <span className="tabular-nums">{remaining > 0 ? `retry in ${remaining}s` : 'Retry'}</span>
          </button>
        )}
      </div>
    </div>
  )
}

function kindLabel(status: number): string {
  if (status === 0) return 'Could not reach the API'
  if (status === 429) return 'Rate limited'
  if (status === 503) return 'Unavailable'
  if (status === 409) return 'Not ready'
  return `Request failed (HTTP ${status})`
}
