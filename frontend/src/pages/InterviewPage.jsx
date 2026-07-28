import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, api, streamQuestions } from '../api.js'
import { JOB_ROLES } from '../jobs.js'
import MockInterview from '../components/MockInterview.jsx'
import SessionSummary from '../components/SessionSummary.jsx'
import { Alert, Button, Card, PageHeader } from '../components/ui.jsx'
import { useHistorySubview } from '../useHistorySubview.js'

const DIFFICULTY = {
  1: { label: 'Easy', cls: 'bg-emerald-50 text-emerald-800 ring-emerald-200' },
  2: { label: 'Medium', cls: 'bg-amber-50 text-amber-900 ring-amber-200' },
  3: { label: 'Hard', cls: 'bg-rose-50 text-rose-800 ring-rose-200' },
}

function TypeBadge({ type }) {
  const cls =
    type === 'behavioral'
      ? 'bg-indigo-50 text-indigo-800 ring-indigo-200'
      : 'bg-sky-50 text-sky-800 ring-sky-200'
  return <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ${cls}`}>{type}</span>
}

function QuestionCard({ q, index }) {
  const diff = DIFFICULTY[q.difficulty] ?? DIFFICULTY[2]
  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-slate-900">
          {index}. {q.question}
        </p>
        <div className="flex shrink-0 gap-2">
          <TypeBadge type={q.type} />
          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ${diff.cls}`}>
            {diff.label}
          </span>
        </div>
      </div>
      <p className="mt-2 text-xs text-slate-500">
        <span className="font-medium">Looks for:</span> {q.looks_for}
      </p>
    </div>
  )
}

/**
 * Phase 2.1 — question bank. Pick a resume + JD, generate a grounded bank, then
 * filter by type and difficulty. "Start Mock Interview" is wired in the next
 * step (2.2); for now it explains that.
 */
