import { useEffect, useRef, useState } from 'react'
import { ApiError, api } from '../api.js'
import { MicPermissionError, WavRecorder } from '../lib/recorder.js'
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
 */
const ACKS = [
  'Thank you.',
  'Got it, thanks.',
  'Great, noted.',
  'Thanks for that answer.',
  'Understood, thank you.',
]

export default function VoiceAnswer({ question, ttsAvailable, busy, onSubmit }) {
  // phase: 'speaking' (question) | 'ready' | 'recording' | 'transcribing'
  const [phase, setPhase] = useState('ready')
  const [transcript, setTranscript] = useState('')
  const [error, setError] = useState(null)
  const recorderRef = useRef(null)
  const audioRef = useRef(null)
  const urlRef = useRef(null)

  // Speak text aloud (local TTS) and resolve when it finishes. Best-effort:
  // if autoplay is blocked or voice is off, it resolves silently.
  async function speak(text) {
    if (!ttsAvailable) return
    try {
      const url = await api.speak(text)
      if (urlRef.current) URL.revokeObjectURL(urlRef.current)
      urlRef.current = url
      const audio = audioRef.current
      if (!audio) return
      audio.src = url
      await audio.play()
      await new Promise((resolve) => {
        audio.onended = resolve
      })
    } catch {
      /* autoplay blocked or voice unavailable — continue silently */
    }
  }

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

  useEffect(
    () => () => {
      if (urlRef.current) URL.revokeObjectURL(urlRef.current)
    },
    [],
  )

  async function startRecording() {
    setError(null)
    const recorder = new WavRecorder()
    try {
      await recorder.start()
      recorderRef.current = recorder
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
    if (!recorderRef.current) return
    setPhase('transcribing')
    try {
      const wav = await recorderRef.current.stop()
      recorderRef.current = null
      const result = await api.transcribe(wav)
      const text = (result.transcript || '').trim()
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
      setError(
        err instanceof ApiError
          ? { message: err.message, hint: err.hint }
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
            {ttsAvailable && (
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
          <p className="text-xs text-slate-400">
            Scoring locally… the next question comes up on its own.
          </p>
        )}
      </div>

      {transcript && phase !== 'recording' && (
        <p className="text-center text-sm italic text-slate-500">You said: “{transcript}”</p>
      )}

      {error && <Alert tone="error" title={error.message} hint={error.hint} />}
    </div>
  )
}
