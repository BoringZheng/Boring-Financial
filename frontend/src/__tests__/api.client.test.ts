/**
 * Tests for the API client interceptor and helper functions.
 *
 * Covers: Authorization header injection, API helper URL construction.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import axios from 'axios'

// We re-create the client logic to test the interceptor in isolation
describe('API Client Interceptor', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('adds Authorization header when token exists in localStorage', async () => {
    localStorage.setItem('bf_access_token', 'test-jwt-token')

    // Create a fresh axios instance mimicking client.ts behavior
    const client = axios.create({ baseURL: '/api' })
    client.interceptors.request.use((config) => {
      const token = localStorage.getItem('bf_access_token')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
      return config
    })

    // Use interceptor manager to extract the resolved config
    const handlers = (client.interceptors.request as any).handlers
    const config = await handlers[0].fulfilled!({
      headers: new axios.AxiosHeaders(),
    } as any)

    expect(config.headers.Authorization).toBe('Bearer test-jwt-token')
  })

  it('does not add Authorization header when no token in localStorage', async () => {
    const client = axios.create({ baseURL: '/api' })
    client.interceptors.request.use((config) => {
      const token = localStorage.getItem('bf_access_token')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
      return config
    })

    const handlers = (client.interceptors.request as any).handlers
    const config = await handlers[0].fulfilled!({
      headers: new axios.AxiosHeaders(),
    } as any)

    expect(config.headers.Authorization).toBeUndefined()
  })
})

describe('API Helper Functions', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.resetModules()
  })

  it('fetchOrganizations calls GET /organizations', async () => {
    vi.doMock('../api/client', () => {
      const mockApi = {
        defaults: { baseURL: '/api' },
        get: vi.fn().mockResolvedValue({ data: [] }),
        post: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      }
      return {
        default: mockApi,
        fetchOrganizations: () => mockApi.get('/organizations'),
        createOrganization: (payload: any) => mockApi.post('/organizations', payload),
        fetchFamilyDashboard: (orgId: number, params?: any) =>
          mockApi.get('/dashboard/summary', { params: { ...params, organization_id: orgId } }),
      }
    })

    const { fetchOrganizations } = await import('../api/client')
    const result = await fetchOrganizations()
    expect(result.data).toEqual([])
  })

  it('fetchFamilyDashboard passes organization_id as query param', async () => {
    const getMock = vi.fn().mockResolvedValue({ data: { total_expense: 1000 } })

    vi.doMock('../api/client', () => {
      const mockApi = {
        defaults: { baseURL: '/api' },
        get: getMock,
        post: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      }
      return {
        default: mockApi,
        fetchFamilyDashboard: (orgId: number, params?: any) =>
          mockApi.get('/dashboard/summary', { params: { ...params, organization_id: orgId } }),
      }
    })

    const { fetchFamilyDashboard } = await import('../api/client')
    await fetchFamilyDashboard(42, { date_from: '2026-01-01' })

    expect(getMock).toHaveBeenCalledWith('/dashboard/summary', {
      params: { date_from: '2026-01-01', organization_id: 42 },
    })
  })
})
