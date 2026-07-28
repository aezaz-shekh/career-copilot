import { Alert } from './ui.jsx'

const DIM_LABEL = {
  structure: 'Structure',
  specificity: 'Specificity',
  star_adherence: 'STAR method',
  relevance: 'Relevance',
}

function ScoreBar({ value }) {
  const pct = (value / 5) * 100
  const color = value >= 4 ? 'bg-emerald-500' : value >= 3 ? 'bg-amber-500' : 'bg-rose-500'
  return (
    <div className="h-2 w-full rounded-full bg-slate-100">
      <div className={`h-2 rounded-full ${color}`} style={{ width: `${pct}%` }} />
    </div>
  )
}

/** Read-only view of a finished (or reopened) session: summary + full transcript with scores. */
export default function SessionSummary({ session }) {
  if (!session) return null
  const { summary, turns } = session

  return (
    <div className="space-y-6">
      {summary && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-baseline justify-between">
            <h2 className="text-lg font-semibold text-slate-900">Results</h2>
            <span className="text-sm text-slate-500">
              Overall {summary.overall_average}/5 · {summary.answered} answered
            </span>
          </div>

          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            {Object.entries(summary.averages).map(([dim, val]) => (
              <div key={dim}>
                <div className="mb-1 flex justify-between text-sm">
                  <span className="text-slate-600">{DIM_LABEL[dim] ?? dim}</span>
                  <span className="font-medium text-slate-900">{val}/5</span>
                </div>
                <ScoreBar value={val} />
              </div>
            ))}
          </div>

          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            <div>
              <h3 className="text-sm font-semibold text-emerald-800">Strengths</h3>
              <ul className="mt-2 space-y-1 text-sm text-slate-700">
                {summary.strengths.length ? (
                  summary.strengths.map((s, i) => <li key={i}>✓ {s}</li>)
                ) : (
                  <li className="text-slate-400">Keep practising to build clear strengths.</li>
                )}
              </ul>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-rose-800">Focus areas</h3>
              <ul className="mt-2 space-y-1 text-sm text-slate-700">
                {summary.improvement_areas.length ? (
                  summary.improvement_areas.map((s, i) => <li key={i}>→ {s}</li>)
                ) : (
                  <li className="text-slate-400">Strong across the board.</li>
                )}
              </ul>
            </div>
          </div>

          {summary.tips.length > 0 && (
            <div className="mt-6">
              <Alert
                tone="info"
                title="Concrete tips from your answers"
              >
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                  {summary.tips.map((t, i) => (
                    <li key={i}>{t}</li>
                  ))}
                </ul>
              </Alert>
            </div>
          )}
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Transcript</h2>
        <div className="mt-4 space-y-5">
          {turns.map((turn) => (
            <div key={turn.id} className="rounded-lg border border-slate-200 p-4">
              <p className="text-sm font-medium text-slate-900">
                {turn.is_followup && (
                  <span className="mr-1 text-xs font-semibold text-indigo-600">Follow-up:</span>
                )}
                {turn.question}
              </p>
              <p className="mt-2 rounded-md bg-slate-50 p-3 text-sm text-slate-700">
                {turn.answer || <span className="text-slate-400">No answer recorded.</span>}
              </p>

              {turn.scores && (
                <div className="mt-3 grid gap-x-6 gap-y-1 text-xs text-slate-600 sm:grid-cols-2">
                  {Object.entries(turn.scores).map(([dim, val]) => (
                    <div key={dim} className="flex justify-between">
                      <span>{DIM_LABEL[dim] ?? dim}</span>
                      <span className="font-medium">{val}/5</span>
                    </div>
                  ))}
                </div>
              )}
              {turn.improvement_tip && (
                <p className="mt-2 text-xs text-slate-500">
                  <span className="font-medium">Tip:</span> {turn.improvement_tip}
                </p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
