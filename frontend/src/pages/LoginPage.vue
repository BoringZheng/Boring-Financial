<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { isAxiosError } from 'axios'
import { Lock, Message, User } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const isRegister = ref(false)
const rememberMe = ref(true)
const form = reactive({ username: '', password: '', email: '' })

function readableError(error: unknown) {
  if (isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (detail === 'username already exists') {
      return '用户名已存在，请换一个用户名，或切换到登录。'
    }
    if (detail === 'invalid credentials') {
      return '用户名或密码不正确。'
    }
    if (Array.isArray(detail)) {
      return '输入不符合要求：用户名至少 3 位，密码至少 6 位，邮箱格式需正确。'
    }
    if (typeof detail === 'string' && detail.trim()) {
      return detail
    }
  }
  return '登录或注册失败，请检查账号信息与后端服务状态。'
}

async function submit() {
  loading.value = true
  try {
    const username = form.username.trim()
    const password = form.password
    const email = form.email.trim() || null
    if (isRegister.value) {
      await auth.register(username, password, email)
    } else {
      await auth.login(username, password)
    }
    router.push('/dashboard')
  } catch (error) {
    ElMessage.error(readableError(error))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <section class="brand-panel">
      <div class="brand-logo">BF</div>
      <h1>Boring Financial</h1>
      <p class="brand-subtitle">智能账单分类系统</p>
      <p class="brand-desc">让每一笔收支都有清晰归因，支持微信/支付宝账单导入、AI 分类、人工校正与 PDF 报表。</p>
      <div class="visual-card">
        <div class="chart-window">
          <span></span>
          <span></span>
          <span></span>
          <span></span>
        </div>
        <div class="visual-list">
          <div></div>
          <div></div>
          <div></div>
        </div>
      </div>
    </section>

    <section class="auth-card panel">
      <div class="auth-tabs">
        <button :class="{ active: !isRegister }" type="button" @click="isRegister = false">登录</button>
        <button :class="{ active: isRegister }" type="button" @click="isRegister = true">注册</button>
      </div>

      <el-form label-position="top" class="auth-form" @submit.prevent>
        <el-form-item label="用户名">
          <el-input
            v-model="form.username"
            :prefix-icon="User"
            placeholder="请输入用户名"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            :prefix-icon="Lock"
            show-password
            placeholder="请输入密码"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-form-item v-if="isRegister" label="邮箱">
          <el-input
            v-model="form.email"
            :prefix-icon="Message"
            placeholder="可选，用于课程演示账号标识"
            @keyup.enter="submit"
          />
        </el-form-item>

        <div class="form-options">
          <el-checkbox v-model="rememberMe">记住我</el-checkbox>
          <el-button text type="primary">忘记密码？</el-button>
        </div>

        <el-button type="primary" size="large" :loading="loading" class="submit" @click="submit">
          {{ isRegister ? '注册并进入系统' : '登录' }}
        </el-button>

        <p class="legal-copy">登录即表示同意课程演示环境的使用约定，数据仅用于本地项目展示。</p>
      </el-form>
    </section>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(360px, 1fr) minmax(360px, 560px);
  padding: 28px;
  background:
    radial-gradient(circle at 18% 24%, rgba(0, 168, 132, 0.24), transparent 28%),
    linear-gradient(135deg, #041a2e 0%, #06233d 48%, #f5f7fa 48%, #f5f7fa 100%);
}

.brand-panel {
  min-height: calc(100vh - 56px);
  padding: 72px 56px;
  color: #fff;
  display: flex;
  flex-direction: column;
  justify-content: center;
  overflow: hidden;
}

.brand-logo {
  width: 64px;
  height: 64px;
  display: grid;
  place-items: center;
  border-radius: 16px;
  border: 2px solid rgba(255, 255, 255, 0.28);
  background: rgba(0, 168, 132, 0.18);
  color: #fff;
  font-size: 22px;
  font-weight: 800;
  box-shadow: 0 20px 60px rgba(0, 168, 132, 0.22);
}

.brand-panel h1 {
  margin: 28px 0 8px;
  font-size: 42px;
  line-height: 1;
  font-weight: 800;
}

.brand-subtitle {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.brand-desc {
  max-width: 460px;
  margin: 18px 0 0;
  color: rgba(255, 255, 255, 0.72);
  line-height: 1.8;
}

.visual-card {
  width: min(420px, 100%);
  margin-top: 48px;
  padding: 24px;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.08);
  box-shadow: 0 30px 80px rgba(0, 0, 0, 0.18);
}

.chart-window {
  height: 170px;
  display: flex;
  align-items: flex-end;
  gap: 18px;
  padding: 24px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.12);
}

.chart-window span {
  flex: 1;
  border-radius: 8px 8px 0 0;
  background: linear-gradient(180deg, #37e2bd 0%, #00a884 100%);
}

.chart-window span:nth-child(1) {
  height: 45%;
}

.chart-window span:nth-child(2) {
  height: 70%;
}

.chart-window span:nth-child(3) {
  height: 56%;
}

.chart-window span:nth-child(4) {
  height: 86%;
}

.visual-list {
  display: grid;
  gap: 10px;
  margin-top: 18px;
}

.visual-list div {
  height: 12px;
  border-radius: 99px;
  background: rgba(255, 255, 255, 0.18);
}

.visual-list div:nth-child(2) {
  width: 76%;
}

.visual-list div:nth-child(3) {
  width: 58%;
}

.auth-card {
  align-self: center;
  width: min(100%, 460px);
  margin: 0 auto;
  padding: 34px;
}

.auth-tabs {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  padding: 4px;
  margin-bottom: 26px;
  border-radius: 8px;
  background: #f1f5f9;
}

.auth-tabs button {
  height: 42px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--color-muted);
  cursor: pointer;
  font-weight: 600;
}

.auth-tabs button.active {
  background: #fff;
  color: var(--color-primary);
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08);
}

.auth-form {
  display: grid;
}

.form-options {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}

.submit {
  width: 100%;
}

.legal-copy {
  margin: 18px 0 0;
  color: var(--color-muted);
  font-size: 12px;
  line-height: 1.6;
  text-align: center;
}

@media (max-width: 900px) {
  .auth-page {
    grid-template-columns: 1fr;
    background: var(--color-bg);
    padding: 16px;
  }

  .brand-panel {
    min-height: auto;
    padding: 28px 20px;
    border-radius: 12px;
    background: linear-gradient(135deg, #041a2e, #06233d);
  }

  .visual-card {
    display: none;
  }

  .auth-card {
    margin-top: 16px;
    padding: 24px;
  }
}
</style>
