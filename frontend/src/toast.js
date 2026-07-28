/**
 * Minimal toast bus — no context wiring, no library.
 *
 * `pushToast` is called from anywhere (including api.js on every request
 * failure), and the mounted <ToastHost /> subscribes to render them. Kept
 * dependency-free so api.js can import it without a cycle.
 */

let listeners = []
let counter = 0

export function subscribeToasts(fn) {
  listeners.push(fn)
  return () => {
    listeners = listeners.filter((l) => l !== fn)
  }
}

export function pushToast({ title, hint = null, tone = 'error' }) {
  const toast = { id: ++counter, title, hint, tone }
  listeners.forEach((l) => l(toast))
  return toast.id
}
