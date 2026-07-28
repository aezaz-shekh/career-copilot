import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ApiError,
  MicPermissionError,
  createListener,
  createSpeaker,
  describeProvider,
  selectProviders,
} from '../lib/speech.js'
import { Alert, Button } from './ui.jsx'

/**
 * Hands-free conversational voice answering.
 *
 *   AI speaks the question → you record → tap Done → AI gives a short spoken
 *   acknowledgment → the parent scores + advances → the next question auto-speaks.
 *
 * There is no separate "submit" step: tapping Done transcribes and submits. The
 * acknowledgment is deliberately neutral/warm (never "perfect") — scores stay
 * hidden until the end, like a real interview.
 *
 * Speech itself is delegated to lib/speech.js, which picks whisper.cpp + Piper
 * when the host can run them and the browser's own speech services otherwise.
 * The flow below is identical either way — it never learns which tier answered.
 */
const ACKS = [
  'Thank you.',
  'Got it, thanks.',
  'Great, noted.',
  'Thanks for that answer.',
  'Understood, thank you.',
]

export default function VoiceAnswer({ question, voiceStatus, busy, onSubmit }) {
  // phase: 'speaking' (question) | 'ready' | 'recording' | 'transcribing'
  const [phase, setPhase] = useState('ready')
  const [transcript, setTranscript] = useState('')
  const [error, setError] = useState(null)
  const listenerRef = useRef(null)
  const audioRef = useRef(null)
  const urlRef = useRef(null)

  const providers = useMemo(() => selectProviders(voiceStatus), [voiceStatus])
  const speak = useMemo(
    () => createSpeaker(providers.tts, { audioEl: audioRef.current, urlRef }),
    [providers.tts],
  )
  const canSpeak = providers.tts !== null
  const providerLabel = describeProvider(providers)

  // A new question arrives → speak it, then wait for the user to record.
  useEffect(() => {
    let cancelled = false
    setTranscript('')
    setError(null)
    ;(async () => {
      setPhase('speaking')
      await speak(question)
      if (!cancelled) setPhase('ready')
    })()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question])

  // Stop any in-flight recognition and release the last audio URL on unmount,
  // so leaving mid-answer never leaves the microphone live.
  useEffect(
    () => () => {
      listenerRef.current?.abort()
      if (urlRef.current) URL.revokeObjectURL(urlRef.current)
    },
    [],
  )

  async function startRecording() {
    setError(null)
    const listener = createListener(providers.stt)
    if (!listener) {
      setError({
        message: 'Speech input is not available here.',
        hint: 'Switch to Text mode above to type your answer instead.',
      })
      return
    }
    try {
      await listener.start()
      listenerRef.current = listener
      setPhase('recording')
    } catch (err) {
      setError(
        err instanceof MicPermissionError
          ? { message: err.message, hint: 'Switch to Text mode above to type instead.' }
          : { message: 'Could not start recording.', hint: null },
      )
      setPhase('ready')
    }
  }

  async function stopAndSubmit() {
    if (!listenerRef.current) return
    setPhase('transcribing')
    try {
      const text = await listenerRef.current.stop()
      listenerRef.current = null
      setTranscript(text)
      if (!text) {
        setError({ message: 'Nothing was transcribed.', hint: 'Tap record and speak a bit louder.' })
        setPhase('ready')
        return
      }
      // Warm spoken acknowledgment, then hand the answer to the parent (which
      // scores it and advances — the next question then auto-speaks).
      await speak(ACKS[Math.floor(Math.random() * ACKS.length)])
      onSubmit(text)
    } catch (err) {
      listenerRef.current = null
      setError(
        err instanceof ApiError
          ? { message: err.message, hint: err.hint }
          : err instanceof MicPermissionError
            ? { message: err.message, hint: 'Switch to Text mode above to type instead.' }
            : { message: 'Transcription failed.', hint: null },
      )
      setPhase('ready')
    }
  }

  return (
    <div className="space-y-3">
      <audio ref={audioRef} className="hidden" />

      <div className="flex flex-col items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-6 text-center">
        {phase === 'speaking' && (
          <p className="flex items-center gap-2 text-sm font-medium text-indigo-600">
            <span className="animate-pulse">🔊</span> Speaking the question…
          </p>
        )}

        {phase === 'ready' && (
          <>
            <Button onClick={startRecording} disabled={busy}>
              🎤 Record your answer
            </Button>
            {canSpeak && (
              <button
                type="button"
                onClick={() => speak(question)}
                className="text-xs text-slate-400 hover:text-slate-600"
              >
                ▶ replay question
              </button>
            )}
          </>
        )}

        {phase === 'recording' && (
          <>
            <span className="flex items-center gap-2 text-sm font-medium text-rose-600">
              <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-rose-500" />
              Listening… speak your answer
            </span>
            <Button variant="danger" onClick={stopAndSubmit}>
              ⏹ Done — I've finished
            </Button>
          </>
        )}

        {phase === 'transcribing' && <p className="text-sm text-slate-500">Hearing your answer…</p>}

        {busy && phase !== 'recording' && (
          <p className="text-xs text-slate-400">Scoring… the next question comes up on its own.</p>
        )}

        {providerLabel && phase === 'ready' && (
          <p className="text-[11px] text-slate-400">{providerLabel}</p>
        )}
      </div>

      {transcript && phase !== 'recording' && (
        <p className="text-center text-sm italic text-slate-500">You said: “{transcript}”</p>
      )}

      {error && <Alert tone="error" title={error.message} hint={error.hint} />}
    </div>
  )
}
