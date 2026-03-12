import { defineStore } from 'pinia'
import api from '../api/client'
import type { TokenPair, User } from '../types/models'

interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    user: null,
    accessToken: localStorage.getItem('bf_access_token'),
    refreshToken: localStorage.getItem('bf_refresh_token'),
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.accessToken),
  },
  actions: {
    applyTokenPair(payload: TokenPair) {
      this.user = payload.user
      this.accessToken = payload.access_token
      this.refreshToken = payload.refresh_token
      localStorage.setItem('bf_access_token', payload.access_token)
      localStorage.setItem('bf_refresh_token', payload.refresh_token)
    },
    async login(username: string, password: string) {
      const { data } = await api.post<TokenPair>('/auth/login', { username, password })
      this.applyTokenPair(data)
    },
    async register(username: string, password: string, email: string | null) {
      const { data } = await api.post<TokenPair>('/auth/register', { username, password, email })
      this.applyTokenPair(data)
    },
    async fetchMe() {
      if (!this.accessToken) return
      const { data } = await api.get<User>('/auth/me')
      this.user = data
    },
    logout() {
      this.user = null
      this.accessToken = null
      this.refreshToken = null
      localStorage.removeItem('bf_access_token')
      localStorage.removeItem('bf_refresh_token')
    },
  },
})
