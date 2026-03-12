<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api/client'

type ImportFileOption = {
  id: number
  batch_id: number
  filename: string
  platform: string | null
  status: string
  created_at: string
}

const form = reactive({
  title: '',
  date_from: '',
  date_to: '',
  uploaded_file_ids: [] as number[],
})
const importFiles = ref<ImportFileOption[]>([])
const lastReport = ref<any | null>(null)
const loading = ref(false)
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'

function formatImportFileLabel(file: ImportFileOption) {
  const platform = file.platform || '未知平台'
  return `[批次 ${file.batch_id}] ${platform} - ${file.filename}`
}

async function loadImportFiles() {
  const { data } = await api.get('/imports/files')
  importFiles.value = data
}

async function createReport() {
  loading.value = true
  try {
    const payload = {
      title: form.title || null,
      date_from: form.date_from || null,
      date_to: form.date_to || null,
      uploaded_file_ids: form.uploaded_file_ids,
    }
    const { data } = await api.post('/reports', payload)
    lastReport.value = data
    ElMessage.success('报表已生成')
  } catch {
    ElMessage.error('生成报表失败，请检查日期、文件筛选或后端服务')
  } finally {
    loading.value = false
  }
}

async function downloadReport() {
  if (!lastReport.value) {
    return
  }
  try {
    const response = await api.get(`/reports/${lastReport.value.id}/download`, {
      responseType: 'blob',
    })
    const blobUrl = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }))
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = `report-${lastReport.value.id}.pdf`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(blobUrl)
  } catch {
    ElMessage.error('下载 PDF 失败，请检查登录状态或后端服务')
  }
}

onMounted(loadImportFiles)
</script>

<template>
  <div class="page-shell">
    <div class="page-title">
      <div>
        <h1>报表中心</h1>
        <p>生成课程答辩可展示、可下载的 PDF 报表，并支持按导入文件筛选。</p>
      </div>
    </div>
    <section class="panel report-card">
      <div class="toolbar">
        <el-input v-model="form.title" placeholder="报表标题" />
        <el-date-picker v-model="form.date_from" type="date" placeholder="开始日期" value-format="YYYY-MM-DDTHH:mm:ss" />
        <el-date-picker v-model="form.date_to" type="date" placeholder="结束日期" value-format="YYYY-MM-DDTHH:mm:ss" />
        <el-select
          v-model="form.uploaded_file_ids"
          multiple
          collapse-tags
          collapse-tags-tooltip
          clearable
          filterable
          placeholder="导入文件"
        >
          <el-option
            v-for="file in importFiles"
            :key="file.id"
            :label="formatImportFileLabel(file)"
            :value="file.id"
          />
        </el-select>
        <el-button type="primary" :loading="loading" @click="createReport">生成报表</el-button>
      </div>
      <el-result
        v-if="lastReport"
        icon="success"
        title="报表已生成"
        :sub-title="`报告 ID: ${lastReport.id}`"
      >
        <template #extra>
          <el-button type="primary" @click="downloadReport">下载 PDF</el-button>
        </template>
      </el-result>
    </section>
  </div>
</template>

<style scoped>
.report-card {
  padding: 20px;
}

.toolbar {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 2fr auto;
  gap: 12px;
}

@media (max-width: 900px) {
  .toolbar {
    grid-template-columns: 1fr;
  }
}
</style>
