import { useCallback, useEffect, useRef, useState } from 'react'
import { api, streamOutreach } from '../api.js'
import { Alert, Button, Card, PageHeader } from '../components/ui.jsx'

const PURPOSES = [
  { id: 'cold', label: 'Cold intro' },
  { id: 'referral', label: 'Referral ask' },
  { id: 'thankyou', label: 'Thank-you' },
  { id: 'followup', label: 'Follow-up' },
]

const PLATFORMS = [
  { id: 'linkedin_note', label: 'LinkedIn note (≤300)' },
  { id: 'inmail', label: 'InMail' },
  { id: 'email', label: 'Email' },
]

const STATUS_CHIP = {
  draft: 'bg-slate-100 text-slate-600 ring-slate-200',
  sent: 'bg-sky-50 text-sky-800 ring-sky-200',
  replied: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
}

const TONE_LABEL = {
  'concise-formal': 'Concise & formal',
  warm: 'Warm',
  direct: 'Direct',
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)
  return (
    <Button
      variant="secondary"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text)
          setCopied(true)
          setTimeout(() => setCopied(false), 1500)
        } catch {
          setCopied(false)
        }
      }}
    >
      {copied ? 'Copied!' : 'Copy'}
    </Button>
  )
}

function VariantCard({ draft }) {
  const over = draft.char_count > draft.char_limit
  const copyText = draft.subject ? `Subject: ${draft.subject}\n\n${draft.text}` : draft.text
  return (
    <div className="flex flex-col rounded-xl border border-t-4 border-slate-200 border-t-emerald-500 bg-white p-4 shadow-sm">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-bold uppercase tracking-wide text-emerald-700">
          {TONE_LABEL[draft.tone] ?? draft.tone}
        </span>
        <span className={`text-xs font-medium ${over ? 'text-rose-600' : 'text-slate-400'}`}>
          {draft.char_count}/{draft.char_limit}
        </span>
      </div>
      {draft.subject && (
        <p className="mb-1 text-sm font-medium text-slate-800">
          <span className="text-slate-400">Subject:</span> {draft.subject}
        </p>
      )}
      <p className="flex-1 whitespace-pre-wrap text-sm text-slate-700">{draft.text}</p>
      <div className="mt-3">
        <CopyButton text={copyText} />
      </div>
    </div>
  )
}

