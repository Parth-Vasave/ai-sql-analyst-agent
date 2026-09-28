import { useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'

const MAX_LENGTH = 500

interface PromptFormProps {
  onSubmit: (question: string) => void
  disabled: boolean
  disabledReason?: string
  /** Earlier questions, oldest first, for shell-style up/down recall. */
  history: string[]
}

export function PromptForm({ onSubmit, disabled, disabledReason, history }: PromptFormProps) {
  const [value, setValue] = useState('')
  // null: typing freely. A number: how far back into `history` (from the end) recall has gone.
  const [historyOffset, setHistoryOffset] = useState<number | null>(null)

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const question = value.trim()
    if (!question || disabled) return
    onSubmit(question)
    setValue('')
    setHistoryOffset(null)
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return
    if (history.length === 0) return
    event.preventDefault()
    if (event.key === 'ArrowUp') {
      const next = historyOffset === null ? history.length - 1 : Math.max(0, historyOffset - 1)
      setHistoryOffset(next)
      setValue(history[next])
    } else {
      if (historyOffset === null) return
      const next = historyOffset + 1
      if (next >= history.length) {
        setHistoryOffset(null)
        setValue('')
      } else {
        setHistoryOffset(next)
        setValue(history[next])
      }
    }
  }

  return (
    <form onSubmit={handleSubmit} className="border-t border-line px-4 py-3 sm:px-6">
      <div className="mx-auto flex max-w-4xl items-start gap-2">
        <span className="pt-2 font-mono text-[14px] text-accent" aria-hidden="true">
          {'>'}
        </span>
        <div className="min-w-0 flex-1">
          <input
            type="text"
            value={value}
            onChange={(event) => {
              setValue(event.target.value.slice(0, MAX_LENGTH))
              setHistoryOffset(null)
            }}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder={disabled && disabledReason ? disabledReason : 'ask a question about this data'}
            aria-label="Ask a question"
            className="w-full border-none bg-transparent py-2 font-mono text-[14px] text-ink outline-none placeholder:text-ink-faint disabled:cursor-not-allowed"
          />
        </div>
        <span className="pt-2 font-mono text-[12px] text-ink-faint tabular-nums">
          {value.length}/{MAX_LENGTH}
        </span>
      </div>
    </form>
  )
}
