import { useEffect, useRef, type ReactNode } from 'react'
import { CloseIcon } from './icons'

interface DialogProps {
  title: string
  description?: ReactNode
  onClose: () => void
  wide?: boolean
  children: ReactNode
}

/** A native modal <dialog>: focus trapping, Escape and the top layer come from the browser. */
export function Dialog({ title, description, onClose, wide = false, children }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = ref.current
    if (dialog && !dialog.open) dialog.showModal?.()
    return () => dialog?.close?.()
  }, [])

  return (
    <dialog
      ref={ref}
      aria-labelledby="dialog-title"
      onCancel={(event) => {
        event.preventDefault()
        onClose()
      }}
      onClick={(event) => {
        // A click on the backdrop lands on the <dialog> element itself, outside the panel.
        if (event.target === event.currentTarget) onClose()
      }}
      className={`rise-in m-auto max-h-[min(85dvh,52rem)] w-[calc(100%-2rem)] overflow-hidden rounded-2xl border border-line bg-surface p-0 text-ink shadow-[var(--shadow-menu)] ${wide ? 'max-w-3xl' : 'max-w-lg'}`}
    >
      <div className="flex max-h-[inherit] flex-col">
        <header className="flex items-start justify-between gap-4 px-6 pt-5 pb-3">
          <div>
            <h2 id="dialog-title" className="text-[17px] font-semibold">
              {title}
            </h2>
            {description && <p className="mt-1 text-[14px] leading-relaxed text-ink-dim">{description}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="-mr-2 rounded-lg p-1.5 text-ink-faint transition-colors hover:bg-raised hover:text-ink"
          >
            <CloseIcon />
          </button>
        </header>
        <div className="overflow-y-auto px-6 pb-6">{children}</div>
      </div>
    </dialog>
  )
}
