<script setup lang="ts">
import * as echarts from 'echarts'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
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

const metrics = computed(() => [
  { label: '总支出', value: summary.value.expense_total },
  { label: '总收入', value: summary.value.income_total },
  { label: '净流入', value: summary.value.net_total },
  { label: '交易数', value: summary.value.transaction_count },
  { label: '待校正', value: summary.value.pending_review_count },
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
  if (filters.uploaded_file_ids.length) {
    filters.uploaded_file_ids.forEach((fileId) => {
      params.append('uploaded_file_ids', String(fileId))
    })
  }
  return params
}

function formatMoney(value: string | number) {
  return Number(value || 0).toFixed(2)
}

function formatImportFileLabel(file: ImportFileOption) {
  const platform = file.platform || '未知平台'
  return `[批次 ${file.batch_id}] ${platform} - ${file.filename}`
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
  if (!trendChart || !categoryChart) {
    return
  }

  trendChart.setOption({
    color: ['#d96c1f', '#4f7cff'],
    tooltip: { trigger: 'axis' },
    legend: { data: ['支出', '收入'] },
    grid: { left: 32, right: 24, top: 48, bottom: 32 },
    xAxis: {
      type: 'category',
      data: summary.value.expense_trend.map((item) => item.date),
      axisLabel: { color: '#6f6257' },
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        color: '#6f6257',
        formatter: (value: number) => value.toFixed(0),
      },
      splitLine: { lineStyle: { color: 'rgba(120, 101, 82, 0.12)' } },
    },
    series: [
      {
        name: '支出',
        type: 'line',
        smooth: true,
        data: summary.value.expense_trend.map((item) => Number(item.expense)),
        areaStyle: { opacity: 0.12 },
      },
      {
        name: '收入',
        type: 'line',
        smooth: true,
        data: summary.value.expense_trend.map((item) => Number(item.income)),
      },
    ],
  })

  categoryChart.setOption({
    color: ['#1f4e5f', '#d96c1f', '#739072', '#b85c38', '#d4a373', '#4b5563'],
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, type: 'scroll' },
    series: [
      {
        name: '分类支出',
        type: 'pie',
        radius: ['42%', '72%'],
        center: ['50%', '45%'],
        avoidLabelOverlap: true,
        label: {
          formatter: '{b}\n{d}%',
        },
        data: summary.value.category_breakdown.map((item) => ({
          name: item.category_name,
          value: Number(item.amount),
        })),
      },
    ],
  })
}

async function loadCategories() {
  const { data } = await api.get('/categories')
  categories.value = data.filter((category: Category) => category.is_active)
}

async function loadImportFiles() {
  const { data } = await api.get('/imports/files')
  importFiles.value = data
}

async function loadSummary() {
  loading.value = true
  try {
    const { data } = await api.get('/dashboard/summary', { params: buildSummaryParams() })
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
    <div class="page-title">
      <div>
        <h1>Dashboard</h1>
        <p>按时间范围、分类和导入文件观察收支变化、分类分布和重点商户。</p>
      </div>
      <el-button type="primary" :loading="loading" @click="loadSummary">刷新</el-button>
    </div>

    <section class="panel filter-card">
      <div class="filter-grid">
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
          <el-option
            v-for="file in importFiles"
            :key="file.id"
            :label="formatImportFileLabel(file)"
            :value="file.id"
          />
        </el-select>
        <el-button type="primary" :loading="loading" @click="loadSummary">应用筛选</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>
    </section>

    <div class="metric-grid metric-grid-wide">
      <section v-for="metric in metrics" :key="metric.label" class="panel metric-card">
        <div class="metric-label">{{ metric.label }}</div>
        <div class="metric-value">{{ metric.value }}</div>
      </section>
    </div>

    <div class="dashboard-grid">
      <section class="panel content-card chart-card">
        <div class="card-head">
          <h3>收支趋势</h3>
          <span>按筛选范围展示每日收入与支出</span>
        </div>
        <div ref="trendChartRef" class="chart-shell"></div>
      </section>

      <section class="panel content-card chart-card">
        <div class="card-head">
          <h3>分类占比</h3>
          <span>查看当前筛选结果中的支出结构</span>
        </div>
        <div ref="categoryChartRef" class="chart-shell"></div>
      </section>

      <section class="panel content-card">
        <div class="card-head">
          <h3>Top 商户</h3>
          <span>按支出金额排序</span>
        </div>
        <el-table :data="summary.top_merchants" size="small">
          <el-table-column prop="merchant" label="商户" min-width="180" />
          <el-table-column label="支出金额" width="120">
            <template #default="{ row }">{{ formatMoney(row.amount) }}</template>
          </el-table-column>
          <el-table-column prop="transaction_count" label="笔数" width="90" />
        </el-table>
      </section>

      <section class="panel content-card">
        <div class="card-head">
          <h3>分类明细</h3>
          <span>当前筛选条件下的支出分布</span>
        </div>
        <el-table :data="summary.category_breakdown" size="small">
          <el-table-column prop="category_name" label="分类" min-width="160" />
          <el-table-column label="支出金额" width="120">
            <template #default="{ row }">{{ formatMoney(row.amount) }}</template>
          </el-table-column>
          <el-table-column prop="transaction_count" label="笔数" width="90" />
        </el-table>
      </section>
    </div>

    <section class="panel content-card jobs-card">
      <div class="card-head">
        <h3>最近导入任务</h3>
        <span>导入和分类任务的最新状态</span>
      </div>
      <el-table :data="summary.recent_jobs" size="small">
        <el-table-column prop="id" label="批次" width="80" />
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column label="进度" min-width="220">
          <template #default="{ row }">
            <el-progress :percentage="row.progress_percent" :stroke-width="12" />
          </template>
        </el-table-column>
        <el-table-column prop="source_count" label="文件数" width="90" />
      </el-table>
    </section>
  </div>
</template>

<style scoped>
.filter-card {
  padding: 20px;
}

.filter-grid {
  display: grid;
  grid-template-columns: minmax(220px, 1.2fr) minmax(180px, 0.8fr) minmax(260px, 1.6fr) 120px 100px;
  gap: 12px;
}

.metric-grid-wide {
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.content-card {
  padding: 20px;
}

.chart-card {
  padding-bottom: 12px;
}

.card-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.card-head h3 {
  margin: 0;
}

.card-head span {
  color: var(--muted);
  font-size: 13px;
}

.chart-shell {
  width: 100%;
  height: 320px;
}

.jobs-card {
  margin-top: 16px;
}

@media (max-width: 1100px) {
  .filter-grid {
    grid-template-columns: 1fr 1fr;
  }

  .metric-grid-wide {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .dashboard-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .filter-grid,
  .metric-grid-wide {
    grid-template-columns: 1fr;
  }

  .card-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
