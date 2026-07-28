/**
 * Microphone recorder that produces 16 kHz mono 16-bit WAV — exactly what
 * whisper.cpp wants — entirely in the browser, with no ffmpeg on the server.
 *
 * MediaRecorder only emits webm/opus, which whisper cannot read directly, so we
 * capture raw PCM through the Web Audio API instead, downsample to 16 kHz, and
 * encode a WAV ourselves. This keeps the whole voice path dependency-light and
 * on-device.
 */

const TARGET_RATE = 16000

export class MicPermissionError extends Error {
  constructor(message) {
    super(message)
    this.name = 'MicPermissionError'
  }
}

export class WavRecorder {
  constructor() {
    this.stream = null
    this.context = null
    this.processor = null
    this.source = null
    this.chunks = []
    this.sampleRate = 44100
  }

  async start() {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch (err) {
      throw new MicPermissionError(
        err?.name === 'NotAllowedError'
          ? 'Microphone permission was denied.'
          : 'No microphone was found.',
      )
    }

    const AudioCtx = window.AudioContext || window.webkitAudioContext
    this.context = new AudioCtx()
    this.sampleRate = this.context.sampleRate
    this.source = this.context.createMediaStreamSource(this.stream)

    // ScriptProcessor is deprecated but works everywhere and is the simplest way
    // to grab raw PCM frames. 4096-frame buffer, mono in / mono out.
    this.processor = this.context.createScriptProcessor(4096, 1, 1)
    this.chunks = []
    this.processor.onaudioprocess = (event) => {
      this.chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)))
    }
    this.source.connect(this.processor)
    this.processor.connect(this.context.destination)
  }

  /** Stop recording and return a WAV Blob (16 kHz mono). */
  async stop() {
    this.processor?.disconnect()
    this.source?.disconnect()
    this.stream?.getTracks().forEach((t) => t.stop())
    if (this.context) await this.context.close()

    const merged = mergeChunks(this.chunks)
    const downsampled = downsample(merged, this.sampleRate, TARGET_RATE)
    return encodeWav(downsampled, TARGET_RATE)
  }
}

function mergeChunks(chunks) {
  const length = chunks.reduce((sum, c) => sum + c.length, 0)
  const out = new Float32Array(length)
  let offset = 0
  for (const c of chunks) {
    out.set(c, offset)
    offset += c.length
  }
  return out
}

function downsample(samples, fromRate, toRate) {
  if (toRate >= fromRate) return samples
  const ratio = fromRate / toRate
  const newLength = Math.round(samples.length / ratio)
  const result = new Float32Array(newLength)
  for (let i = 0; i < newLength; i++) {
    const start = Math.floor(i * ratio)
    const end = Math.floor((i + 1) * ratio)
    let sum = 0
    let count = 0
    for (let j = start; j < end && j < samples.length; j++) {
      sum += samples[j]
      count++
    }
    result[i] = count ? sum / count : 0 // average the window to reduce aliasing
  }
  return result
}

function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buffer)

  const writeString = (offset, str) => {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i))
  }

  writeString(0, 'RIFF')
  view.setUint32(4, 36 + samples.length * 2, true)
  writeString(8, 'WAVE')
  writeString(12, 'fmt ')
  view.setUint32(16, 16, true) // PCM chunk size
  view.setUint16(20, 1, true) // PCM format
  view.setUint16(22, 1, true) // mono
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true) // byte rate
  view.setUint16(32, 2, true) // block align
  view.setUint16(34, 16, true) // bits per sample
  writeString(36, 'data')
  view.setUint32(40, samples.length * 2, true)

  // Float32 [-1,1] -> signed 16-bit PCM.
  let offset = 44
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true)
    offset += 2
  }

  return new Blob([view], { type: 'audio/wav' })
}
