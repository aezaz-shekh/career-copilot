import { useCallback, useEffect, useRef, useState } from 'react'
import { api, streamPull } from '../api.js'
import { Alert, Button, Card } from '../components/ui.jsx'

function StepIcon({ state }) {
  const map = {
    ok: 'bg-emerald-500 text-white',
    todo: 'bg-amber-500 text-white',
    off: 'bg-slate-200 text-slate-500',
  }
  const glyph = { ok: '✓', todo: '!', off: '–' }
  return (
    <span
      className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-sm font-bold ${map[state]}`}
    >
      {glyph[state]}
    </span>
  )
}

/** One model row: shows installed, or a Download button with a live progress bar. */
function ModelRow({ model, installed, onPulled }) {
  const [pulling, setPulling] = useState(false)
  const [percent, setPercent] = useState(null)
  const [status, setStatus] = useState('')
  const abortRef = useRef(null)

  function pull() {
    setPulling(true)
    setPercent(null)
    setStatus('starting…')
    abortRef.current = streamPull(model, (event, data) => {
      if (event === 'progress') {
        setStatus(data.status || '')
        if (data.percent != null) setPercent(data.percent)
      } else if (event === 'done') {
        setPulling(false)
        setStatus('done')
        onPulled?.()
      } else if (event === 'error') {
        setPulling(false)
        setStatus(data.message || 'failed')
      }
    })
  }

  return (
    <div className="flex items-center gap-3 py-2">
      <StepIcon state={installed ? 'ok' : 'todo'} />
      <div className="min-w-0 flex-1">
        <p className="font-mono text-sm text-slate-800">{model}</p>
        {pulling && (
          <div className="mt-1">
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
              <div
                className="h-full rounded-full bg-indigo-500 transition-all"
                style={{ width: `${percent ?? 5}%` }}
              />
            </div>
            <p className="mt-0.5 text-xs text-slate-400">
              {status}
              {percent != null ? ` · ${percent}%` : ''}
            </p>
          </div>
        )}
      </div>
      {!installed && !pulling && (
        <Button variant="secondary" onClick={pull}>
          Download
        </Button>
      )}
      {installed && <span className="text-xs font-medium text-emerald-600">installed</span>}
    </div>
  )
}

/**
 * Phase 4 first-run setup wizard: checks Ollama, offers to auto-pull any missing
 * models with a progress bar, and reports whether optional voice is configured.
 */
export default function SetupPage() {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setStatus(await api.setupStatus())
    } catch {
      setStatus(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  if (loading && !status) {
    return (
      <Card>
        <p className="text-sm text-slate-500">Checking your setup…</p>
      </Card>
    )
  }

  if (!status) {
    return (
      <Card>
        <Alert
          tone="error"
          title="Can't reach the backend"
          hint="Make sure uvicorn is running on 127.0.0.1:8000, then re-check."
        />
        <div className="mt-4">
          <Button onClick={load}>Re-check</Button>
        </div>
      </Card>
    )
  }

  const { ollama, models, voice } = status
  const installed = new Set(models.installed)

  return (
    <div className="space-y-6">
      <Card
        title="First-run setup"
        subtitle="Three checks and you're ready. After the one-time downloads, everything runs offline."
      >
        {/* Step 1: Ollama */}
        <div className="mt-4 flex items-center gap-3 border-b border-slate-100 pb-4">
          <StepIcon state={ollama.reachable ? 'ok' : 'todo'} />
          <div className="flex-1">
            <p className="font-semibold text-slate-800">Ollama runtime</p>
            <p className="text-sm text-slate-500">
              {ollama.reachable ? `Reachable at ${ollama.url}` : 'Not running'}
            </p>
          </div>
        </div>
        {!ollama.reachable && (
          <Alert
            tone="warn"
            title="Start Ollama, then re-check"
            hint="Open a terminal and run: ollama serve"
          />
        )}

        {/* Step 2: Models */}
        <div className="mt-4">
          <div className="flex items-center gap-3">
            <StepIcon state={models.missing.length === 0 ? 'ok' : 'todo'} />
            <p className="font-semibold text-slate-800">Required models</p>
          </div>
          <div className="mt-2 divide-y divide-slate-100 pl-10">
            {Object.entries(models.required).map(([role, name]) => (
              <div key={role}>
                <span className="text-xs uppercase tracking-wide text-slate-400">{role}</span>
                <ModelRow model={name} installed={installed.has(name)} onPulled={load} />
              </div>
            ))}
          </div>
          {!ollama.reachable && (
            <p className="mt-2 pl-10 text-xs text-amber-700">Start Ollama to enable downloads.</p>
          )}
        </div>

        {/* Step 3: Voice (optional) */}
        <div className="mt-5 flex items-center gap-3 border-t border-slate-100 pt-4">
          <StepIcon state={voice.configured ? 'ok' : 'off'} />
          <div className="flex-1">
            <p className="font-semibold text-slate-800">Voice mode (optional)</p>
            <p className="text-sm text-slate-500">
              {voice.configured
                ? 'whisper.cpp and Piper are installed.'
                : 'Optional, not configured — the app works fully in text mode.'}
            </p>
          </div>
        </div>

        <div className="mt-6 flex items-center gap-3">
          <Button onClick={load}>Re-check</Button>
          {status.ready && (
            <span className="text-sm font-medium text-emerald-600">
              ✓ You're ready — all models installed.
            </span>
          )}
        </div>
      </Card>

      <Card title="Where your data lives">
        <p className="mt-2 font-mono text-xs text-slate-600">{status.data_path}</p>
        <p className="mt-1 text-sm text-slate-500">
          One local SQLite file. Nothing leaves this machine.
        </p>
      </Card>
    </div>
  )
}
