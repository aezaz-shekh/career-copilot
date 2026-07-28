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

/**
 * Give the synthesiser something to breathe on.
 *
 * A question like "Tell me about a time you failed What did you learn" runs
 * together without punctuation. Adding a comma after a leading clause and a
 * full stop between sentences that lack one makes the delivery land as speech
 * rather than a single long string.
 */
function addBreathingRoom(text) {
  return text
    .replace(/([a-z0-9])\s+(But|And|So|Then|Now|However|Also)\s/g, '$1. $2 ')
    .replace(/([.!?])([A-Z])/g, '$1 $2')
    .replace(/:\s*/g, ': ')
    .trim()
}

/**
 * Resolve once the browser has actually populated its voice list.
 *
 * getVoices() is empty on the first call in Chrome — the list arrives later on
 * a voiceschanged event. Speaking before it lands is what makes the first
 * utterance come out in the wrong voice, or not at all, so callers wait here.
 * Cached after the first success; the timeout keeps a browser that never fires
 * the event from blocking speech forever.
 */
let voicesReady = null
function whenVoicesReady() {
  if (voicesReady) return voicesReady
  voicesReady = new Promise((resolve) => {
    const synth = globalThis.speechSynthesis
    if (!synth) {
      resolve([])
      return
    }
    const existing = synth.getVoices()
    if (existing.length) {
      resolve(existing)
      return
    }
    const done = () => {
      clearTimeout(timer)
      synth.removeEventListener?.('voiceschanged', done)
      resolve(synth.getVoices())
    }
    const timer = setTimeout(done, 1500)
    synth.addEventListener?.('voiceschanged', done)
  })
  return voicesReady
}

/**
 * Pick a natural-sounding English voice.
 *
 * Browsers list system voices in no useful order and the default is often the
 * most robotic one, so prefer the known-good names first and fall back to any
 * local English voice before letting the browser choose.
 */
// Warm, clear female voices, best first. The project's own Piper voice is
// female (en_US-amy-medium), so the browser tier matching that keeps the app
// sounding like itself wherever it runs.
//
// The "Natural"/"Online" Microsoft voices and macOS's premium set are neural
// rather than concatenative — noticeably smoother and clearer than the older
// built-ins — so they are listed above the classic ones.
const PREFERRED_VOICES = [
  // Neural, the clearest available in each browser.
  'Microsoft Aria Online (Natural) - English (United States)',
  'Microsoft Jenny Online (Natural) - English (United States)',
  'Microsoft Michelle Online (Natural) - English (United States)',
  'Google US English',
  // macOS / iOS premium and enhanced variants, when the user has downloaded them.
  'Samantha (Premium)',
  'Ava (Premium)',
  'Allison (Premium)',
  'Samantha (Enhanced)',
  'Ava (Enhanced)',
  // Solid classic fallbacks.
  'Samantha',
  'Ava',
  'Allison',
  'Susan',
  'Microsoft Zira - English (United States)',
  'Karen',
  'Tessa',
]

// Names that reliably indicate a female voice, for browsers whose list does not
// include any of the above.
const FEMALE_HINTS =
  /samantha|karen|moira|tessa|victoria|fiona|zira|aria|jenny|michelle|ava|allison|susan|serena|female|woman|girl/i

// Voices that sound robotic even when they match everything else. Excluded so a
// fallback never lands on one.
const LOW_QUALITY = /albert|bad news|bahh|bells|boing|bubbles|cellos|deranged|good news|jester|organ|superstar|trinoids|whisper|wobble|zarvox|junior|ralph|fred|grandma|grandpa|rocko|shelley|sandy|flo|eddy|reed|rishi/i

// Default rate is noticeably brisk for an interview question you are meant to
// think about. Slightly under 1 reads as measured rather than hurried, and
// slower still is where words start to smear together.
const SPEECH_RATE = 0.95
// Slightly above neutral brightens the tone without tipping into a cartoon
// pitch, which is what makes a synthesised voice sound thin.
const SPEECH_PITCH = 1.08
// Full volume: anything less reads as muffled through laptop speakers.
const SPEECH_VOLUME = 1.0

function pickVoice(voices) {
  const usable = voices.filter((v) => !LOW_QUALITY.test(v.name))

  for (const name of PREFERRED_VOICES) {
    const match = usable.find((v) => v.name === name)
    if (match) return match
  }

  const english = usable.filter((v) => v.lang?.startsWith('en'))
  return (
    // A neural voice, whatever it is called, beats a classic one on clarity.
    english.find((v) => /natural|premium|enhanced|neural/i.test(v.name) && FEMALE_HINTS.test(v.name)) ||
    english.find((v) => FEMALE_HINTS.test(v.name)) ||
    english.find((v) => /natural|premium|enhanced|neural/i.test(v.name)) ||
    english.find((v) => v.localService) ||
    english[0] ||
    null
  )
}

