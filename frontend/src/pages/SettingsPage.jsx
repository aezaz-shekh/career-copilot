import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import { pushToast } from '../toast.js'
import { Alert, Button, Card } from '../components/ui.jsx'

function formatBytes(n) {
  if (!n) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.min(Math.floor(Math.log(n) / Math.log(1024)), units.length - 1)
  return `${(n / 1024 ** i).toFixed(i ? 1 : 0)} ${units[i]}`
}

/**
 * Phase 4 settings: switch the active chat model to any installed one, see where
 * data lives, and delete all data behind a two-step (checkbox + typed) confirm.
 */
export default function SettingsPage() {
  const [settings, setSettings] = useState(null)
  const [model, setModel] = useState('')
  const [saving, setSaving] = useState(false)

  const [armed, setArmed] = useState(false)
  const [confirmText, setConfirmText] = useState('')
  const [deleting, setDeleting] = useState(false)

  const load = useCallback(async () => {
    try {
      const s = await api.getSettings()
      setSettings(s)
      setModel(s.chat_model)
    } catch {
      setSettings(null)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function saveModel() {
    setSaving(true)
    try {
      await api.setChatModel(model)
      pushToast({ tone: 'success', title: `Chat model switched to ${model}` })
      load()
    } catch {
      // toast already raised by the api layer
    } finally {
      setSaving(false)
    }
  }

  async function deleteAll() {
    setDeleting(true)
    try {
      const res = await api.deleteAllData('DELETE')
      pushToast({
        tone: 'success',
        title: 'All data deleted',
        hint: `${res.tables_cleared} tables cleared.`,
      })
      setArmed(false)
      setConfirmText('')
      load()
    } catch {
      // toast already raised
    } finally {
      setDeleting(false)
    }
  }

  if (!settings) {
    return (
      <Card>
        <p className="text-sm text-slate-500">Loading settings…</p>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <Card title="Model" subtitle="Pick any model you've installed. Answer scoring and question generation keep their tuned models.">
        <label className="mt-4 block">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Active chat model
          </span>
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            {!settings.installed_models.includes(model) && <option value={model}>{model}</option>}
            {settings.installed_models.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
        {settings.installed_models.length === 0 && (
          <p className="mt-2 text-sm text-amber-700">
            No models detected — is Ollama running? Check the Setup tab.
          </p>
        )}
        <div className="mt-4">
          <Button onClick={saveModel} disabled={saving || model === settings.chat_model}>
            {saving ? 'Saving…' : 'Save model'}
          </Button>
        </div>
        <p className="mt-3 text-xs text-slate-400">
          Default: {settings.default_chat_model} · Questions: {settings.question_model} · Embeddings:{' '}
          {settings.embed_model}
        </p>
      </Card>

      <Card title="Where my data lives">
        <div className="mt-3 text-sm">
          <p className="font-mono text-xs text-slate-600">{settings.data_path}</p>
          <p className="mt-2 text-slate-500">
            One local SQLite file · {formatBytes(settings.data_bytes)}. Nothing is uploaded anywhere.
          </p>
        </div>
      </Card>

      <Card title="Danger zone">
        <Alert
          tone="error"
          title="Delete ALL my data"
          hint="Removes every resume, job description, review, interview, roadmap, contact, and draft. This cannot be undone."
        />
        <div className="mt-4 space-y-3">
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={armed}
              onChange={(e) => {
                setArmed(e.target.checked)
                setConfirmText('')
              }}
              className="h-4 w-4 rounded border-slate-300"
            />
            I understand this permanently deletes everything.
          </label>
          {armed && (
            <div className="flex flex-wrap items-center gap-3">
              <input
                value={confirmText}
                onChange={(e) => setConfirmText(e.target.value)}
                placeholder="Type DELETE to confirm"
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
              <Button variant="danger" onClick={deleteAll} disabled={confirmText !== 'DELETE' || deleting}>
                {deleting ? 'Deleting…' : 'Delete everything'}
              </Button>
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}
