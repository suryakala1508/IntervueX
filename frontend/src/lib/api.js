/**
 * The single place that talks to the IntervueX API.
 *
 * Responsibilities kept here so no component has to think about them:
 *  - attaching the bearer token,
 *  - refreshing a expired access token once and replaying the request,
 *  - turning error responses into an Error with a message worth showing.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''
const API = `${BASE_URL}/api/v1`

const ACCESS_KEY = 'intervuex.access'
const REFRESH_KEY = 'intervuex.refresh'

export class ApiError extends Error {
  constructor(message, status, payload) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.payload = payload
  }
}

// localStorage throws in some privacy modes; never let that break the app.
function readStorage(key) {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

function writeStorage(key, value) {
  try {
    if (value === null) window.localStorage.removeItem(key)
    else window.localStorage.setItem(key, value)
  } catch {
    /* ignore - the session simply will not survive a reload */
  }
}

export const tokens = {
  get access() {
    return readStorage(ACCESS_KEY)
  },
  get refresh() {
    return readStorage(REFRESH_KEY)
  },
  set({ access_token, refresh_token }) {
    writeStorage(ACCESS_KEY, access_token)
    writeStorage(REFRESH_KEY, refresh_token)
  },
  clear() {
    writeStorage(ACCESS_KEY, null)
    writeStorage(REFRESH_KEY, null)
  },
}

/** Called when refreshing fails, so the app can send the user back to sign-in. */
let onSessionExpired = () => {}
export function setSessionExpiredHandler(handler) {
  onSessionExpired = handler
}

/**
 * FastAPI returns `detail` as a string for our own errors and as a list of
 * objects for validation failures. Flatten both into one readable line.
 */
function messageFromPayload(payload, status) {
  const detail = payload?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const field = (item.loc ?? []).filter((p) => p !== 'body').join('.')
        return field ? `${field}: ${item.msg}` : item.msg
      })
      .join('; ')
  }
  if (status === 0) return 'Could not reach the server. Is the backend running?'
  return `Request failed (${status})`
}

async function parseBody(response) {
  const type = response.headers.get('content-type') ?? ''
  if (!type.includes('application/json')) return null
  try {
    return await response.json()
  } catch {
    return null
  }
}

// A single in-flight refresh shared by every request that hits a 401 at once,
// so a page with three parallel loads does not burn three refresh tokens.
let refreshInFlight = null

async function refreshAccessToken() {
  const refresh_token = tokens.refresh
  if (!refresh_token) return false

  refreshInFlight ??= (async () => {
    try {
      const response = await fetch(`${API}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token }),
      })
      if (!response.ok) return false
      tokens.set(await response.json())
      return true
    } catch {
      return false
    } finally {
      refreshInFlight = null
    }
  })()

  return refreshInFlight
}

export async function request(path, { method = 'GET', body, formData, retry = true } = {}) {
  const headers = {}
  const access = tokens.access
  if (access) headers.Authorization = `Bearer ${access}`

  let payloadBody
  if (formData) {
    // Let the browser set the multipart boundary itself.
    payloadBody = formData
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payloadBody = JSON.stringify(body)
  }

  let response
  try {
    response = await fetch(`${API}${path}`, { method, headers, body: payloadBody })
  } catch {
    throw new ApiError('Could not reach the server. Is the backend running?', 0, null)
  }

  if (response.status === 401 && retry && tokens.refresh) {
    if (await refreshAccessToken()) {
      return request(path, { method, body, formData, retry: false })
    }
    tokens.clear()
    onSessionExpired()
  }

  if (response.status === 204) return null

  const payload = await parseBody(response)
  if (!response.ok) {
    throw new ApiError(messageFromPayload(payload, response.status), response.status, payload)
  }
  return payload
}

const get = (path) => request(path)
const post = (path, body) => request(path, { method: 'POST', body })
const put = (path, body) => request(path, { method: 'PUT', body })
const del = (path) => request(path, { method: 'DELETE' })
const upload = (path, formData) => request(path, { method: 'POST', formData })

export const api = {
  auth: {
    register: (payload) => post('/auth/register', payload),
    login: (payload) => post('/auth/login', payload),
    logout: () => post('/auth/logout'),
    me: () => get('/users/me'),
  },

  profile: {
    get: () => get('/profile'),
    update: (payload) => put('/profile', payload),
    uploadResume: (file) => {
      const form = new FormData()
      form.append('file', file)
      return upload('/profile/resume', form)
    },
  },

  documents: {
    list: () => get('/documents'),
    upload: (file, docType = 'other') => {
      const form = new FormData()
      form.append('file', file)
      form.append('doc_type', docType)
      return upload('/documents/upload', form)
    },
    remove: (id) => del(`/documents/${id}`),
    search: (query, limit = 6) =>
      get(`/documents/search?q=${encodeURIComponent(query)}&limit=${limit}`),
  },

  jobs: {
    list: () => get('/jobs'),
    get: (id) => get(`/jobs/${id}`),
    create: (payload) => post('/jobs', payload),
    activate: (id) => post(`/jobs/${id}/activate`),
    upload: (file, { title, company, setActive = true } = {}) => {
      const form = new FormData()
      form.append('file', file)
      if (title) form.append('title', title)
      if (company) form.append('company', company)
      form.append('set_active', String(setActive))
      return upload('/jobs/upload', form)
    },
  },

  interviews: {
    list: () => get('/interviews'),
    get: (id) => get(`/interviews/${id}`),
    start: (payload) => post('/interviews', payload),
    answer: (id, payload) => post(`/interviews/${id}/answer`, payload),
    complete: (id) => post(`/interviews/${id}/complete`),
    abandon: (id) => post(`/interviews/${id}/abandon`),
    plan: (id) => get(`/interviews/${id}/plan`),
    remove: (id) => del(`/interviews/${id}`),

    /**
     * Streaming answer turn. Calls onStep for each workflow node so the UI can
     * show what the agent is doing, and resolves with the same payload the
     * plain REST endpoint returns.
     *
     * fetch is used rather than EventSource because this is a POST that needs
     * an Authorization header, which EventSource cannot send.
     */
    answerStream: async (id, payload, { onStep } = {}) => {
      const headers = { 'Content-Type': 'application/json' }
      const access = tokens.access
      if (access) headers.Authorization = `Bearer ${access}`

      const response = await fetch(`${API}/interviews/${id}/answer/stream`, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      })

      if (!response.ok) {
        const body = await parseBody(response)
        throw new ApiError(messageFromPayload(body, response.status), response.status, body)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let result = null
      let streamError = null

      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        // SSE frames are separated by a blank line; keep any partial tail.
        const frames = buffer.split('\n\n')
        buffer = frames.pop() ?? ''

        for (const frame of frames) {
          const event = frame.match(/^event: (.*)$/m)?.[1]
          const raw = frame.match(/^data: (.*)$/m)?.[1]
          if (!event || !raw) continue

          let data
          try {
            data = JSON.parse(raw)
          } catch {
            continue
          }

          if (event === 'step') onStep?.(data)
          else if (event === 'result') result = data
          else if (event === 'error') streamError = data.detail
        }
      }

      if (streamError) throw new ApiError(streamError, 502, null)
      if (!result) throw new ApiError('The interview engine returned no result', 502, null)
      return result
    },
  },

  dashboard: {
    get: () => get('/dashboard'),
  },

  admin: {
    overview: () => get('/admin/overview'),
    users: () => get('/admin/users'),
    toolLogs: (limit = 50) => get(`/admin/tool-logs?limit=${limit}`),
  },

  health: () => {
    return fetch(`${BASE_URL}/health`).then((r) => r.json())
  },
}