export default function InterviewPage({ ready }) {
  const [jobSearch, setJobSearch] = useState('')
  const [selectedJob, setSelectedJob] = useState('')
  const [topics, setTopics] = useState('')

  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState(null) // {detail, elapsed_s} while generating
  const [questions, setQuestions] = useState(null)
  const [elapsedMs, setElapsedMs] = useState(null)
  const [error, setError] = useState(null)
  const [typeFilter, setTypeFilter] = useState('all')
  const [difficultyFilter, setDifficultyFilter] = useState('all')

  // phase: 'bank' (browsing questions) | 'interview' (answering) | 'summary'
  const [phase, setPhase] = useState('bank')
  const [session, setSession] = useState(null) // {session_id, questions}
  const [summary, setSummary] = useState(null)
  const [history, setHistory] = useState([])
  const [starting, setStarting] = useState(false)
  const [voice, setVoice] = useState(null) // {stt_available, tts_available}
  const pendingMock = useRef(false) // start the interview right after generating?

  const loadLists = useCallback(async () => {
    setHistory(await api.listInterviews().catch(() => []))
  }, [])

  useEffect(() => {
    loadLists()
    api.voiceStatus().then(setVoice).catch(() => setVoice(null))
  }, [loadLists])

  const filteredJobs = JOB_ROLES.filter((j) =>
    j.toLowerCase().includes(jobSearch.trim().toLowerCase()),
  )

  function generate(mockAfter = false) {
    const job = selectedJob.trim()
    const focus = topics.trim()
    if (!job && !focus) {
      setError({
        message: 'Pick a job or type a topic to generate questions.',
        hint: 'Choose a role from the list above, or type your interview topics.',
      })
      return
    }
    pendingMock.current = mockAfter
    setBusy(true)
    setError(null)
    setQuestions(null)
    setElapsedMs(null)
    setProgress({ detail: 'Starting…', elapsed_s: 0 })
    // Streams progress (step/heartbeat/done/error) so a multi-minute generation
    // on CPU shows a live elapsed-time instead of a spinner that looks stuck.
    streamQuestions({ jobTitle: job || undefined, topics: focus || undefined }, (event, data) => {
      if (event === 'step') {
        setProgress((p) => ({ ...(p ?? {}), detail: data.detail }))
      } else if (event === 'heartbeat') {
        setProgress((p) => ({ ...(p ?? {}), elapsed_s: data.elapsed_s }))
      } else if (event === 'done') {
        setQuestions({
          questions: data.questions,
          behavioral_count: data.behavioral_count,
          technical_count: data.technical_count,
        })
        setElapsedMs(data.elapsed_ms)
        setProgress(null)
        setBusy(false)
        if (pendingMock.current) startInterviewWith(data.questions)
      } else if (event === 'error') {
        setError({ message: data.message, hint: data.hint })
        setProgress(null)
        setBusy(false)
      }
    })
  }

  const filtered = (questions?.questions ?? []).filter(
    (q) =>
      (typeFilter === 'all' || q.type === typeFilter) &&
      (difficultyFilter === 'all' || String(q.difficulty) === difficultyFilter),
  )

  const canRun = ready && (selectedJob.trim() || topics.trim()) && !busy && !starting

  async function startInterviewWith(qs) {
    if (!qs || qs.length === 0) return
    setStarting(true)
    setError(null)
    try {
      const result = await api.startInterview({ jd_id: null, mode: 'text', questions: qs })
      setSession(result)
      setPhase('interview')
    } catch (err) {
      setError(
        err instanceof ApiError
          ? { message: err.message, hint: err.hint }
          : { message: String(err), hint: null },
      )
    } finally {
      setStarting(false)
    }
  }

  const startInterview = () => startInterviewWith(filtered)

  function handleFinished(finishedSession) {
    setSummary(finishedSession)
    setPhase('summary')
    loadLists()
  }

  function backToBank() {
    setPhase('bank')
    setSession(null)
    setSummary(null)
  }

  // While the mock-interview / summary sub-view is up, make the browser Back
  // button return to the question setup instead of jumping to another tab.
  useHistorySubview(phase !== 'bank', backToBank)

  async function openPastSession(id) {
    setError(null)
    try {
      const s = await api.getInterview(id)
      setSummary(s)
      setPhase('summary')
    } catch (err) {
      setError({ message: err.message, hint: err.hint })
    }
  }

  // --- Interview and summary phases take over the page ------------------- #
  if (phase === 'interview' && session) {
    return (
      <div className="space-y-4">
        <MockInterview
          sessionId={session.session_id}
          questions={session.questions}
          voiceStatus={voice}
          onFinish={handleFinished}
          onCancel={backToBank}
        />
      </div>
    )
  }

  if (phase === 'summary' && summary) {
    return (
      <div className="space-y-4">
        <Button variant="secondary" onClick={backToBank}>
          ← Back to questions
        </Button>
        <SessionSummary session={summary} />
      </div>
    )
  }

  const fieldCls =
    'mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-violet-400 focus:bg-white focus:ring-2 focus:ring-violet-100'
  const filterCls =
    'rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-sm outline-none transition focus:border-violet-400 focus:bg-white focus:ring-2 focus:ring-violet-100'

  return (
    <div className="space-y-6">
      <PageHeader
        theme="violet"
        badge="Mock Interview"
        icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        }
        title="Practice for the real thing"
        subtitle="Pick a role or your own topics, generate behavioral + technical questions, then run a scored mock interview — hands-free with voice, all on this machine."
      />

      <Card
        accent="violet"
        icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
            <path d="M12 3a4 4 0 0 0-4 4v3a4 4 0 0 0 8 0V7a4 4 0 0 0-4-4z" />
            <path d="M5 10v1a7 7 0 0 0 14 0v-1M12 18v3M8 21h8" strokeLinecap="round" />
          </svg>
        }
        title="Set up your interview"
        subtitle="Pick a job (or type your own topics) and generate behavioral + technical questions."
      >
        {/* Searchable job list */}
        <label className="block">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-700">
            Choose a job
            <span className="ml-2 font-medium normal-case text-slate-400">({filteredJobs.length} roles)</span>
          </span>
          <input
            value={jobSearch}
            onChange={(e) => setJobSearch(e.target.value)}
            placeholder="Search roles… e.g. React, Data Analyst, QA"
            className={fieldCls}
          />
        </label>
        <div className="mt-2 max-h-56 overflow-y-auto rounded-xl border border-slate-200 bg-slate-50/50 p-2">
          <div className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
            {filteredJobs.map((job) => {
              const isSel = selectedJob === job
              return (
                <button
                  key={job}
                  type="button"
                  onClick={() => setSelectedJob(job)}
                  className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm font-medium transition ${
                    isSel
                      ? 'border-violet-400 bg-violet-50 font-semibold text-violet-700 shadow-sm'
                      : 'border-slate-200 bg-white text-slate-800 hover:-translate-y-0.5 hover:border-violet-300 hover:bg-violet-50/40 hover:shadow-sm'
                  }`}
                >
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    className={`h-4 w-4 shrink-0 ${isSel ? 'text-violet-500' : 'text-slate-500'}`}
                  >
                    <rect x="3" y="7" width="18" height="13" rx="2" />
                    <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                  </svg>
                  <span className="flex-1 truncate">{job}</span>
                  {isSel && (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" className="h-4 w-4 shrink-0 text-violet-600">
                      <path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                </button>
              )
            })}
            {filteredJobs.length === 0 && (
              <p className="col-span-full py-3 text-center text-xs text-slate-400">
                No roles match “{jobSearch}”. You can still type topics below.
              </p>
            )}
          </div>
        </div>

        {/* Interview topics */}
        <label className="mt-4 block">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-700">
            Interview topics <span className="font-medium normal-case text-slate-400">(optional)</span>
          </span>
          <textarea
            value={topics}
            onChange={(e) => setTopics(e.target.value)}
            rows={2}
            placeholder="e.g. React hooks, REST APIs, SQL joins, system design basics"
            className={`${fieldCls} resize-y leading-relaxed`}
          />
        </label>

        {selectedJob && (
          <p className="mt-2 text-xs text-slate-500">
            Generating for: <span className="font-semibold text-slate-700">{selectedJob}</span>
          </p>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button variant="gradient" onClick={() => generate(false)} disabled={!canRun}>
            {busy && !pendingMock.current ? 'Generating…' : 'Generate questions'}
          </Button>
          <Button variant="secondary" onClick={() => generate(true)} disabled={!canRun}>
            {busy && pendingMock.current
              ? 'Starting…'
              : starting
                ? 'Starting…'
                : '🎙 Start mock interview'}
          </Button>
          {!ready && <span className="text-sm text-slate-500">Needs the local model to be ready.</span>}
        </div>

        {busy && (
          <div className="mt-4">
            <Alert
              tone="info"
              title={progress?.detail ?? 'Generating a full question bank…'}
              hint={`Runs entirely on your machine — a couple of minutes on CPU.${
                progress?.elapsed_s ? ` ${progress.elapsed_s}s elapsed…` : ''
              }`}
            />
          </div>
        )}

        {error && <div className="mt-4"><Alert tone="error" title={error.message} hint={error.hint} /></div>}
      </Card>

      {questions && (
        <Card
          title={`${questions.questions.length} questions`}
          subtitle={`${questions.behavioral_count} behavioral · ${questions.technical_count} technical${
            elapsedMs ? ` · generated in ${(elapsedMs / 1000).toFixed(1)}s` : ''
          }`}
        >
          <div className="mt-4 flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium uppercase text-slate-500">Type</span>
              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className={filterCls}
              >
                <option value="all">All</option>
                <option value="behavioral">Behavioral</option>
                <option value="technical">Technical</option>
              </select>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium uppercase text-slate-500">Difficulty</span>
              <select
                value={difficultyFilter}
                onChange={(e) => setDifficultyFilter(e.target.value)}
                className={filterCls}
              >
                <option value="all">All</option>
                <option value="1">Easy</option>
                <option value="2">Medium</option>
                <option value="3">Hard</option>
              </select>
            </div>
            <span className="text-xs text-slate-400">
              Showing {filtered.length} of {questions.questions.length}
            </span>
          </div>

          <div className="mt-4 space-y-3">
            {filtered.map((q, i) => (
              <QuestionCard key={i} q={q} index={i + 1} />
            ))}
            {filtered.length === 0 && (
              <p className="py-6 text-center text-sm text-slate-400">No questions match these filters.</p>
            )}
          </div>

          <div className="mt-6 border-t border-slate-200 pt-5">
            <div className="flex items-center gap-3">
              <Button variant="gradient" onClick={startInterview} disabled={starting || filtered.length === 0}>
                {starting ? 'Starting…' : `🎙 Start Mock Interview (${filtered.length} questions)`}
              </Button>
              <span className="text-xs text-slate-400">
                Uses the questions currently shown. Scores are revealed at the end.
              </span>
            </div>
          </div>
        </Card>
      )}

      {history.length > 0 && (
        <Card title="Past interviews" subtitle="Replay a finished session or resume one in progress.">
          <ul className="mt-4 space-y-2">
            {history.map((h) => (
              <li
                key={h.id}
                className="group flex items-center gap-3 rounded-xl border border-slate-200 p-3 transition hover:border-violet-200 hover:bg-violet-50/40"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500 to-fuchsia-600 text-white">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                  </svg>
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-slate-800">
                    {h.turn_count} answer{h.turn_count === 1 ? '' : 's'}
                    {h.ended_at ? '' : ' · in progress'}
                  </p>
                  <p className="text-xs text-slate-400">{new Date(h.started_at).toLocaleString()}</p>
                </div>
                <button
                  onClick={() => openPastSession(h.id)}
                  className="shrink-0 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:border-violet-300 hover:bg-white hover:text-violet-700"
                >
                  {h.ended_at ? 'Replay' : 'View'}
                </button>
                <button
                  onClick={async () => {
                    await api.deleteInterview(h.id)
                    loadLists()
                  }}
                  aria-label="Delete interview"
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-slate-400 transition hover:bg-rose-50 hover:text-rose-600"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
                    <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M6 6v14a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V6M10 11v6M14 11v6" strokeLinecap="round" />
                  </svg>
                </button>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}
