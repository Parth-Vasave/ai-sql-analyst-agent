import { useState } from 'react'
import type { ResultCheck } from '../api/types'

export function ChecksRow({ checks }: { checks: ResultCheck[] }) {
  const [openIndex, setOpenIndex] = useState<number | null>(null)
  if (checks.length === 0) return null

  return (
    <div className="font-mono text-[14px]">
      <span className="text-accent">[check]</span>{' '}
      <span className="inline-flex flex-wrap gap-2 align-middle">
        {checks.map((check, index) => (
          <button
            key={index}
            type="button"
            onClick={() => setOpenIndex(openIndex === index ? null : index)}
            className={chipClass(check.severity)}
            aria-expanded={openIndex === index}
          >
            {check.severity === 'warning' ? '●' : '○'} {check.code}
          </button>
        ))}
      </span>
      {openIndex !== null && (
        <p className="mt-1 ml-[3.5rem] max-w-[36rem] text-ink-dim">
          {checks[openIndex].message}
          {checks[openIndex].column && <span className="text-ink-faint"> (column: {checks[openIndex].column})</span>}
          {checks[openIndex].repairable && <span className="text-ink-faint"> — fed back for one repair attempt</span>}
        </p>
      )}
    </div>
  )
}

function chipClass(severity: ResultCheck['severity']): string {
  const base = 'border px-1.5 py-0.5 text-[13px] leading-none transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent'
  return severity === 'warning'
    ? `${base} border-accent text-accent hover:bg-accent-soft`
    : `${base} border-line text-ink-dim hover:border-ink-faint`
}