function StatusChip({ status }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ${STATUS_CHIP[status] ?? STATUS_CHIP.draft}`}
    >
      {status}
    </span>
  )
}

/**
 * Phase 3a — Outreach drafter. Manage hand-typed contacts, then generate three
 * toned, length-capped message variants grounded in your resume. The app never
 * sends anything: copy a variant, then mark it sent / replied.
 */
export default function OutreachPage({ ready }) {
  const [contacts, setContacts] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [contact, setContact] = useState(null) // detail with drafts

  const [form, setForm] = useState({ name: '', role: '', company: '', notes: '' })
  const [purpose, setPurpose] = useState('cold')
  const [platform, setPlatform] = useState('linkedin_note')
  const [hook, setHook] = useState('')

  const [running, setRunning] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [variants, setVariants] = useState(null)
  const [error, setError] = useState(null)
  const abortRef = useRef(null)

  const loadContacts = useCallback(async () => {
    setContacts(await api.listContacts().catch(() => []))
  }, [])

  useEffect(() => {
    loadContacts()
    return () => abortRef.current?.()
  }, [loadContacts])

  const openContact = useCallback(async (id) => {
    setSelectedId(id)
    setVariants(null)
    setError(null)
    try {
      setContact(await api.getContact(id))
    } catch (err) {
      setError({ message: err.message, hint: err.hint })
    }
  }, [])

  async function addContact(e) {
    e.preventDefault()
    if (!form.name.trim()) return
    const created = await api.createContact({
      name: form.name.trim(),
      role: form.role.trim() || null,
      company: form.company.trim() || null,
      notes: form.notes.trim() || null,
    })
    setForm({ name: '', role: '', company: '', notes: '' })
    await loadContacts()
    openContact(created.id)
  }

  function generate() {
    setRunning(true)
    setError(null)
    setVariants(null)
    setElapsed(0)

    abortRef.current = streamOutreach(
      { contactId: selectedId, purpose, platform, hook: hook.trim() },
      (event, data) => {
        if (event === 'heartbeat') setElapsed(data.elapsed_s)
        else if (event === 'done') {
          setVariants(data.drafts)
          setRunning(false)
          openContact(selectedId) // refresh history
        } else if (event === 'error') {
          setError({ message: data.message, hint: data.hint })
          setRunning(false)
        }
      },
    )
  }

  async function setStatus(draftId, status) {
    await api.setDraftStatus(draftId, status)
    openContact(selectedId)
  }

  const canGenerate = ready && selectedId && hook.trim() && !running
  const fieldCls =
    'w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-emerald-400 focus:bg-white focus:ring-2 focus:ring-emerald-100'

  return (
    <div className="space-y-6">
      <PageHeader
        theme="emerald"
        badge="Outreach"
        icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
            <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
          </svg>
        }
        title="Reach out with confidence"
        subtitle="Add a contact, then generate three toned, length-checked messages grounded in your resume. The app never sends — you copy, send, and track replies."
      />

      <Card title="Contacts" subtitle="Everyone here is typed by hand — nothing is scraped.">
        <form onSubmit={addContact} className="mt-4 grid gap-3 sm:grid-cols-2">
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Name *"
            className={fieldCls}
          />
          <input
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
            placeholder="Role"
            className={fieldCls}
          />
          <input
            value={form.company}
            onChange={(e) => setForm({ ...form, company: e.target.value })}
            placeholder="Company"
            className={fieldCls}
          />
          <input
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
            placeholder="Notes (a hook you know about them)"
            className={fieldCls}
          />
          <div className="sm:col-span-2">
            <Button type="submit" variant="gradient" disabled={!form.name.trim()}>
              + Add contact
            </Button>
          </div>
        </form>

        {contacts.length > 0 && (
          <ul className="mt-4 space-y-2">
            {contacts.map((c) => {
              const isSel = selectedId === c.id
              return (
                <li
                  key={c.id}
                  className={`group flex items-center gap-3 rounded-xl border p-3 transition ${
                    isSel
                      ? 'border-emerald-300 bg-emerald-50/60 ring-1 ring-emerald-200'
                      : 'border-slate-200 hover:border-emerald-200 hover:bg-emerald-50/30'
                  }`}
                >
                  <button onClick={() => openContact(c.id)} className="flex min-w-0 flex-1 items-center gap-3 text-left">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 text-sm font-bold uppercase text-white">
                      {c.name[0]}
                    </span>
                    <span className="min-w-0">
                      <span className={`block truncate text-sm ${isSel ? 'font-bold text-slate-900' : 'font-semibold text-slate-800'}`}>
                        {c.name}
                      </span>
                      <span className="block truncate text-xs text-slate-400">
                        {[c.role, c.company].filter(Boolean).join(' · ') || 'No details'}
                        {c.draft_count ? ` · ${c.draft_count} draft${c.draft_count === 1 ? '' : 's'}` : ''}
                      </span>
                    </span>
                  </button>
                  <button
                    onClick={async () => {
                      await api.deleteContact(c.id)
                      if (selectedId === c.id) {
                        setSelectedId(null)
                        setContact(null)
                      }
                      loadContacts()
                    }}
                    aria-label={`Delete ${c.name}`}
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-slate-400 transition hover:bg-rose-50 hover:text-rose-600"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
                      <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M6 6v14a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V6M10 11v6M14 11v6" strokeLinecap="round" />
                    </svg>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </Card>

      {contact && (
        <Card
          title={`Draft outreach to ${contact.name}`}
          subtitle={[contact.role, contact.company].filter(Boolean).join(' · ') || null}
        >
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
                Purpose
              </span>
              <select
                value={purpose}
                onChange={(e) => setPurpose(e.target.value)}
                className={`mt-1 ${fieldCls}`}
              >
                {PURPOSES.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
                Platform
              </span>
              <select
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
                className={`mt-1 ${fieldCls}`}
              >
                {PLATFORMS.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <label className="mt-4 block">
            <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Hook — one specific detail (required)
            </span>
            <input
              value={hook}
              onChange={(e) => setHook(e.target.value)}
              placeholder="e.g. their talk on FastAPI caching at PyCon"
              className={`mt-1 ${fieldCls}`}
            />
          </label>

          <div className="mt-4 flex items-center gap-3">
            <Button variant="gradient" onClick={generate} disabled={!canGenerate}>
              {running ? 'Drafting…' : '✦ Generate 3 variants'}
            </Button>
            {!ready && (
              <span className="text-sm text-slate-500">Needs the local model to be ready.</span>
            )}
            {!hook.trim() && ready && (
              <span className="text-sm text-slate-500">Add a hook to enable drafting.</span>
            )}
          </div>

          {running && (
            <div className="mt-4">
              <Alert
                tone="info"
                title="Writing three variants…"
                hint={`Grounded in your resume, all local${elapsed ? ` · ${elapsed}s elapsed` : ''}.`}
              />
            </div>
          )}

          {error && (
            <div className="mt-4">
              <Alert tone="error" title={error.message} hint={error.hint} />
            </div>
          )}

          {variants && (
            <div className="mt-5 grid gap-4 lg:grid-cols-3">
              {variants.map((d) => (
                <VariantCard key={d.id} draft={d} />
              ))}
            </div>
          )}
        </Card>
      )}

      {contact && contact.drafts.length > 0 && (
        <Card title="Draft history" subtitle="Copy a message into LinkedIn or Gmail, then mark it.">
          <ul className="mt-3 space-y-3">
            {contact.drafts.map((d) => (
              <li key={d.id} className="rounded-lg border border-slate-200 p-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs text-slate-500">
                    <span className="font-medium text-slate-700">
                      {d.platform.replace('_', ' ')}
                    </span>
                    · {d.purpose} · {TONE_LABEL[d.tone] ?? d.tone} · v{d.variant_no}
                    <StatusChip status={d.status} />
                  </div>
                  <div className="flex gap-2">
                    {d.status !== 'sent' && (
                      <Button variant="secondary" onClick={() => setStatus(d.id, 'sent')}>
                        Mark sent
                      </Button>
                    )}
                    {d.status === 'sent' && (
                      <Button variant="secondary" onClick={() => setStatus(d.id, 'replied')}>
                        Mark replied
                      </Button>
                    )}
                    <Button
                      variant="danger"
                      onClick={async () => {
                        await api.deleteDraft(d.id)
                        openContact(selectedId)
                      }}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
                {d.subject && (
                  <p className="mt-2 text-sm font-medium text-slate-700">Subject: {d.subject}</p>
                )}
                <p className="mt-1 whitespace-pre-wrap text-sm text-slate-600">{d.text}</p>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}
