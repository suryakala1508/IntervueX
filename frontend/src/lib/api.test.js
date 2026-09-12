import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api, request, tokens } from './api'

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('token storage', () => {
  it('round-trips and clears a token pair', () => {
    tokens.set({ access_token: 'a', refresh_token: 'r' })
    expect(tokens.access).toBe('a')
    expect(tokens.refresh).toBe('r')

    tokens.clear()
    expect(tokens.access).toBeNull()
    expect(tokens.refresh).toBeNull()
  })

  it('survives localStorage being unavailable', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked in private mode')
    })
    // Must degrade to "signed out" rather than crashing the app.
    expect(tokens.access).toBeNull()
  })
})

describe('request', () => {
  beforeEach(() => {
    tokens.clear()
  })

  it('sends the bearer token when one is stored', async () => {
    tokens.set({ access_token: 'token-123', refresh_token: 'r' })
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await request('/profile')

    const [, options] = fetchMock.mock.calls[0]
    expect(options.headers.Authorization).toBe('Bearer token-123')
  })

  it('serialises a JSON body and sets the content type', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}))
    vi.stubGlobal('fetch', fetchMock)

    await request('/jobs', { method: 'POST', body: { title: 'Backend' } })

    const [, options] = fetchMock.mock.calls[0]
    expect(options.headers['Content-Type']).toBe('application/json')
    expect(JSON.parse(options.body)).toEqual({ title: 'Backend' })
  })

  it('leaves the content type unset for a file upload', async () => {
    // The browser must add the multipart boundary itself.
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}))
    vi.stubGlobal('fetch', fetchMock)

    await request('/documents/upload', { method: 'POST', formData: new FormData() })

    const [, options] = fetchMock.mock.calls[0]
    expect(options.headers['Content-Type']).toBeUndefined()
  })

  it('turns a string detail into the error message', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ detail: 'Interview not found' }, 404)),
    )

    await expect(request('/interviews/x')).rejects.toThrow('Interview not found')
  })

  it('flattens a FastAPI validation error into one readable line', async () => {
    const detail = [
      { loc: ['body', 'email'], msg: 'value is not a valid email address' },
      { loc: ['body', 'password'], msg: 'String should have at least 8 characters' },
    ]
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail }, 422)))

    await expect(request('/auth/register', { method: 'POST', body: {} })).rejects.toThrow(
      'email: value is not a valid email address; password: String should have at least 8 characters',
    )
  })

  it('reports an unreachable server in plain language', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(request('/dashboard')).rejects.toThrow(/Could not reach the server/)
  })

  it('carries the status code on the error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: 'nope' }, 403)))

    await expect(request('/admin/users')).rejects.toMatchObject({
      name: 'ApiError',
      status: 403,
    })
  })

  it('refreshes an expired token once and replays the request', async () => {
    tokens.set({ access_token: 'expired', refresh_token: 'refresh-me' })

    const fetchMock = vi
      .fn()
      // 1. the original call, rejected
      .mockResolvedValueOnce(jsonResponse({ detail: 'expired' }, 401))
      // 2. the refresh
      .mockResolvedValueOnce(
        jsonResponse({ access_token: 'fresh', refresh_token: 'refresh-2' }),
      )
      // 3. the replay
      .mockResolvedValueOnce(jsonResponse({ id: 'me' }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await request('/users/me')

    expect(result).toEqual({ id: 'me' })
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(fetchMock.mock.calls[1][0]).toContain('/auth/refresh')
    // The replay must use the new token, not the expired one.
    expect(fetchMock.mock.calls[2][1].headers.Authorization).toBe('Bearer fresh')
    expect(tokens.access).toBe('fresh')
  })

  it('does not retry forever when the refresh itself fails', async () => {
    tokens.set({ access_token: 'expired', refresh_token: 'stale' })

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: 'expired' }, 401))
      .mockResolvedValueOnce(jsonResponse({ detail: 'invalid refresh token' }, 401))
    vi.stubGlobal('fetch', fetchMock)

    await expect(request('/users/me')).rejects.toBeInstanceOf(ApiError)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    // A dead session must be cleared, or every later request retries pointlessly.
    expect(tokens.access).toBeNull()
  })

  it('does not attempt a refresh when there is no refresh token', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ detail: 'unauthorised' }, 401))
    vi.stubGlobal('fetch', fetchMock)

    await expect(request('/users/me')).rejects.toBeInstanceOf(ApiError)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})

describe('answerStream', () => {
  function streamOf(...frames) {
    const encoder = new TextEncoder()
    return new ReadableStream({
      start(controller) {
        for (const frame of frames) controller.enqueue(encoder.encode(frame))
        controller.close()
      },
    })
  }

  function sse(event, data) {
    return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`
  }

  it('reports each step and resolves with the final result', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          streamOf(
            sse('step', { node: 'record_answer', message: 'Recording your answer' }),
            sse('step', { node: 'evaluate', message: 'Grading against the rubric' }),
            sse('result', { evaluation: { score: 8 }, finished: false }),
            sse('done', {}),
          ),
          { status: 200 },
        ),
      ),
    )

    const steps = []
    const result = await api.interviews.answerStream(
      'interview-1',
      { question_id: 'q1', answer_text: 'an answer' },
      { onStep: (step) => steps.push(step.message) },
    )

    expect(steps).toEqual(['Recording your answer', 'Grading against the rubric'])
    expect(result.evaluation.score).toBe(8)
  })

  it('reassembles a frame split across two network chunks', async () => {
    // The reader gives whatever arrived, not whole SSE frames.
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          streamOf('event: result\ndata: {"evaluation":', '{"score":6},"finished":true}\n\n'),
          { status: 200 },
        ),
      ),
    )

    const result = await api.interviews.answerStream('i', { question_id: 'q' })
    expect(result).toEqual({ evaluation: { score: 6 }, finished: true })
  })

  it('raises an error event as a rejection', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(streamOf(sse('error', { detail: 'The model timed out' }), sse('done', {})), {
          status: 200,
        }),
      ),
    )

    await expect(
      api.interviews.answerStream('i', { question_id: 'q' }),
    ).rejects.toThrow('The model timed out')
  })

  it('rejects when the stream ends without a result', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(streamOf(sse('done', {})), { status: 200 })),
    )

    await expect(api.interviews.answerStream('i', { question_id: 'q' })).rejects.toThrow(
      /no result/,
    )
  })

  it('surfaces a rejected request as an ApiError before streaming', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ detail: 'Already answered' }, 409)),
    )

    await expect(
      api.interviews.answerStream('i', { question_id: 'q' }),
    ).rejects.toMatchObject({ status: 409, message: 'Already answered' })
  })
})
