<script setup lang="ts">
import * as echarts from 'echarts'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import api from '../api/client'

type Category = {
  id: number
  name: string
  is_active: boolean
}

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
  recent_jobs: Array<{
    id: number
    status: string
    processed_count: number
    total_count: number
    source_count: number
    progress_percent: number
  }>
}

const loading = ref(false)
const categories = ref<Category[]>([])
const importFiles = ref<ImportFileOption[]>([])
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

const filters = reactive<{
  date_range: [string, string] | []
  category_id?: number
  uploaded_file_ids: number[]
}>({
  date_range: [],
  category_id: undefined,
  uploaded_file_ids: [],
})

const trendChartRef = ref<HTMLDivElement | null>(null)
const categoryChartRef = ref<HTMLDivElement | null>(null)
let trendChart: echarts.ECharts | null = null
let categoryChart: echarts.ECharts | null = null

const savingsRate = computed(() => {
  const income = Number(summary.value.income_total || 0)
  const net = Number(summary.value.net_total || 0)
  if (income <= 0) return '0.0%'
  return `${((net / income) * 100).toFixed(1)}%`
})

const metrics = computed(() => [
  { label: '本月收入', value: money(summary.value.income_total), foot: '已导入账单统计', tone: 'positive' },
  { label: '本月支出', value: money(summary.value.expense_total), foot: '按当前筛选范围', tone: 'negative' },
  { label: '储蓄率', value: savingsRate.value, foot: `净流入 ${money(summary.value.net_total)}`, tone: 'primary' },
  { label: '未分类交易', value: `${summary.value.pending_review_count} 笔`, foot: `共 ${summary.value.transaction_count} 笔交易`, tone: 'warning' },
])

function buildSummaryParams() {
  const params = new URLSearchParams()
  if (filters.date_range.length === 2) {
    params.append('date_from', filters.date_range[0])
    params.append('date_to', filters.date_range[1])
  }
  if (filters.category_id !== undefined) {
    params.append('category_id', String(filters.category_id))
  }
  filters.uploaded_file_ids.forEach((fileId) => params.append('uploaded_file_ids', String(fileId)))
  return params
}

