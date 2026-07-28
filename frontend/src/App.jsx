import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'
import { speakOnce } from './lib/speech.js'
import ToastHost from './components/ToastHost.jsx'
import WelcomeModal from './components/WelcomeModal.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import InterviewPage from './pages/InterviewPage.jsx'
import JobDescriptionPage from './pages/JobDescriptionPage.jsx'
import OutreachPage from './pages/OutreachPage.jsx'
import ResumePage from './pages/ResumePage.jsx'
import ReviewPage from './pages/ReviewPage.jsx'
import RoadmapPage from './pages/RoadmapPage.jsx'
import SettingsPage from './pages/SettingsPage.jsx'
import SetupPage from './pages/SetupPage.jsx'
import StatusPage from './pages/StatusPage.jsx'

const POLL_INTERVAL_MS = 10000

const STATUS = {
  connected: {
    label: 'Local AI · Connected',
    dot: 'bg-emerald-500',
    cls: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  },
  connectedHosted: {
    label: 'Hosted AI · Connected',
    dot: 'bg-emerald-500',
    cls: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  },
  degraded: {
    label: 'Setup incomplete',
    dot: 'bg-amber-500',
    cls: 'bg-amber-50 text-amber-800 ring-amber-200',
  },
  offline: { label: 'Offline', dot: 'bg-rose-500', cls: 'bg-rose-50 text-rose-700 ring-rose-200' },
  checking: {
    label: 'Checking…',
    dot: 'bg-slate-400 animate-pulse',
    cls: 'bg-slate-50 text-slate-600 ring-slate-200',
  },
}

const TABS = [
  { id: 'dashboard', label: 'Home' },
  { id: 'resume', label: 'Resume' },
  { id: 'interview', label: 'Interview' },
  { id: 'jd', label: 'Job Description' },
  { id: 'review', label: 'Review' },
  { id: 'roadmap', label: 'Roadmap' },
  { id: 'outreach', label: 'Outreach' },
  { id: 'setup', label: 'Setup' },
  { id: 'settings', label: 'Settings' },
  { id: 'status', label: 'Status' },
]

// Which tabs are "system/utility" (shown under a divider in the sidebar).
const SYSTEM_TABS = new Set(['setup', 'settings', 'status'])

/** A small line icon per nav item. */
function NavIcon({ id }) {
  const p = {
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    className: 'h-5 w-5 shrink-0',
  }
  switch (id) {
    case 'dashboard':
      return (
        <svg {...p}>
          <path d="M3 10.5L12 3l9 7.5" />
          <path d="M5 9.5V21h14V9.5" />
          <path d="M9 21v-6h6v6" />
        </svg>
      )
    case 'resume':
      return (
        <svg {...p}>
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <path d="M14 2v6h6" />
          <path d="M8 13h8M8 17h6" />
        </svg>
      )
    case 'jd':
      return (
        <svg {...p}>
          <rect x="3" y="7" width="18" height="13" rx="2" />
          <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
        </svg>
      )
    case 'review':
      return (
        <svg {...p}>
          <circle cx="11" cy="11" r="7" />
          <path d="M21 21l-4.3-4.3" />
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
          <path d="M22 2L11 13" />
          <path d="M22 2l-7 20-4-9-9-4 20-7z" />
        </svg>
      )
    case 'setup':
      return (
        <svg {...p}>
          <path d="M12 3v12" />
          <path d="M8 11l4 4 4-4" />
          <path d="M4 21h16" />
        </svg>
      )
    case 'settings':
      return (
        <svg {...p}>
          <circle cx="12" cy="12" r="3" />
          <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1l2.1-2.1M17 7l2.1-2.1" />
        </svg>
      )
    case 'status':
      return (
        <svg {...p}>
          <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
        </svg>
      )
    default:
      return null
  }
}

/**
 * Shell: owns the health poll (several pages need to know whether the model is
 * ready) and switches between pages.
 */