/**
 * Speak via the browser, resolving when playback finishes.
 *
 * Chrome stops firing `onend` if an utterance runs past roughly fifteen
 * seconds, which would leave the interview waiting on a promise that never
 * settles. The watchdog below resolves on a duration estimated from the text
 * so the flow always continues.
 */
async function browserSpeak(text) {
  if (!browserTtsSupported() || !text) return
  const voices = await whenVoicesReady()
  const synth = globalThis.speechSynthesis
  if (!synth) return

  return new Promise((resolve) => {
    // Synthesisers run sentences together when the punctuation is sparse, which
    // is most of what makes a spoken answer hard to follow. Nudging the pauses
    // costs nothing and buys a lot of clarity.
    const utterance = new globalThis.SpeechSynthesisUtterance(addBreathingRoom(text))
    const voice = pickVoice(voices)
    if (voice) utterance.voice = voice
    utterance.lang = voice?.lang || 'en-US'
    utterance.rate = SPEECH_RATE
    utterance.pitch = SPEECH_PITCH
    utterance.volume = SPEECH_VOLUME

    let settled = false
    const finish = () => {
      if (settled) return
      settled = true
      clearTimeout(watchdog)
      resolve()
    }
    // ~12 characters a second, plus headroom, then give up waiting.
    const watchdog = setTimeout(finish, (text.length / (12 * SPEECH_RATE)) * 1000 + 5000)

    // Resolve either way: a failed line must never block the interview.
    utterance.onend = finish
    utterance.onerror = finish
    synth.cancel() // drop anything still queued
    synth.speak(utterance)
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

async function serverSpeak(text, audioRef, urlRef) {
  const url = await api.speak(text)
  if (urlRef.current) URL.revokeObjectURL(urlRef.current)
  urlRef.current = url
  // Read the element at call time, not when the speaker was built: refs are
  // still null on the first render, so capturing .current up front silently
  // skipped the very first spoken question.
  const audioEl = audioRef?.current
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
export function createSpeaker(ttsProvider, { audioRef, urlRef } = {}) {
  if (ttsProvider === 'server') {
    return async (text) => {
      try {
        await serverSpeak(text, audioRef, urlRef)
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
export async function speakOnce(text, { preferServer = false } = {}) {
  // The greeting is the first thing a visitor hears, and Piper is a network
  // round-trip away — on a hosted instance that is seconds of silence before
  // anything happens. The browser speaks immediately, so for a one-off line it
  // wins on latency even though Piper wins on quality. Callers that can afford
  // the wait pass preferServer.
  if (!preferServer && browserTtsSupported()) {
    await browserSpeak(text)
    return true
  }

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

/**
 * Start loading the browser's voice list before anything needs to speak.
 *
 * The first getVoices() call is what costs the delay, so paying it during app
 * start means the first spoken question begins immediately instead of after a
 * pause. Safe to call anywhere: it is idempotent and never throws.
 */
/**
 * Flatten Markdown into something worth listening to.
 *
 * The assistant is prompted to answer in Markdown, so the raw text is full of
 * "##", "**" and "-". Spoken verbatim those become "hash hash", "star star" —
 * the markup has to come off before the text reaches a synthesiser.
 */
export function stripMarkdown(markdown) {
  return markdown
    .replace(/```[\s\S]*?```/g, ' code block ') // fenced code reads as noise
    .replace(/`([^`]+)`/g, '$1')
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1') // links: keep the label
    .replace(/^\s{0,3}#{1,6}\s+/gm, '')
    .replace(/^\s*[-*_]{3,}\s*$/gm, '') // horizontal rules
    .replace(/^\s*[-*+]\s+/gm, '')
    .replace(/^\s*\d+\.\s+/gm, '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/^\s*>\s?/gm, '')
    .replace(/\n{2,}/g, '. ')
    .replace(/\s+/g, ' ')
    .trim()
}

/** Stop anything currently being spoken (navigating away, closing a chat). */
export function stopSpeaking() {
  try {
    globalThis.speechSynthesis?.cancel()
  } catch {
    /* nothing to cancel */
  }
}

export function prewarmSpeech() {
  if (browserTtsSupported()) whenVoicesReady()
}

export { ApiError, MicPermissionError }
