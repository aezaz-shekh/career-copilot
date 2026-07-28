import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import AskAssistant from '../components/AskAssistant.jsx'
import { Button, Card } from '../components/ui.jsx'

/** "Good morning/afternoon/evening" based on the local clock. */
function timeGreeting() {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning'
  if (h < 17) return 'Good afternoon'
  return 'Good evening'
}

/** A tiny inline sparkline for the interview score trend (no chart library). */
function Sparkline({ values }) {
  const w = 240
  const h = 56
  const pad = 6
  const max = 5
  const points = values.map((v, i) => {
    const x = values.length === 1 ? w / 2 : pad + (i * (w - 2 * pad)) / (values.length - 1)
    const y = h - pad - (Math.max(0, Math.min(v, max)) / max) * (h - 2 * pad)
    return [x, y]
  })
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="max-w-full">
      <polyline
        fill="none"
        stroke="#4f46e5"
        strokeWidth="2"
        points={points.map((p) => p.join(',')).join(' ')}
      />
      {points.map((p, i) => (
        <circle key={i} cx={p[0]} cy={p[1]} r="2.5" fill="#4f46e5" />
      ))}
    </svg>
  )
}

/** Line icons used on the colored stat cards. */
function StatIcon({ id }) {
  const p = {
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.9,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    className: 'h-5 w-5',
  }
  switch (id) {
    case 'resume':
      return (
        <svg {...p}>
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <path d="M14 2v6h6M8 13h8M8 17h6" />
        </svg>
      )
    case 'interview':
      return (
        <svg {...p}>
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      )
    case 'roadmap':
      return (
        <svg {...p}>
          <path d="M9 18l-6 3V6l6-3 6 3 6-3v15l-6 3-6-3z" />
          <path d="M9 3v15M15 6v15" />
        </svg>
      )
    case 'outreach':
      return (
        <svg {...p}>
          <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
        </svg>
      )
    default:
      return null
  }
}

/**
 * A colored stat card — each module gets its own accent gradient + icon, so the
 * home page reads at a glance instead of a wall of gray tiles.
 */
function StatCard({ id, accent, label, value, sub }) {
  return (
    <div
      className={`relative overflow-hidden rounded-xl border border-white/60 bg-gradient-to-br ${accent} p-3.5 shadow-sm`}
    >
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-white/90">{label}</p>
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-white/20 text-white">
          <StatIcon id={id} />
        </span>
      </div>
      <p className="mt-1.5 text-2xl font-extrabold text-white drop-shadow-sm">{value}</p>
      {sub && <p className="mt-0.5 truncate text-xs font-medium text-white/85">{sub}</p>}
    </div>
  )
}

/**
 * "What to do next" — a guided funnel that reads the user's real state and
 * points at the next uncompleted step. Never empty (unlike raw counters), it
 * turns the home page into a story: add resume → add job → review → interview →
 * outreach. Done steps are ticked; the first open one is highlighted with a CTA.
 */