export default function App() {
  const [tab, setTab] = useState('dashboard')
  const [health, setHealth] = useState(null)
  const [backendError, setBackendError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [checkedAt, setCheckedAt] = useState(null)
  // Starts null on every load, so the welcome modal appears each time the app
  // is opened (the user asked to be greeted by name on every visit).
  const [userName, setUserName] = useState(null)
  // Mobile/tablet: the sidebar is an off-canvas drawer toggled by a hamburger.
  const [sidebarOpen, setSidebarOpen] = useState(false)

  async function speakGreeting(who) {
    // Piper when the host runs it, the browser's voice otherwise, silence if
    // neither — greeting the user must never surface an error.
    await speakOnce(`Hello ${who}, welcome to AI Career Co-Pilot`)
  }

  const checkHealth = useCallback(async () => {
    setLoading(true)
    try {
      const controller = new AbortController()
      const timer = setTimeout(() => controller.abort(), 8000)
      const response = await fetch('/health', { signal: controller.signal })
      clearTimeout(timer)
      if (!response.ok) throw new Error(`Backend returned HTTP ${response.status}`)
      setHealth(await response.json())
      setBackendError(null)
    } catch {
      setHealth(null)
      setBackendError('Cannot reach the backend API at 127.0.0.1:8000.')
    } finally {
      setLoading(false)
      setCheckedAt(new Date())
    }
  }, [])

  useEffect(() => {
    checkHealth()
    const id = setInterval(checkHealth, POLL_INTERVAL_MS)
    return () => clearInterval(id)
  }, [checkHealth])

  // Wire tab switches into browser history so the Back button moves between
  // screens (and lands on Home) instead of leaving the app.
  const navigate = useCallback((next) => {
    setTab(next)
    setSidebarOpen(false) // close the mobile drawer after picking a screen
    window.history.pushState({ tab: next }, '')
  }, [])

  useEffect(() => {
    // Mark the current entry as the "root" (Home), then push a buffer entry on
    // top. That guarantees the Back button always pops to a same-document entry
    // — so it can never unload the app; the worst it can do is return Home.
    window.history.replaceState({ tab: 'dashboard', root: true }, '')
    window.history.pushState({ tab: 'dashboard' }, '')
    const onPop = (event) => {
      const st = event.state
      if (st && st.tab && !st.root) {
        setTab(st.tab)
      } else {
        // Hit the root (or a foreign entry) — stay in the app, show Home, and
        // re-arm the buffer so the next Back press is caught too.
        setTab('dashboard')
        window.history.pushState({ tab: 'dashboard' }, '')
      }
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  // Generation runs on this machine unless the backend reports a hosted
  // provider, so the privacy copy below can state what is actually true rather
  // than claiming "local" on a deployment where chat is answered remotely.
  const isHosted = health?.inference_mode === 'hosted'
  const providerName = health?.inference_provider ?? 'a hosted provider'

  let state = 'checking'
  if (!loading || health || backendError) {
    if (backendError) state = 'offline'
    else if (health?.status === 'ok') state = isHosted ? 'connectedHosted' : 'connected'
    else if (health) state = health.ollama?.reachable ? 'degraded' : 'offline'
  }

  // Both connected variants are healthy; only the label differs.
  const isConnected = state === 'connected' || state === 'connectedHosted'
  const status = STATUS[state] ?? STATUS.checking
  const renderNavItem = (item) => (
    <button
      key={item.id}
      onClick={() => navigate(item.id)}
      className={`group flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
        tab === item.id
          ? 'bg-gradient-to-r from-indigo-600 to-violet-600 text-white shadow-sm shadow-indigo-200'
          : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
      }`}
    >
      <NavIcon id={item.id} />
      <span className="flex-1 text-left">{item.label}</span>
      {SYSTEM_TABS.has(item.id) && !isConnected && (
        <span
          className={`h-2 w-2 rounded-full ${state === 'offline' ? 'bg-rose-500' : 'bg-amber-500'}`}
        />
      )}
    </button>
  )

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-slate-50 text-slate-900">
      {!userName && <WelcomeModal onDone={(name) => setUserName(name)} />}

      {/* Slim gradient trust bar with a gentle shimmer sweep */}
      <div className="relative shrink-0 overflow-hidden bg-gradient-to-r from-indigo-500 via-violet-500 to-sky-500 px-4 py-2 text-white">
        <div className="pointer-events-none absolute inset-0 -translate-x-full animate-[shimmer_4s_ease-in-out_infinite] bg-gradient-to-r from-transparent via-white/25 to-transparent" />
        <div className="relative flex flex-wrap items-center justify-center gap-x-6 gap-y-1 text-xs font-semibold">
          <span className="flex items-center gap-1.5">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5">
              <path d="M12 2l8 4v6c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6l8-4z" />
            </svg>
            {isHosted ? 'Private · your data stays here' : '100% local & private'}
          </span>
          <span className="flex items-center gap-1.5">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5">
              <rect x="6" y="6" width="12" height="12" rx="2" />
              <path d="M9 2v2M15 2v2M9 20v2M15 20v2M2 9h2M2 15h2M20 9h2M20 15h2" />
            </svg>
            Runs on this machine
          </span>
          <span className="flex items-center gap-1.5">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5">
              <circle cx="12" cy="12" r="9" />
              <path d="M8 8h6M8 12h6M11 8c2 0 3 4-1 4l3 4" />
            </svg>
            ₹0 running cost
          </span>
          <span className="flex items-center gap-1.5">
            <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5">
              <path d="M12 3l2.09 6.26L20 11l-5.91 1.74L12 19l-2.09-6.26L4 11l5.91-1.74L12 3z" />
            </svg>
            5 AI modules
          </span>
        </div>
      </div>

      {/* Mobile/tablet top bar with a hamburger — hidden on large screens */}
      <div className="flex shrink-0 items-center gap-3 border-b border-slate-200 bg-white px-4 py-2.5 lg:hidden">
        <button
          onClick={() => setSidebarOpen(true)}
          aria-label="Open menu"
          className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-600 transition hover:bg-slate-100"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-6 w-6">
            <path d="M4 6h16M4 12h16M4 18h16" strokeLinecap="round" />
          </svg>
        </button>
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 via-violet-500 to-sky-500 text-white shadow-sm">
            <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
              <path d="M12 3l2.09 6.26L20 11l-5.91 1.74L12 19l-2.09-6.26L4 11l5.91-1.74L12 3z" />
            </svg>
          </div>
          <span className="bg-gradient-to-r from-indigo-600 to-violet-600 bg-clip-text text-sm font-extrabold text-transparent">
            Career Co-Pilot
          </span>
        </div>
        <span className={`ml-auto h-2.5 w-2.5 rounded-full ${status.dot}`} title={status.label} />
      </div>

      <div className="flex min-h-0 flex-1">
        {/* Dim backdrop behind the drawer on mobile */}
        {sidebarOpen && (
          <button
            aria-label="Close menu"
            onClick={() => setSidebarOpen(false)}
            className="fixed inset-0 z-30 bg-slate-900/40 lg:hidden"
          />
        )}

        {/* Sidebar — off-canvas drawer below lg, permanent from lg up */}
        <aside
          className={`fixed inset-y-0 left-0 z-40 flex h-full w-64 max-w-[82%] shrink-0 flex-col border-r border-slate-200 bg-white transition-transform duration-200 lg:static lg:z-auto lg:w-60 lg:max-w-none lg:translate-x-0 ${
            sidebarOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full'
          }`}
        >
          <div className="flex items-center gap-3 border-b border-slate-100 px-5 py-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 via-violet-500 to-sky-500 text-white shadow-md shadow-indigo-200/60">
              <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5">
                <path d="M12 3l2.09 6.26L20 11l-5.91 1.74L12 19l-2.09-6.26L4 11l5.91-1.74L12 3z" />
              </svg>
            </div>
            <div className="min-w-0">
              <p className="truncate bg-gradient-to-r from-indigo-600 to-violet-600 bg-clip-text text-base font-extrabold text-transparent">
                Career Co-Pilot
              </p>
              <p className="truncate text-[11px] text-slate-400">
                {isHosted ? 'Career assistant' : 'On-device assistant'}
              </p>
            </div>
            <button
              onClick={() => setSidebarOpen(false)}
              aria-label="Close menu"
              className="ml-auto flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100 lg:hidden"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
                <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
              </svg>
            </button>
          </div>

          <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
            {TABS.filter((t) => !SYSTEM_TABS.has(t.id)).map(renderNavItem)}
            <p className="px-3 pb-1 pt-4 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              System
            </p>
            {TABS.filter((t) => SYSTEM_TABS.has(t.id)).map(renderNavItem)}
          </nav>

          <div className="space-y-2 border-t border-slate-100 p-3">
            <span
              className={`flex items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold ring-1 ${status.cls}`}
            >
              <span className={`h-2 w-2 rounded-full ${status.dot}`} />
              {status.label}
            </span>
            {userName && (
              <button
                onClick={() => speakGreeting(userName)}
                title="Replay greeting"
                className="w-full rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:border-indigo-300 hover:text-indigo-700"
              >
                👋 Hi, {userName}
              </button>
            )}
          </div>
        </aside>

        {/* Content — the dashboard fills the whole surface (full-page chat);
            every other page keeps a comfortable centered, scrollable column. */}
        <main className="min-w-0 flex-1 overflow-y-auto">
          {tab === 'dashboard' ? (
            <DashboardPage onNavigate={navigate} userName={userName} />
          ) : (
            <div className="px-4 py-8 sm:px-8">
              <div className="mx-auto max-w-4xl">
                {tab === 'resume' && <ResumePage ready={isConnected} />}
                {tab === 'jd' && <JobDescriptionPage />}
                {tab === 'review' && <ReviewPage ready={isConnected} />}
                {tab === 'interview' && <InterviewPage ready={isConnected} />}
                {tab === 'roadmap' && <RoadmapPage ready={isConnected} />}
                {tab === 'outreach' && <OutreachPage ready={isConnected} />}
                {tab === 'setup' && <SetupPage />}
                {tab === 'settings' && <SettingsPage />}
                {tab === 'status' && (
                  <StatusPage
                    health={health}
                    backendError={backendError}
                    loading={loading}
                    checkedAt={checkedAt}
                    state={state}
                    onRecheck={checkHealth}
                  />
                )}
              </div>
            </div>
          )}
        </main>
      </div>
      <ToastHost />
    </div>
  )
}
