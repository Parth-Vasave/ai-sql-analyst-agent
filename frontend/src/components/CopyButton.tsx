import { useState } from 'react'
import { CheckIcon, CopyIcon } from './icons'

export function CopyButton({ text, label = 'Copy' }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false)

  async function handleClick() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // clipboard permission denied or unavailable; nothing to fall back to silently
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      className="flex shrink-0 items-center gap-1.5 rounded-lg px-2 py-1 text-[13px] text-ink-faint transition-colors hover:bg-raised hover:text-ink"
    >
      {copied ? <CheckIcon size={15} className="text-ok" /> : <CopyIcon size={15} />}
      {copied ? 'Copied' : label}
    </button>
  )
}
