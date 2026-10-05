import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import { ArrowUpIcon, StopIcon } from './icons'

const MAX_LENGTH = 500
// The counter only matters near the limit; below it, it's noise on every keystroke.
const COUNTER_FROM = 400
const MAX_HEIGHT_PX = 200

interface ComposerProps {
  onSubmit: (question: string) => void
  disabled: boolean
  disabledReason?: string
  placeholder?: string
  /** Earlier questions in this chat, oldest first, for shell-style up/down recall. */
  history: string[]
  /** While a question runs, the send button becomes a stop button. */
  onStop?: () => void
}

export function Composer({ onSubmit, disabled, disabledReason, placeholder = 'Ask a question about your data', history, onStop }: ComposerProps) {
  const [value, setValue] = useState('')
  // null: typing freely. A number: how far back into `history` recall has gone.
  const [historyOffset, setHistoryOffset] = useState<number | null>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const canSend = !disabled && value.trim() !== ''

  // Focus on arrival and again whenever the previous question finishes, so the next one can be
  // typed straight away.
  useEffect(() => {
    if (!disabled) input.current?.focus({ preventScroll: true })
  }, [disabled])

  // Grow with the text up to a cap, then scroll inside.
  useLayoutEffect(() => {
    const element = input.current
    if (!element) return
    element.style.height = 'auto'
    element.style.height = `${Math.min(element.scrollHeight, MAX_HEIGHT_PX)}px`
  }, [value])

  function send() {
    const question = value.trim()
    if (!question || disabled) return
    onSubmit(question)
    setValue('')
    setHistoryOffset(null)
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    send()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.nativeEvent.isComposing) return
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      send()
      return
    }
    // History recall only from an empty box or while already recalling, so arrow keys still move
    // the caret inside a multi-line question.
    const recalling = historyOffset !== null
    if (history.length === 0 || (value !== '' && !recalling)) return
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      const next = recalling ? Math.max(0, historyOffset - 1) : history.length - 1
      setHistoryOffset(next)
      setValue(history[next])
    } else if (event.key === 'ArrowDown' && recalling) {
      event.preventDefault()
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
    <form onSubmit={handleSubmit} className="w-full">
      <div
        className={`flex items-end gap-2 rounded-[1.75rem] border border-line bg-surface py-2 pr-2 pl-5 shadow-[var(--shadow-composer)] transition-colors focus-within:border-ink-faint/60 ${disabled ? 'opacity-70' : ''}`}
      >
        <textarea
          ref={input}
          rows={1}
          value={value}
          onChange={(event) => {
            setValue(event.target.value.slice(0, MAX_LENGTH))
            setHistoryOffset(null)
          }}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          enterKeyHint="send"
          placeholder={disabled && disabledReason ? disabledReason : placeholder}
          aria-label="Ask a question"
          className="max-h-[200px] min-h-6 flex-1 resize-none self-center bg-transparent py-1.5 text-[16px] leading-6 text-ink outline-none placeholder:text-ink-faint focus-visible:outline-none disabled:cursor-not-allowed sm:text-[15.5px]"
        />
        {value.length >= COUNTER_FROM && (
          <span className={`self-center text-[12px] tabular-nums ${value.length >= MAX_LENGTH ? 'text-accent' : 'text-ink-faint'}`}>
            {value.length}/{MAX_LENGTH}
          </span>
        )}
        {onStop ? (
          <button
            type="button"
            onClick={onStop}
            aria-label="Stop waiting for the answer"
            className="flex size-9 shrink-0 items-center justify-center rounded-full bg-ink text-surface transition-opacity hover:opacity-85"
          >
            <StopIcon size={18} />
          </button>
        ) : (
          <button
            type="submit"
            disabled={!canSend}
            aria-label="Send question"
            className="flex size-9 shrink-0 items-center justify-center rounded-full bg-ink text-surface transition-opacity hover:opacity-85 disabled:cursor-not-allowed disabled:opacity-25"
          >
            <ArrowUpIcon size={18} strokeWidth={2.25} />
          </button>
        )}
      </div>
    </form>
  )
}
