/**
 * Reusable confirmation dialog.
 *
 * Controlled by `open`. Closes via the backdrop, Escape, or Cancel. Focus is
 * trapped while open and returned to the element that opened it on close.
 * `busy` disables every way out while the confirm action is in flight.
 */

import { useEffect, useId, useRef } from 'react'
import { Button } from './ui'

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])'

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  tone = 'danger',
  icon,
  busy = false,
  onConfirm,
  onCancel,
  children,
}) {
  const titleId = useId()
  const panelRef = useRef(null)
  const previousFocus = useRef(null)
  const callbacks = useRef({ onConfirm, onCancel })
  callbacks.current.onConfirm = onConfirm
  callbacks.current.onCancel = onCancel

  useEffect(() => {
    if (!open) return undefined

    previousFocus.current = document.activeElement
    const originalOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    return () => {
      document.body.style.overflow = originalOverflow
      previousFocus.current?.focus()
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    const panel = panelRef.current
    panel?.focus()

    function onKeyDown(event) {
      if (event.key === 'Escape') {
        if (busy) return
        event.stopPropagation()
        callbacks.current.onCancel?.()
        return
      }

      if (event.key !== 'Tab' || !panel) return

      const focusables = Array.from(panel.querySelectorAll(FOCUSABLE))
      if (focusables.length === 0) {
        event.preventDefault()
        panel.focus()
        return
      }
      const first = focusables[0]
      const last = focusables[focusables.length - 1]

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown, true)
    return () => document.removeEventListener('keydown', onKeyDown, true)
  }, [open, busy])

  if (!open) return null

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-ink-950/40 p-4 backdrop-blur-sm animate-overlay-in"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) callbacks.current.onCancel?.()
      }}
    >
      <div
        ref={panelRef}
        tabIndex={-1}
        className="w-full max-w-sm rounded-[24px] border border-ink-200/70 bg-white p-7 text-center shadow-lift outline-none animate-modal-in"
      >
        {icon && (
          <div className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-full bg-bad-500/15 text-bad-600">
            {icon}
          </div>
        )}

        <h2 id={titleId} className="text-xl font-bold tracking-tight text-ink-900">
          {title}
        </h2>
        {message && <p className="mt-1.5 text-sm text-ink-500">{message}</p>}
        {children}

        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-center">
          <Button
            type="button"
            variant="secondary"
            onClick={() => callbacks.current.onCancel?.()}
            disabled={busy}
            className="sm:flex-1"
          >
            {cancelLabel}
          </Button>
          <Button
            type="button"
            variant={tone === 'danger' ? 'danger' : 'primary'}
            onClick={() => callbacks.current.onConfirm?.()}
            loading={busy}
            className="sm:flex-1"
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  )
}