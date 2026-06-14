/**
 * Tests for the useRetryProgress composable.
 *
 * Covers: SSE stream parsing, percentage calculation, error handling.
 */
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { useRetryProgress } from '../composables/useRetryProgress'

// Mock the api module
vi.mock('../api/client', () => ({
  default: {
    defaults: { baseURL: '/api' },
    post: vi.fn(),
    get: vi.fn(),
  },
}))

function createMockResponse(chunks: string[]) {
  let index = 0
  const encoder = new TextEncoder()

  const stream = new ReadableStream({
    pull(controller) {
      if (index < chunks.length) {
        controller.enqueue(encoder.encode(chunks[index]))
        index++
      } else {
        controller.close()
      }
    },
  })

  return {
    ok: true,
    body: stream,
  } as unknown as Response
}

describe('useRetryProgress', () => {
  beforeEach(() => {
    localStorage.clear()
    localStorage.setItem('bf_access_token', 'test-token')
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('requeuePercent is 0 when no progress', () => {
    const { requeuePercent, requeueProgress } = useRetryProgress()
    expect(requeuePercent.value).toBe(0)
    expect(requeueProgress.value).toBeNull()
  })

  it('requeuePercent computes correctly from progress', () => {
    const { requeuePercent, requeueProgress } = useRetryProgress()
    requeueProgress.value = { current: 3, total: 10, done: false }
    expect(requeuePercent.value).toBe(30)
  })

  it('requeuePercent is 0 when total is 0', () => {
    const { requeuePercent, requeueProgress } = useRetryProgress()
    requeueProgress.value = { current: 0, total: 0, done: false }
    expect(requeuePercent.value).toBe(0)
  })

  it('requeuePercent rounds to nearest integer', () => {
    const { requeuePercent, requeueProgress } = useRetryProgress()
    requeueProgress.value = { current: 1, total: 3, done: false }
    expect(requeuePercent.value).toBe(33)
  })

  it('startRequeue processes SSE stream events correctly', async () => {
    const mockResponse = createMockResponse([
      'data: {"current": 1, "total": 5}\n\n',
      'data: {"current": 3, "total": 5}\n\n',
      'data: {"done": true, "queued": 5}\n\n',
    ])
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockResponse))

    const { startRequeue, requeueProgress, requeueRunning } = useRetryProgress()

    await startRequeue()

    // After completion
    expect(requeueRunning.value).toBe(false)
    expect(requeueProgress.value?.done).toBe(true)
  })

  it('startRequeue handles failed fetch gracefully', async () => {
    const mockResponse = { ok: false, body: null } as unknown as Response
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockResponse))

    const { startRequeue, requeueRunning } = useRetryProgress()
    await startRequeue()

    expect(requeueRunning.value).toBe(false)
  })

  it('startRequeue sends correct authorization header', async () => {
    localStorage.setItem('bf_access_token', 'my-secret-token')
    const mockResponse = createMockResponse([])
    const fetchMock = vi.fn().mockResolvedValue(mockResponse)
    vi.stubGlobal('fetch', fetchMock)

    const { startRequeue } = useRetryProgress()
    await startRequeue()

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/classification/retry-all-stream',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer my-secret-token',
        }),
      }),
    )
  })

  it('startRequeue handles multi-chunk split lines', async () => {
    // Simulate a line split across two chunks
    const mockResponse = createMockResponse([
      'data: {"curre',
      'nt": 2, "total": 4}\n\ndata: {"done": true, "queued": 4}\n\n',
    ])
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockResponse))

    const { startRequeue, requeueProgress } = useRetryProgress()
    await startRequeue()

    expect(requeueProgress.value?.done).toBe(true)
  })
})
