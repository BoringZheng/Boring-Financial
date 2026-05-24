import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { pinia } from '../stores'
import AppLayout from '../layouts/AppLayout.vue'
import LoginPage from '../pages/LoginPage.vue'
import DashboardPage from '../pages/DashboardPage.vue'
import ImportsPage from '../pages/ImportsPage.vue'
import TransactionsPage from '../pages/TransactionsPage.vue'
import ReviewPage from '../pages/ReviewPage.vue'
import CategoriesPage from '../pages/CategoriesPage.vue'
import PersonalityPage from '../pages/PersonalityPage.vue'
import ReportsPage from '../pages/ReportsPage.vue'
import SettingsPage from '../pages/SettingsPage.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginPage },
    {
      path: '/',
      component: AppLayout,
      meta: { requiresAuth: true },
      children: [
        { path: '', redirect: '/dashboard' },
        { path: 'dashboard', component: DashboardPage },
        { path: 'imports', component: ImportsPage },
        { path: 'transactions', component: TransactionsPage },
        { path: 'review', component: ReviewPage },
        { path: 'categories', component: CategoriesPage },
        { path: 'reports', component: ReportsPage },
        { path: 'personality', component: PersonalityPage },
        { path: 'settings', component: SettingsPage },
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
