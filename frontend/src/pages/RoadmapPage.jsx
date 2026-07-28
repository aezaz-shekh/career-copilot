import { useCallback, useEffect, useRef, useState } from 'react'
import { api, streamRoadmap } from '../api.js'
import { Alert, Button, Card, PageHeader } from '../components/ui.jsx'
import { ROADMAP_EXTRAS, ROLE_ROADMAPS, SKILL_ROADMAPS, STATIC_ROADMAPS } from '../roadmaps.js'

const STEPS = [
  { id: 'retrieve', label: 'Reading your resume' },
  { id: 'skill_gap', label: 'Assessing skill gaps' },
  { id: 'roadmap', label: 'Building your roadmap' },
]

const PRIORITY = {
  high: { bar: 'bg-rose-500', badge: 'bg-rose-50 text-rose-800 ring-rose-200', edge: 'border-l-rose-500', rank: 0 },
  medium: { bar: 'bg-amber-500', badge: 'bg-amber-50 text-amber-900 ring-amber-200', edge: 'border-l-amber-500', rank: 1 },
  low: { bar: 'bg-sky-500', badge: 'bg-sky-50 text-sky-800 ring-sky-200', edge: 'border-l-sky-500', rank: 2 },
}

const ACTION_TYPE = {
  course: 'bg-indigo-50 text-indigo-800 ring-indigo-200',
  project: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  cert: 'bg-violet-50 text-violet-800 ring-violet-200',
  practice: 'bg-slate-100 text-slate-700 ring-slate-200',
}

const itemLabel = (it) => (Array.isArray(it) ? it[0] : it)
const itemNote = (it) => (Array.isArray(it) ? it[1] : null)

// Each roadmap section cycles through a colour theme, so the graph reads as a
// bright, sequenced journey. Full literal class strings so Tailwind picks them up.
const SECTION_THEMES = [
  { node: 'bg-gradient-to-br from-indigo-500 to-violet-600', group: 'border-indigo-200 bg-indigo-50', bar: 'border-t-indigo-500', dot: 'bg-indigo-500' },
  { node: 'bg-gradient-to-br from-sky-500 to-cyan-600', group: 'border-sky-200 bg-sky-50', bar: 'border-t-sky-500', dot: 'bg-sky-500' },
  { node: 'bg-gradient-to-br from-emerald-500 to-teal-600', group: 'border-emerald-200 bg-emerald-50', bar: 'border-t-emerald-500', dot: 'bg-emerald-500' },
  { node: 'bg-gradient-to-br from-amber-500 to-orange-600', group: 'border-amber-200 bg-amber-50', bar: 'border-t-amber-500', dot: 'bg-amber-500' },
  { node: 'bg-gradient-to-br from-rose-500 to-pink-600', group: 'border-rose-200 bg-rose-50', bar: 'border-t-rose-500', dot: 'bg-rose-500' },
]

// Coloured avatar backgrounds for the "Essential Tools" chips.
const TOOL_COLORS = [
  'bg-indigo-500', 'bg-sky-500', 'bg-emerald-500', 'bg-amber-500',
  'bg-rose-500', 'bg-violet-500', 'bg-cyan-500', 'bg-teal-500',
]

// A relevant emoji per section, chosen from keywords in the section title, so
// each card gets an icon like the poster without needing per-roadmap art.
function sectionIcon(title = '') {
  const t = title.toLowerCase()
  const map = [
    [/found|basic|fundament|intro/, '🧱'],
    [/core|essential/, '⚙️'],
    [/tool|quality/, '🛠️'],
    [/job|ready|portfolio|career/, '🚀'],
    [/secur|auth/, '🔐'],
    [/test|qa/, '🧪'],
    [/data|database/, '🗄️'],
    [/deploy|devops|cloud|ops/, '☁️'],
    [/design|ui|ux/, '🎨'],
    [/practice/, '💪'],
    [/write|bullet/, '✍️'],
    [/format|ats/, '📄'],
    [/polish|proof|review/, '✨'],
    [/prepare|target/, '🎯'],
    [/tailor|apply|section|structure/, '📬'],
    [/advanced/, '🔥'],
    [/api|integrat/, '🔌'],
    [/concept|idea|scale/, '💡'],
    [/skill|now/, '🧠'],
    [/month/, '📅'],
  ]
  for (const [re, icon] of map) if (re.test(t)) return icon
  return '📌'
}

