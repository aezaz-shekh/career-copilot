/**
 * Thin wrapper around fetch for the local API.
 *
 * Its one job is to turn every failure into an ApiError carrying a `message`
 * and a `hint`, so no component ever has to guess how a given endpoint reports
 * problems. The backend sends {detail: {message, hint}} for its own errors and
 * FastAPI's own array shape for validation failures; both are normalised here.
 */

import { pushToast } from './toast.js'

export class ApiError extends Error {
  constructor(message, hint, status) {
    super(message)
    this.name = 'ApiError'
    this.hint = hint
    this.status = status
  }
}

async function toApiError(response) {
  let detail
  try {
    detail = (await response.json()).detail
  } catch {
    return new ApiError(`Request failed (HTTP ${response.status})`, null, response.status)
  }

  // FastAPI validation errors arrive as an array of {loc, msg, type}.
  if (Array.isArray(detail)) {
    const first = detail[0]
    const field = first?.loc?.slice(1).join('.') || 'input'
    return new ApiError(`${field}: ${first?.msg ?? 'invalid value'}`, null, response.status)
  }

  if (detail && typeof detail === 'object') {
    return new ApiError(detail.message ?? 'Request failed', detail.hint, response.status)
  }

  return new ApiError(detail || `Request failed (HTTP ${response.status})`, null, response.status)
}

// Long, but bounded: a big generation on CPU can take minutes, yet a request
// must never hang forever (e.g. if the backend was restarted mid-flight).
const LONG_TIMEOUT_MS = 12 * 60 * 1000

// Every request failure also raises a toast (with the fix hint), so a dropped
// backend or a down Ollama is visible app-wide, not only where a component
// happens to render the error inline (Prompt 4.1, friendly error handling).
async function request(path, options) {
  try {
    return await _request(path, options)
  } catch (err) {
    if (err instanceof ApiError) pushToast({ title: err.message, hint: err.hint })
    throw err
  }
}

async function _request(path, { timeoutMs, ...options } = {}) {
  const controller = new AbortController()
  const timer = timeoutMs ? setTimeout(() => controller.abort(), timeoutMs) : null

  let response
  try {
    response = await fetch(path, { ...options, signal: controller.signal })
  } catch (err) {
    if (err.name === 'AbortError') {
      throw new ApiError(
        'The request took too long and was cancelled.',
        'The local model may be overloaded. Close other heavy apps to free RAM, then retry.',
      )
    }
    throw new ApiError(
      'Cannot reach the backend API.',
      'Check that uvicorn is still running on 127.0.0.1:8000.',
    )
  } finally {
    if (timer) clearTimeout(timer)
  }

  if (!response.ok) throw await toApiError(response)
  if (response.status === 204) return null
  return response.json()
}

const json = (method, body) => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  health: () => request('/health'),

  uploadResume(file) {
    const form = new FormData()
    form.append('file', file)
    return request('/api/resumes/upload', { method: 'POST', body: form })
  },

  // Extract plain text from an attached document (PDF/TXT/MD). Same local
  // extractor as resume upload; nothing is persisted. Returns {raw_text, ...}.
  extractDocument(file) {
    const form = new FormData()
    form.append('file', file)
    return request('/api/resumes/upload', { method: 'POST', body: form })
  },

  // A full generation on CPU can take minutes, so allow a long — but bounded —
  // timeout rather than letting the UI hang forever if the backend goes away.
  structureResume: (rawText) =>
    request('/api/resumes/structure', { ...json('POST', { raw_text: rawText }), timeoutMs: LONG_TIMEOUT_MS }),

  saveResume: (payload) => request('/api/resumes', json('POST', payload)),
  listResumes: () => request('/api/resumes'),
  getResume: (id) => request(`/api/resumes/${id}`),
  deleteResume: (id) => request(`/api/resumes/${id}`, { method: 'DELETE' }),

  saveJd: (payload) => request('/api/jds', json('POST', payload)),
  listJds: () => request('/api/jds'),
  deleteJd: (id) => request(`/api/jds/${id}`, { method: 'DELETE' }),

  listReviews: () => request('/api/review'),
  getReview: (id) => request(`/api/review/${id}`),
  deleteReview: (id) => request(`/api/review/${id}`, { method: 'DELETE' }),

  startInterview: (payload) => request('/api/interviews/start', json('POST', payload)),
  submitAnswer: (payload) => request('/api/interviews/answer', json('POST', payload)),
  finishInterview: (id) => request(`/api/interviews/${id}/finish`, { method: 'POST' }),
  listInterviews: () => request('/api/interviews'),
  getInterview: (id) => request(`/api/interviews/${id}`),
  deleteInterview: (id) => request(`/api/interviews/${id}`, { method: 'DELETE' }),

  listRoadmaps: () => request('/api/roadmap'),
  getRoadmap: (id) => request(`/api/roadmap/${id}`),
  deleteRoadmap: (id) => request(`/api/roadmap/${id}`, { method: 'DELETE' }),
  setRoadmapItemDone: (itemId, done) =>
    request(`/api/roadmap/items/${itemId}`, json('PATCH', { done })),

  listContacts: () => request('/api/outreach/contacts'),
  getContact: (id) => request(`/api/outreach/contacts/${id}`),
  createContact: (payload) => request('/api/outreach/contacts', json('POST', payload)),
  updateContact: (id, payload) => request(`/api/outreach/contacts/${id}`, json('PATCH', payload)),
  deleteContact: (id) => request(`/api/outreach/contacts/${id}`, { method: 'DELETE' }),
  setDraftStatus: (draftId, status) =>
    request(`/api/outreach/drafts/${draftId}`, json('PATCH', { status })),
  deleteDraft: (draftId) => request(`/api/outreach/drafts/${draftId}`, { method: 'DELETE' }),

  setupStatus: () => request('/api/setup/status'),
  getSettings: () => request('/api/settings'),
  setChatModel: (model) => request('/api/settings/model', json('PUT', { model })),
  deleteAllData: (confirm) => request('/api/settings/data', json('DELETE', { confirm })),
  getStats: () => request('/api/stats'),

  voiceStatus: () => request('/api/voice/status'),

  transcribe(wavBlob) {
    const form = new FormData()
    form.append('file', wavBlob, 'answer.wav')
    return request('/api/voice/transcribe', { method: 'POST', body: form })
  },

  // Returns an object URL for the synthesised WAV (caller revokes it).
  async speak(text) {
    const response = await fetch('/api/voice/speak', json('POST', { text }))
    if (!response.ok) throw await toApiError(response)
    const blob = await response.blob()
    return URL.createObjectURL(blob)
  },
}

