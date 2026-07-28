import { useCallback, useEffect, useState } from 'react'
import { ApiError, api } from '../api.js'
import { Alert, Button, Card, Field, PageHeader, TextArea } from '../components/ui.jsx'

/**
 * Paste-only job description entry.
 *
 * There is deliberately no fetch-by-URL option: SOW §4.2 rules out scraping
 * LinkedIn, Indeed or Naukri on Terms-of-Service grounds.
 */
export default function JobDescriptionPage() {
  const [title, setTitle] = useState('')
  const [company, setCompany] = useState('')
  const [rawText, setRawText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(null)
  const [jds, setJds] = useState([])

  const refresh = useCallback(async () => {
    try {
      setJds(await api.listJds())
    } catch {
      /* listing failure is not worth an error banner */
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  async function pasteFromClipboard() {
    try {
      const text = await navigator.clipboard.readText()
      if (text) setRawText((prev) => (prev ? `${prev}\n${text}` : text))
    } catch {
      setError({ message: 'Could not read the clipboard.', hint: 'Paste manually with Ctrl+V.' })
    }
  }

  async function handleSave() {
    setBusy(true)
    setError(null)
    setSaved(null)
    try {
      const result = await api.saveJd({
        title: title.trim(),
        company: company.trim() || null,
        raw_text: rawText,
      })
      setSaved(result)
      setTitle('')
      setCompany('')
      setRawText('')
      await refresh()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? { message: err.message, hint: err.hint }
          : { message: String(err), hint: null },
      )
    } finally {
      setBusy(false)
    }
  }

  const canSave = !busy && title.trim() && rawText.trim().length >= 20

  return (
    <div className="space-y-6">
      <PageHeader
        theme="sky"
        badge="Job Descriptions"
        icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
            <rect x="3" y="7" width="18" height="13" rx="2" />
            <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
          </svg>
        }
        title="Add a target job"
        subtitle="Paste a posting you're aiming for. It powers your resume review, interview questions and skill-gap roadmap — stored locally, nothing scraped."
        stat={{ value: jds.length, label: 'saved' }}
      />

      {/* Form */}
      <Card
        title="Paste the posting"
        subtitle="Copy it straight from the job board — it's stored exactly as pasted."
      >
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <Field
            label="Job title"
            value={title}
            onChange={(v) => setTitle(v ?? '')}
            placeholder="Junior Python Developer"
            icon={
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
                <rect x="3" y="7" width="18" height="13" rx="2" />
                <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              </svg>
            }
          />
          <Field
            label="Company (optional)"
            value={company}
            onChange={(v) => setCompany(v ?? '')}
            placeholder="TechNova Solutions"
            icon={
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
                <path d="M3 21h18M5 21V5a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v16M9 7h2M9 11h2M9 15h2" />
              </svg>
            }
          />
        </div>

        <div className="mt-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Job description text
            </span>
            <button
              type="button"
              onClick={pasteFromClipboard}
              className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-medium text-indigo-600 transition hover:bg-indigo-50"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-3.5 w-3.5">
                <rect x="8" y="2" width="8" height="4" rx="1" />
                <path d="M8 4H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2" />
              </svg>
              Paste from clipboard
            </button>
          </div>
          <TextArea
            rows={14}
            value={rawText}
            onChange={setRawText}
            placeholder="Paste the full posting: responsibilities, required skills, nice-to-haves…"
          />
          <p className="mt-1 text-xs text-slate-400">
            {rawText.length.toLocaleString()} characters — paste the whole posting, including the
            nice-to-haves. Gap analysis matches against the employer&apos;s own wording.
          </p>
        </div>

        <div className="mt-4">
          <Button variant="gradient" onClick={handleSave} disabled={!canSave}>
            {busy ? 'Saving…' : 'Save job description'}
          </Button>
        </div>
      </Card>

      {saved && (
        <Alert
          tone="success"
          title={`Saved "${saved.title}"`}
          hint={saved.company ? `at ${saved.company} · id ${saved.id}` : `id ${saved.id}`}
        />
      )}

      {error && <Alert tone="error" title={error.message} hint={error.hint} />}

      {jds.length > 0 && (
        <Card
          title="Saved job descriptions"
          subtitle="Reused across Review, Interview and Roadmap — all stored locally."
        >
          <ul className="mt-4 space-y-2">
            {jds.map((jd) => (
              <li
                key={jd.id}
                className="group flex items-center gap-3 rounded-xl border border-slate-200 p-3 transition hover:border-indigo-200 hover:bg-indigo-50/40"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-sky-500 to-indigo-600 text-white">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
                    <rect x="3" y="7" width="18" height="13" rx="2" />
                    <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                  </svg>
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-slate-800">{jd.title}</p>
                  <p className="truncate text-xs text-slate-400">
                    {jd.company ? `${jd.company} · ` : ''}
                    {new Date(jd.created_at).toLocaleString()}
                  </p>
                </div>
                <button
                  onClick={async () => {
                    await api.deleteJd(jd.id)
                    refresh()
                  }}
                  aria-label={`Delete ${jd.title}`}
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
