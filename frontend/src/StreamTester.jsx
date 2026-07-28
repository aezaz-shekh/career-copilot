import { useRef, useState } from 'react'

/**
 * Phase 0 exit criterion: prove tokens stream from the local model to the browser.
 *
 * EventSource can only issue GET requests, so this reads the Server-Sent Event
 * stream off a POST using fetch + ReadableStream and parses the frames by hand.
 *
 * It also times the first token, which is the SOW §7 performance NFR
 * (first token within ~10 s on CPU-only hardware) — measured, not assumed.
 */
export default function StreamTester({ ready }) {
  const [prompt, setPrompt] = useState('Say hello in one short sentence.')
  const [output, setOutput] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [firstTokenMs, setFirstTokenMs] = useState(null)
  const [totalMs, setTotalMs] = useState(null)
  const abortRef = useRef(null)

  async function run() {
    setBusy(true)
    setOutput('')
    setError(null)
    setFirstTokenMs(null)
    setTotalMs(null)

    const started = performance.now()
    let sawToken = false

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const response = await fetch('/api/dev/echo-llm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: prompt }),
        signal: controller.signal,
      })

      if (!response.ok) throw new Error(`Backend returned HTTP ${response.status}`)

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        // SSE frames are separated by a blank line.
        const frames = buffer.split('\n\n')
        buffer = frames.pop() ?? ''

        for (const frame of frames) {
          let event = 'message'
          let data = ''
          for (const line of frame.split('\n')) {
            if (line.startsWith('event: ')) event = line.slice(7)
            else if (line.startsWith('data: ')) data += line.slice(6)
          }
          if (!data) continue

          const payload = JSON.parse(data)
          if (event === 'token') {
            if (!sawToken) {
              sawToken = true
              setFirstTokenMs(Math.round(performance.now() - started))
            }
            setOutput((prev) => prev + payload.text)
          } else if (event === 'error') {
            setError(payload)
          } else if (event === 'done') {
            setTotalMs(Math.round(performance.now() - started))
          }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError({ message: err.message, hint: 'Check that the backend is still running.' })
      }
    } finally {
      setBusy(false)
      abortRef.current = null
    }
  }

  function stop() {
    abortRef.current?.abort()
  }

  return (
    <section className="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold">Streaming test</h2>
      <p className="mt-1 text-sm text-slate-600">
        Sends your prompt to the local model and streams the reply back token by token.
      </p>

      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        rows={2}
        className="mt-4 w-full resize-y rounded-lg border border-slate-300 p-3 font-mono text-sm focus:border-slate-500 focus:outline-none"
      />

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button
          onClick={run}
          disabled={busy || !ready || !prompt.trim()}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? 'Generating…' : 'Send to local model'}
        </button>
        {busy && (
          <button
            onClick={stop}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Stop
          </button>
        )}
        {!ready && (
          <span className="text-sm text-slate-500">
            Available once the status above turns green.
          </span>
        )}
      </div>

      {(output || busy) && (
        <pre className="mt-4 max-h-72 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-900 p-4 font-mono text-sm text-slate-100">
          {output}
          {busy && <span className="animate-pulse">▋</span>}
        </pre>
      )}

      {(firstTokenMs !== null || totalMs !== null) && (
        <div className="mt-3 flex flex-wrap gap-4 text-xs text-slate-500">
          {firstTokenMs !== null && (
            <span>
              First token:{' '}
              <strong className={firstTokenMs <= 10000 ? 'text-emerald-700' : 'text-amber-700'}>
                {firstTokenMs} ms
              </strong>{' '}
              (target ≤ 10 000 ms on CPU)
            </span>
          )}
          {totalMs !== null && <span>Total: {totalMs} ms</span>}
        </div>
      )}

      {error && (
        <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-4">
          <p className="font-semibold text-rose-900">{error.message}</p>
          {error.hint && <p className="mt-1 text-sm text-rose-800">{error.hint}</p>}
        </div>
      )}
    </section>
  )
}
