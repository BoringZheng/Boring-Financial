<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api/client'
import { useAuthStore } from '../stores/auth'
import { useRetryProgress } from '../composables/useRetryProgress'

const settingsForm = reactive({
  provider: 'composite',
  lowConfidenceThreshold: 0.75,
  openaiModel: 'gpt-4.1-mini',
  localModel: 'Qwen2.5-7B-Instruct',
})

const settingsLoading = ref(false)
const settingsSaving = ref(false)

const thresholdText = computed(() => `${Math.round(settingsForm.lowConfidenceThreshold * 100)}%`)
const auth = useAuthStore()
const { requeueProgress, requeueRunning, requeuePercent, startRequeue } = useRetryProgress()
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
  batch_total: number
  batch_completed: number
  batch_failed: number
  batch_pending: number
  batch_ts: string | null
}

async function loadSettings() {
  settingsLoading.value = true
  try {
    const { data } = await api.get<{
      provider: string
      low_confidence_threshold: number
      openai_model: string
      local_model: string
    }>('/settings')
    settingsForm.provider = data.provider
    settingsForm.lowConfidenceThreshold = data.low_confidence_threshold
    settingsForm.openaiModel = data.openai_model
    settingsForm.localModel = data.local_model
  } catch {
    // Use defaults on failure
  } finally {
    settingsLoading.value = false
  }
}

async function saveSettings() {
  settingsSaving.value = true
  try {
    await api.put('/settings', {
      provider: settingsForm.provider,
      low_confidence_threshold: settingsForm.lowConfidenceThreshold,
      openai_model: settingsForm.openaiModel,
      local_model: settingsForm.localModel,
    })
    ElMessage.success('设置已保存')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    settingsSaving.value = false
  }
}

const workerPercent = computed(() => {
  if (!retryStatus.value || retryStatus.value.batch_total === 0) return 0
  return Math.round(
    ((retryStatus.value.batch_completed + retryStatus.value.batch_failed) / retryStatus.value.batch_total) * 100
  )
})

const workerActive = computed(() => {
  return retryStatus.value != null && retryStatus.value.batch_pending > 0
})

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

async function handleRetryAll() {
  await startRequeue()
  await loadRetryStatus(true)
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
  loadSettings()
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
        <p>分类策略与模型配置面板，设置将自动保存至服务器。</p>
      </div>
    </div>

    <section class="settings-grid">
      <div class="panel card settings-main" v-loading="settingsLoading">
        <div class="section-title">
          <h2>分类策略</h2>
          <span>选择分类供应商并调整置信度阈值</span>
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
          <el-form-item>
            <el-button type="primary" :loading="settingsSaving" @click="saveSettings">保存设置</el-button>
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
          <!-- Requeue action + progress -->
          <div class="retry-action-area">
            <el-button type="primary" :loading="requeueRunning" :disabled="requeueRunning" @click="handleRetryAll">
              一键重试历史超时
            </el-button>
            <div v-if="requeueRunning || (requeueProgress && !requeueProgress.done)" class="progress-section">
              <span class="progress-label">放回进度：{{ requeueProgress?.current ?? 0 }} / {{ requeueProgress?.total ?? 0 }}</span>
              <el-progress :percentage="requeuePercent" :stroke-width="14" :show-text="false" status="success" />
            </div>
          </div>

          <!-- Worker processing progress -->
          <div v-if="retryStatus && retryStatus.batch_total > 0" class="worker-progress-section">
            <div class="progress-header">
              <strong>Worker 处理进度</strong>
              <span class="progress-label">
                {{ retryStatus.batch_completed }} 成功 / {{ retryStatus.batch_failed }} 失败 / {{ retryStatus.batch_pending }} 等待
              </span>
            </div>
            <el-progress
              :percentage="workerPercent"
              :stroke-width="14"
              :color="workerActive ? '#409EFF' : '#67C23A'"
            />
          </div>
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
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.settings-main {
  flex: 1;
  max-width: 820px;
  min-width: 0;
}

.settings-side {
  width: 340px;
  flex-shrink: 0;
}

.settings-main :deep(.el-segmented) {
  max-width: 100%;
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

.retry-action-area {
  display: grid;
  gap: 10px;
}

.progress-section,
.worker-progress-section {
  display: grid;
  gap: 6px;
}

.progress-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.progress-label {
  font-size: 12px;
  color: var(--color-muted);
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