function money(value: string | number) {
  return `¥ ${Number(value || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatImportFileLabel(file: ImportFileOption) {
  const platform = file.platform || '未知平台'
  return `批次 ${file.batch_id} / ${platform} / ${file.filename}`
}

function jobStatusType(status: string) {
  if (status === 'done') return 'success'
  if (status === 'failed' || status === 'partial_failed') return 'danger'
  if (status === 'processing' || status === 'queued') return 'warning'
  return 'info'
}

function jobStatusText(status: string) {
  const statusMap: Record<string, string> = {
    queued: '排队中',
    processing: '解析中',
    done: '成功',
    partial_failed: '部分失败',
    failed: '失败',
  }
  return statusMap[status] ?? status
}

function initCharts() {
  if (trendChartRef.value && !trendChart) {
    trendChart = echarts.init(trendChartRef.value)
  }
  if (categoryChartRef.value && !categoryChart) {
    categoryChart = echarts.init(categoryChartRef.value)
  }
}

function resizeCharts() {
  trendChart?.resize()
  categoryChart?.resize()
}

function renderCharts() {
  if (!trendChart || !categoryChart) return

  trendChart.setOption({
    color: ['#00A884', '#EF4444'],
    tooltip: { trigger: 'axis' },
    legend: { top: 0, right: 0, data: ['收入', '支出'] },
    grid: { left: 42, right: 20, top: 46, bottom: 30 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: summary.value.expense_trend.map((item) => item.date),
      axisLine: { lineStyle: { color: '#E5E7EB' } },
      axisLabel: { color: '#6B7280' },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#6B7280' },
      splitLine: { lineStyle: { color: '#EEF2F7' } },
    },
    series: [
      {
        name: '收入',
        type: 'line',
        smooth: true,
        data: summary.value.expense_trend.map((item) => Number(item.income)),
        areaStyle: { color: 'rgba(0, 168, 132, 0.12)' },
      },
      {
        name: '支出',
        type: 'line',
        smooth: true,
        data: summary.value.expense_trend.map((item) => Number(item.expense)),
        areaStyle: { color: 'rgba(239, 68, 68, 0.08)' },
      },
    ],
  })

  categoryChart.setOption({
    color: ['#00A884', '#3B82F6', '#F59E0B', '#8B5CF6', '#EF4444', '#14B8A6', '#64748B'],
    tooltip: { trigger: 'item', formatter: '{b}<br/>¥{c} ({d}%)' },
    legend: { type: 'scroll', bottom: 0, icon: 'circle' },
    series: [
      {
        name: '支出分类',
        type: 'pie',
        radius: ['52%', '76%'],
        center: ['50%', '43%'],
        label: { formatter: '{b}\n{d}%', color: '#334155' },
        data: summary.value.category_breakdown.map((item) => ({
          name: item.category_name || '未分类',
          value: Number(item.amount),
        })),
      },
    ],
  })
}

async function loadCategories() {
  const { data } = await api.get<Category[]>('/categories')
  categories.value = data.filter((category) => category.is_active)
}

async function loadImportFiles() {
  const { data } = await api.get<ImportFileOption[]>('/imports/files')
  importFiles.value = data
}

async function loadSummary() {
  loading.value = true
  try {
    const { data } = await api.get<DashboardSummary>('/dashboard/summary', { params: buildSummaryParams() })
    summary.value = data
    await nextTick()
    renderCharts()
  } finally {
    loading.value = false
  }
}

async function resetFilters() {
  filters.date_range = []
  filters.category_id = undefined
  filters.uploaded_file_ids = []
  await loadSummary()
}

onMounted(async () => {
  await nextTick()
  initCharts()
  window.addEventListener('resize', resizeCharts)
  await Promise.all([loadCategories(), loadImportFiles(), loadSummary()])
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  trendChart?.dispose()
  categoryChart?.dispose()
})
</script>

<template>
  <div class="page-shell">
    <div class="page-heading">
      <div>
        <h1>你好，欢迎回来 👋</h1>
        <p>基于当前账单数据观察收支趋势、分类结构、重点商户与导入任务状态。</p>
      </div>
      <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadSummary">刷新数据</el-button>
    </div>

    <section class="panel card filter-card">
      <div class="toolbar-grid filter-grid">
        <el-date-picker
          v-model="filters.date_range"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DDTHH:mm:ss"
        />
        <el-select v-model="filters.category_id" clearable filterable placeholder="选择分类">
          <el-option v-for="category in categories" :key="category.id" :label="category.name" :value="category.id" />
        </el-select>
        <el-select
          v-model="filters.uploaded_file_ids"
          multiple
          collapse-tags
          collapse-tags-tooltip
          clearable
          filterable
          placeholder="选择导入文件"
        >
          <el-option v-for="file in importFiles" :key="file.id" :label="formatImportFileLabel(file)" :value="file.id" />
        </el-select>
        <el-button type="primary" :loading="loading" @click="loadSummary">应用筛选</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>
    </section>

    <div class="metric-grid">
      <section v-for="metric in metrics" :key="metric.label" class="panel metric-card" :class="`metric-${metric.tone}`">
        <div class="metric-label">{{ metric.label }}</div>
        <div class="metric-value">{{ metric.value }}</div>
        <div class="metric-foot">{{ metric.foot }}</div>
      </section>
    </div>

    <div class="dashboard-grid">
      <section class="panel card chart-card">
        <div class="section-title">
          <h2>收支趋势</h2>
          <span>按日期统计收入与支出</span>
        </div>
        <div ref="trendChartRef" class="chart-shell"></div>
      </section>

      <section class="panel card chart-card">
        <div class="section-title">
          <h2>支出分类占比</h2>
          <span>展示当前筛选范围内的支出结构</span>
        </div>
        <div ref="categoryChartRef" class="chart-shell"></div>
      </section>

      <section class="panel card">
        <div class="section-title">
          <h2>TOP 支出商家</h2>
          <span>按支出金额排序</span>
        </div>
        <el-table :data="summary.top_merchants" size="small" empty-text="暂无商家数据">
          <el-table-column type="index" label="#" width="56" />
          <el-table-column prop="merchant" label="商家" min-width="160" />
          <el-table-column label="金额" width="130" align="right">
            <template #default="{ row }">
              <span class="amount negative">{{ money(row.amount) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="transaction_count" label="笔数" width="80" align="right" />
        </el-table>
      </section>

      <section class="panel card">
        <div class="section-title">
          <h2>导入任务状态</h2>
          <span>最近 5 个批次</span>
        </div>
        <div class="job-list">
          <div v-for="job in summary.recent_jobs" :key="job.id" class="job-item">
            <div>
              <strong>批次 #{{ job.id }}</strong>
              <span>{{ job.processed_count }} / {{ job.total_count || '-' }} 笔</span>
            </div>
            <el-progress :percentage="job.progress_percent" :stroke-width="10" />
            <el-tag :type="jobStatusType(job.status)" class="status-tag">{{ jobStatusText(job.status) }}</el-tag>
          </div>
          <el-empty v-if="!summary.recent_jobs.length" description="暂无导入任务" :image-size="88" />
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.filter-grid {
  grid-template-columns: minmax(260px, 1.1fr) minmax(170px, 0.8fr) minmax(280px, 1.3fr) 108px 88px;
}

.metric-card {
  border-left: 4px solid transparent;
}

.metric-positive {
  border-left-color: var(--color-success);
}

.metric-negative {
  border-left-color: var(--color-error);
}

.metric-primary {
  border-left-color: var(--color-primary);
}

.metric-warning {
  border-left-color: var(--color-warning);
}

.dashboard-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
  gap: 16px;
}

.chart-shell {
  width: 100%;
  height: 320px;
}

.job-list {
  display: grid;
  gap: 12px;
}

.job-item {
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr) 90px;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
}

.job-item strong,
.job-item span {
  display: block;
}

.job-item span {
  margin-top: 4px;
  color: var(--color-muted);
  font-size: 12px;
}

@media (max-width: 1180px) {
  .filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .dashboard-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .filter-grid,
  .job-item {
    grid-template-columns: 1fr;
  }
}
</style>