/**
 * POST `body` to `path` and dispatch each SSE frame to `onEvent(event, data)`.
 * Returns a function that aborts the stream.
 *
 * Shared by the review and question-bank streams: both are long CPU generations
 * that must show progress rather than block on one silent request (a silent POST
 * behind the Vite proxy can be severed mid-flight and look frozen forever).
 */
function postSse(path, body, onEvent) {
  const controller = new AbortController()

  ;(async () => {
    try {
      const response = await fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      })
      if (!response.ok) {
        const err = await toApiError(response)
        onEvent('error', { message: err.message, hint: err.hint })
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const frames = buffer.split('\n\n')
        buffer = frames.pop() ?? ''
        for (const frame of frames) {
          let event = 'message'
          let data = ''
          for (const line of frame.split('\n')) {
            if (line.startsWith('event: ')) event = line.slice(7)
            else if (line.startsWith('data: ')) data += line.slice(6)
          }
          if (data) onEvent(event, JSON.parse(data))
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        onEvent('error', { message: err.message, hint: 'Is the backend still running?' })
      }
    }
  })()

  return () => controller.abort()
}

/**
 * Run a review, calling `onEvent(event, data)` for each SSE frame
 * (step / done / error). Returns a function that aborts the run.
 */
export function runReview({ resumeId, jdId }, onEvent) {
  return postSse('/api/review', { resume_id: resumeId, jd_id: jdId }, onEvent)
}

/**
 * Generate a question bank, calling `onEvent(event, data)` for each SSE frame
 * (step / heartbeat / done / error). Returns a function that aborts the run.
 *
 * One large generation on CPU: the heartbeat frames carry elapsed seconds so the
 * UI shows live progress instead of a spinner that looks stuck.
 */
export function streamQuestions({ resumeId, jdId, jobTitle, topics }, onEvent) {
  const body = {}
  if (resumeId != null) body.resume_id = resumeId
  if (jdId != null) body.jd_id = jdId
  if (jobTitle) body.job_title = jobTitle
  if (topics) body.topics = topics
  return postSse('/api/interviews/questions', body, onEvent)
}

/**
 * Generate a career roadmap, calling `onEvent(event, data)` for each SSE frame
 * (step / done / error). Returns a function that aborts the run.
 *
 * Two 3B generations on CPU take minutes; the step frames drive the stepper so
 * the UI shows real progress. Pass `regeneratePlanId` to regenerate an existing
 * plan while keeping the user's ticked-off actions.
 */
export function streamRoadmap({ resumeId, targetRole, regeneratePlanId }, onEvent) {
  const body = { resume_id: resumeId, target_role: targetRole }
  if (regeneratePlanId != null) body.regenerate_plan_id = regeneratePlanId
  return postSse('/api/roadmap', body, onEvent)
}

/**
 * Generate outreach drafts, calling `onEvent(event, data)` for each SSE frame
 * (step / heartbeat / done / error). Returns a function that aborts the run.
 */
export function streamOutreach({ contactId, purpose, platform, hook }, onEvent) {
  return postSse(
    '/api/outreach/draft',
    { contact_id: contactId, purpose, platform, hook },
    onEvent,
  )
}

/**
 * Pull a model, calling `onEvent(event, data)` for each SSE frame
 * (progress / done / error). Returns a function that aborts the pull.
 */
export function streamPull(model, onEvent) {
  return postSse('/api/setup/pull', { model }, onEvent)
}

/**
 * Ask the local model a free-form career question, streaming the reply token by
 * token. `onEvent` receives ('token', {text}) as the answer builds, then
 * ('done', {}) or ('error', {message, hint}). Returns an abort function.
 */
export function streamAsk(question, onEvent, context = '') {
  const doc = context
    ? `The user attached a document. Use it to answer.\n---\n${context.slice(0, 3000)}\n---\n\n`
    : ''
  const message =
    'You are a friendly, knowledgeable career assistant helping a job seeker.\n' +
    'Give a helpful, reasonably detailed answer: a short intro plus three or ' +
    'four focused sections, and include a brief example or practical tip where ' +
    'it helps. Be thorough but do not pad or repeat yourself, and finish with a ' +
    'complete closing thought.\n' +
    'Format the answer in clean Markdown so it is easy to read:\n' +
    '- Use a short "## Heading" for each section.\n' +
    '- Use "**bold**" for key terms.\n' +
    '- Use "-" bullet points for lists.\n' +
    '- Put a "---" divider line between sections.\n' +
    'Do not wrap the whole reply in a code block.\n\n' +
    doc +
    `Question: ${question}`
  // num_predict is a generous safety cap so a long answer can still finish.
  return postSse(
    '/api/dev/echo-llm',
    { message: message.slice(0, 4000), temperature: 0.5, num_predict: 1024 },
    onEvent,
  )
}