// The three-step "Practice · Build · Deploy" footer labels + icons.
const PBD = [
  ['Practice', '💪'],
  ['Build', '🔨'],
  ['Deploy', '🚀'],
]

/** Centered pill header sitting on a divider line (roadmap.sh-style). */
function PillHeader({ children }) {
  return (
    <div className="relative my-5 flex items-center justify-center">
      <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-slate-200" />
      <span className="relative rounded-lg border border-slate-200 bg-white px-4 py-1.5 text-sm font-semibold text-slate-700 shadow-sm">
        {children}
      </span>
    </div>
  )
}

// Coloured left accents cycled across the catalog cards.
const CARD_ACCENTS = [
  'border-l-indigo-400', 'border-l-sky-400', 'border-l-emerald-400',
  'border-l-amber-400', 'border-l-rose-400', 'border-l-violet-400',
]

// A relevant emoji for each roadmap name (keyword-matched, with a fallback).
function roadmapIcon(name = '') {
  const t = name.toLowerCase()
  const map = [
    [/front/, '🎨'],
    [/back/, '🗄️'],
    [/full ?stack/, '🧩'],
    [/data scien/, '🔬'],
    [/data anal/, '📊'],
    [/data eng/, '🛠️'],
    [/devops/, '☁️'],
    [/cloud/, '☁️'],
    [/qa|test/, '🧪'],
    [/ios/, '🍎'],
    [/android|mobile/, '📱'],
    [/game/, '🎮'],
    [/blockchain|web3/, '⛓️'],
    [/\bai\b|machine/, '🤖'],
    [/cyber|security/, '🔒'],
    [/ui\/ux|design/, '🎨'],
    [/python/, '🐍'],
    [/javascript/, '📜'],
    [/typescript/, '🟦'],
    [/react/, '⚛️'],
    [/node/, '🟢'],
    [/\bjava\b/, '☕'],
    [/docker|container/, '🐳'],
    [/\bgit/, '🌿'],
    [/data struct|algorith|dsa/, '🧮'],
    [/sql|database/, '🗃️'],
    [/system design/, '🏗️'],
    [/resume/, '📄'],
  ]
  for (const [re, icon] of map) if (re.test(t)) return icon
  return '🧭'
}

/** A grid of clickable roadmap cards; clicking one generates that roadmap. */
function CatalogGrid({ items, onPick, disabled }) {
  return (
    <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((label, i) => (
        <button
          key={label}
          type="button"
          onClick={() => onPick(label)}
          disabled={disabled}
          className={`group flex items-center gap-3 rounded-xl border border-l-4 border-slate-200 bg-white px-3.5 py-3 text-left shadow-sm transition enabled:hover:-translate-y-0.5 enabled:hover:border-indigo-300 enabled:hover:shadow-md disabled:cursor-not-allowed disabled:opacity-50 ${CARD_ACCENTS[i % CARD_ACCENTS.length]}`}
        >
          <span className="text-xl leading-none">{roadmapIcon(label)}</span>
          <span className="flex-1 text-sm font-semibold text-slate-800 group-enabled:group-hover:text-indigo-700">
            {label}
          </span>
          <span className="text-slate-300 transition group-enabled:group-hover:text-indigo-500">
            →
          </span>
        </button>
      ))}
    </div>
  )
}

/**
 * A curated, static roadmap shown instantly (no model call). Progress is ticked
 * per item and saved in the browser (localStorage), so it survives reloads
 * without needing the backend.
 */
