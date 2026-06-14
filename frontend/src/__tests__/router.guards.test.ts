/**
 * Tests for the Vue Router navigation guards.
 *
 * Covers: redirect unauthenticated to login, redirect authenticated away from login,
 *         fetchMe on first navigation with stored token.
 */
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { createRouter, createWebHistory, type RouteLocationNormalized } from 'vue-router'
import { setActivePinia, createPinia } from 'pinia'
import { defineComponent } from 'vue'
import { useAuthStore } from '../stores/auth'

// Mock the api module
vi.mock('../api/client', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

import api from '../api/client'

const EmptyComponent = defineComponent({ template: '<div />' })

function createTestRouter() {
  const pinia = createPinia()
  setActivePinia(pinia)

  const router = createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/login', component: EmptyComponent },
      {
        path: '/',
        component: EmptyComponent,
        meta: { requiresAuth: true },
        children: [
          { path: '', redirect: '/dashboard' },
          { path: 'dashboard', component: EmptyComponent },
          { path: 'settings', component: EmptyComponent },
        ],
      },
    ],
  })

  // Replicate the beforeEach guard from src/router/index.ts
  router.beforeEach(async (to) => {
    const auth = useAuthStore(pinia)
    if (auth.accessToken && !auth.user) {
      try {
        await auth.fetchMe()
      } catch {
        auth.logout()
      }
    }
    if (to.meta.requiresAuth && !auth.isAuthenticated) {
      return '/login'
    }
    if (to.path === '/login' && auth.isAuthenticated) {
      return '/dashboard'
    }
    return true
  })

  return { router, pinia }
}

describe('Router Guards', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('redirects unauthenticated user to /login when accessing protected route', async () => {
    const { router } = createTestRouter()

    await router.push('/dashboard')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('allows authenticated user to access protected routes', async () => {
    localStorage.setItem('bf_access_token', 'valid-token')
    vi.mocked(api.get).mockResolvedValue({
      data: { id: 1, username: 'alice', email: null, is_active: true, is_admin: false },
    })

    const { router } = createTestRouter()

    await router.push('/dashboard')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('redirects authenticated user away from /login to /dashboard', async () => {
    localStorage.setItem('bf_access_token', 'valid-token')
    vi.mocked(api.get).mockResolvedValue({
      data: { id: 1, username: 'alice', email: null, is_active: true, is_admin: false },
    })

    const { router } = createTestRouter()

    await router.push('/login')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('calls fetchMe when token exists but user is not loaded', async () => {
    localStorage.setItem('bf_access_token', 'stored-token')
    vi.mocked(api.get).mockResolvedValue({
      data: { id: 1, username: 'alice', email: null, is_active: true, is_admin: false },
    })

    const { router } = createTestRouter()

    await router.push('/dashboard')
    await router.isReady()

    expect(api.get).toHaveBeenCalledWith('/auth/me')
  })

  it('logs out and redirects to /login if fetchMe fails', async () => {
    localStorage.setItem('bf_access_token', 'expired-token')
    vi.mocked(api.get).mockRejectedValue(new Error('401 Unauthorized'))

    const { router } = createTestRouter()

    await router.push('/dashboard')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/login')
    expect(localStorage.getItem('bf_access_token')).toBeNull()
  })

  it('does not call fetchMe if user is already loaded', async () => {
    localStorage.setItem('bf_access_token', 'valid-token')

    const { router, pinia } = createTestRouter()
    const auth = useAuthStore(pinia)
    // Pre-set user (simulates already loaded)
    auth.user = { id: 1, username: 'alice', email: null, is_active: true, is_admin: false }

    // Clear any prior mock calls before the navigation we care about
    vi.mocked(api.get).mockClear()

    await router.push('/settings')
    await router.isReady()

    // fetchMe should not have been called since user already exists
    expect(api.get).not.toHaveBeenCalled()
    expect(router.currentRoute.value.path).toBe('/settings')
  })
})
