import { useCallback, useEffect, useState } from 'react'
import { ApiError, api } from '../api.js'
import FileDrop from '../components/FileDrop.jsx'
import ResumeEditor from '../components/ResumeEditor.jsx'
import { Alert, Button, Card, PageHeader, TextArea } from '../components/ui.jsx'

const EMPTY_PARSED = {
  contact: { name: null, email: null, phone: null, location: null, links: [] },
  summary: null,
  experience: [],
  education: [],
  skills: [],
  projects: [],
  certifications: [],
}

/** A step card with a numbered badge that turns green when the step is done. */
function StepCard({ n, title, subtitle, state, children, id }) {
  const badge =
    state === 'done'
      ? 'bg-emerald-500 text-white'
      : state === 'active'
        ? 'bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-md shadow-indigo-200'
        : 'bg-slate-100 text-slate-400'
  return (
    <section
      id={id}
      className={`rounded-2xl border bg-white p-6 shadow-sm transition ${
        state === 'todo' ? 'border-slate-200 opacity-75' : 'border-slate-200'
      }`}
    >
      <div className="flex items-start gap-3.5">
        <span
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-bold ${badge}`}
        >
          {state === 'done' ? (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" className="h-4 w-4">
              <path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          ) : (
            n
          )}
        </span>
        <div className="min-w-0">
          <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
          {subtitle && <p className="mt-0.5 text-sm text-slate-600">{subtitle}</p>}
        </div>
      </div>
      {children}
    </section>
  )
}

/**
 * Upload -> extract -> structure -> review and edit -> save.
 *
 * The review step between structuring and saving is required by SOW §11, so
 * "Save" only appears once the user has had a chance to correct the parse.
 */
export default function ResumePage({ ready }) {
  const [rawText, setRawText] = useState('')
  const [quality, setQuality] = useState(null)
  const [parsed, setParsed] = useState(null)
  const [title, setTitle] = useState('')
  const [busy, setBusy] = useState(null) // 'upload' | 'structure' | 'save'
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(null)
  const [elapsedMs, setElapsedMs] = useState(null)
  const [versions, setVersions] = useState([])

  const refreshVersions = useCallback(async () => {
    try {
      setVersions(await api.listResumes())
    } catch {
      /* the list is not important enough to surface an error for */
    }
  }, [])

  useEffect(() => {
    refreshVersions()
  }, [refreshVersions])

  function fail(err) {
    setError(
      err instanceof ApiError
        ? { message: err.message, hint: err.hint }
        : { message: String(err), hint: null },
    )
  }

  async function handleFile(file) {
    setBusy('upload')
    setError(null)
    setSaved(null)
    try {
      const result = await api.uploadResume(file)
      setRawText(result.raw_text)
      setQuality(result.quality)
      setParsed(null)
      if (!title) setTitle(file.name.replace(/\.(pdf|txt)$/i, ''))
    } catch (err) {
      fail(err)
    } finally {
      setBusy(null)
    }
  }

  async function handleStructure() {
    setBusy('structure')
    setError(null)
    try {
      const result = await api.structureResume(rawText)
      setParsed(result.parsed)
      setElapsedMs(result.elapsed_ms)
    } catch (err) {
      fail(err)
    } finally {
      setBusy(null)
    }
  }

  async function handleSave() {
    setBusy('save')
    setError(null)
    try {
      const result = await api.saveResume({
        title: title.trim() || 'Untitled resume',
        raw_text: rawText,
        parsed_json: parsed,
      })
      setSaved(result)
      await refreshVersions()
    } catch (err) {
      fail(err)
    } finally {
      setBusy(null)
    }
  }

  function reset() {
    setRawText('')
    setQuality(null)
    setParsed(null)
    setTitle('')
    setSaved(null)
    setError(null)
    setElapsedMs(null)
  }

  // Load a saved version back into the review step so it can be viewed/edited.
  async function openVersion(id) {
    setError(null)
    setSaved(null)
    try {
      const v = await api.getResume(id)
      setRawText(v.raw_text || '')
      setParsed(v.parsed_json ?? EMPTY_PARSED)
      setTitle(v.title || '')
      setQuality(null)
      setElapsedMs(null)
      // Bring the loaded content into view.
      requestAnimationFrame(() =>
        document.getElementById('resume-review')?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
      )
    } catch (err) {
      fail(err)
    }
  }

  // Step progress drives the numbered badges (todo → active → done).
  const step1 = rawText ? 'done' : 'active'
  const step2 = parsed ? 'done' : rawText ? 'active' : 'todo'
  const step3 = saved ? 'done' : parsed ? 'active' : 'todo'

  return (
    <div className="space-y-6">
      <PageHeader
        theme="indigo"
        badge="Resume Studio"
        icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <path d="M14 2v6h6M8 13h8M8 17h6" />
          </svg>
        }
        title="Build & structure your resume"
        subtitle="Upload a PDF, let the local AI split it into clean sections, review, and save versions — all private, on your machine."
        stat={{ value: versions.length, label: 'saved' }}
      />

      <StepCard
        n={1}
        state={step1}
        title="Upload your resume"
        subtitle="PDF or plain text. You can also paste the text directly below."
      >
        <div className="mt-4">
          <FileDrop onFile={handleFile} disabled={busy !== null} />
        </div>

        {busy === 'upload' && <p className="mt-3 text-sm text-slate-500">Reading file…</p>}

        {quality && (
          <div className="mt-4 space-y-3">
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate-500">
              <span>
                Parser: <strong className="text-slate-700">{quality.parser_used}</strong>
              </span>
              <span>
                {quality.character_count.toLocaleString()} characters
                {quality.page_count > 0 && ` · ${quality.page_count} page(s)`}
              </span>
              {quality.fallback_used && <span className="text-amber-700">fallback parser used</span>}
            </div>

            {quality.warnings.length > 0 && (
              <Alert
                tone="warn"
                title="The extracted text may be incomplete"
                hint="Check the text below and fix anything wrong before continuing — that is what this step is for."
              >
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                  {quality.warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              </Alert>
            )}
          </div>
        )}
      </StepCard>

      <StepCard
        n={2}
        state={step2}
        title="Check the extracted text"
        subtitle="Edit anything the parser got wrong. This text is what the model reads."
      >
        <div className="mt-4">
          <TextArea
            rows={12}
            mono
            value={rawText}
            onChange={setRawText}
            placeholder="Upload a file above, or paste your resume text here."
          />
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button
            onClick={handleStructure}
            disabled={busy !== null || !ready || rawText.trim().length < 20}
          >
            {busy === 'structure' ? 'Working…' : 'Split into sections with local AI'}
          </Button>
          {rawText && (
            <Button variant="secondary" onClick={reset}>
              Start over
            </Button>
          )}
          {!ready && <span className="text-sm text-slate-500">Needs the local model to be ready.</span>}
        </div>

        {busy === 'structure' && (
          <Alert
            tone="info"
            title="Generating…"
            hint="A full resume takes a few minutes on CPU-only hardware. This runs entirely on your machine."
          />
        )}
      </StepCard>

      {parsed && (
        <StepCard
          id="resume-review"
          n={3}
          state={step3}
          title="Review and correct the sections"
          subtitle="Nothing is saved until you press Save, so edit freely."
        >
          {elapsedMs !== null && (
            <p className="mt-1 text-xs text-slate-400">
              Structured locally in {(elapsedMs / 1000).toFixed(1)} s
            </p>
          )}
          <div className="mt-4">
            <ResumeEditor parsed={parsed} onChange={setParsed} />
          </div>

          <div className="mt-8 border-t border-slate-200 pt-5">
            <label className="block">
              <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
                Version name
              </span>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Original, or Tailored for TechNova"
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
              />
            </label>
            <div className="mt-3 flex items-center gap-3">
              <Button onClick={handleSave} disabled={busy !== null}>
                {busy === 'save' ? 'Saving…' : 'Save this version'}
              </Button>
              <span className="text-xs text-slate-400">
                Versions accumulate so you can compare tailored against original.
              </span>
            </div>
          </div>
        </StepCard>
      )}

      {saved && (
        <Alert
          tone="success"
          title={`Saved as "${saved.title}"`}
          hint={`Version id ${saved.id}. Stored in your local SQLite file — nothing left this machine.`}
        />
      )}

      {error && <Alert tone="error" title={error.message} hint={error.hint} />}

      {versions.length > 0 && (
        <Card title="Saved versions" subtitle="Each version is stored locally — compare tailored against original.">
          <ul className="mt-4 space-y-2">
            {versions.map((version) => (
              <li
                key={version.id}
                className="group flex items-center gap-3 rounded-xl border border-slate-200 p-3 transition hover:border-indigo-200 hover:bg-indigo-50/40"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 text-white">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <path d="M14 2v6h6M8 13h8M8 17h6" />
                  </svg>
                </span>
                <button
                  onClick={() => openVersion(version.id)}
                  className="min-w-0 flex-1 text-left"
                  title="Open this version"
                >
                  <p className="truncate text-sm font-semibold text-slate-800 group-hover:text-indigo-700">
                    {version.title}
                  </p>
                  <p className="text-xs text-slate-400">
                    {new Date(version.created_at).toLocaleString()}
                  </p>
                </button>
                <button
                  onClick={() => openVersion(version.id)}
                  className="shrink-0 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:border-indigo-300 hover:bg-white hover:text-indigo-700"
                >
                  Open
                </button>
                <button
                  onClick={async () => {
                    await api.deleteResume(version.id)
                    refreshVersions()
                  }}
                  aria-label={`Delete ${version.title}`}
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
