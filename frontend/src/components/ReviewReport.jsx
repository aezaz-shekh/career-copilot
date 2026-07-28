import { useState } from 'react'
import { Alert, Button } from './ui.jsx'

/** Colour by severity/importance — high is the loudest. */
const LEVEL = {
  high: 'bg-rose-50 text-rose-800 ring-rose-200',
  medium: 'bg-amber-50 text-amber-900 ring-amber-200',
  low: 'bg-slate-50 text-slate-700 ring-slate-200',
}

function Pill({ level }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-semibold uppercase ring-1 ${LEVEL[level] ?? LEVEL.low}`}
    >
      {level}
    </span>
  )
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      onClick={async () => {
        await navigator.clipboard.writeText(text)
        setCopied(true)
        setTimeout(() => setCopied(false), 1500)
      }}
      className="rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
    >
      {copied ? 'Copied ✓' : 'Copy'}
    </button>
  )
}

const TABS = [
  { id: 'critique', label: 'Critique' },
  { id: 'rewrites', label: 'Rewrites' },
  { id: 'gaps', label: 'Keyword Gap' },
  { id: 'ats', label: 'ATS' },
]

function CritiqueTab({ sections }) {
  if (!sections?.length) return <Empty>No section critique was produced.</Empty>
  return (
    <div className="space-y-5">
      {sections.map((section, i) => (
        <div key={i} className="rounded-lg border border-slate-200 p-4">
          <h4 className="font-semibold text-slate-900">{section.name}</h4>
          {section.strengths?.length > 0 && (
            <ul className="mt-2 space-y-1 text-sm text-emerald-800">
              {section.strengths.map((s, j) => (
                <li key={j}>✓ {s}</li>
              ))}
            </ul>
          )}
          {section.issues?.length > 0 && (
            <ul className="mt-3 space-y-3">
              {section.issues.map((issue, j) => (
                <li key={j} className="rounded-md bg-slate-50 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm font-medium text-slate-800">{issue.issue}</p>
                    <Pill level={issue.severity} />
                  </div>
                  <p className="mt-1 text-sm text-slate-600">
                    <span className="font-medium">Fix:</span> {issue.fix}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  )
}

function RewritesTab({ rewrites }) {
  if (!rewrites?.length) return <Empty>No experience bullets were available to rewrite.</Empty>
  return (
    <div className="space-y-4">
      {rewrites.map((r, i) => (
        <div key={i} className="rounded-lg border border-slate-200 p-4">
          <p className="text-sm text-slate-400 line-through">{r.original}</p>
          <div className="mt-2 flex items-start justify-between gap-3">
            <p className="text-sm font-medium text-slate-900">{r.improved}</p>
            <CopyButton text={r.improved} />
          </div>
          <p className="mt-2 text-xs text-slate-500">
            <span className="font-medium">Why:</span> {r.why}
          </p>
        </div>
      ))}
    </div>
  )
}

function GapsTab({ gaps }) {
  if (!gaps?.length) return <Empty>No keyword gaps were found.</Empty>
  const missing = gaps.filter((g) => !g.present_in_resume)
  const weak = gaps.filter((g) => g.present_in_resume)
  return (
    <div className="space-y-5">
      <p className="text-sm text-slate-600">
        {missing.length} missing · {weak.length} present but could be stronger
      </p>
      <ul className="space-y-2">
        {gaps.map((g, i) => (
          <li key={i} className="flex items-start justify-between gap-3 rounded-lg border border-slate-200 p-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-medium text-slate-900">{g.keyword}</span>
                <Pill level={g.importance} />
                {!g.present_in_resume && (
                  <span className="text-xs font-semibold text-rose-600">missing</span>
                )}
              </div>
              <p className="mt-1 text-sm text-slate-600">{g.suggestion}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

function AtsTab({ ats }) {
  if (!ats?.checks?.length) return <Empty>No ATS checks were run.</Empty>
  return (
    <div>
      <p className="mb-4 text-sm font-medium text-slate-700">
        {ats.passed_count} of {ats.total} checks passed
      </p>
      <ul className="space-y-2">
        {ats.checks.map((c, i) => (
          <li key={i} className="flex items-start gap-3 rounded-lg border border-slate-200 p-3">
            <span className={c.passed ? 'text-emerald-600' : 'text-rose-600'}>
              {c.passed ? '✓' : '✗'}
            </span>
            <div>
              <p className="text-sm font-medium text-slate-900">{c.name}</p>
              <p className="text-sm text-slate-600">{c.detail}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

function Empty({ children }) {
  return <p className="py-6 text-center text-sm text-slate-400">{children}</p>
}

export default function ReviewReport({ report }) {
  const [tab, setTab] = useState('critique')
  if (!report) return null

  return (
    <div>
      <div className="mb-5 flex gap-1 rounded-lg border border-slate-200 bg-slate-50 p-1">
        {TABS.map((t) => {
          const count =
            t.id === 'critique'
              ? report.sections?.length
              : t.id === 'rewrites'
                ? report.rewrites?.length
                : t.id === 'gaps'
                  ? report.gaps?.length
                  : `${report.ats?.passed_count ?? 0}/${report.ats?.total ?? 0}`
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition ${
                tab === t.id ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              {t.label}
              {count !== undefined && <span className="ml-1.5 text-xs text-slate-400">{count}</span>}
            </button>
          )
        })}
      </div>

      {tab === 'critique' && <CritiqueTab sections={report.sections} />}
      {tab === 'rewrites' && <RewritesTab rewrites={report.rewrites} />}
      {tab === 'gaps' && <GapsTab gaps={report.gaps} />}
      {tab === 'ats' && <AtsTab ats={report.ats} />}
    </div>
  )
}

export { Alert, Button }
