import { ref, computed } from 'vue'
import api from '../api/client'

export type RequeueProgress = {
  current: number
  total: number
  done: boolean
}

export function useRetryProgress() {
  const requeueProgress = ref<RequeueProgress | null>(null)
  const requeueRunning = ref(false)

  async function startRequeue() {
    requeueRunning.value = true
    requeueProgress.value = { current: 0, total: 0, done: false }

    try {
      const baseURL = api.defaults.baseURL || '/api'
      const response = await fetch(baseURL + '/classification/retry-all-stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('bf_access_token')}`,
        },
        body: JSON.stringify({}),
      })

      if (!response.ok || !response.body) {
        throw new Error('SSE connection failed')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6))
            if (data.done) {
              requeueProgress.value = { current: data.queued, total: data.queued, done: true }
            } else {
              requeueProgress.value = { current: data.current, total: data.total, done: false }
            }
          }
        }
      }
    } catch (err) {
      console.error('Requeue stream error:', err)
    } finally {
      requeueRunning.value = false
    }
  }

  const requeuePercent = computed(() => {
    if (!requeueProgress.value || requeueProgress.value.total === 0) return 0
    return Math.round((requeueProgress.value.current / requeueProgress.value.total) * 100)
  })

  return {
    requeueProgress,
    requeueRunning,
    requeuePercent,
    startRequeue,
  }
}
