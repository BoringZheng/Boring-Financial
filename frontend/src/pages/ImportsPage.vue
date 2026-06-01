<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile, UploadFiles, UploadRawFile, UploadUserFile } from 'element-plus'
import { Delete, Refresh, UploadFilled } from '@element-plus/icons-vue'
import api from '../api/client'

type ImportBatch = {
  id: number
  user_id: number
  status: string
  source_count: number
  total_count: number
  processed_count: number
  progress_percent: number
  error_message: string | null
  created_at: string
  updated_at: string
}

type UploadedFile = {
  id: number
  batch_id: number
  filename: string
  platform: string | null
  status: string
  error_message: string | null
  created_at: string
  updated_at: string
}

const uploadFileList = ref<UploadUserFile[]>([])
const selectedFiles = ref<UploadRawFile[]>([])
const loading = ref(false)
const deletingBatchId = ref<number | null>(null)
const batchResult = ref<ImportBatch | null>(null)
const importBatches = ref<ImportBatch[]>([])
const uploadedFiles = ref<UploadedFile[]>([])
let pollTimer: number | null = null

const activeStatuses = new Set(['queued', 'processing'])

const latestBatchProgress = computed(() => batchResult.value?.progress_percent ?? 0)
const activeBatchCount = computed(() => importBatches.value.filter((batch) => activeStatuses.has(batch.status)).length)

function syncSelectedFiles(files: UploadFiles) {
  selectedFiles.value = files.map((file) => file.raw).filter((file): file is UploadRawFile => Boolean(file))
}

function handleChange(_: UploadFile, files: UploadFiles) {
  uploadFileList.value = files
  syncSelectedFiles(files)
}

function handleRemove(_: UploadFile, files: UploadFiles) {
  uploadFileList.value = files
  syncSelectedFiles(files)
}

function isBatchActive(batch: ImportBatch | null) {
  return Boolean(batch && activeStatuses.has(batch.status))
}

