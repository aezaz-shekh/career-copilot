/** Small shared form and layout primitives, so pages stay readable. */

/** Accent palettes for Card's optional coloured header. */
const CARD_ACCENTS = {
  indigo: { badge: 'from-indigo-500 to-violet-600 shadow-indigo-200/60', strip: 'from-indigo-50 to-white' },
  sky: { badge: 'from-sky-500 to-indigo-600 shadow-sky-200/60', strip: 'from-sky-50 to-white' },
  violet: { badge: 'from-violet-500 to-fuchsia-600 shadow-fuchsia-200/60', strip: 'from-violet-50 to-white' },
  emerald: { badge: 'from-emerald-500 to-teal-600 shadow-emerald-200/60', strip: 'from-emerald-50 to-white' },
  purple: { badge: 'from-purple-500 to-blue-600 shadow-purple-200/60', strip: 'from-purple-50 to-white' },
}

/**
 * A white content card. Pass `accent` (+ optional `icon`) to give it a coloured
 * header strip with an icon badge and a divider — this breaks up long stretches
 * of white and gives the section a clear identity. Without `accent`/`icon` it
 * renders exactly as before (plain white, title on top).
 */
export function Card({ title, subtitle, children, className = '', icon = null, accent = null }) {
  if (!accent && !icon) {
    return (
      <section className={`rounded-xl border border-slate-200 bg-white p-6 shadow-sm ${className}`}>
        {title && <h2 className="text-lg font-semibold text-slate-900">{title}</h2>}
        {subtitle && <p className="mt-1 text-sm text-slate-600">{subtitle}</p>}
        {children}
      </section>
    )
  }
  const a = CARD_ACCENTS[accent] ?? CARD_ACCENTS.indigo
  return (
    <section className={`overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm ${className}`}>
      <div className={`flex items-start gap-3 border-b border-slate-100 bg-gradient-to-r ${a.strip} px-6 py-4`}>
        {icon && (
          <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${a.badge} text-white shadow-md`}>
            {icon}
          </span>
        )}
        <div className="min-w-0">
          {title && <h2 className="text-lg font-semibold text-slate-900">{title}</h2>}
          {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
        </div>
      </div>
      <div className="p-6">{children}</div>
    </section>
  )
}

export function Field({ label, value, onChange, placeholder, type = 'text', icon = null }) {
  return (
    <label className="block">
      <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</span>
      <div className="relative mt-1">
        {icon && (
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
            {icon}
          </span>
        )}
        <input
          type={type}
          value={value ?? ''}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value || null)}
          className={`w-full rounded-xl border border-slate-200 bg-slate-50 py-2.5 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-indigo-400 focus:bg-white focus:ring-2 focus:ring-indigo-100 ${
            icon ? 'pl-9 pr-3' : 'px-3.5'
          }`}
        />
      </div>
    </label>
  )
}

export function TextArea({ label, value, onChange, rows = 4, placeholder, mono = false }) {
  return (
    <label className="block">
      {label && (
        <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</span>
      )}
      <textarea
        rows={rows}
        value={value ?? ''}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className={`mt-1 w-full resize-y rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-indigo-400 focus:bg-white focus:ring-2 focus:ring-indigo-100 ${
          mono ? 'font-mono text-xs' : 'leading-relaxed'
        }`}
      />
    </label>
  )
}

export function Button({ children, variant = 'primary', className = '', ...props }) {
  const styles = {
    primary: 'bg-slate-900 text-white hover:bg-slate-700',
    gradient:
      'bg-gradient-to-r from-indigo-600 to-violet-600 text-white shadow-sm shadow-indigo-200 hover:from-indigo-700 hover:to-violet-700',
    secondary: 'border border-slate-300 text-slate-700 hover:bg-slate-50',
    danger: 'border border-rose-200 text-rose-700 hover:bg-rose-50',
  }
  return (
    <button
      className={`rounded-lg px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-60 ${styles[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}

export function Alert({ tone = 'info', title, hint, children }) {
  const tones = {
    info: 'border-slate-200 bg-slate-50 text-slate-800',
    warn: 'border-amber-200 bg-amber-50 text-amber-900',
    error: 'border-rose-200 bg-rose-50 text-rose-900',
    success: 'border-emerald-200 bg-emerald-50 text-emerald-900',
  }
  return (
    <div className={`rounded-lg border p-4 ${tones[tone]}`}>
      {title && <p className="font-semibold">{title}</p>}
      {hint && <p className="mt-1 text-sm opacity-90">{hint}</p>}
      {children}
    </div>
  )
}

/**
 * Per-module colour identity for PageHeader. Full class strings (Tailwind can't
 * see interpolated names), one entry per module accent.
 */
const HEADER_THEMES = {
  // Clean neutral look: the background is a soft near-white/grey for every
  // theme; colour identity comes only from the accent bar, icon badge and chip.
  indigo: {
    accent: 'from-indigo-500 to-violet-500',
    wash: 'from-slate-100 via-slate-50 to-white',
    blob: 'bg-slate-200/40',
    iconBg: 'from-indigo-500 to-violet-600 shadow-indigo-200/70',
    chip: 'bg-white text-indigo-700 ring-indigo-200',
    stat: 'text-indigo-600',
  },
  sky: {
    accent: 'from-sky-500 to-indigo-500',
    wash: 'from-slate-100 via-slate-50 to-white',
    blob: 'bg-slate-200/40',
    iconBg: 'from-sky-500 to-indigo-600 shadow-sky-200/70',
    chip: 'bg-white text-sky-700 ring-sky-200',
    stat: 'text-sky-600',
  },
  violet: {
    accent: 'from-violet-500 to-fuchsia-500',
    wash: 'from-slate-100 via-slate-50 to-white',
    blob: 'bg-slate-200/40',
    iconBg: 'from-violet-500 to-fuchsia-600 shadow-fuchsia-200/70',
    chip: 'bg-white text-violet-700 ring-violet-200',
    stat: 'text-violet-600',
  },
  emerald: {
    accent: 'from-emerald-500 to-teal-500',
    wash: 'from-slate-100 via-slate-50 to-white',
    blob: 'bg-slate-200/40',
    iconBg: 'from-emerald-500 to-teal-600 shadow-teal-200/70',
    chip: 'bg-white text-emerald-700 ring-emerald-200',
    stat: 'text-emerald-600',
  },
  purple: {
    accent: 'from-purple-500 to-blue-500',
    wash: 'from-slate-100 via-slate-50 to-white',
    blob: 'bg-slate-200/40',
    iconBg: 'from-purple-500 to-blue-600 shadow-purple-200/70',
    chip: 'bg-white text-purple-700 ring-purple-200',
    stat: 'text-purple-600',
  },
}

/**
 * Light, premium page header: near-white card with a faint colour wash, a thin
 * colour accent bar, a colour icon badge and dark text. Replaces the old
 * saturated gradient banners (which read as "template"). One `theme` per module
 * keeps each page's colour identity as an accent, not a flood.
 */
export function PageHeader({ theme = 'indigo', badge, icon, title, subtitle, stat }) {
  const t = HEADER_THEMES[theme] ?? HEADER_THEMES.indigo
  return (
    <section
      className={`relative overflow-hidden rounded-2xl border border-slate-200 bg-gradient-to-br ${t.wash} p-6 shadow-sm sm:p-7`}
    >
      <div className={`pointer-events-none absolute -right-10 -top-12 h-40 w-40 rounded-full ${t.blob} blur-3xl`} />
      <div className={`absolute inset-y-0 left-0 w-2 bg-gradient-to-b ${t.accent}`} />
      <div className="relative flex items-start justify-between gap-4 pl-2">
        <div>
          <div className="flex items-center gap-3">
            {icon && (
              <span
                className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${t.iconBg} text-white shadow-md`}
              >
                {icon}
              </span>
            )}
            {badge && (
              <span
                className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wide ring-1 ${t.chip}`}
              >
                {badge}
              </span>
            )}
          </div>
          <h1 className="mt-3 text-2xl font-extrabold text-slate-900 sm:text-3xl">{title}</h1>
          {subtitle && <p className="mt-1 max-w-xl text-sm text-slate-500">{subtitle}</p>}
        </div>
        {stat && (
          <div className="hidden shrink-0 rounded-xl border border-slate-200 bg-white px-4 py-3 text-center shadow-sm sm:block">
            <p className={`text-2xl font-extrabold ${t.stat}`}>{stat.value}</p>
            <p className="text-[11px] font-medium text-slate-400">{stat.label}</p>
          </div>
        )}
      </div>
    </section>
  )
}

/** Convert between a textarea (one item per line) and a string array. */
export const linesToArray = (text) =>
  text
    .split('\n')
    .map((line) => line.replace(/^[-•*]\s*/, '').trim())
    .filter(Boolean)

export const arrayToLines = (items) => (items ?? []).join('\n')

export const commasToArray = (text) =>
  text
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