function NextSteps({ steps, onNavigate }) {
  const firstTodo = steps.findIndex((s) => !s.done)
  const doneCount = steps.filter((s) => s.done).length
  const allDone = firstTodo === -1
  const pct = Math.round((doneCount / steps.length) * 100)

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-md shadow-indigo-200/60">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5">
              <circle cx="12" cy="12" r="9" />
              <path d="m15.5 8.5-2 5-5 2 2-5 5-2z" />
            </svg>
          </span>
          <div>
            <h2 className="text-sm font-bold text-slate-900">
              {allDone ? "You're all set 🎉" : 'What to do next'}
            </h2>
            <p className="text-xs text-slate-400">
              {allDone
                ? 'Every step done — keep practicing and refining.'
                : `${doneCount} of ${steps.length} steps complete`}
            </p>
          </div>
        </div>
        <div className="hidden items-center gap-2 sm:flex">
          <div className="h-1.5 w-24 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500 transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className="text-xs font-bold text-indigo-600">{pct}%</span>
        </div>
      </div>

      <ol className="mt-4 space-y-1.5">
        {steps.map((step, i) => {
          const current = i === firstTodo
          return (
            <li
              key={step.id}
              className={`flex items-center gap-3 rounded-xl px-3 py-2.5 transition ${
                current ? 'bg-indigo-50 ring-1 ring-indigo-100' : ''
              }`}
            >
              <span
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                  step.done
                    ? 'bg-emerald-500 text-white'
                    : current
                      ? 'bg-indigo-600 text-white'
                      : 'bg-slate-100 text-slate-400'
                }`}
              >
                {step.done ? (
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" className="h-3.5 w-3.5">
                    <path d="M20 6L9 17l-5-5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                ) : (
                  i + 1
                )}
              </span>
              <div className="min-w-0 flex-1">
                <p
                  className={`truncate text-sm font-semibold ${
                    step.done ? 'text-slate-400' : current ? 'text-indigo-900' : 'text-slate-500'
                  }`}
                >
                  {step.label}
                </p>
                {current && <p className="truncate text-xs text-indigo-500">{step.hint}</p>}
              </div>
              {current ? (
                <button
                  onClick={() => onNavigate?.(step.tab)}
                  className="group inline-flex shrink-0 items-center gap-1 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-bold text-white shadow-sm transition hover:bg-indigo-700"
                >
                  Go
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5">
                    <path d="M5 12h14M13 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
              ) : step.done ? (
                <span className="shrink-0 text-xs font-semibold text-emerald-600">Done</span>
              ) : null}
            </li>
          )
        })}
      </ol>
    </section>
  )
}

/**
 * Phase 4 home dashboard — a warm greeting hero with the Ask box, then a row of
 * colorful stat cards summarising every module. The score trend only appears
 * once there are enough finished interviews to draw a real line.
 */
export default function DashboardPage({ onNavigate, userName }) {
  const [stats, setStats] = useState(null)
  const [jdCount, setJdCount] = useState(0)
  const [reviewCount, setReviewCount] = useState(0)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    // Stats doesn't carry JD/review counts, so fetch those lists too — they
    // drive the "What to do next" funnel. All are best-effort.
    const [st, jds, reviews] = await Promise.all([
      api.getStats().catch(() => null),
      api.listJds().catch(() => []),
      api.listReviews().catch(() => []),
    ])
    setStats(st)
    setJdCount(jds.length)
    setReviewCount(reviews.length)
    setLoading(false)
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const s = stats ?? {}
  const roadmap = s.roadmap ?? { done: 0, total: 0, percent: 0 }
  const outreach = s.outreach ?? { contacts: 0, sent: 0, replied: 0, reply_rate: 0 }
  const interviews = s.interviews ?? { count: 0, score_trend: [], latest_average: null }
  const trend = interviews.score_trend ?? []

  const greeting = userName
    ? `${timeGreeting()}, ${userName}`
    : `${timeGreeting()} — what can I help with?`

  // The mock-interview section — a rich gradient call-to-action when there's no
  // trend yet, or the score trend (still attractive) once there's data.
  const mockSection =
    trend.length >= 2 ? (
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Interview score trend
            </p>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-slate-900">
                {interviews.latest_average}
              </span>
              <span className="text-sm text-slate-400">/ 5 latest</span>
            </div>
            <div className="mt-2">
              <Sparkline values={trend} />
            </div>
          </div>
          <Button onClick={() => onNavigate?.('interview')}>Practice again</Button>
        </div>
      </section>
    ) : (
      <section className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-violet-600 via-indigo-600 to-sky-600 p-6 text-white shadow-lg shadow-indigo-200/50 sm:p-7">
        <div className="pointer-events-none absolute -right-8 -top-10 h-36 w-36 rounded-full bg-white/10 blur-2xl" />
        <div className="pointer-events-none absolute -bottom-12 left-10 h-36 w-36 rounded-full bg-white/10 blur-2xl" />
        <div className="relative flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="max-w-xl">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-white/15 px-3 py-1 text-xs font-semibold ring-1 ring-white/25">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v4" />
              </svg>
              AI Mock Interview
            </span>
            <h3 className="mt-3 text-xl font-bold sm:text-2xl">Practice a real voice interview</h3>
            <p className="mt-1.5 text-sm leading-relaxed text-white/85">
              The AI asks real questions out loud, listens to your spoken answers, and scores you on
              clarity and content — completely hands-free.
            </p>
            <div className="mt-3 flex flex-wrap gap-2 text-xs font-medium text-white/85">
              <span className="rounded-full bg-white/10 px-2.5 py-1 ring-1 ring-white/15">🎙 Voice Q&amp;A</span>
              <span className="rounded-full bg-white/10 px-2.5 py-1 ring-1 ring-white/15">📊 Scored feedback</span>
              <span className="rounded-full bg-white/10 px-2.5 py-1 ring-1 ring-white/15">🔒 100% local</span>
            </div>
          </div>
          <button
            onClick={() => onNavigate?.('interview')}
            className="group inline-flex shrink-0 items-center gap-2 self-start rounded-xl bg-white px-5 py-3 text-sm font-bold text-indigo-700 shadow-md transition hover:bg-indigo-50 sm:self-center"
          >
            Start mock interview
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="h-4 w-4 transition-transform group-hover:translate-x-0.5">
              <path d="M5 12h14M13 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>
      </section>
    )

  const statCards = (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Your snapshot
        </h2>
        <button
          onClick={load}
          disabled={loading}
          className="text-xs font-medium text-slate-500 transition hover:text-indigo-600 disabled:opacity-40"
        >
          {loading ? 'Refreshing…' : '↻ Refresh'}
        </button>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          id="resume"
          accent="from-indigo-500 to-indigo-600"
          label="Resume"
          value={s.resume ? s.resume.count : '—'}
          sub={s.resume ? s.resume.latest_title : 'None saved yet'}
        />
        <StatCard
          id="interview"
          accent="from-violet-500 to-fuchsia-600"
          label="Interviews"
          value={interviews.count}
          sub={
            interviews.latest_average != null
              ? `Last score ${interviews.latest_average}/5`
              : 'None finished yet'
          }
        />
        <StatCard
          id="roadmap"
          accent="from-sky-500 to-cyan-600"
          label="Roadmap"
          value={`${roadmap.percent}%`}
          sub={`${roadmap.done}/${roadmap.total} actions done`}
        />
        <StatCard
          id="outreach"
          accent="from-emerald-500 to-teal-600"
          label="Outreach replies"
          value={`${outreach.reply_rate}%`}
          sub={`${outreach.replied}/${outreach.sent} sent replied`}
        />
      </div>
    </div>
  )

  // The guided funnel — each step's `done` flag is derived from real data, so it
  // always points at the genuine next action.
  const steps = [
    {
      id: 'resume',
      label: 'Add your resume',
      hint: 'Upload a PDF and let the AI structure it.',
      tab: 'resume',
      done: (s.resume?.count ?? 0) > 0,
    },
    {
      id: 'jd',
      label: 'Add a target job',
      hint: 'Paste a posting you’re aiming for.',
      tab: 'jd',
      done: jdCount > 0,
    },
    {
      id: 'review',
      label: 'Run a resume review',
      hint: 'Score your fit and flag ATS issues.',
      tab: 'review',
      done: reviewCount > 0,
    },
    {
      id: 'interview',
      label: 'Practice a mock interview',
      hint: 'Answer real questions and get scored.',
      tab: 'interview',
      done: interviews.count > 0,
    },
    {
      id: 'outreach',
      label: 'Draft your first outreach',
      hint: 'Generate a message grounded in your resume.',
      tab: 'outreach',
      done: (outreach.sent ?? 0) > 0 || (outreach.contacts ?? 0) > 0,
    },
  ]

  // The snapshot shown beneath the welcome screen (hidden once a chat starts).
  // Mock-interview CTA stays on top, then guided next-steps, then the stat cards.
  const snapshot = (
    <div className="space-y-6">
      {mockSection}
      <NextSteps steps={steps} onNavigate={onNavigate} />
      {statCards}
    </div>
  )

  return <AskAssistant hero greeting={greeting} belowWelcome={snapshot} />
}
