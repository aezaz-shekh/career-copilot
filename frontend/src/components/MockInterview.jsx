import { useEffect, useRef, useState } from 'react'
import { ApiError, api } from '../api.js'
import { Alert, Button } from './ui.jsx'
import VoiceAnswer from './VoiceAnswer.jsx'

/**
 * Chat-style mock interview runner.
 *
 * Presents one question at a time. On submit, the answer is scored server-side
 * (two LLM calls) — but scores are NOT shown here; they are revealed only on the
 * summary once the session ends, which is more like a real interview. A
 * follow-up question, when the model asks for one, is slotted in as the next
 * question before moving on.
 */
/** The interviewer avatar — a violet gradient badge with a person icon. */
function InterviewerAvatar() {
  return (
    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 via-fuchsia-500 to-purple-600 text-white shadow-md shadow-fuchsia-200/60">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
        <circle cx="12" cy="8" r="4" />
        <path d="M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1" />
      </svg>
    </span>
  )
}

export default function MockInterview({
  sessionId,
  questions,
  voiceStatus,
  onFinish,
  onCancel,
}) {
  // The queue starts as the planned questions; follow-ups are spliced in.
  const [queue, setQueue] = useState(() =>
    questions.map((q) => ({ ...q, isFollowup: false })),
  )
  const [index, setIndex] = useState(0)
  const [answer, setAnswer] = useState('')
  const [transcript, setTranscript] = useState([]) // {question, answer, isFollowup}
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [mode, setMode] = useState('text') // 'text' | 'voice'
  const bottomRef = useRef(null)

  const voiceOffered = Boolean(voiceStatus?.stt_available)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [transcript, index])

  const current = queue[index]
  const done = index >= queue.length

  async function submit(givenAnswer) {
    const text = (givenAnswer ?? answer).trim()
    if (!text || busy) return
    setBusy(true)
    setError(null)
    const asked = current
    try {
      const resp = await api.submitAnswer({
        session_id: sessionId,
        question: asked.question,
        answer: text,
        is_followup: asked.isFollowup,
      })

      setTranscript((prev) => [
        ...prev,
        { question: asked.question, answer: text, isFollowup: asked.isFollowup },
      ])
      setAnswer('')

      // Splice a follow-up in as the immediate next question, if the model asked.
      if (resp.needs_followup && resp.followup_question) {
        setQueue((prev) => {
          const next = [...prev]
          next.splice(index + 1, 0, {
            question: resp.followup_question,
            type: asked.type,
            difficulty: asked.difficulty,
            isFollowup: true,
          })
          return next
        })
      }
      setIndex((i) => i + 1)
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

  async function finish() {
    setBusy(true)
    try {
      const summary = await api.finishInterview(sessionId)
      onFinish(summary)
    } catch (err) {
      setError({ message: err.message, hint: err.hint })
      setBusy(false)
    }
  }

  const answered = transcript.length
  const pct = queue.length ? Math.round((answered / queue.length) * 100) : 0

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      {/* Progress bar across the top */}
      <div className="h-1.5 w-full bg-slate-100">
        <div
          className="h-full bg-gradient-to-r from-violet-500 to-fuchsia-500 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>

      <div className="p-6">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <InterviewerAvatar />
            <div>
              <h2 className="text-lg font-semibold leading-tight text-slate-900">Mock interview</h2>
              <p className="text-xs text-slate-400">
                {done ? `${answered} answered` : `Question ${index + 1} of ${queue.length}`}
              </p>
            </div>
          </div>
          {voiceOffered && !done && (
            <div className="flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs font-semibold">
              {['text', 'voice'].map((m) => (
                <button
                  key={m}
                  onClick={() => setMode(m)}
                  disabled={busy}
                  className={`rounded-md px-3 py-1 capitalize transition ${
                    mode === m ? 'bg-violet-600 text-white shadow-sm' : 'text-slate-500 hover:text-slate-800'
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="max-h-80 space-y-3 overflow-y-auto pr-1">
          {transcript.map((t, i) => (
            <div key={i} className="space-y-2">
              <div className="flex justify-start">
                <div className="max-w-[80%] rounded-2xl rounded-tl-sm bg-slate-100 px-4 py-2 text-sm text-slate-800">
                  {t.isFollowup && (
                    <span className="mr-1 text-xs font-semibold text-violet-600">Follow-up:</span>
                  )}
                  {t.question}
                </div>
              </div>
              <div className="flex justify-end">
                <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-violet-600 px-4 py-2 text-sm text-white">
                  {t.answer}
                </div>
              </div>
            </div>
          ))}

          {!done && current && (
            <div className="flex items-start gap-2">
              <InterviewerAvatar />
              <div className="max-w-[80%] rounded-2xl rounded-tl-sm bg-violet-50 px-4 py-2.5 text-sm font-medium text-slate-900 ring-1 ring-violet-100">
                {current.isFollowup && (
                  <span className="mr-1 text-xs font-semibold text-violet-600">Follow-up:</span>
                )}
                {current.question}
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

      {error && (
        <div className="mt-4">
          <Alert tone="error" title={error.message} hint={error.hint} />
        </div>
      )}

      {!done ? (
        <div className="mt-5">
          {mode === 'voice' && voiceOffered ? (
            <VoiceAnswer
              question={current.question}
              ttsAvailable={Boolean(voiceStatus?.tts_available)}
              busy={busy}
              onSubmit={(text) => submit(text)}
            />
          ) : (
            <>
              <textarea
                rows={4}
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                disabled={busy}
                placeholder="Type your answer… (use the STAR method: Situation, Task, Action, Result)"
                className="w-full resize-y rounded-xl border border-slate-200 bg-slate-50 p-3.5 text-sm leading-relaxed text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-violet-400 focus:bg-white focus:ring-2 focus:ring-violet-100"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submit()
                }}
              />
              <div className="mt-2 flex items-center justify-between">
                <span className="text-xs text-slate-400">Ctrl/⌘ + Enter to submit</span>
                <div className="flex gap-2">
                  <Button variant="secondary" onClick={onCancel} disabled={busy}>
                    Cancel
                  </Button>
                  <Button variant="gradient" onClick={() => submit()} disabled={busy || !answer.trim()}>
                    {busy ? 'Scoring…' : 'Submit answer'}
                  </Button>
                </div>
              </div>
            </>
          )}
          {busy && (
            <p className="mt-2 text-xs text-slate-400">
              Scoring your answer locally — two AI passes, a moment on CPU. Scores are revealed at the
              end.
            </p>
          )}
        </div>
      ) : (
        <div className="mt-5 border-t border-slate-200 pt-5 text-center sm:text-left">
          <p className="text-sm text-slate-600">
            🎉 You&apos;ve answered all {answered} questions. Finish to reveal your scores and summary.
          </p>
          <div className="mt-3">
            <Button variant="gradient" onClick={finish} disabled={busy}>
              {busy ? 'Finishing…' : 'Finish & see results'}
            </Button>
          </div>
        </div>
      )}
      </div>
    </div>
  )
}
