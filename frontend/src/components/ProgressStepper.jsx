/** Stepper shown while the review runs, driven by SSE `step` events. */

const STEPS = [
  { id: 'retrieve', label: 'Finding relevant context' },
  { id: 'critique', label: 'Critiquing sections' },
  { id: 'rewrites', label: 'Rewriting bullets' },
  { id: 'keyword_gap', label: 'Analysing keyword gaps' },
  { id: 'ats', label: 'Checking ATS readability' },
]

export default function ProgressStepper({ current, done, detail }) {
  return (
    <ol className="space-y-3">
      {STEPS.map((step) => {
        const isDone = done.includes(step.id)
        const isCurrent = current === step.id && !isDone
        return (
          <li key={step.id} className="flex items-center gap-3">
            <span
              className={[
                'flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold',
                isDone
                  ? 'bg-emerald-500 text-white'
                  : isCurrent
                    ? 'bg-slate-900 text-white'
                    : 'bg-slate-200 text-slate-500',
              ].join(' ')}
            >
              {isDone ? '✓' : isCurrent ? '…' : ''}
            </span>
            <span
              className={
                isDone
                  ? 'text-sm text-slate-500'
                  : isCurrent
                    ? 'text-sm font-medium text-slate-900'
                    : 'text-sm text-slate-400'
              }
            >
              {step.label}
              {isCurrent && detail && <span className="ml-2 text-xs text-slate-400">{detail}</span>}
            </span>
          </li>
        )
      })}
    </ol>
  )
}