function stopPolling() {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

function syncLatestBatchFromList() {
  if (!batchResult.value) return
  const latest = importBatches.value.find((batch) => batch.id === batchResult.value?.id)
  if (latest) batchResult.value = latest
}

function maybeStopPolling() {
  if (importBatches.value.some((batch) => activeStatuses.has(batch.status))) return
  if (isBatchActive(batchResult.value)) return
  stopPolling()
}

function startPolling() {
  if (pollTimer !== null) return
  pollTimer = window.setInterval(async () => {
    await Promise.all([loadImportBatches(), loadUploadedFiles()])
    syncLatestBatchFromList()
    maybeStopPolling()
  }, 1500)
}

function formatDate(value: string) {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function statusText(status: string) {
  const map: Record<string, string> = {
    queued: '排队中',
    processing: '解析中',
    done: '成功',
    partial_failed: '部分失败',
    failed: '失败',
  }
  return map[status] ?? status
}

function statusTagType(status: string) {
  if (status === 'done') return 'success'
  if (status === 'failed' || status === 'partial_failed') return 'danger'
  if (status === 'queued' || status === 'processing') return 'warning'
  return 'info'
}

function progressStatus(batch: ImportBatch): 'success' | 'exception' | 'warning' | undefined {
  if (batch.status === 'done') return 'success'
  if (batch.status === 'partial_failed' || batch.status === 'failed') return 'exception'
  if (batch.status === 'processing' || batch.status === 'queued') return 'warning'
  return undefined
}

async function loadImportBatches() {
  const { data } = await api.get<ImportBatch[]>('/imports')
  importBatches.value = data
  syncLatestBatchFromList()
  if (!batchResult.value && data.length) {
    batchResult.value = data[0]
  }
}

async function loadUploadedFiles() {
  const { data } = await api.get<UploadedFile[]>('/imports/files')
  uploadedFiles.value = data
}

async function refreshRecords() {
  await Promise.all([loadImportBatches(), loadUploadedFiles()])
}

async function submit() {
  if (!selectedFiles.value.length) {
    ElMessage.warning('请先选择微信或支付宝账单文件')
    return
  }
  loading.value = true
  try {
    const formData = new FormData()
    selectedFiles.value.forEach((file) => formData.append('files', file, file.name))
    const { data } = await api.post<{ batch: ImportBatch; message: string }>('/imports', formData)
    batchResult.value = data.batch
    uploadFileList.value = []
    selectedFiles.value = []
    await Promise.all([loadImportBatches(), loadUploadedFiles()])
    startPolling()
    ElMessage.success('导入任务已启动，系统会自动刷新解析进度')
  } catch {
    ElMessage.error('导入失败，请检查文件格式、模型接口或后端服务状态')
  } finally {
    loading.value = false
  }
}

async function removeBatch(batch: ImportBatch) {
  await ElMessageBox.confirm(
    `删除批次 ${batch.id} 后，对应上传文件、交易记录和分类结果都会一起删除。`,
    '确认删除导入批次',
    {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    },
  )

  deletingBatchId.value = batch.id
  try {
    await api.delete(`/imports/${batch.id}`)
    if (batchResult.value?.id === batch.id) {
      batchResult.value = null
    }
    await Promise.all([loadImportBatches(), loadUploadedFiles()])
    maybeStopPolling()
    ElMessage.success('导入批次已删除')
  } catch {
    ElMessage.error('删除失败，请稍后重试')
  } finally {
    deletingBatchId.value = null
  }
}

onMounted(async () => {
  await Promise.all([loadImportBatches(), loadUploadedFiles()])
  if (importBatches.value.some((batch) => activeStatuses.has(batch.status))) {
    startPolling()
  }
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<template>
  <div class="page-shell">
    <div class="page-heading">
      <div>
        <h1>导入账单</h1>
        <p>上传微信或支付宝导出的 CSV/XLS/XLSX 文件，系统会完成解析、去重和自动分类。</p>
      </div>
      <el-button :icon="Refresh" @click="refreshRecords">刷新记录</el-button>
    </div>

    <section class="import-hero">
      <div class="panel card upload-panel">
        <el-upload
          v-model:file-list="uploadFileList"
          drag
          multiple
          :auto-upload="false"
          :show-file-list="true"
          :on-change="handleChange"
          :on-remove="handleRemove"
        >
          <el-icon class="upload-icon"><UploadFilled /></el-icon>
          <div class="upload-title">拖拽或点击上传账单文件</div>
          <div class="upload-hint">支持 WeChat、Alipay 导出的 CSV / XLS / XLSX 文件，单个文件建议不超过 50MB。</div>
        </el-upload>
        <div class="upload-actions">
          <div class="muted">已选择 {{ selectedFiles.length }} 个文件</div>
          <el-button type="primary" :loading="loading" @click="submit">开始导入</el-button>
        </div>
      </div>

      <div class="panel card status-panel">
        <div class="section-title">
          <h2>最近导入结果</h2>
          <el-tag :type="activeBatchCount ? 'warning' : 'success'">{{ activeBatchCount ? `${activeBatchCount} 个处理中` : '当前空闲' }}</el-tag>
        </div>
        <template v-if="batchResult">
          <div class="batch-id">批次 #{{ batchResult.id }}</div>
          <el-progress :percentage="latestBatchProgress" :status="progressStatus(batchResult)" :stroke-width="14" />
          <div class="batch-meta">
            <span>文件 {{ batchResult.source_count }}</span>
            <span>交易 {{ batchResult.processed_count }} / {{ batchResult.total_count || '-' }}</span>
            <span>{{ statusText(batchResult.status) }}</span>
          </div>
          <el-alert
            v-if="batchResult.error_message"
            type="error"
            :title="batchResult.error_message"
            show-icon
            :closable="false"
          />
        </template>
        <el-empty v-else description="暂无导入结果" :image-size="86" />
      </div>
    </section>

    <section class="panel card">
      <div class="section-title">
        <h2>最近导入记录</h2>
        <span>文件来源、解析进度与状态</span>
      </div>
      <el-table :data="uploadedFiles" empty-text="暂无上传文件记录">
        <el-table-column prop="filename" label="文件名称" min-width="220" />
        <el-table-column label="来源" width="120">
          <template #default="{ row }">{{ row.platform || '未知平台' }}</template>
        </el-table-column>
        <el-table-column prop="batch_id" label="批次" width="90" />
        <el-table-column label="导入时间" min-width="170">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" class="status-tag">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="错误信息" min-width="180">
          <template #default="{ row }">{{ row.error_message || '-' }}</template>
        </el-table-column>
      </el-table>
    </section>

    <section class="panel card">
      <div class="section-title">
        <h2>导入批次</h2>
        <span>删除批次会清理对应交易与分类结果</span>
      </div>
      <el-table :data="importBatches" empty-text="暂无导入批次">
        <el-table-column prop="id" label="批次 ID" width="100" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" class="status-tag">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source_count" label="文件数" width="100" />
        <el-table-column label="进度" min-width="260">
          <template #default="{ row }">
            <div class="table-progress">
              <el-progress :percentage="row.progress_percent" :status="progressStatus(row)" :stroke-width="12" />
              <div class="table-progress-meta">{{ row.processed_count }} / {{ row.total_count || '-' }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" min-width="170">
          <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button type="danger" text :icon="Delete" :loading="deletingBatchId === row.id" @click="removeBatch(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>

<style scoped>
.import-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(320px, 0.8fr);
  gap: 16px;
}

.upload-panel {
  display: grid;
  gap: 16px;
}

.upload-panel :deep(.el-upload-dragger) {
  padding: 42px 24px;
  border-color: #cbd5e1;
  background: #fbfdff;
}

.upload-icon {
  font-size: 44px;
  color: var(--color-primary);
}

.upload-title {
  margin-top: 12px;
  font-size: 18px;
  font-weight: 700;
  color: var(--color-text);
}

.upload-hint {
  margin-top: 8px;
  color: var(--color-muted);
}

.upload-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.status-panel {
  display: grid;
  align-content: start;
  gap: 16px;
}

.batch-id {
  font-size: 26px;
  font-weight: 800;
}

.batch-meta {
  display: flex;
  gap: 14px;
  color: var(--color-muted);
  font-size: 13px;
}

.table-progress-meta {
  margin-top: 6px;
  color: var(--color-muted);
  font-size: 12px;
}

@media (max-width: 980px) {
  .import-hero {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .upload-actions,
  .batch-meta {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
