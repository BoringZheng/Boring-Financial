<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Bell,
  DataAnalysis,
  Document,
  Files,
  FolderChecked,
  HomeFilled,
  Search,
  Setting,
  SwitchButton,
  Tickets,
} from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const menuItems = [
  { path: '/dashboard', label: 'Dashboard', subLabel: '仪表盘', icon: HomeFilled },
  { path: '/imports', label: 'Imports', subLabel: '导入账单', icon: Files },
  { path: '/transactions', label: 'Transactions', subLabel: '交易列表', icon: Tickets },
  { path: '/review', label: 'Review', subLabel: '分类校正', icon: FolderChecked },
  { path: '/categories', label: 'Categories', subLabel: '分类管理', icon: Document },
  { path: '/reports', label: 'Reports', subLabel: '报表中心', icon: DataAnalysis },
  { path: '/settings', label: 'Settings', subLabel: '系统设置', icon: Setting },
]

const activePath = computed(() => route.path)
const currentTitle = computed(() => menuItems.find((item) => item.path === activePath.value)?.subLabel ?? '工作台')
const userInitial = computed(() => (auth.user?.username || 'U').slice(0, 1).toUpperCase())

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
    <aside class="sidebar">
      <div class="brand-block">
        <div class="brand-mark">BF</div>
        <div>
          <div class="brand-name">Boring Financial</div>
          <div class="brand-sub">智能账单分类系统</div>
        </div>
      </div>

      <el-menu :default-active="activePath" class="side-menu" @select="handleSelect">
        <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <span class="menu-copy">
            <strong>{{ item.label }}</strong>
            <small>{{ item.subLabel }}</small>
          </span>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer">
        <div class="server-badge">
          <span class="status-dot"></span>
          生产环境轻量模式
        </div>
        <el-button :icon="SwitchButton" plain class="logout-button" @click="logout">退出登录</el-button>
      </div>
    </aside>

    <section class="workspace">
      <header class="topbar panel">
        <div>
          <div class="topbar-kicker">Boring Financial / {{ currentTitle }}</div>
          <div class="topbar-title">{{ currentTitle }}</div>
        </div>
        <div class="topbar-actions">
          <el-input class="global-search" placeholder="搜索交易、商家、分类..." :prefix-icon="Search" />
          <el-button :icon="Bell" circle />
          <div class="user-chip">
            <span class="avatar">{{ userInitial }}</span>
            <span>{{ auth.user?.username ?? '未登录' }}</span>
          </div>
        </div>
      </header>

      <main class="content">
        <RouterView />
      </main>
    </section>
  </div>
</template>

<style scoped>
.app-layout {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  background: var(--color-bg);
}

.sidebar {
  min-height: 100vh;
  padding: 18px 14px;
  background: linear-gradient(180deg, var(--color-sidebar) 0%, var(--color-sidebar-deep) 100%);
  color: #fff;
  display: flex;
  flex-direction: column;
  gap: 22px;
  position: sticky;
  top: 0;
}

.brand-block {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 8px 12px;
}

.brand-mark {
  width: 38px;
  height: 38px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  background: var(--color-primary);
  color: #fff;
  font-weight: 800;
  letter-spacing: 0.02em;
}

.brand-name {
  font-size: 15px;
  font-weight: 700;
}

.brand-sub {
  margin-top: 3px;
  color: rgba(255, 255, 255, 0.65);
  font-size: 12px;
}

.side-menu {
  flex: 1;
  border-right: 0;
  background: transparent;
}

.side-menu :deep(.el-menu-item) {
  height: 48px;
  margin: 4px 0;
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.82);
}

.side-menu :deep(.el-menu-item:hover),
.side-menu :deep(.el-menu-item.is-active) {
  background: var(--color-primary);
  color: #fff;
}

.menu-copy {
  display: grid;
  line-height: 1.2;
}

.menu-copy strong {
  font-size: 13px;
}

.menu-copy small {
  margin-top: 2px;
  color: rgba(255, 255, 255, 0.62);
  font-size: 11px;
}

.side-menu :deep(.el-menu-item.is-active .menu-copy small),
.side-menu :deep(.el-menu-item:hover .menu-copy small) {
  color: rgba(255, 255, 255, 0.78);
}

.sidebar-footer {
  display: grid;
  gap: 12px;
}

.server-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.72);
  font-size: 12px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 99px;
  background: var(--color-success);
}

.logout-button {
  width: 100%;
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.18);
  color: #fff;
}

.workspace {
  min-width: 0;
  display: grid;
  grid-template-rows: auto 1fr;
}

.topbar {
  height: 72px;
  margin: 16px 18px 0;
  padding: 0 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.topbar-kicker {
  color: var(--color-muted);
  font-size: 12px;
}

.topbar-title {
  margin-top: 4px;
  font-size: 18px;
  font-weight: 700;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.global-search {
  width: 280px;
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px 6px 6px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: #fff;
  color: var(--color-text);
}

.avatar {
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  border-radius: 999px;
  background: #e6f7f3;
  color: var(--color-primary);
  font-weight: 700;
}

.content {
  padding: 18px;
  min-width: 0;
}

@media (max-width: 980px) {
  .app-layout {
    grid-template-columns: 1fr;
  }

  .sidebar {
    min-height: auto;
    position: static;
    padding: 12px;
  }

  .side-menu {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 4px;
  }

  .side-menu :deep(.el-menu-item) {
    margin: 0;
    padding: 0 10px;
  }

  .sidebar-footer {
    display: none;
  }

  .topbar {
    margin: 12px 12px 0;
  }

  .global-search {
    display: none;
  }

  .content {
    padding: 12px;
  }
}

@media (max-width: 640px) {
  .side-menu {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .topbar {
    height: auto;
    padding: 14px;
    align-items: flex-start;
    flex-direction: column;
  }

  .topbar-actions {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
