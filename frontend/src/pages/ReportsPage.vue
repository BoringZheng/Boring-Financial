<script setup lang="ts">
import * as echarts from 'echarts'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Refresh } from '@element-plus/icons-vue'
import api from '../api/client'

type ImportFileOption = {
  id: number
  batch_id: number
  filename: string
  platform: string | null
  status: string
  created_at: string
}

type DashboardSummary = {
  expense_total: string
  income_total: string
  net_total: string
  transaction_count: number
  pending_review_count: number
  top_merchants: Array<{ merchant: string; amount: string; transaction_count: number }>
  category_breakdown: Array<{ category_id: number | null; category_name: string; amount: string; transaction_count: number }>
  expense_trend: Array<{ date: string; expense: string; income: string }>
  recent_jobs: Array<{ id: number; status: string; progress_percent: number }>
}

type ReportRead = {
  id: number
  user_id: number
  job_id: number
  title: string
  file_path: string
}

const form = reactive({
  title: '',
  date_range: [] as [string, string] | [],
  uploaded_file_ids: [] as number[],
})
const importFiles = ref<ImportFileOption[]>([])
const lastReport = ref<ReportRead | null>(null)
const loading = ref(false)
const summaryLoading = ref(false)
const reportPreviewUrl = ref('')
const summary = ref<DashboardSummary>({
  expense_total: '0.00',
  income_total: '0.00',
  net_total: '0.00',
  transaction_count: 0,
  pending_review_count: 0,
  top_merchants: [],
  category_breakdown: [],
  expense_trend: [],
  recent_jobs: [],
})

const trendChartRef = ref<HTMLDivElement | null>(null)
let trendChart: echarts.ECharts | null = null

const savingsRate = computed(() => {
  const income = Number(summary.value.income_total || 0)
  const net = Number(summary.value.net_total || 0)
  if (income <= 0) return '0.0%'
  return `${((net / income) * 100).toFixed(1)}%`
})

