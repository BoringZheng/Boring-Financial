<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile, UploadFiles, UploadRawFile, UploadUserFile } from 'element-plus'
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

const uploadFileList = ref<UploadUserFile[]>([])
const selectedFiles = ref<UploadRawFile[]>([])
const loading = ref(false)
const deletingBatchId = ref<number | null>(null)
const batchResult = ref<ImportBatch | null>(null)
const importBatches = ref<ImportBatch[]>([])
let pollTimer: number | null = null

const activeStatuses = new Set(['queued', 'processing'])

const latestBatchProgress = computed(() => {
  if (!batchResult.value) {
    return 0
  }
  return batchResult.value.progress_percent
})

function syncSelectedFiles(files: UploadFiles) {
  selectedFiles.value = files
    .map((file) => file.raw)
    .filter((file): file is UploadRawFile => Boolean(file))
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
  if (!batchResult.value) {
    return
  }
  const latest = importBatches.value.find((batch) => batch.id === batchResult.value?.id)
  if (latest) {
    batchResult.value = latest
  }
}

function maybeStopPolling() {
  if (importBatches.value.some((batch) => activeStatuses.has(batch.status))) {
    return
  }
  if (isBatchActive(batchResult.value)) {
    return
  }
  stopPolling()
}

function startPolling() {
  if (pollTimer !== null) {
    return
  }
  pollTimer = window.setInterval(async () => {
    await loadImportBatches()
    syncLatestBatchFromList()
    maybeStopPolling()
  }, 1500)
}

async function loadImportBatches() {
  const { data } = await api.get('/imports')
  importBatches.value = data
  syncLatestBatchFromList()
  if (!batchResult.value && data.length) {
    batchResult.value = data[0]
  }
}

async function submit() {
  if (!selectedFiles.value.length) {
    ElMessage.warning('请先选择账单文件')
    return
  }
  loading.value = true
  try {
    const formData = new FormData()
    selectedFiles.value.forEach((file) => formData.append('files', file, file.name))
    const { data } = await api.post('/imports', formData)
    batchResult.value = data.batch
    uploadFileList.value = []
    selectedFiles.value = []
    await loadImportBatches()
    startPolling()
    ElMessage.success('导入任务已启动，系统会自动刷新处理进度')
  } catch {
    ElMessage.error('导入失败，请检查文件格式、模型接口或后端服务')
  } finally {
    loading.value = false
  }
}

async function removeBatch(batch: ImportBatch) {
  await ElMessageBox.confirm(
    `删除批次 ${batch.id} 后，对应上传文件、交易记录和分类结果都会一起删除。`,
    '确认删除',
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
    await loadImportBatches()
    maybeStopPolling()
    ElMessage.success('导入批次已删除')
  } catch {
    ElMessage.error('删除失败，请稍后重试')
  } finally {
    deletingBatchId.value = null
  }
}

function progressStatus(batch: ImportBatch) {
  if (batch.status === 'done') {
    return 'success'
  }
  if (batch.status === 'partial_failed' || batch.status === 'failed') {
    return 'exception'
  }
  return undefined
}

onMounted(async () => {
  await loadImportBatches()
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
    <div class="page-title">
      <div>
        <h1>账单导入</h1>
        <p>上传微信或支付宝导出的 CSV/XLS/XLSX 文件，系统会自动解析并分类。</p>
      </div>
    </div>

    <section class="panel upload-card">
      <el-upload
        v-model:file-list="uploadFileList"
        drag
        multiple
        :auto-upload="false"
        :show-file-list="true"
        :on-change="handleChange"
        :on-remove="handleRemove"
      >
        <div class="upload-copy">拖拽文件到这里，或点击选择账单文件</div>
      </el-upload>
      <el-button type="primary" class="upload-button" :loading="loading" @click="submit">开始导入</el-button>
    </section>

    <section v-if="batchResult" class="panel upload-card">
      <h3>最近导入结果</h3>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="批次 ID">{{ batchResult.id }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ batchResult.status }}</el-descriptions-item>
        <el-descriptions-item label="文件数">{{ batchResult.source_count }}</el-descriptions-item>
        <el-descriptions-item label="已处理 / 总数">
          {{ batchResult.processed_count }} / {{ batchResult.total_count || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="处理进度" :span="2">
          <div class="progress-block">
            <el-progress
              :percentage="latestBatchProgress"
              :status="progressStatus(batchResult)"
              :stroke-width="14"
            />
            <div v-if="batchResult.total_count === 0 && isBatchActive(batchResult)" class="progress-hint">
              正在解析文件并统计待处理交易...
            </div>
          </div>
        </el-descriptions-item>
        <el-descriptions-item v-if="batchResult.error_message" label="错误信息" :span="2">
          {{ batchResult.error_message }}
        </el-descriptions-item>
      </el-descriptions>
    </section>

    <section class="panel upload-card">
      <div class="section-head">
        <h3>导入批次</h3>
        <el-button text @click="loadImportBatches">刷新</el-button>
      </div>
      <el-table :data="importBatches" empty-text="暂无导入记录">
        <el-table-column prop="id" label="批次 ID" width="100" />
        <el-table-column prop="status" label="状态" width="140" />
        <el-table-column prop="source_count" label="文件数" width="100" />
        <el-table-column label="进度" min-width="240">
          <template #default="{ row }">
            <div class="table-progress">
              <el-progress
                :percentage="row.progress_percent"
                :status="progressStatus(row)"
                :stroke-width="12"
              />
              <div class="table-progress-meta">{{ row.processed_count }} / {{ row.total_count || '-' }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" min-width="180" />
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button
              type="danger"
              text
              :loading="deletingBatchId === row.id"
              @click="removeBatch(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>

<style scoped>
.upload-card {
  padding: 20px;
}

.upload-copy {
  padding: 20px;
  color: var(--muted);
}

.upload-button {
  margin-top: 16px;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.section-head h3 {
  margin: 0;
}

.progress-block {
  width: 100%;
}

.progress-hint {
  margin-top: 8px;
  color: var(--muted);
  font-size: 13px;
}

.table-progress {
  width: 100%;
}

.table-progress-meta {
  margin-top: 6px;
  color: var(--muted);
  font-size: 12px;
}
</style>
