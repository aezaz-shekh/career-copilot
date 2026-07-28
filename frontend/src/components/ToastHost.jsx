import { useEffect, useState } from 'react'
import { subscribeToasts } from '../toast.js'

const TONE = {
  error: 'border-rose-200 bg-rose-50 text-rose-900',
  info: 'border-slate-200 bg-white text-slate-800',
  success: 'border-emerald-200 bg-emerald-50 text-emerald-900',
}

const DISMISS_MS = 7000

/** Fixed toast stack. Subscribes to the toast bus; auto-dismisses each toast. */
export default function ToastHost() {
  const [toasts, setToasts] = useState([])

  useEffect(() => {
    return subscribeToasts((toast) => {
      setToasts((prev) => [...prev, toast])
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== toast.id))
      }, DISMISS_MS)
    })
  }, [])

  const dismiss = (id) => setToasts((prev) => prev.filter((t) => t.id !== id))

  if (toasts.length === 0) return null

  return (
    <div className="fixed bottom-4 right-4 z-50 flex w-80 max-w-[90vw] flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`rounded-lg border p-3 shadow-lg ${TONE[t.tone] ?? TONE.error}`}
          role="alert"
        >
          <div className="flex items-start justify-between gap-2">
            <p className="text-sm font-semibold">{t.title}</p>
            <button
              onClick={() => dismiss(t.id)}
              className="shrink-0 text-lg leading-none opacity-50 hover:opacity-100"
              aria-label="Dismiss"
            >
              ×
            </button>
          </div>
          {t.hint && <p className="mt-1 text-xs opacity-90">{t.hint}</p>}
        </div>
      ))}
    </div>
  )
}
