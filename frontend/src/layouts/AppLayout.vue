<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const menuItems = [
  { path: '/dashboard', label: '总览' },
  { path: '/imports', label: '账单导入' },
  { path: '/transactions', label: '交易列表' },
  { path: '/review', label: '分类校正' },
  { path: '/categories', label: '分类管理' },
  { path: '/reports', label: '报表中心' },
]

const activePath = computed(() => route.path)

function handleSelect(path: string) {
  router.push(path)
}

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="app-layout">
    <aside class="sidebar panel">
      <div>
        <div class="brand">Boring Financial</div>
        <div class="brand-sub">智能账单分类系统</div>
      </div>
      <el-menu :default-active="activePath" class="menu" @select="handleSelect">
        <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
          {{ item.label }}
        </el-menu-item>
      </el-menu>
      <div class="sidebar-footer">
        <div class="user-name">{{ auth.user?.username ?? '未登录' }}</div>
        <el-button type="primary" plain @click="logout">退出</el-button>
      </div>
    </aside>
    <main class="content">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app-layout {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 20px;
  padding: 20px;
}

.sidebar {
  padding: 24px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.brand {
  font-size: 26px;
  font-weight: 700;
}

.brand-sub {
  margin-top: 6px;
  color: var(--muted);
}

.menu {
  border-right: 0;
  background: transparent;
  margin-top: 24px;
}

.content {
  padding: 12px 8px 24px;
}

.sidebar-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.user-name {
  color: var(--muted);
}

@media (max-width: 900px) {
  .app-layout {
    grid-template-columns: 1fr;
  }
}
</style>
