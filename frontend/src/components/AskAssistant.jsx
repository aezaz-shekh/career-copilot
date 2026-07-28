import { memo, useCallback, useEffect, useRef, useState } from 'react'
import { api, streamAsk } from '../api.js'
import { MicPermissionError } from '../lib/recorder.js'
import { createListener, selectProviders } from '../lib/speech.js'
import { Alert, Card } from './ui.jsx'

function MicIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
    </svg>
  )
}

function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="h-4 w-4">
      <line x1="12" y1="19" x2="12" y2="5" />
      <polyline points="5 12 12 5 19 12" />
    </svg>
  )
}

function PaperclipIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
      <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
    </svg>
  )
}

/** The small gradient sparkle avatar shown beside the assistant's replies. */
function BotAvatar() {
  return (
    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 via-violet-500 to-sky-500 text-white shadow-sm">
      <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
        <path d="M12 3l2.09 6.26L20 11l-5.91 1.74L12 19l-2.09-6.26L4 11l5.91-1.74L12 3z" />
      </svg>
    </span>
  )
}

/** Three bouncing dots while the model is thinking. */
function TypingDots() {
  return (
    <span className="flex items-center gap-1 py-1">
      {[0, 150, 300].map((delay) => (
        <span
          key={delay}
          className="h-2 w-2 animate-bounce rounded-full bg-slate-400"
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
    </span>
  )
}

// Inline formatting: **bold**, `code`. Returns an array of React nodes.
function renderInline(text, keyPrefix) {
  const nodes = []
  const regex = /(\*\*([^*]+)\*\*|`([^`]+)`)/g
  let last = 0
  let m
  let n = 0
  while ((m = regex.exec(text))) {
    if (m.index > last) nodes.push(text.slice(last, m.index))
    if (m[2] !== undefined) {
      nodes.push(
        <strong key={`${keyPrefix}-b${n}`} className="font-semibold text-slate-900">
          {m[2]}
        </strong>,
      )
    } else if (m[3] !== undefined) {
      nodes.push(
        <code
          key={`${keyPrefix}-c${n}`}
          className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[0.85em] text-slate-800"
        >
          {m[3]}
        </code>,
      )
    }
    last = m.index + m[0].length
    n += 1
  }
  if (last < text.length) nodes.push(text.slice(last))
  return nodes
}

/**
 * A tiny, dependency-free markdown renderer — enough to make replies read like
 * a real AI: headings, bullet/numbered lists, bold and inline code. Anything
 * else falls through as a paragraph, so partial streamed text renders fine.
 */
const Markdown = memo(function Markdown({ text }) {
  const lines = text.split('\n')
  const blocks = []
  let i = 0
  let key = 0
  while (i < lines.length) {
    const line = lines[i]
    if (!line.trim()) {
      i += 1
      continue
    }
    // Horizontal rule — a divider line between sections.
    if (/^\s*([-*_])\1{2,}\s*$/.test(line)) {
      blocks.push(<hr key={key++} className="my-4 border-slate-200" />)
      i += 1
      continue
    }
    const h = line.match(/^(#{1,6})\s+(.*)$/)
    if (h) {
      const level = h[1].length
      const size = level === 1 ? 'text-base' : 'text-sm'
      blocks.push(
        <p key={key++} className={`font-semibold text-slate-900 ${size}`}>
          {renderInline(h[2], `h${key}`)}
        </p>,
      )
      i += 1
      continue
    }
    if (/^\s*[-*]\s+/.test(line)) {
      const items = []
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*]\s+/, ''))
        i += 1
      }
      blocks.push(
        <ul key={key++} className="list-disc space-y-1 pl-5 text-sm leading-relaxed text-slate-700">
          {items.map((it, k) => (
            <li key={k}>{renderInline(it, `ul${key}-${k}`)}</li>
          ))}
        </ul>,
      )
      continue
    }
    if (/^\s*\d+\.\s+/.test(line)) {
      const items = []
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+\.\s+/, ''))
        i += 1
      }
      blocks.push(
        <ol
          key={key++}
          className="list-decimal space-y-1 pl-5 text-sm leading-relaxed text-slate-700"
        >
          {items.map((it, k) => (
            <li key={k}>{renderInline(it, `ol${key}-${k}`)}</li>
          ))}
        </ol>,
      )
      continue
    }
    const para = []
    while (
      i < lines.length &&
      lines[i].trim() &&
      !/^\s*[-*]\s+/.test(lines[i]) &&
      !/^\s*\d+\.\s+/.test(lines[i]) &&
      !/^#{1,6}\s+/.test(lines[i]) &&
      !/^\s*([-*_])\1{2,}\s*$/.test(lines[i])
    ) {
      para.push(lines[i])
      i += 1
    }
    blocks.push(
      <p key={key++} className="text-sm leading-relaxed text-slate-700">
        {renderInline(para.join(' '), `p${key}`)}
      </p>,
    )
  }
  return <div className="space-y-3">{blocks}</div>
})

// Starter prompts shown before the first message, like a real assistant.
const SUGGESTIONS = [
  'How do I improve my resume?',
  'Common interview questions for my role',
  'What skills should I learn next?',
  'Write a LinkedIn message to a recruiter',
]

/**
 * A premium AI-assistant chat — your question sits in a small bubble on the
 * right, the AI's reply flows full-width beside its avatar (no bubble, real
 * markdown), it remembers the last few turns, and everything runs locally.
 */
/** The large sparkle avatar for the empty welcome screen. */
function WelcomeAvatar() {
  return (
    <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 via-violet-500 to-sky-500 text-white shadow-lg shadow-indigo-200">
      <svg viewBox="0 0 24 24" fill="currentColor" className="h-8 w-8">
        <path d="M12 3l2.09 6.26L20 11l-5.91 1.74L12 19l-2.09-6.26L4 11l5.91-1.74L12 3z" />
      </svg>
    </span>
  )
}

export default function AskAssistant({ hero = false, greeting = '', belowWelcome = null }) {
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState([]) // {role:'user'|'assistant', text}
  const [recording, setRecording] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const [answering, setAnswering] = useState(false)
  const [error, setError] = useState(null)
  // Which tier can listen here: 'server' (whisper.cpp), 'browser', or null.
  const [sttProvider, setSttProvider] = useState(null)
  // Whether chat is answered on this machine or by a hosted provider, so the
  // captions below state what is actually true for this deployment.
  const [isHosted, setIsHosted] = useState(false)
  const [attachment, setAttachment] = useState(null) // {name, text}
  const [uploading, setUploading] = useState(false)
  const recorderRef = useRef(null)
  const abortRef = useRef(null)
  const fileRef = useRef(null)
  const endRef = useRef(null)
  const messagesRef = useRef(messages)

  useEffect(() => {
    messagesRef.current = messages
  }, [messages])

  useEffect(() => {
    api
      .voiceStatus()
      .then((v) => setSttProvider(selectProviders(v).stt))
      // The probe failing does not mean speech is impossible — the browser may
      // still be able to listen, so fall back to whatever it supports.
      .catch(() => setSttProvider(selectProviders(null).stt))
    api
      .health()
      .then((h) => setIsHosted(h?.inference_mode === 'hosted'))
      .catch(() => setIsHosted(false))
    return () => abortRef.current?.()
  }, [])

  useEffect(() => {
    // Instant (not smooth) so streaming tokens don't stack scroll animations,
    // and only when already near the bottom, so manual scroll-up is respected.
    const el = endRef.current
    const scroller = el?.closest('.overflow-y-auto')
    if (!el) return
    if (scroller) {
      const nearBottom =
        scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 160
      if (!nearBottom) return
    }
    el.scrollIntoView({ block: 'end' })
  }, [messages])

  const closeChat = useCallback(() => {
    abortRef.current?.()
    setMessages([])
    setAnswering(false)
    setError(null)
    setQuestion('')
  }, [])

  // Starting a chat pushes a history entry (see `send`), so the browser Back
  // button returns to the welcome screen instead of skipping past it. When Back
  // lands on any non-chat entry, close the open conversation.
  useEffect(() => {
    const onPop = (event) => {
      if (!event.state?.chat && messagesRef.current.length) closeChat()
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [closeChat])

  async function startRecording() {
    setError(null)
    const listener = createListener(sttProvider)
    if (!listener) return
    try {
      await listener.start()
      recorderRef.current = listener
      setRecording(true)
    } catch (err) {
      setError(
        err instanceof MicPermissionError
          ? { message: err.message, hint: 'You can type your question instead.' }
          : { message: 'Could not start recording.', hint: null },
      )
    }
  }

  async function stopRecording() {
    if (!recorderRef.current) return
    setRecording(false)
    setTranscribing(true)
    try {
      const text = await recorderRef.current.stop()
      recorderRef.current = null
      if (text) {
        setQuestion((prev) => (prev.trim() ? `${prev.trim()} ${text}` : text))
      } else {
        setError({ message: 'Nothing was transcribed.', hint: 'Try again, a bit louder.' })
      }
    } catch (err) {
      setError({ message: err.message || 'Transcription failed.', hint: err.hint })
    } finally {
      setTranscribing(false)
    }
  }

  async function onPickFile(e) {
    const file = e.target.files?.[0]
    e.target.value = '' // allow re-picking the same file
    if (!file) return
    setError(null)
    setUploading(true)
    try {
      const res = await api.extractDocument(file)
      const text = (res.raw_text || '').trim()
      if (!text) {
        setError({ message: 'No text found in that file.', hint: 'Try a text-based PDF or a .txt file.' })
      } else {
        setAttachment({ name: file.name, text })
      }
    } catch (err) {
      setError({ message: err.message || 'Could not read that file.', hint: err.hint })
    } finally {
      setUploading(false)
    }
  }

  function send(text) {
    const q = (text ?? question).trim() || (attachment ? 'Summarise the attached document briefly.' : '')
    if (!q || answering) return
    setError(null)
    setQuestion('')

    // Remember the last few turns so follow-up questions have context.
    const history = messages
      .slice(-4)
      .map((m) => `${m.role === 'user' ? 'User' : 'Assistant'}: ${m.text}`)
      .join('\n')
    const context = [history, attachment?.text].filter(Boolean).join('\n\n')

    // First message of a conversation gets its own history entry, so Back
    // closes the chat and returns to the welcome screen.
    if (messages.length === 0) {
      window.history.pushState({ tab: 'dashboard', chat: true }, '')
    }

    setMessages((prev) => [...prev, { role: 'user', text: q }, { role: 'assistant', text: '' }])
    setAnswering(true)

    abortRef.current = streamAsk(
      q,
      (event, data) => {
        if (event === 'token') {
          setMessages((prev) => {
            const next = [...prev]
            const last = next[next.length - 1]
            if (last?.role === 'assistant') next[next.length - 1] = { ...last, text: last.text + (data.text || '') }
            return next
          })
        } else if (event === 'done') {
          setAnswering(false)
        } else if (event === 'error') {
          setError({ message: data.message, hint: data.hint })
          setAnswering(false)
          setMessages((prev) => {
            const next = [...prev]
            if (next[next.length - 1]?.role === 'assistant' && !next[next.length - 1].text) next.pop()
            return next
          })
        }
      },
      context,
    )
  }

  function newChat() {
    // Pop the chat history entry so Back and "New chat" behave identically;
    // the popstate handler then clears the conversation.
    if (messages.length) window.history.back()
    else closeChat()
  }

  const pillPad = hero ? 'py-2 pl-3 pr-2' : 'py-1.5 pl-2 pr-1.5'
  const btnSize = hero ? 'h-11 w-11' : 'h-9 w-9'
  const inputText = hero ? 'text-base' : 'text-sm'
  const hasChat = messages.length > 0

  const chips = (
    <div className={`flex flex-wrap gap-2 ${hero ? 'justify-center' : ''}`}>
      {SUGGESTIONS.map((s) => (
        <button
          key={s}
          type="button"
          onClick={() => send(s)}
          disabled={answering}
          className="rounded-full bg-slate-100 px-3.5 py-2 text-xs font-medium text-slate-600 ring-1 ring-slate-200 transition hover:bg-slate-200 disabled:opacity-40"
        >
          {s}
        </button>
      ))}
    </div>
  )

  // The conversation — user in a soft bubble on the right, the AI full-width
  // beside its avatar (document-style, no bubble), like ChatGPT / Claude.
  const thread = (
    <div className="mx-auto w-full max-w-3xl space-y-8">
      {messages.map((m, i) =>
        m.role === 'user' ? (
          <div key={i} className="flex justify-end">
            <div className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-indigo-50 px-4 py-2.5 text-sm text-indigo-950 ring-1 ring-indigo-100">
              {m.text}
            </div>
          </div>
        ) : (
          <div key={i} className="flex gap-3">
            <BotAvatar />
            <div className="min-w-0 flex-1 pt-0.5">
              {m.text ? (
                <>
                  <Markdown text={m.text} />
                  {answering && i === messages.length - 1 && (
                    <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-slate-400 align-middle" />
                  )}
                </>
              ) : (
                <TypingDots />
              )}
            </div>
          </div>
        ),
      )}
      <div ref={endRef} />
    </div>
  )

  const composer = (
    <div className="mx-auto w-full max-w-3xl">
      {attachment && (
        <div className="mb-2 flex items-center gap-2">
          <span className="inline-flex max-w-full items-center gap-1.5 rounded-full bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700 ring-1 ring-indigo-200">
            📎 <span className="truncate">{attachment.name}</span>
            <button
              type="button"
              onClick={() => setAttachment(null)}
              className="ml-0.5 text-indigo-400 hover:text-indigo-700"
              aria-label="Remove attachment"
            >
              ✕
            </button>
          </span>
        </div>
      )}

      <input ref={fileRef} type="file" accept=".pdf,.txt,.md,.text" onChange={onPickFile} className="hidden" />
      <div
        className={`flex items-center gap-1.5 rounded-full border bg-white ${pillPad} shadow-sm transition ${
          recording
            ? 'border-rose-300 ring-2 ring-rose-100'
            : 'border-slate-300 focus-within:border-slate-400 focus-within:ring-2 focus-within:ring-slate-100'
        }`}
      >
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          disabled={uploading || recording || answering}
          title="Attach a document (PDF, TXT, MD)"
          aria-label="Attach a document"
          className={`flex ${btnSize} shrink-0 items-center justify-center rounded-full text-slate-500 transition hover:bg-slate-100 disabled:opacity-40`}
        >
          {uploading ? <span className="h-3 w-3 animate-pulse rounded-full bg-slate-400" /> : <PaperclipIcon />}
        </button>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={recording}
          placeholder={
            recording
              ? 'Listening…'
              : transcribing
                ? 'Transcribing…'
                : attachment
                  ? 'Ask about the attached file…'
                  : hasChat
                    ? 'Reply…'
                    : 'Ask anything'
          }
          className={`min-w-0 flex-1 bg-transparent px-1 ${inputText} text-slate-800 outline-none placeholder:text-slate-400 disabled:cursor-not-allowed`}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              send()
            }
          }}
        />

        {sttProvider && (
          <button
            type="button"
            onClick={recording ? stopRecording : startRecording}
            disabled={transcribing || answering}
            title={recording ? 'Stop recording' : 'Speak your question'}
            aria-label={recording ? 'Stop recording' : 'Speak your question'}
            className={`flex ${btnSize} shrink-0 items-center justify-center rounded-full transition disabled:opacity-40 ${
              recording ? 'bg-rose-500 text-white' : 'text-slate-500 hover:bg-slate-100'
            }`}
          >
            {recording ? <span className="h-3 w-3 rounded-sm bg-white" /> : <MicIcon />}
          </button>
        )}

        <button
          type="button"
          onClick={() => send()}
          disabled={answering || (!question.trim() && !attachment) || recording || uploading}
          title="Send"
          aria-label="Send"
          className={`flex ${btnSize} shrink-0 items-center justify-center rounded-full bg-slate-900 text-white transition hover:bg-slate-700 disabled:opacity-30`}
        >
          {answering ? <span className="h-3 w-3 animate-pulse rounded-full bg-white" /> : <SendIcon />}
        </button>
      </div>

      <div className="mt-2 flex items-center justify-between px-1">
        <p className="text-[11px] text-slate-400">
          {isHosted
            ? 'Your resumes and history stay in this app’s own database.'
            : 'Answers run locally — nothing leaves your machine.'}
        </p>
        {hasChat && (
          <button
            type="button"
            onClick={newChat}
            className="text-[11px] font-medium text-slate-500 transition hover:text-indigo-600"
          >
            ✚ New chat
          </button>
        )}
      </div>

      {error && (
        <div className="mt-3">
          <Alert tone="error" title={error.message} hint={error.hint} />
        </div>
      )}
    </div>
  )

  // Hero, full-page. Empty = a centered ChatGPT-style welcome (with the snapshot
  // below); active = a full-bleed chat, thread scrolling, composer pinned wide.
  if (hero) {
    if (!hasChat) {
      return (
        <div className="h-full overflow-y-auto">
          <div className="flex min-h-[70vh] flex-col items-center justify-center px-4 py-10 text-center">
            <WelcomeAvatar />
            <h1 className="mt-5 bg-gradient-to-r from-indigo-600 via-violet-600 to-sky-600 bg-clip-text text-3xl font-extrabold text-transparent sm:text-4xl">
              {greeting || 'How can I help?'}
            </h1>
            <p className="mt-2 text-slate-500">
              {isHosted
                ? 'Ask me anything about your career.'
                : 'Ask me anything about your career — answered locally on your machine.'}
            </p>
            <div className="mt-8 w-full max-w-2xl">{composer}</div>
            <div className="mt-5 w-full max-w-2xl">{chips}</div>
          </div>
          {belowWelcome && (
            <div className="border-t border-slate-200 bg-slate-50/60 px-4 py-8 sm:px-8">
              <div className="mx-auto max-w-4xl">{belowWelcome}</div>
            </div>
          )}
        </div>
      )
    }
    return (
      <div className="flex h-full flex-col">
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-8 sm:px-6">{thread}</div>
        <div className="shrink-0 border-t border-slate-200 bg-white/90 px-4 py-3 backdrop-blur sm:px-6">
          {composer}
        </div>
      </div>
    )
  }

  return (
    <Card
      title="Ask your Career Co-Pilot"
      subtitle={
        isHosted
          ? 'Type or speak a career question.'
          : 'Type or speak a career question — answered locally by your AI.'
      }
    >
      {!hasChat && <div className="mb-3">{chips}</div>}
      {hasChat && <div className="mb-3 max-h-[24rem] overflow-y-auto">{thread}</div>}
      {composer}
    </Card>
  )
}