function money(value: string | number) {
  return `¥ ${Number(value || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatImportFileLabel(file: ImportFileOption) {
  const platform = file.platform || '未知平台'
  return `批次 ${file.batch_id} / ${platform} / ${file.filename}`
}

function buildSummaryParams() {
  const params = new URLSearchParams()
  if (form.date_range.length === 2) {
    params.append('date_from', form.date_range[0])
    params.append('date_to', form.date_range[1])
  }
  form.uploaded_file_ids.forEach((fileId) => params.append('uploaded_file_ids', String(fileId)))
  return params
}

function reportPayload() {
  return {
    title: form.title || null,
    date_from: form.date_range.length === 2 ? form.date_range[0] : null,
    date_to: form.date_range.length === 2 ? form.date_range[1] : null,
    uploaded_file_ids: form.uploaded_file_ids,
  }
}

function initChart() {
  if (trendChartRef.value && !trendChart) {
    trendChart = echarts.init(trendChartRef.value)
  }
}

function renderChart() {
  if (!trendChart) return
  trendChart.setOption({
    color: ['#00A884', '#EF4444', '#3B82F6'],
    tooltip: { trigger: 'axis' },
    legend: { top: 0, right: 0, data: ['收入', '支出', '结余'] },
    grid: { left: 42, right: 18, top: 44, bottom: 30 },
    xAxis: {
      type: 'category',
      data: summary.value.expense_trend.map((item) => item.date),
      axisLine: { lineStyle: { color: '#E5E7EB' } },
      axisLabel: { color: '#6B7280' },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#EEF2F7' } },
      axisLabel: { color: '#6B7280' },
    },
    series: [
      { name: '收入', type: 'bar', data: summary.value.expense_trend.map((item) => Number(item.income)) },
      { name: '支出', type: 'bar', data: summary.value.expense_trend.map((item) => Number(item.expense)) },
      {
        name: '结余',
        type: 'line',
        smooth: true,
        data: summary.value.expense_trend.map((item) => Number(item.income) - Number(item.expense)),
      },
    ],
  })
}

function revokePreviewUrl() {
  if (reportPreviewUrl.value) {
    window.URL.revokeObjectURL(reportPreviewUrl.value)
    reportPreviewUrl.value = ''
  }
}

async function loadImportFiles() {
  const { data } = await api.get<ImportFileOption[]>('/imports/files')
  importFiles.value = data
}

async function loadSummary() {
  summaryLoading.value = true
  try {
    const { data } = await api.get<DashboardSummary>('/dashboard/summary', { params: buildSummaryParams() })
    summary.value = data
    await nextTick()
    renderChart()
  } finally {
    summaryLoading.value = false
  }
}

async function refreshPreviewData() {
  await loadSummary()
  ElMessage.success('报表预览数据已刷新')
}

async function createReport() {
  loading.value = true
  try {
    const { data } = await api.post<ReportRead>('/reports', reportPayload())
    lastReport.value = data
    await loadReportPreview(data.id)
    ElMessage.success('PDF 报表已生成')
  } catch {
    ElMessage.error('生成报表失败，请检查日期、文件筛选或后端服务状态')
  } finally {
    loading.value = false
  }
}

async function loadReportPreview(reportId: number) {
  const response = await api.get(`/reports/${reportId}/download`, { responseType: 'blob' })
  revokePreviewUrl()
  reportPreviewUrl.value = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }))
}

async function downloadReport() {
  if (!lastReport.value) return
  try {
    if (!reportPreviewUrl.value) {
      await loadReportPreview(lastReport.value.id)
    }
    const link = document.createElement('a')
    link.href = reportPreviewUrl.value
    link.download = `report-${lastReport.value.id}.pdf`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  } catch {
    ElMessage.error('下载 PDF 失败，请检查登录状态或后端服务')
  }
}

onMounted(async () => {
  await nextTick()
  initChart()
  await Promise.all([loadImportFiles(), loadSummary()])
})

onBeforeUnmount(() => {
  trendChart?.dispose()
  revokePreviewUrl()
})
</script>

<template>
  <div class="page-shell">
    <div class="page-heading">
      <div>
        <h1>报表中心</h1>
        <p>选择账单范围，预览月度收支概况，并生成可下载的 PDF 报告。</p>
      </div>
      <el-button :icon="Refresh" :loading="summaryLoading" @click="refreshPreviewData">刷新预览</el-button>
    </div>

    <section class="panel card report-form">
      <div class="section-title">
        <h2>生成条件</h2>
        <span>选择范围后可先刷新预览，再生成 PDF</span>
      </div>
      <div class="toolbar-grid report-grid">
        <el-input v-model="form.title" placeholder="报表标题，例如：2026 年 5 月账单报告" />
        <el-date-picker
          v-model="form.date_range"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DDTHH:mm:ss"
        />
        <el-select
          v-model="form.uploaded_file_ids"
          multiple
          collapse-tags
          collapse-tags-tooltip
          clearable
          filterable
          placeholder="导入文件"
        >
          <el-option v-for="file in importFiles" :key="file.id" :label="formatImportFileLabel(file)" :value="file.id" />
        </el-select>
        <el-button :loading="summaryLoading" @click="loadSummary">预览摘要</el-button>
        <el-button type="primary" :loading="loading" @click="createReport">生成 PDF</el-button>
      </div>
    </section>

    <div class="metric-grid">
      <section class="panel metric-card">
        <div class="metric-label">总收入</div>
        <div class="metric-value">{{ money(summary.income_total) }}</div>
        <div class="metric-foot positive">报表范围内</div>
      </section>
      <section class="panel metric-card">
        <div class="metric-label">总支出</div>
        <div class="metric-value">{{ money(summary.expense_total) }}</div>
        <div class="metric-foot negative">报表范围内</div>
      </section>
      <section class="panel metric-card">
        <div class="metric-label">结余</div>
        <div class="metric-value">{{ money(summary.net_total) }}</div>
        <div class="metric-foot">收入减支出</div>
      </section>
      <section class="panel metric-card">
        <div class="metric-label">储蓄率</div>
        <div class="metric-value">{{ savingsRate }}</div>
        <div class="metric-foot">用于答辩展示</div>
      </section>
    </div>

    <section class="report-main">
      <div class="panel card">
        <div class="section-title">
          <h2>收支趋势</h2>
          <span>PDF 生成前的摘要预览</span>
        </div>
        <div ref="trendChartRef" class="chart-shell"></div>
      </div>

      <div class="panel card report-status">
        <div class="section-title">
          <h2>最近生成</h2>
          <span>当前会话</span>
        </div>
        <template v-if="lastReport">
          <div class="report-id">#{{ lastReport.id }}</div>
          <h3>{{ lastReport.title }}</h3>
          <p class="muted">任务 ID：{{ lastReport.job_id }}</p>
          <el-button type="primary" :icon="Download" @click="downloadReport">下载 PDF</el-button>
        </template>
        <el-empty v-else description="尚未生成报表" :image-size="90" />
      </div>
    </section>

    <section class="panel card pdf-panel">
      <div class="section-title">
        <h2>报表预览（PDF）</h2>
        <span>{{ lastReport ? `报告 ID：${lastReport.id}` : '生成后显示预览' }}</span>
      </div>
      <iframe v-if="reportPreviewUrl" class="pdf-frame" :src="reportPreviewUrl"></iframe>
      <div v-else class="pdf-placeholder">
        <strong>Boring Financial 月度财务报告</strong>
        <span>生成 PDF 后将在这里预览报告封面、收支概览和分类明细。</span>
      </div>
    </section>
  </div>
</template>

<style scoped>
.report-grid {
  grid-template-columns: minmax(240px, 1.1fr) minmax(260px, 1.1fr) minmax(260px, 1.2fr) 104px 104px;
}

.report-main {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.6fr);
  gap: 16px;
}

.chart-shell {
  height: 320px;
}

.report-status {
  display: grid;
  align-content: start;
  gap: 12px;
}

.report-id {
  width: fit-content;
  padding: 6px 10px;
  border-radius: 999px;
  background: #e6f7f3;
  color: var(--color-primary);
  font-weight: 800;
}

.report-status h3 {
  margin: 0;
  font-size: 18px;
}

.pdf-frame {
  width: 100%;
  min-height: 520px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: #fff;
}

.pdf-placeholder {
  min-height: 360px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 12px;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  background: #f8fafc;
  color: var(--color-muted);
  text-align: center;
}

.pdf-placeholder strong {
  color: var(--color-text);
  font-size: 20px;
}

@media (max-width: 1180px) {
  .report-grid,
  .report-main {
    grid-template-columns: 1fr;
  }
}
</style>
