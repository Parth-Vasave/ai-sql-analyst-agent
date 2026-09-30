import { useEffect, useState } from 'react'
import { ApiError } from '../api/types'

export function ErrorBanner({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  const [countdown, setCountdown] = useState({ error, elapsed: 0 })
  if (countdown.error !== error) setCountdown({ error, elapsed: 0 })
  const remaining = Math.max(0, (error.retryAfterSeconds ?? 0) - countdown.elapsed)

  useEffect(() => {
    if (!error.retryAfterSeconds) return
    const interval = setInterval(() => setCountdown((c) => ({ ...c, elapsed: c.elapsed + 1 })), 1000)
    return () => clearInterval(interval)
  }, [error])

  return (
    <div className="border-l-2 border-accent bg-accent-soft/40 px-3 py-2 font-mono text-[14px]">
      <p className="text-ink">
        <span className="text-accent">[error]</span> {kindLabel(error.httpStatus)}: {error.message}
      </p>
      {error.requestId && <p className="mt-0.5 text-[12px] text-ink-faint">request {error.requestId}</p>}
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          disabled={remaining > 0}
          className="mt-1.5 border border-line px-2 py-0.5 text-[13px] text-ink-dim transition-colors hover:border-ink-faint hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
        >
          {remaining > 0 ? `retry in ${remaining}s` : 'retry'}
        </button>
      )}
    </div>
  )
}

function kindLabel(status: number): string {
  if (status === 0) return 'unreachable'
  if (status === 429) return 'rate limited'
  if (status === 503) return 'unavailable'
  if (status === 409) return 'not ready'
  return `http ${status}`
}
