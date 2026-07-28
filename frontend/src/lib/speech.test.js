/**
 * Provider selection is the part of voice that decides whether the feature is
 * offered at all, on every deployment. Getting it wrong either hides voice
 * where it would work or offers it where it cannot, so it is tested directly.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { browserSttSupported, browserTtsSupported, describeProvider, selectProviders } from './speech.js'

const SERVER_ON = { stt_available: true, tts_available: true }
const SERVER_OFF = { stt_available: false, tts_available: false }

/** Pretend the browser does / does not implement the speech APIs. */
function setBrowserSupport({ stt, tts }) {
  vi.stubGlobal('SpeechRecognition', stt ? function FakeRecognition() {} : undefined)
  vi.stubGlobal('webkitSpeechRecognition', undefined)
  vi.stubGlobal('speechSynthesis', tts ? { speak() {}, cancel() {} } : undefined)
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.resetModules()
})

describe('selectProviders', () => {
  it('prefers the server tier when the host offers it', () => {
    // whisper is more accurate than browser recognition and keeps audio on the
    // machine, so it must win even where the browser could also listen.
    setBrowserSupport({ stt: true, tts: true })
    expect(selectProviders(SERVER_ON)).toEqual({ stt: 'server', tts: 'server' })
  })

  it('falls back to the browser when the host cannot run the binaries', () => {
    setBrowserSupport({ stt: true, tts: true })
    expect(selectProviders(SERVER_OFF)).toEqual({ stt: 'browser', tts: 'browser' })
  })

  it('reports null when neither tier can listen or speak', () => {
    setBrowserSupport({ stt: false, tts: false })
    const { stt } = selectProviders(SERVER_OFF)
    expect(stt).toBeNull()
  })

  it('treats a failed status probe as no server tier', () => {
    // /api/voice/status failing does not mean speech is impossible — the
    // browser may still handle it, so voice must not be hidden outright.
    setBrowserSupport({ stt: true, tts: true })
    expect(selectProviders(null)).toEqual({ stt: 'browser', tts: 'browser' })
  })

  it('mixes tiers when only one side is available server-side', () => {
    setBrowserSupport({ stt: true, tts: true })
    expect(selectProviders({ stt_available: true, tts_available: false })).toEqual({
      stt: 'server',
      tts: 'browser',
    })
  })
})

describe('describeProvider', () => {
  it('names the on-device engines when the server tier is in use', () => {
    expect(describeProvider({ stt: 'server', tts: 'server' })).toMatch(/whisper/i)
  })

  it('does not claim browser recognition is on-device', () => {
    // Chrome streams recognition audio to Google, so the caption must not
    // describe the browser tier as local.
    const label = describeProvider({ stt: 'browser', tts: 'browser' })
    expect(label).toMatch(/browser/i)
    expect(label).not.toMatch(/on-device|local/i)
  })

  it('returns null when there is nothing to describe', () => {
    expect(describeProvider({ stt: null, tts: null })).toBeNull()
  })
})

describe('capability detection', () => {
  it('detects a missing SpeechRecognition implementation', () => {
    setBrowserSupport({ stt: false, tts: false })
    expect(browserSttSupported()).toBe(false)
  })

  it('detects speechSynthesis when the browser provides it', () => {
    setBrowserSupport({ stt: false, tts: true })
    expect(browserTtsSupported()).toBe(true)
  })
})
