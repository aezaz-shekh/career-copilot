/**
 * Speech providers: one interface, three tiers.
 *
 * Voice used to mean exactly one thing — upload a WAV to /api/voice/transcribe
 * and let whisper.cpp and Piper answer. That works on a laptop and fails on a
 * small host: whisper and Piper together need a few hundred MB, and on a 512 MB
 * instance the OOM killer takes the whole process rather than just the
 * transcription. So voice was simply off there.
 *
 * Browsers already ship speech recognition and synthesis. Using them costs the
 * server nothing, so voice can stay available where the binaries cannot run.
 * This module picks the best provider the current environment supports:
 *
 *   server   whisper.cpp + Piper via the API      (best quality, needs the host)
 *   browser  SpeechRecognition + speechSynthesis  (free, no server memory)
 *   null     neither — the caller falls back to text mode
 *
 * Callers see one shape and never branch on which tier answered:
 *
 *   listen(): Promise<string>   resolve with a transcript, reject on failure
 *   speak(text): Promise<void>  resolve when speech finishes
 *
 * Note on privacy: `speechSynthesis` is on-device everywhere. Speech
 * *recognition* is not — Chrome streams audio to Google. That is why the server
 * tier is preferred whenever it is available, and why describeProvider() below
 * says "your browser's speech service" rather than claiming it is local.
 */

import { ApiError, api } from '../api.js'
import { MicPermissionError, WavRecorder } from './recorder.js'

/**
 * Recognition constructor for this browser, or undefined.
 *
 * Resolved on each call rather than captured at module load: the globals are
 * read through globalThis so detection works the same in a browser and under a
 * test runner, and so a page that installs a polyfill after this module is
 * imported is still picked up.
 */
function getSpeechRecognition() {
  return globalThis.SpeechRecognition || globalThis.webkitSpeechRecognition || undefined
}

export function browserSttSupported() {
  return Boolean(getSpeechRecognition())
}

export function browserTtsSupported() {
  return Boolean(globalThis.speechSynthesis)
}

/**
 * A recognition session. `start()` begins listening; `stop()` ends it and
 * resolves with everything heard.
 *
 * continuous + interimResults keep a long answer from being cut off at the
 * first pause, which is the default behaviour and useless for interview
 * answers that run for thirty seconds with thinking pauses in them.
 */
function createBrowserListener() {
  const recognition = new (getSpeechRecognition())()
  recognition.continuous = true
  recognition.interimResults = true
  recognition.lang = 'en-US'

  let finalText = ''
  let settle = null
  let failed = null

  recognition.onresult = (event) => {
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const result = event.results[i]
      if (result.isFinal) finalText += result[0].transcript
    }
  }

  recognition.onerror = (event) => {
    // "no-speech" and "aborted" are normal endings, not failures: the user may
    // have stopped without saying anything, which the caller reports itself.
    if (event.error === 'no-speech' || event.error === 'aborted') return
    failed =
      event.error === 'not-allowed'
        ? new MicPermissionError('Microphone permission was denied.')
        : new Error(`Speech recognition failed: ${event.error}`)
  }

  recognition.onend = () => {
    if (settle) settle()
  }

  return {
    start() {
      finalText = ''
      failed = null
      recognition.start()
    },
    stop() {
      return new Promise((resolve, reject) => {
        settle = () => (failed ? reject(failed) : resolve(finalText.trim()))
        try {
          recognition.stop()
        } catch {
          // Already stopped; onend may never fire, so settle directly.
          settle()
        }
      })
    },
    abort() {
      try {
        recognition.abort()
      } catch {
        /* nothing to abort */
      }
    },
  }
}

/** Speak via the browser, resolving when playback finishes. */
function browserSpeak(text) {
  return new Promise((resolve) => {
    if (!browserTtsSupported() || !text) {
      resolve()
      return
    }
    const utterance = new globalThis.SpeechSynthesisUtterance(text)
    utterance.rate = 1.0
    utterance.pitch = 1.0
    // Resolve either way: a failed greeting must never block the interview.
    utterance.onend = resolve
    utterance.onerror = resolve
    globalThis.speechSynthesis.cancel() // drop anything still queued
    globalThis.speechSynthesis.speak(utterance)
  })
}

