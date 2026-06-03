import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('bf_access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export default api

// --- Organization APIs ---

import type { Organization, OrganizationMember } from '../types/models'

export function fetchOrganizations() {
  return api.get<Organization[]>('/organizations')
}

export function createOrganization(payload: { name: string }) {
  return api.post<Organization>('/organizations', payload)
}

export function updateOrganization(id: number, payload: { name?: string; plan?: string | null; subscription_status?: string | null }) {
  return api.patch<Organization>(`/organizations/${id}`, payload)
}

export function fetchOrganizationMembers(orgId: number) {
  return api.get<OrganizationMember[]>(`/organizations/${orgId}/members`)
}

export function addOrganizationMember(orgId: number, payload: { username: string }) {
  return api.post<OrganizationMember>(`/organizations/${orgId}/members`, payload)
}

export function updateMemberRole(orgId: number, userId: number, payload: { role: 'admin' | 'member' }) {
  return api.patch<OrganizationMember>(`/organizations/${orgId}/members/${userId}`, payload)
}

export function removeOrganizationMember(orgId: number, userId: number) {
  return api.delete(`/organizations/${orgId}/members/${userId}`)
}

export function fetchFamilyDashboard(orgId: number, params?: Record<string, any>) {
  return api.get('/dashboard/summary', { params: { ...params, organization_id: orgId } })
}

export function fetchFamilyPersonality(orgId: number) {
  return api.get('/personality/profile', { params: { organization_id: orgId } })
}

export function orgRetryAll(orgId: number) {
  return api.post<{ queued: number }>(`/classification/organizations/${orgId}/retry-all`, {})
}

export function orgReclassify(orgId: number, transactionIds: number[], provider?: string) {
  return api.post(`/classification/organizations/${orgId}/reclassify`, {
    transaction_ids: transactionIds,
    provider: provider || null,
  })
}