function StaticRoadmap({ name }) {
  const data = STATIC_ROADMAPS[name]
  const extras = ROADMAP_EXTRAS[name]
  const storeKey = `roadmap-progress:${name}`
  const [done, setDone] = useState(() => new Set())

  useEffect(() => {
    try {
      setDone(new Set(JSON.parse(localStorage.getItem(storeKey) || '[]')))
    } catch {
      setDone(new Set())
    }
  }, [storeKey])

  function toggle(label) {
    setDone((prev) => {
      const next = new Set(prev)
      if (next.has(label)) next.delete(label)
      else next.add(label)
      try {
        localStorage.setItem(storeKey, JSON.stringify([...next]))
      } catch {
        /* private mode — progress just won't persist */
      }
      return next
    })
  }

  const total = data.sections.reduce((n, s) => n + s.items.length, 0)
  const completed = data.sections.reduce(
    (n, s) => n + s.items.filter((it) => done.has(itemLabel(it))).length,
    0,
  )

  const pct = total ? Math.round((completed / total) * 100) : 0

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-slate-50 shadow-sm">
      {/* Header banner — infographic style */}
      <div className="relative overflow-hidden bg-gradient-to-br from-purple-600 via-indigo-600 to-blue-600 px-6 py-6 text-white sm:px-8">
        <div className="pointer-events-none absolute -right-10 -top-12 h-40 w-40 rounded-full bg-white/10 blur-2xl" />
        <div className="pointer-events-none absolute -bottom-14 left-16 h-40 w-40 rounded-full bg-white/10 blur-2xl" />
        <div className="relative">
          <p className="text-[11px] font-bold uppercase tracking-[0.25em] text-white/75">
            {data.kind === 'role' ? 'Career Roadmap' : 'Skill Roadmap'}
          </p>
          <h2 className="mt-1 text-2xl font-extrabold uppercase tracking-tight sm:text-3xl">
            {name}
          </h2>
          <span className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-amber-300/90 px-3 py-1 text-xs font-bold text-amber-950 shadow-sm">
            ⭐ {data.summary}
          </span>
          {/* Progress */}
          <div className="mt-4 flex items-center gap-3">
            <div className="h-2 w-full max-w-sm overflow-hidden rounded-full bg-white/25">
              <div
                className="h-full rounded-full bg-white transition-all duration-500"
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="shrink-0 text-xs font-bold text-white/90">
              {completed}/{total} · {pct}%
            </span>
          </div>
        </div>
      </div>

      {/* Numbered colourful cards in a flowing grid */}
      <div className="grid gap-4 p-5 sm:grid-cols-2 sm:p-6 xl:grid-cols-3">
        {data.sections.map((section, i) => {
          const theme = SECTION_THEMES[i % SECTION_THEMES.length]
          return (
            <div
              key={section.title}
              className={`relative flex flex-col rounded-2xl border-2 border-t-4 p-4 pt-6 shadow-sm ${theme.group} ${theme.bar}`}
            >
              {/* Circle number badge overlapping the top edge */}
              <span
                className={`absolute -top-4 left-4 flex h-8 w-8 items-center justify-center rounded-full text-xs font-extrabold text-white shadow-md ring-4 ring-white ${theme.node}`}
              >
                {String(i + 1).padStart(2, '0')}
              </span>
              <div className="mb-3 flex items-center gap-2.5">
                <span className="text-2xl leading-none">{sectionIcon(section.title)}</span>
                <h3 className="text-base font-bold leading-tight text-slate-800">{section.title}</h3>
              </div>
              <div className="space-y-0.5">
                {section.items.map((it) => {
                  const label = itemLabel(it)
                  const note = itemNote(it)
                  const isDone = done.has(label)
                  return (
                    <button
                      key={label}
                      type="button"
                      onClick={() => toggle(label)}
                      className="flex w-full items-start gap-2.5 rounded-lg px-2 py-1.5 text-left transition hover:bg-white/70"
                    >
                      <span
                        className={`mt-1 flex h-4 w-4 shrink-0 items-center justify-center rounded-full transition ${
                          isDone ? 'bg-emerald-500' : ''
                        }`}
                      >
                        {isDone ? (
                          <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3.5" className="h-2.5 w-2.5">
                            <path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" />
                          </svg>
                        ) : (
                          <span className={`h-1.5 w-1.5 rounded-full ${theme.dot}`} />
                        )}
                      </span>
                      <span className="min-w-0">
                        <span
                          className={`block text-sm font-medium leading-snug ${
                            isDone ? 'text-slate-400 line-through' : 'text-slate-800'
                          }`}
                        >
                          {label}
                        </span>
                        {note && <span className="block text-xs text-slate-400">{note}</span>}
                      </span>
                    </button>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>

      {/* Essential Tools strip */}
      {extras?.tools?.length > 0 && (
        <div className="border-t border-slate-200 bg-white px-6 py-5">
          <p className="mb-3 text-center text-[11px] font-bold uppercase tracking-[0.2em] text-slate-400">
            Essential Tools
          </p>
          <div className="flex flex-wrap justify-center gap-2">
            {extras.tools.map((t, idx) => (
              <span
                key={t}
                className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 shadow-sm"
              >
                <span
                  className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold text-white ${TOOL_COLORS[idx % TOOL_COLORS.length]}`}
                >
                  {t[0]}
                </span>
                {t}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Practice · Build · Deploy footer band */}
      {extras?.practice?.length === 3 && (
        <div className="grid gap-px border-t border-slate-200 bg-slate-200 sm:grid-cols-3">
          {PBD.map(([label, icon], idx) => (
            <div key={label} className="bg-white px-5 py-4 text-center">
              <p className="text-2xl leading-none">{icon}</p>
              <p className="mt-1.5 text-[11px] font-bold uppercase tracking-wider text-indigo-600">
                {label}
              </p>
              <p className="mt-0.5 text-sm text-slate-600">{extras.practice[idx]}</p>
            </div>
          ))}
        </div>
      )}

      <p className="border-t border-slate-200 bg-white px-6 py-4 text-center text-xs text-slate-400">
        Tick any topic to mark it done — your progress is saved in this browser.
      </p>
    </div>
  )
}

/** A 5-cell level bar: filled = current, coloured = the gap, faint = beyond required. */
function Badge({ className, children }) {
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ${className}`}>
      {children}
    </span>
  )
}

// Wrap a long skill name onto (up to) two balanced lines so labels never clip.
function wrapLabel(text) {
  if (text.length <= 12) return [text]
  const words = text.split(' ')
  if (words.length === 1) return [text]
  const half = Math.ceil(text.length / 2)
  let line1 = ''
  let line2 = ''
  for (const w of words) {
    if (!line1 || (line1 + ' ' + w).trim().length <= half) line1 = (line1 + ' ' + w).trim()
    else line2 = (line2 + ' ' + w).trim()
  }
  return line2 ? [line1, line2] : [line1]
}

/**
 * A radar / spider chart: two overlaid polygons — your current level vs. the
 * target level the role needs — across all skills. Pure SVG, no chart library.
 */
function RadarChart({ skills }) {
  const n = skills.length
  const max = 5
  const W = 600
  const H = 520
  const cx = W / 2
  const cy = H / 2
  const maxR = 150
  const angle = (i) => (-90 + (360 / n) * i) * (Math.PI / 180)
  const point = (value, i, radius = maxR) => {
    const a = angle(i)
    const rr = (Math.max(0, Math.min(value, max)) / max) * radius
    return [cx + rr * Math.cos(a), cy + rr * Math.sin(a)]
  }
  const polygon = (vals) => vals.map((v, i) => point(v, i).join(',')).join(' ')
  const current = skills.map((s) => s.current_level || 0)
  const target = skills.map((s) => s.required_level || 0)

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full max-w-2xl" style={{ overflow: 'visible' }}>
      {/* grid rings */}
      {[1, 2, 3, 4, 5].map((level) => (
        <polygon
          key={level}
          points={skills.map((_, i) => point(level, i).join(',')).join(' ')}
          fill={level === 5 ? '#f8fafc' : 'none'}
          stroke="#e2e8f0"
          strokeWidth="1"
        />
      ))}
      {/* axis spokes */}
      {skills.map((_, i) => {
        const [x, y] = point(max, i)
        return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke="#e2e8f0" strokeWidth="1" />
      })}
      {/* scale numbers 1-5 along the top spoke */}
      {[1, 2, 3, 4, 5].map((level) => {
        const [, y] = point(level, 0)
        return (
          <text key={level} x={cx - 6} y={y} textAnchor="end" fontSize="9" fill="#cbd5e1">
            {level}
          </text>
        )
      })}
      {/* target polygon (dashed amber) */}
      <polygon
        points={polygon(target)}
        fill="rgba(245, 158, 11, 0.10)"
        stroke="#f59e0b"
        strokeWidth="2"
        strokeDasharray="5 3"
      />
      {/* current polygon (filled indigo) */}
      <polygon points={polygon(current)} fill="rgba(99, 102, 241, 0.28)" stroke="#6366f1" strokeWidth="2.5" />
      {skills.map((s, i) => {
        const [x, y] = point(current[i], i)
        return <circle key={i} cx={x} cy={y} r="4" fill="#6366f1" stroke="white" strokeWidth="1.5" />
      })}
      {/* labels (wrapped, never truncated) */}
      {skills.map((s, i) => {
        const [x, y] = point(max + 0.95, i)
        const cos = Math.cos(angle(i))
        const anchor = cos > 0.3 ? 'start' : cos < -0.3 ? 'end' : 'middle'
        const lines = wrapLabel(s.skill)
        return (
          <text
            key={i}
            x={x}
            y={y}
            textAnchor={anchor}
            dominantBaseline="middle"
            fontSize="12.5"
            fontWeight="600"
            fill="#334155"
          >
            {lines.length === 1 ? (
              lines[0]
            ) : (
              <>
                <tspan x={x} dy="-0.4em">
                  {lines[0]}
                </tspan>
                <tspan x={x} dy="1.15em">
                  {lines[1]}
                </tspan>
              </>
            )}
          </text>
        )
      })}
    </svg>
  )
}

function SkillGapTable({ skills }) {
  if (!skills?.length) return null
  const totReq = skills.reduce((n, s) => n + (s.required_level || 0), 0)
  const totHave = skills.reduce((n, s) => n + Math.min(s.current_level || 0, s.required_level || 0), 0)
  const readiness = totReq ? Math.round((totHave / totReq) * 100) : 0
  const ordered = [...skills].sort((a, a2) => {
    const pa = (PRIORITY[a.priority] ?? PRIORITY.medium).rank
    const pb = (PRIORITY[a2.priority] ?? PRIORITY.medium).rank
    return pa - pb || (a2.gap || 0) - (a.gap || 0)
  })
  // A radar reads best with a handful of spokes — show the most important ones.
  const MAX_RADAR = 8
  const radarSkills = ordered.slice(0, MAX_RADAR)
  const trimmed = skills.length > MAX_RADAR

  return (
    <Card>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Skill-gap radar</h2>
          <p className="mt-0.5 text-sm text-slate-500">
            Your current level vs. what the target role needs.
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-2xl font-extrabold text-indigo-600">{readiness}%</p>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            role ready
          </p>
        </div>
      </div>

      {/* Chart — full width, centered, large (top skills only for a clean shape) */}
      <div className="mt-4 flex flex-col items-center">
        <RadarChart skills={radarSkills} />
        <p className="mt-2 text-center text-xs text-slate-400">
          {trimmed
            ? `Top ${MAX_RADAR} priority skills · rings are levels 1 → 5 (outer = expert)`
            : 'Each corner is a skill · rings are levels 1 → 5 (outer = expert)'}
        </p>
      </div>

      {/* Legend + full skill list below, in two columns */}
      <div className="mt-5 border-t border-slate-100 pt-4">
        <div className="mb-3 flex flex-wrap justify-center gap-5 text-xs font-semibold text-slate-600">
          <span className="flex items-center gap-1.5">
            <span className="h-3 w-4 rounded-sm bg-indigo-400/50 ring-1 ring-indigo-500" /> Your level
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-3 w-4 rounded-sm border-2 border-dashed border-amber-500" /> Target level
          </span>
        </div>
        <div className="grid gap-1.5 sm:grid-cols-2">
          {ordered.map((s, i) => {
            const tone = PRIORITY[s.priority] ?? PRIORITY.medium
            return (
              <div
                key={i}
                className={`flex items-center justify-between gap-2 rounded-lg border border-l-4 border-slate-100 bg-slate-50 px-3 py-1.5 ${tone.edge}`}
              >
                <span className="truncate text-sm font-medium text-slate-700">{s.skill}</span>
                <span className="flex shrink-0 items-center gap-2">
                  <span className="text-xs text-slate-400">
                    {s.current_level}/{s.required_level}
                  </span>
                  <Badge className={tone.badge}>{s.priority}</Badge>
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </Card>
  )
}

// A roadmap.sh-style card: light, rounded, hover-lifted. The checkbox is our
// equivalent of roadmap.sh's bookmark — ticking it saves progress.
function ActionCard({ action, onToggle }) {
  const done = action.done
  return (
    <div
      className={`group relative rounded-xl border p-4 shadow-sm transition ${
        done
          ? 'border-emerald-200 bg-emerald-50/60'
          : 'border-slate-200 bg-white hover:-translate-y-0.5 hover:border-indigo-300 hover:shadow-md'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <p
          className={`text-sm font-semibold leading-snug ${done ? 'text-slate-400 line-through' : 'text-slate-900'}`}
        >
          {action.action}
        </p>
        <input
          type="checkbox"
          checked={done}
          onChange={(e) => onToggle(action.item_id, e.target.checked)}
          aria-label="Mark action done"
          className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer rounded border-slate-300 accent-indigo-600"
        />
      </div>
      <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
        <Badge className={ACTION_TYPE[action.type] ?? ACTION_TYPE.practice}>{action.type}</Badge>
        {action.skill && <span className="text-xs font-medium text-slate-400">{action.skill}</span>}
      </div>
      {action.why && <p className="mt-2 text-xs leading-relaxed text-slate-500">{action.why}</p>}
    </div>
  )
}

/**
 * The AI-generated roadmap, rendered in the same infographic style as the
 * curated ones: a gradient header banner + numbered colourful phase cards.
 */
function AiRoadmap({ roadmap, onToggle }) {
  const total = roadmap.phases.reduce((n, p) => n + p.actions.length, 0)
  const doneN = roadmap.phases.reduce((n, p) => n + p.actions.filter((a) => a.done).length, 0)
  const pct = total ? Math.round((doneN / total) * 100) : 0
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-slate-50 shadow-sm">
      <div className="relative overflow-hidden bg-gradient-to-br from-purple-600 via-indigo-600 to-blue-600 px-6 py-6 text-white sm:px-8">
        <div className="pointer-events-none absolute -right-10 -top-12 h-40 w-40 rounded-full bg-white/10 blur-2xl" />
        <div className="pointer-events-none absolute -bottom-14 left-16 h-40 w-40 rounded-full bg-white/10 blur-2xl" />
        <div className="relative">
          <p className="text-[11px] font-bold uppercase tracking-[0.25em] text-white/75">
            Personalised Roadmap
          </p>
          <h2 className="mt-1 text-2xl font-extrabold sm:text-3xl">{roadmap.target_role}</h2>
          <p className="mt-1 max-w-xl text-sm text-white/85">
            Built from your resume. Tick actions as you finish them — progress saves automatically.
          </p>
          <div className="mt-4 flex items-center gap-3">
            <div className="h-2 w-full max-w-sm overflow-hidden rounded-full bg-white/25">
              <div
                className="h-full rounded-full bg-white transition-all duration-500"
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="shrink-0 text-xs font-bold text-white/90">
              {doneN}/{total} · {pct}%
            </span>
          </div>
        </div>
      </div>

      <div className="grid gap-4 p-5 sm:p-6 xl:grid-cols-3">
        {roadmap.phases.map((phase, i) => {
          const theme = SECTION_THEMES[i % SECTION_THEMES.length]
          return (
            <div
              key={phase.horizon}
              className={`relative flex flex-col rounded-2xl border-2 border-t-4 p-4 pt-6 shadow-sm ${theme.group} ${theme.bar}`}
            >
              <span
                className={`absolute -top-4 left-4 flex h-8 w-8 items-center justify-center rounded-full text-xs font-extrabold text-white shadow-md ring-4 ring-white ${theme.node}`}
              >
                {String(i + 1).padStart(2, '0')}
              </span>
              <div className="mb-3 flex items-center gap-2.5">
                <span className="text-2xl leading-none">{sectionIcon(phase.label)}</span>
                <h3 className="text-base font-bold leading-tight text-slate-800">{phase.label}</h3>
              </div>
              <div className="space-y-3">
                {phase.actions.length > 0 ? (
                  phase.actions.map((action) => (
                    <ActionCard key={action.item_id} action={action} onToggle={onToggle} />
                  ))
                ) : (
                  <p className="py-2 text-center text-xs text-slate-400">No actions in this phase.</p>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

/**
 * Phase 3 — Career Path & Skill-Gap. Pick a resume + target role, generate a
 * skill-gap table and a phased (now / 3-month / 12-month) roadmap. Ticking an
 * action persists immediately; regenerating keeps the ticks you already made.
 */
export default function RoadmapPage({ ready }) {
  const [resumes, setResumes] = useState([])
  const [resumeId, setResumeId] = useState('')
  const [targetRole, setTargetRole] = useState('')

  const [running, setRunning] = useState(false)
  const [current, setCurrent] = useState(null)
  const [doneSteps, setDoneSteps] = useState([])
  const [detail, setDetail] = useState('')

  const [roadmap, setRoadmap] = useState(null)
  const [planId, setPlanId] = useState(null)
  const [error, setError] = useState(null)
  const [history, setHistory] = useState([])
  const [staticName, setStaticName] = useState(null) // curated roadmap shown instantly
  const abortRef = useRef(null)
  const staticRef = useRef(null)

  function pickStatic(name) {
    setStaticName(name)
    // Let React render the roadmap, then scroll it into view.
    setTimeout(() => staticRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
  }

  const loadLists = useCallback(async () => {
    const [r, h] = await Promise.all([
      api.listResumes().catch(() => []),
      api.listRoadmaps().catch(() => []),
    ])
    setResumes(r)
    setHistory(h)
    if (r[0] && !resumeId) setResumeId(String(r[0].id))
  }, [resumeId])

  useEffect(() => {
    loadLists()
    return () => abortRef.current?.()
  }, [loadLists])

  function start(regeneratePlanId = null, roleOverride = null) {
    const role = (roleOverride ?? targetRole).trim()
    if (!resumeId) {
      setError({ message: 'Add and select a resume first.', hint: 'Save one on the Resume tab.' })
      return
    }
    if (!role) return
    if (roleOverride) setTargetRole(roleOverride)

    setRunning(true)
    setError(null)
    setDoneSteps([])
    setCurrent('retrieve')
    setDetail('')
    if (!regeneratePlanId) setRoadmap(null)

    abortRef.current = streamRoadmap(
      { resumeId: Number(resumeId), targetRole: role, regeneratePlanId },
      (event, data) => {
        if (event === 'step') {
          if (data.status === 'running') setCurrent(data.stage)
          else if (data.status === 'done') {
            setDoneSteps((prev) => [...new Set([...prev, data.stage])])
            setDetail(data.detail || '')
          }
        } else if (event === 'done') {
          setRoadmap(data.roadmap)
          setPlanId(data.plan_id)
          setRunning(false)
          setCurrent(null)
          loadLists()
        } else if (event === 'error') {
          setError({ message: data.message, hint: data.hint })
          setRunning(false)
          setCurrent(null)
        }
      },
    )
  }

  async function toggleItem(itemId, done) {
    // Optimistic: flip locally, then persist. Revert on failure.
    setRoadmap((prev) => patchLocalDone(prev, itemId, done))
    try {
      await api.setRoadmapItemDone(itemId, done)
      loadLists() // refresh done_count in history
    } catch (err) {
      setRoadmap((prev) => patchLocalDone(prev, itemId, !done))
      setError({ message: err.message, hint: err.hint })
    }
  }

  async function openPast(id) {
    setError(null)
    try {
      const r = await api.getRoadmap(id)
      setRoadmap(r)
      setPlanId(id)
    } catch (err) {
      setError({ message: err.message, hint: err.hint })
    }
  }

  const canRun = ready && resumeId && targetRole.trim() && !running

  return (
    <div className="space-y-6">
      <PageHeader
        theme="purple"
        badge="Career Roadmaps"
        icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
            <path d="M9 18l-6 3V6l6-3 6 3 6-3v15l-6 3-6-3z" />
            <path d="M9 3v15M15 6v15" />
          </svg>
        }
        title="Chart your path to the job"
        subtitle="Browse a curated roadmap for any role or skill, or generate one personalised to your resume — with a skill-gap analysis. All on this machine."
      />

      {/* Browse — curated roadmaps open instantly, no waiting */}
      <Card
        title="Browse roadmaps"
        subtitle="Click any role or skill to open its roadmap instantly."
      >
        <div className="mt-2">
          <PillHeader>Role-based roadmaps</PillHeader>
          <CatalogGrid items={ROLE_ROADMAPS} onPick={pickStatic} />
          <PillHeader>Skill-based roadmaps</PillHeader>
          <CatalogGrid items={SKILL_ROADMAPS} onPick={pickStatic} />
        </div>
      </Card>

      <div ref={staticRef}>{staticName && <StaticRoadmap name={staticName} />}</div>

      <Card
        title="AI-personalized roadmap (optional)"
        subtitle="Prefer one built from your own resume, with a skill-gap analysis? Generate it here — this uses the local model and takes a couple of minutes on CPU."
      >
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Resume</span>
            <select
              value={resumeId}
              onChange={(e) => setResumeId(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            >
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
              Target role
            </span>
            <input
              type="text"
              value={targetRole}
              placeholder="e.g. Backend Engineer"
              onChange={(e) => setTargetRole(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
            />
          </label>
        </div>

        {resumes.length === 0 && (
          <p className="mt-3 text-sm text-amber-700">
            You need a saved resume first (Resume tab).
          </p>
        )}

        <div className="mt-4 flex items-center gap-3">
          <Button onClick={() => start()} disabled={!canRun}>
            {running ? 'Generating…' : 'Generate roadmap'}
          </Button>
          {roadmap && planId && !running && (
            <Button variant="secondary" onClick={() => start(planId)}>
              Regenerate (keep my progress)
            </Button>
          )}
          {!ready && (
            <span className="text-sm text-slate-500">Needs the local model to be ready.</span>
          )}
        </div>

        {running && (
          <div className="mt-6 rounded-lg border border-slate-200 bg-slate-50 p-5">
            <p className="mb-4 text-sm text-slate-600">
              Two AI passes on CPU — a skill-gap assessment then the roadmap. A few minutes, all local.
            </p>
            <ol className="space-y-3">
              {STEPS.map((step) => {
                const isDone = doneSteps.includes(step.id)
                const isCurrent = current === step.id && !isDone
                return (
                  <li key={step.id} className="flex items-center gap-3">
                    <span
                      className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${
                        isDone
                          ? 'bg-emerald-500 text-white'
                          : isCurrent
                            ? 'bg-slate-900 text-white'
                            : 'bg-slate-200 text-slate-500'
                      }`}
                    >
                      {isDone ? '✓' : isCurrent ? '…' : ''}
                    </span>
                    <span
                      className={
                        isDone
                          ? 'text-sm text-slate-500'
                          : isCurrent
                            ? 'text-sm font-medium text-slate-900'
                            : 'text-sm text-slate-400'
                      }
                    >
                      {step.label}
                      {isCurrent && detail && (
                        <span className="ml-2 text-xs text-slate-400">{detail}</span>
                      )}
                    </span>
                  </li>
                )
              })}
            </ol>
          </div>
        )}

        {error && (
          <div className="mt-4">
            <Alert tone="error" title={error.message} hint={error.hint} />
          </div>
        )}
      </Card>

      {roadmap && (
        <>
          <SkillGapTable skills={roadmap.skill_gap} />
          <AiRoadmap roadmap={roadmap} onToggle={toggleItem} />
        </>
      )}

      {history.length > 0 && (
        <Card title="Saved roadmaps">
          <ul className="mt-3 divide-y divide-slate-100">
            {history.map((h) => (
              <li key={h.id} className="flex items-center justify-between py-2">
                <div>
                  <p className="text-sm font-medium text-slate-800">{h.target_role}</p>
                  <p className="text-xs text-slate-400">
                    {h.done_count}/{h.total_count} done · {new Date(h.updated_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button variant="secondary" onClick={() => openPast(h.id)}>
                    Open
                  </Button>
                  <Button
                    variant="danger"
                    onClick={async () => {
                      await api.deleteRoadmap(h.id)
                      if (planId === h.id) {
                        setRoadmap(null)
                        setPlanId(null)
                      }
                      loadLists()
                    }}
                  >
                    Delete
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}

/** Return a copy of the roadmap with one action's `done` flipped. */
function patchLocalDone(roadmap, itemId, done) {
  if (!roadmap) return roadmap
  return {
    ...roadmap,
    phases: roadmap.phases.map((phase) => ({
      ...phase,
      actions: phase.actions.map((a) => (a.item_id === itemId ? { ...a, done } : a)),
    })),
  }
}
