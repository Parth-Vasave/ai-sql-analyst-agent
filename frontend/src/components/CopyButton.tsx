import { useState } from 'react'

export function CopyButton({ text, label = 'copy' }: { text: string; label?: string }) {
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
      className="shrink-0 px-1.5 py-0.5 font-mono text-[12px] text-ink-faint transition-colors hover:text-ink-dim"
    >
      {copied ? 'copied' : label}
    </button>
  )
}
