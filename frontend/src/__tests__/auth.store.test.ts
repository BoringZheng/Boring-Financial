/**
 * Tests for the auth Pinia store.
 *
 * Covers: token persistence, login/logout flows, isAuthenticated getter.
 */
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../stores/auth'

// Mock the api module
vi.mock('../api/client', () => {
  return {
    default: {
      post: vi.fn(),
      get: vi.fn(),
    },
  }
})

import api from '../api/client'

describe('useAuthStore', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('initializes with null state when localStorage is empty', () => {
    const auth = useAuthStore()
    expect(auth.user).toBeNull()
    expect(auth.accessToken).toBeNull()
    expect(auth.refreshToken).toBeNull()
    expect(auth.isAuthenticated).toBe(false)
  })

  it('initializes accessToken from localStorage', () => {
    localStorage.setItem('bf_access_token', 'stored-token')
    localStorage.setItem('bf_refresh_token', 'stored-refresh')
    setActivePinia(createPinia())

    const auth = useAuthStore()
    expect(auth.accessToken).toBe('stored-token')
    expect(auth.refreshToken).toBe('stored-refresh')
    expect(auth.isAuthenticated).toBe(true)
  })

  it('applyTokenPair stores user and tokens in state and localStorage', () => {
    const auth = useAuthStore()
    const tokenPair = {
      access_token: 'new-access',
      refresh_token: 'new-refresh',
      token_type: 'bearer',
      user: { id: 1, username: 'alice', email: null, is_active: true, is_admin: false },
    }

    auth.applyTokenPair(tokenPair)

    expect(auth.user).toEqual(tokenPair.user)
    expect(auth.accessToken).toBe('new-access')
    expect(auth.refreshToken).toBe('new-refresh')
    expect(auth.isAuthenticated).toBe(true)
    expect(localStorage.getItem('bf_access_token')).toBe('new-access')
    expect(localStorage.getItem('bf_refresh_token')).toBe('new-refresh')
  })

  it('logout clears state and localStorage', () => {
    const auth = useAuthStore()
    // Set up authenticated state
    auth.applyTokenPair({
      access_token: 'x',
      refresh_token: 'y',
      token_type: 'bearer',
      user: { id: 1, username: 'alice', email: null, is_active: true, is_admin: false },
    })

    auth.logout()

    expect(auth.user).toBeNull()
    expect(auth.accessToken).toBeNull()
    expect(auth.refreshToken).toBeNull()
    expect(auth.isAuthenticated).toBe(false)
    expect(localStorage.getItem('bf_access_token')).toBeNull()
    expect(localStorage.getItem('bf_refresh_token')).toBeNull()
  })

  it('login calls API and applies token pair', async () => {
    const auth = useAuthStore()
    const mockResponse = {
      data: {
        access_token: 'login-token',
        refresh_token: 'login-refresh',
        token_type: 'bearer',
        user: { id: 2, username: 'bob', email: 'bob@test.com', is_active: true, is_admin: false },
      },
    }
    vi.mocked(api.post).mockResolvedValue(mockResponse)

    await auth.login('bob', 'password123')

    expect(api.post).toHaveBeenCalledWith('/auth/login', { username: 'bob', password: 'password123' })
    expect(auth.user?.username).toBe('bob')
    expect(auth.accessToken).toBe('login-token')
  })

  it('register calls API and applies token pair', async () => {
    const auth = useAuthStore()
    const mockResponse = {
      data: {
        access_token: 'reg-token',
        refresh_token: 'reg-refresh',
        token_type: 'bearer',
        user: { id: 3, username: 'carol', email: 'carol@test.com', is_active: true, is_admin: false },
      },
    }
    vi.mocked(api.post).mockResolvedValue(mockResponse)

    await auth.register('carol', 'pass', 'carol@test.com')

    expect(api.post).toHaveBeenCalledWith('/auth/register', {
      username: 'carol',
      password: 'pass',
      email: 'carol@test.com',
    })
    expect(auth.user?.username).toBe('carol')
  })

  it('fetchMe does nothing if no access token', async () => {
    const auth = useAuthStore()
    await auth.fetchMe()
    expect(api.get).not.toHaveBeenCalled()
  })

  it('fetchMe fetches user when access token exists', async () => {
    localStorage.setItem('bf_access_token', 'existing-token')
    setActivePinia(createPinia())
    const auth = useAuthStore()

    const mockUser = { id: 1, username: 'alice', email: null, is_active: true, is_admin: true }
    vi.mocked(api.get).mockResolvedValue({ data: mockUser })

    await auth.fetchMe()

    expect(api.get).toHaveBeenCalledWith('/auth/me')
    expect(auth.user).toEqual(mockUser)
  })
})