/**
 * Server tier: record a WAV, upload it, get the transcript back.
 * This is the original path, unchanged.
 */
function createServerListener() {
  const recorder = new WavRecorder()
  return {
    async start() {
      await recorder.start()
    },
    async stop() {
      const wav = await recorder.stop()
      const result = await api.transcribe(wav)
      return (result.transcript || '').trim()
    },
    abort() {
      recorder.stop().catch(() => {})
    },
  }
}

async function serverSpeak(text, audioEl, urlRef) {
  const url = await api.speak(text)
  if (urlRef.current) URL.revokeObjectURL(urlRef.current)
  urlRef.current = url
  if (!audioEl) return
  audioEl.src = url
  await audioEl.play()
  await new Promise((resolve) => {
    audioEl.onended = resolve
  })
}

/**
 * Choose the speech provider for the current environment.
 *
 * @param {{stt_available?: boolean, tts_available?: boolean} | null} voiceStatus
 *   What /api/voice/status reported, or null if it could not be read.
 * @returns {{stt: 'server'|'browser'|null, tts: 'server'|'browser'|null}}
 *
 * The server tier wins when offered: whisper is more accurate than browser
 * recognition, Piper sounds better than most system voices, and neither sends
 * audio anywhere. Browser support is the fallback, not the preference.
 */
export function selectProviders(voiceStatus) {
  return {
    stt: voiceStatus?.stt_available ? 'server' : browserSttSupported() ? 'browser' : null,
    tts: voiceStatus?.tts_available ? 'server' : browserTtsSupported() ? 'browser' : null,
  }
}

/** Build a listener for the chosen tier, or null when speech input is unavailable. */
export function createListener(sttProvider) {
  if (sttProvider === 'server') return createServerListener()
  if (sttProvider === 'browser') return createBrowserListener()
  return null
}

/**
 * Build a speak(text) for the chosen tier. Always returns a callable, so the
 * caller can await it unconditionally — with no provider it is a no-op.
 *
 * Speech is decorative: a blocked autoplay or a missing voice must never stop
 * an interview, so every failure resolves quietly rather than rejecting.
 */
export function createSpeaker(ttsProvider, { audioEl, urlRef } = {}) {
  if (ttsProvider === 'server') {
    return async (text) => {
      try {
        await serverSpeak(text, audioEl, urlRef)
      } catch {
        /* autoplay blocked or voice unavailable — continue silently */
      }
    }
  }
  if (ttsProvider === 'browser') {
    return async (text) => {
      try {
        await browserSpeak(text)
      } catch {
        /* speech synthesis refused — continue silently */
      }
    }
  }
  return async () => {}
}

/** How the UI should describe where speech is being handled. */
export function describeProvider({ stt, tts }) {
  if (stt === 'server' || tts === 'server') return 'On-device speech (whisper.cpp · Piper)'
  if (stt === 'browser' || tts === 'browser') return 'Your browser’s built-in speech'
  return null
}

/**
 * Speak a one-off line (the welcome greeting), trying Piper first and falling
 * back to the browser. Purely decorative: every failure resolves quietly, so a
 * missing voice or a blocked autoplay never surfaces an error.
 *
 * @returns {Promise<boolean>} whether anything was actually spoken.
 */
export async function speakOnce(text) {
  try {
    const url = await api.speak(text)
    const audio = new Audio(url)
    await audio.play()
    await new Promise((resolve) => {
      audio.onended = resolve
      audio.onerror = resolve
    })
    URL.revokeObjectURL(url)
    return true
  } catch {
    /* server voice unavailable — try the browser below */
  }
  if (!browserTtsSupported()) return false
  await browserSpeak(text)
  return true
}

export { ApiError, MicPermissionError }
