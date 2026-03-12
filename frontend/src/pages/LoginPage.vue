<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const isRegister = ref(false)
const form = reactive({ username: '', password: '', email: '' })

async function submit() {
  loading.value = true
  try {
    if (isRegister.value) {
      await auth.register(form.username, form.password, form.email || null)
    } else {
      await auth.login(form.username, form.password)
    }
    router.push('/dashboard')
  } catch (error) {
    ElMessage.error('登录或注册失败，请检查后端服务与输入信息')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-card panel">
      <p class="eyebrow">Software Engineering Project</p>
      <h1>智能账单分类系统</h1>
      <p class="desc">支持微信/支付宝账单导入、规则+LLM 混合分类、人工校正与 PDF 报表。</p>
      <el-form label-position="top" class="auth-form">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="输入用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" show-password placeholder="输入密码" />
        </el-form-item>
        <el-form-item v-if="isRegister" label="邮箱">
          <el-input v-model="form.email" placeholder="可选" />
        </el-form-item>
        <el-button type="primary" size="large" :loading="loading" class="submit" @click="submit">
          {{ isRegister ? '注册并进入系统' : '登录系统' }}
        </el-button>
        <el-button text class="switch" @click="isRegister = !isRegister">
          {{ isRegister ? '已有账号，去登录' : '没有账号，先注册' }}
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
}

.auth-card {
  width: min(520px, 100%);
  padding: 36px;
}

.eyebrow {
  margin: 0;
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 12px;
}

h1 {
  margin: 12px 0;
  font-size: 36px;
}

.desc {
  margin: 0 0 24px;
  color: var(--muted);
}

.submit,
.switch {
  width: 100%;
}
</style>
