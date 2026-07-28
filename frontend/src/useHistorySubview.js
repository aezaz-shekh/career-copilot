import { useEffect, useRef } from 'react'

/**
 * Keep a "takeover" sub-view (the running mock interview, an opened roadmap, a
 * review report…) in sync with the browser Back button.
 *
 * While `open` is true, one extra history entry is held, so a Back press fires
 * `onBack()` — which should close the sub-view — instead of popping the previous
 * tab entry and throwing the user onto another page. Closing the sub-view from
 * inside the app (a Cancel / "Back to…" button) consumes that same entry, so the
 * history stack never drifts out of sync.
 *
 * Works alongside the app-level tab history in App.jsx: on a real Back press the
 * entry below the sub-view is the current page's own tab entry, so the app stays
 * on this page while this hook closes the sub-view.
 */
export function useHistorySubview(open, onBack) {
  const ref = useRef({ pushed: false, closing: false })
  const onBackRef = useRef(onBack)
  onBackRef.current = onBack

  useEffect(() => {
    const s = ref.current
    if (open && !s.pushed) {
      window.history.pushState({ subview: true }, '')
      s.pushed = true
    } else if (!open && s.pushed && !s.closing) {
      // Closed from inside the app — pop our extra entry to stay in sync.
      s.closing = true
      window.history.back()
    }
  }, [open])

  useEffect(() => {
    function onPop() {
      const s = ref.current
      if (!s.pushed) return
      s.pushed = false
      if (s.closing) {
        s.closing = false // our own history.back() during an in-app close
        return
      }
      onBackRef.current?.() // a real Back press — close the sub-view
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])
}
