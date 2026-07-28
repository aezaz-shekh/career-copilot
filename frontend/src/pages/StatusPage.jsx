import StreamTester from '../StreamTester.jsx'
import { Alert, Button, Card } from '../components/ui.jsx'

const STATE = {
  checking: { label: 'Local AI: Checking…', dot: 'bg-slate-400', chip: 'bg-slate-100 text-slate-700 ring-slate-300' },
  connected: { label: 'Local AI: Connected', dot: 'bg-emerald-500', chip: 'bg-emerald-50 text-emerald-800 ring-emerald-300' },
  degraded: { label: 'Local AI: Setup incomplete', dot: 'bg-amber-500', chip: 'bg-amber-50 text-amber-900 ring-amber-300' },
  offline: { label: 'Local AI: Offline', dot: 'bg-rose-500', chip: 'bg-rose-50 text-rose-800 ring-rose-300' },
}

function StatusBadge({ state }) {
  const style = STATE[state]
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold ring-1 ${style.chip}`}
    >
      <span className={`h-2.5 w-2.5 rounded-full ${style.dot}`} />
      {style.label}
    </span>
  )
}

function Row({ label, children }) {
  return (
    <div className="flex justify-between gap-4 border-b border-slate-100 py-2 last:border-0">
      <span className="text-slate-500">{label}</span>
      <span className="text-right font-mono text-slate-800">{children}</span>
    </div>
  )
}

function FixItPanel({ title, hint, commands }) {
  return (
    <div className="mt-5 rounded-lg border border-amber-200 bg-amber-50 p-4">
      <p className="font-semibold text-amber-900">{title}</p>
      {hint && <p className="mt-1 text-sm text-amber-800">{hint}</p>}
      {commands?.length > 0 && (
        <div className="mt-3 space-y-1">
          {commands.map((cmd) => (
            <code
              key={cmd}
              className="block rounded bg-slate-900 px-3 py-2 font-mono text-xs text-slate-100"
            >
              {cmd}
            </code>
          ))}
        </div>
      )}
    </div>
  )
}

export default function StatusPage({ health, backendError, loading, checkedAt, state, onRecheck }) {
  const missing = health?.models_missing ?? []

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <StatusBadge state={state} />
          <Button onClick={onRecheck} disabled={loading}>
            {loading ? 'Checking…' : 'Re-check'}
          </Button>
        </div>

        {health && (
          <div className="mt-6 text-sm">
            <Row label="Chat model">{health.models_required.chat}</Row>
            <Row label="Embedding model">{health.models_required.embed}</Row>
            <Row label="Ollama">{health.ollama.url}</Row>
            <Row label="Models pulled">
              {health.ollama.models_installed.length > 0
                ? health.ollama.models_installed.join(', ')
                : 'none'}
            </Row>
          </div>
        )}

        {backendError && (
          <FixItPanel
            title="Backend not running"
            hint={`${backendError} Start it from the backend/ folder:`}
            commands={[
              '.venv\\Scripts\\activate',
              'uvicorn app.main:app --reload --host 127.0.0.1 --port 8000',
            ]}
          />
        )}

        {health && !health.ollama.reachable && (
          <FixItPanel
            title="Ollama is not running"
            hint={health.ollama.hint}
            commands={['ollama serve']}
          />
        )}

        {health?.ollama.reachable && missing.length > 0 && (
          <FixItPanel
            title={`${missing.length} model${missing.length > 1 ? 's' : ''} not downloaded yet`}
            hint="This is a one-time download. After it completes the app works fully offline."
            commands={missing.map((name) => `ollama pull ${name}`)}
          />
        )}

        {state === 'connected' && (
          <div className="mt-5">
            <Alert
              tone="success"
              hint="Everything is ready. All five modules run entirely on this machine — no account, no API key, no data leaving your disk."
            />
          </div>
        )}

        {checkedAt && (
          <p className="mt-4 text-xs text-slate-400">
            Last checked {checkedAt.toLocaleTimeString()} · re-checks every 10s
          </p>
        )}
      </Card>

      <StreamTester ready={state === 'connected'} />
    </div>
  )
}
