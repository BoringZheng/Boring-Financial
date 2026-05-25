<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api/client'
import { useAuthStore } from '../stores/auth'

const settingsForm = reactive({
  provider: 'composite',
  lowConfidenceThreshold: 0.75,
  openaiModel: 'gpt-4.1-mini',
  localModel: 'Qwen2.5-7B-Instruct',
})

const thresholdText = computed(() => `${Math.round(settingsForm.lowConfidenceThreshold * 100)}%`)
const auth = useAuthStore()
const retryingAll = ref(false)
const retryStatusLoading = ref(false)
const retryStatus = ref<RetryQueueStatus | null>(null)
let retryStatusTimer: number | undefined

type RetryQueueStatus = {
  queued: number
  failed: number
  total: number
  max_retries: number
  delay_seconds: number
  poll_seconds: number
  oldest_queued_at: string | null
  oldest_failed_at: string | null
  newest_activity_at: string | null
  providers: Array<{ provider: string; queued: number; failed: number }>
  retry_counts: Array<{ retry_count: number; queued: number }>
}

function formatStatusTime(value: string | null) {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

async function loadRetryStatus(silent = false) {
  if (!auth.user?.is_admin) return
  if (!silent) retryStatusLoading.value = true
  try {
    const { data } = await api.get<RetryQueueStatus>('/classification/retry-status')
    retryStatus.value = data
  } catch {
    if (!silent) ElMessage.error('重试池状态加载失败')
  } finally {
    if (!silent) retryStatusLoading.value = false
  }
}

async function retryAllTimeouts() {
  retryingAll.value = true
  try {
    const { data } = await api.post<{ queued: number }>('/classification/retry-all', {})
    ElMessage.success(`已放回重试池 ${data.queued} 笔`)
    await loadRetryStatus(true)
  } catch {
    ElMessage.error('重试池操作失败，请确认当前账号有管理员权限')
  } finally {
    retryingAll.value = false
  }
}

function startRetryStatusPolling() {
  if (!auth.user?.is_admin || retryStatusTimer !== undefined) return
  loadRetryStatus()
  retryStatusTimer = window.setInterval(() => loadRetryStatus(true), 5000)
}

function stopRetryStatusPolling() {
  if (retryStatusTimer !== undefined) {
    window.clearInterval(retryStatusTimer)
    retryStatusTimer = undefined
  }
}

watch(
  () => auth.user?.is_admin,
  (isAdmin) => {
    if (isAdmin) {
      startRetryStatusPolling()
    } else {
      stopRetryStatusPolling()
      retryStatus.value = null
    }
  },
)

onMounted(() => {
  startRetryStatusPolling()
})

onUnmounted(() => {
  stopRetryStatusPolling()
})
</script>

<template>
  <div class="page-shell">
    <div class="page-heading">
      <div>
        <h1>系统设置</h1>
        <p>用于课程演示的分类策略与模型配置面板。本阶段仅保留前端状态，不伪造后端保存。</p>
      </div>
    </div>

    <section class="settings-grid">
      <div class="panel card settings-main">
        <div class="section-title">
          <h2>分类策略</h2>
          <span>影响 demo 中的重分类展示口径</span>
        </div>
        <el-form label-position="top">
          <el-form-item label="分类策略">
            <el-segmented
              v-model="settingsForm.provider"
              :options="[
                { label: '混合分类', value: 'composite' },
                { label: '外部模型', value: 'openai_compatible_api' },
                { label: '本地模型', value: 'local_model' },
                { label: '规则优先', value: 'rule' },
              ]"
            />
          </el-form-item>
          <el-form-item :label="`低置信度阈值：${thresholdText}`">
            <el-slider v-model="settingsForm.lowConfidenceThreshold" :min="0.1" :max="1" :step="0.05" />
          </el-form-item>
          <el-form-item label="外部模型">
            <el-input v-model="settingsForm.openaiModel" />
          </el-form-item>
          <el-form-item label="本地模型">
            <el-input v-model="settingsForm.localModel" />
          </el-form-item>
        </el-form>
      </div>

      <aside class="panel card settings-side">
        <div class="section-title">
          <h2>运行模式</h2>
          <el-tag type="success">轻量</el-tag>
        </div>
        <div v-if="auth.user?.is_admin" class="admin-actions" v-loading="retryStatusLoading">
          <div class="admin-actions-head">
            <strong>超时重试池</strong>
            <el-button text size="small" @click="loadRetryStatus()">刷新</el-button>
          </div>
          <div class="retry-stats">
            <div>
              <span>等待</span>
              <b>{{ retryStatus?.queued ?? 0 }}</b>
            </div>
            <div>
              <span>失败</span>
              <b>{{ retryStatus?.failed ?? 0 }}</b>
            </div>
            <div>
              <span>合计</span>
              <b>{{ retryStatus?.total ?? 0 }}</b>
            </div>
          </div>
          <div class="retry-meta">
            <span>最早等待：{{ formatStatusTime(retryStatus?.oldest_queued_at ?? null) }}</span>
            <span>最近变更：{{ formatStatusTime(retryStatus?.newest_activity_at ?? null) }}</span>
            <span>节流：{{ retryStatus?.delay_seconds ?? '-' }}s / 最大 {{ retryStatus?.max_retries ?? '-' }} 次</span>
          </div>
          <div v-if="retryStatus?.providers.length" class="provider-breakdown">
            <span v-for="item in retryStatus.providers" :key="item.provider">
              {{ item.provider }}：{{ item.queued }} 等待 / {{ item.failed }} 失败
            </span>
          </div>
          <el-button type="primary" :loading="retryingAll" @click="retryAllTimeouts">一键重试历史超时</el-button>
        </div>
        <div class="mode-list">
          <div>
            <strong>前端增强优先</strong>
            <span>图表、筛选和流程展示尽量复用现有 API。</span>
          </div>
          <div>
            <strong>低配服务器友好</strong>
            <span>避免高频模型调用、实时推送和大规模后台任务。</span>
          </div>
          <div>
            <strong>接口保持稳定</strong>
            <span>本轮重设计不改变后端路由、请求参数或响应结构。</span>
          </div>
        </div>
      </aside>
    </section>
  </div>
</template>

<style scoped>
.settings-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 16px;
}

.settings-main {
  max-width: 820px;
}

.settings-main :deep(.el-segmented) {
  max-width: 100%;
}

.settings-side {
  align-self: start;
}

.mode-list {
  display: grid;
  gap: 12px;
}

.admin-actions {
  display: grid;
  gap: 10px;
  padding: 14px;
  margin-bottom: 14px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: #f8fafc;
}

.admin-actions-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.retry-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.retry-stats div {
  display: grid;
  gap: 4px;
  padding: 10px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: #ffffff;
}

.retry-stats span,
.retry-meta,
.provider-breakdown {
  color: var(--color-muted);
  font-size: 12px;
}

.retry-stats b {
  font-size: 20px;
}

.retry-meta,
.provider-breakdown {
  display: grid;
  gap: 5px;
  line-height: 1.5;
}

.mode-list div {
  padding: 14px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: #f8fafc;
}

.mode-list strong,
.mode-list span {
  display: block;
}

.mode-list span {
  margin-top: 6px;
  color: var(--color-muted);
  line-height: 1.6;
  font-size: 13px;
}

@media (max-width: 960px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }

  .settings-main {
    max-width: none;
  }
}
</style>
