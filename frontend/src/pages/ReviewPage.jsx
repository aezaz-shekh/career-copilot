import { useCallback, useEffect, useRef, useState } from 'react'
import { api, runReview } from '../api.js'
import ProgressStepper from '../components/ProgressStepper.jsx'
import ReviewReport from '../components/ReviewReport.jsx'
import { Alert, Button, Card, PageHeader } from '../components/ui.jsx'

/**
 * The headline feature: pick a resume + JD, run the review, watch the stepper,
 * read the tabbed report. Past reports are listed and reopenable without
 * re-running (which would cost minutes again).
 */
export default function ReviewPage({ ready }) {
  const [resumes, setResumes] = useState([])
  const [jds, setJds] = useState([])
  const [resumeId, setResumeId] = useState('')
  const [jdId, setJdId] = useState('')

  const [running, setRunning] = useState(false)
  const [current, setCurrent] = useState(null)
  const [doneSteps, setDoneSteps] = useState([])
  const [detail, setDetail] = useState('')
  const [report, setReport] = useState(null)
  const [error, setError] = useState(null)
  const [history, setHistory] = useState([])
  const abortRef = useRef(null)

  const loadLists = useCallback(async () => {
    const [r, j, h] = await Promise.all([
      api.listResumes().catch(() => []),
      api.listJds().catch(() => []),
      api.listReviews().catch(() => []),
    ])
    setResumes(r)
    setJds(j)
    setHistory(h)
    if (r[0] && !resumeId) setResumeId(String(r[0].id))
    if (j[0] && !jdId) setJdId(String(j[0].id))
  }, [resumeId, jdId])

  useEffect(() => {
    loadLists()
    return () => abortRef.current?.()
  }, [loadLists])

  function start() {
    setRunning(true)
    setReport(null)
    setError(null)
    setDoneSteps([])
    setCurrent('retrieve')
    setDetail('')

    abortRef.current = runReview({ resumeId: Number(resumeId), jdId: Number(jdId) }, (event, data) => {
      if (event === 'step') {
        if (data.status === 'running') {
          setCurrent(data.stage)
        } else if (data.status === 'done') {
          setDoneSteps((prev) => [...new Set([...prev, data.stage])])
          setDetail(data.detail || '')
        }
      } else if (event === 'done') {
        setReport(data.report)
        setRunning(false)
        setCurrent(null)
        loadLists()
      } else if (event === 'error') {
        setError({ message: data.message, hint: data.hint })
        setRunning(false)
        setCurrent(null)
      }
    })
  }

  async function openPast(id) {
    setError(null)
    try {
      const r = await api.getReview(id)
      setReport(r.report_json)
    } catch (err) {
      setError({ message: err.message, hint: err.hint })
    }
  }

  const canRun = ready && resumeId && jdId && !running
  const selectCls =
    'mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-800 outline-none transition focus:border-indigo-400 focus:bg-white focus:ring-2 focus:ring-indigo-100'
  const resumeTitle = (id) => resumes.find((r) => r.id === id)?.title || `Resume #${id}`
  const jdTitle = (id) => {
    const j = jds.find((x) => x.id === id)
    return j ? `${j.title}${j.company ? ` — ${j.company}` : ''}` : `JD #${id}`
  }

  return (
    <div className="space-y-6">
      <PageHeader
        theme="indigo"
        badge="Resume Review"
        icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
            <circle cx="11" cy="11" r="7" />
            <path d="M21 21l-4.3-4.3" />
          </svg>
        }
        title="Match your resume to a job"
        subtitle="The AI compares a saved resume against a job description — scoring the fit, flagging ATS issues, and suggesting fixes. Runs entirely on this machine."
      />

      {/* Selector */}
      <Card title="Choose what to review" subtitle="Pick a saved resume and the job you're targeting.">
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Resume</span>
            <select value={resumeId} onChange={(e) => setResumeId(e.target.value)} className={selectCls}>
              <option value="">Select a resume…</option>
              {resumes.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.title}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Job description
            </span>
            <select value={jdId} onChange={(e) => setJdId(e.target.value)} className={selectCls}>
              <option value="">Select a job description…</option>
              {jds.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.title}
                  {j.company ? ` — ${j.company}` : ''}
                </option>
              ))}
            </select>
          </label>
        </div>

        {(resumes.length === 0 || jds.length === 0) && (
          <div className="mt-3">
            <Alert
              tone="warn"
              title="You need a saved resume and a job description first"
              hint="Add them on the Resume and Job Description tabs, then come back."
            />
          </div>
        )}

        <div className="mt-4 flex items-center gap-3">
          <Button variant="gradient" onClick={start} disabled={!canRun}>
            {running ? 'Reviewing…' : 'Run review'}
          </Button>
          {!ready && <span className="text-sm text-slate-500">Needs the local model to be ready.</span>}
        </div>

        {running && (
          <div className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-5">
            <p className="mb-4 text-sm text-slate-600">
              This takes a few minutes on CPU — three AI passes plus an ATS check, all local.
            </p>
            <ProgressStepper current={current} done={doneSteps} detail={detail} />
          </div>
        )}

        {error && <div className="mt-4"><Alert tone="error" title={error.message} hint={error.hint} /></div>}
      </Card>

      {report && (
        <Card title="Review report">
          <ReviewReport report={report} />
        </Card>
      )}

      {history.length > 0 && (
        <Card title="Past reviews" subtitle="Reopen a report without re-running it.">
          <ul className="mt-4 space-y-2">
            {history.map((h) => (
              <li
                key={h.id}
                className="group flex items-center gap-3 rounded-xl border border-slate-200 p-3 transition hover:border-indigo-200 hover:bg-indigo-50/40"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 text-white">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
                    <circle cx="11" cy="11" r="7" />
                    <path d="M21 21l-4.3-4.3" />
                  </svg>
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-slate-800">
                    {resumeTitle(h.resume_id)} <span className="text-slate-400">vs</span> {jdTitle(h.jd_id)}
                  </p>
                  <p className="text-xs text-slate-400">{new Date(h.created_at).toLocaleString()}</p>
                </div>
                <button
                  onClick={() => openPast(h.id)}
                  className="shrink-0 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:border-indigo-300 hover:bg-white hover:text-indigo-700"
                >
                  Open
                </button>
                <button
                  onClick={async () => {
                    await api.deleteReview(h.id)
                    loadLists()
                  }}
                  aria-label="Delete review"
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
