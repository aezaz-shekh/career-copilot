import { useState } from 'react'
import { api } from '../api.js'

/**
 * First-run welcome. The user enters their name, then the local Piper TTS voice
 * greets them out loud. If voice isn't configured the greeting is silent — the
 * modal still works. Called once (App gates it on a stored name).
 */
export default function WelcomeModal({ onDone }) {
  const [name, setName] = useState('')
  const [greeting, setGreeting] = useState(false)
  const [speaking, setSpeaking] = useState(false)

  async function submit(e) {
    e.preventDefault()
    const clean = name.trim()
    if (!clean) return
    setGreeting(true)
    setSpeaking(true)
    try {
      const url = await api.speak(`Hello ${clean}, welcome to AI Career Co-Pilot`)
      const audio = new Audio(url)
      audio.onended = () => {
        URL.revokeObjectURL(url)
        setSpeaking(false)
      }
      await audio.play().catch(() => setSpeaking(false))
    } catch {
      // Voice not configured — greet silently.
      setSpeaking(false)
    }
  }

  const clean = name.trim()

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-sm">
      <div className="w-full max-w-md overflow-hidden rounded-3xl bg-white shadow-2xl">
        <div className="bg-gradient-to-br from-indigo-500 via-violet-500 to-sky-500 px-8 py-9 text-center text-white">
          <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-2xl bg-white/20 text-3xl shadow-inner backdrop-blur">
            🚀
          </div>
          <h2 className="text-2xl font-bold tracking-tight">AI Career Co-Pilot</h2>
          <p className="mt-1 text-sm text-white/80">Private · Yours · ₹0</p>
        </div>

        <div className="p-8">
          {!greeting ? (
            <form onSubmit={submit}>
              <label className="block text-sm font-semibold text-slate-700">
                What should we call you?
              </label>
              <input
                autoFocus
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Enter your name"
                maxLength={40}
                className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
              />
              <button
                type="submit"
                disabled={!clean}
                className="mt-4 w-full rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-4 py-3 text-sm font-semibold text-white shadow-lg transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Enter →
              </button>
              <p className="mt-3 text-center text-xs text-slate-400">
                Your name stays on this device.
              </p>
            </form>
          ) : (
            <div className="text-center">
              <p className="text-2xl font-bold text-slate-900">
                Hello, {clean}! <span className="inline-block animate-pulse">👋</span>
              </p>
              <p className="mt-2 text-slate-600">Welcome to AI Career Co-Pilot.</p>
              {speaking && (
                <p className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-indigo-500">
                  <span className="animate-pulse">🔊</span> speaking…
                </p>
              )}
              <button
                onClick={() => onDone(clean)}
                className="mt-6 w-full rounded-xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white transition hover:bg-slate-700"
              >
                Get started
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
