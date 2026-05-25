<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
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

async function retryAllTimeouts() {
  retryingAll.value = true
  try {
    const { data } = await api.post<{ queued: number }>('/classification/retry-all', {})
    ElMessage.success(`已放回重试池 ${data.queued} 笔`)
  } catch {
    ElMessage.error('重试池操作失败，请确认当前账号有管理员权限')
  } finally {
    retryingAll.value = false
  }
}
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
        <div v-if="auth.user?.is_admin" class="admin-actions">
          <strong>超时重试池</strong>
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
