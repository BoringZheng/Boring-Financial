import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { pinia } from '../stores'
import AppLayout from '../layouts/AppLayout.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: () => import('../pages/LoginPage.vue') },
    {
      path: '/',
      component: AppLayout,
      meta: { requiresAuth: true },
      children: [
        { path: '', redirect: '/dashboard' },
        { path: 'dashboard', component: () => import('../pages/DashboardPage.vue') },
        { path: 'imports', component: () => import('../pages/ImportsPage.vue') },
        { path: 'transactions', component: () => import('../pages/TransactionsPage.vue') },
        { path: 'review', component: () => import('../pages/ReviewPage.vue') },
        { path: 'categories', component: () => import('../pages/CategoriesPage.vue') },
        { path: 'reports', component: () => import('../pages/ReportsPage.vue') },
        { path: 'personality', component: () => import('../pages/PersonalityPage.vue') },
        { path: 'organization', component: () => import('../pages/OrganizationPage.vue') },
        { path: 'settings', component: () => import('../pages/SettingsPage.vue') },
      ],
    },
  ],
})

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

export default router
