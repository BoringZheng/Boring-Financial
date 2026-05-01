<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { EditPen, Refresh, Search, View } from '@element-plus/icons-vue'
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

type TransactionRow = {
  id: number
  platform: string
  occurred_at: string
  type: string
  amount: string
  merchant: string | null
  item: string | null
  note: string | null
  auto_provider: string | null
  auto_reason: string | null
  auto_confidence: string | null
  auto_category_id: number | null
  final_category_id: number | null
  needs_review: boolean
}

type TransactionListResponse = {
  items: TransactionRow[]
  total: number
}

const router = useRouter()
const loading = ref(false)
const transactions = ref<TransactionRow[]>([])
const total = ref(0)
const categories = ref<Category[]>([])
const importFiles = ref<ImportFileOption[]>([])
const detailDrawerVisible = ref(false)
const selectedRow = ref<TransactionRow | null>(null)
const filters = reactive({
  page: 1,
  page_size: 20,
  search: '',
  platform: '',
  category_id: undefined as number | undefined,
  uploaded_file_ids: [] as number[],
  date_range: [] as [string, string] | [],
  review_status: '',
})

const categoryMap = computed(() => new Map(categories.value.map((category) => [category.id, category.name])))
const legacyIncomeType = String.fromCharCode(0x93c0, 0x8dfa, 0x53c6)

function buildTransactionParams() {
  const params = new URLSearchParams()
  params.append('page', String(filters.page))
  params.append('page_size', String(filters.page_size))
  if (filters.search) params.append('search', filters.search)
  if (filters.platform) params.append('platform', filters.platform)
  if (filters.category_id !== undefined) params.append('category_id', String(filters.category_id))
  if (filters.date_range.length === 2) {
    params.append('date_from', filters.date_range[0])
    params.append('date_to', filters.date_range[1])
  }
  if (filters.review_status === 'needs_review') params.append('needs_review', 'true')
  if (filters.review_status === 'confirmed') params.append('needs_review', 'false')
  filters.uploaded_file_ids.forEach((fileId) => params.append('uploaded_file_ids', String(fileId)))
  return params
}

function money(value: string | number) {
  return `¥ ${Number(value || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function isIncome(row: TransactionRow) {
  return row.type === '收入' || row.type === legacyIncomeType
}

function transactionTypeText(row: TransactionRow) {
  if (isIncome(row)) return '收入'
  if (row.type === '支出') return '支出'
  return row.type || '-'
}

function categoryName(row: TransactionRow) {
  const categoryId = row.final_category_id ?? row.auto_category_id
  if (categoryId == null) return '未分类'
  return categoryMap.value.get(categoryId) ?? `分类 ${categoryId}`
}

function providerText(provider: string | null) {
  const map: Record<string, string> = {
    rule: '规则',
    composite: '混合',
    openai_compatible_api: '外部模型',
    local_model: '本地模型',
  }
  return provider ? map[provider] ?? provider : '未分类'
}

function formatDate(value: string) {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function formatImportFileLabel(file: ImportFileOption) {
  const platform = file.platform || '未知平台'
  return `批次 ${file.batch_id} / ${platform} / ${file.filename}`
}

async function loadCategories() {
  const { data } = await api.get<Category[]>('/categories')
  categories.value = data
}

async function loadImportFiles() {
  const { data } = await api.get<ImportFileOption[]>('/imports/files')
  importFiles.value = data
}

async function loadTransactions() {
  loading.value = true
  try {
    const { data } = await api.get<TransactionListResponse>('/transactions', { params: buildTransactionParams() })
    transactions.value = data.items
    total.value = data.total
  } catch {
    ElMessage.error('交易列表加载失败，请检查筛选条件或后端服务状态')
  } finally {
    loading.value = false
  }
}

async function applyFilters() {
  filters.page = 1
  await loadTransactions()
}

async function resetFilters() {
  filters.page = 1
  filters.search = ''
  filters.platform = ''
  filters.category_id = undefined
  filters.uploaded_file_ids = []
  filters.date_range = []
  filters.review_status = ''
  await loadTransactions()
}

function openDetail(row: TransactionRow) {
  selectedRow.value = row
  detailDrawerVisible.value = true
}

function goReview() {
  router.push('/review')
}

onMounted(async () => {
  await Promise.all([loadCategories(), loadImportFiles(), loadTransactions()])
})
</script>

<template>
  <div class="page-shell">
    <div class="page-heading">
      <div>
        <h1>交易列表</h1>
        <p>按日期、来源、分类、导入文件和商家关键词筛选交易，查看分类来源与模型理由。</p>
      </div>
      <el-button :icon="Refresh" @click="loadTransactions">刷新</el-button>
    </div>

    <section class="panel card">
      <div class="toolbar-grid filter-grid">
        <el-date-picker
          v-model="filters.date_range"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DDTHH:mm:ss"
        />
        <el-select v-model="filters.platform" clearable placeholder="来源平台">
          <el-option label="全部平台" value="" />
          <el-option label="微信账单" value="WeChat" />
          <el-option label="支付宝账单" value="Alipay" />
        </el-select>
        <el-select v-model="filters.category_id" clearable filterable placeholder="分类">
          <el-option v-for="category in categories" :key="category.id" :label="category.name" :value="category.id" />
        </el-select>
        <el-select
          v-model="filters.uploaded_file_ids"
          multiple
          collapse-tags
          collapse-tags-tooltip
          clearable
          filterable
          placeholder="导入文件"
        >
          <el-option v-for="file in importFiles" :key="file.id" :label="formatImportFileLabel(file)" :value="file.id" />
        </el-select>
        <el-select v-model="filters.review_status" clearable placeholder="状态">
          <el-option label="待校正" value="needs_review" />
          <el-option label="已确认" value="confirmed" />
        </el-select>
        <el-input v-model="filters.search" :prefix-icon="Search" clearable placeholder="搜索商家 / 商品 / 备注" />
        <el-button type="primary" @click="applyFilters">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>
    </section>

    <section class="panel card">
      <el-table :data="transactions" v-loading="loading" empty-text="暂无交易数据">
        <el-table-column label="日期" min-width="170">
          <template #default="{ row }">{{ formatDate(row.occurred_at) }}</template>
        </el-table-column>
        <el-table-column prop="platform" label="来源" width="110" />
        <el-table-column prop="merchant" label="商家" min-width="160" show-overflow-tooltip />
        <el-table-column label="分类" width="140">
          <template #default="{ row }">
            <el-tag :type="row.needs_review ? 'warning' : 'success'" effect="light">{{ categoryName(row) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="金额" width="130" align="right">
          <template #default="{ row }">
            <span class="amount" :class="isIncome(row) ? 'positive' : 'negative'">
              {{ isIncome(row) ? '+' : '-' }}{{ money(row.amount) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.needs_review ? 'warning' : 'success'" class="status-tag">
              {{ row.needs_review ? '待校正' : '已确认' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="分类来源" width="130">
          <template #default="{ row }">{{ providerText(row.auto_provider) }}</template>
        </el-table-column>
        <el-table-column prop="auto_reason" label="分类理由" min-width="220" show-overflow-tooltip />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button :icon="View" circle text @click="openDetail(row)" />
            <el-button :icon="EditPen" circle text type="primary" @click="goReview" />
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-row">
        <el-pagination
          background
          layout="sizes, prev, pager, next, total"
          :page-sizes="[10, 20, 50, 100]"
          :current-page="filters.page"
          :page-size="filters.page_size"
          :total="total"
          @size-change="(size:number) => { filters.page_size = size; filters.page = 1; loadTransactions() }"
          @current-change="(page:number) => { filters.page = page; loadTransactions() }"
        />
      </div>
    </section>

    <el-drawer v-model="detailDrawerVisible" title="交易详情" size="420px">
      <div v-if="selectedRow" class="detail-stack">
        <div class="detail-amount" :class="isIncome(selectedRow) ? 'positive' : 'negative'">
          {{ isIncome(selectedRow) ? '+' : '-' }}{{ money(selectedRow.amount) }}
        </div>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="交易类型">{{ transactionTypeText(selectedRow) }}</el-descriptions-item>
          <el-descriptions-item label="交易时间">{{ formatDate(selectedRow.occurred_at) }}</el-descriptions-item>
          <el-descriptions-item label="来源平台">{{ selectedRow.platform }}</el-descriptions-item>
          <el-descriptions-item label="商家">{{ selectedRow.merchant || '-' }}</el-descriptions-item>
          <el-descriptions-item label="商品 / 摘要">{{ selectedRow.item || selectedRow.note || '-' }}</el-descriptions-item>
          <el-descriptions-item label="当前分类">{{ categoryName(selectedRow) }}</el-descriptions-item>
          <el-descriptions-item label="分类来源">{{ providerText(selectedRow.auto_provider) }}</el-descriptions-item>
          <el-descriptions-item label="置信度">{{ selectedRow.auto_confidence || '-' }}</el-descriptions-item>
          <el-descriptions-item label="分类理由">{{ selectedRow.auto_reason || '-' }}</el-descriptions-item>
        </el-descriptions>
        <el-button type="primary" @click="goReview">前往分类校正</el-button>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.filter-grid {
  grid-template-columns: minmax(260px, 1.3fr) minmax(130px, 0.7fr) minmax(150px, 0.8fr) minmax(220px, 1.1fr) minmax(110px, 0.6fr) minmax(220px, 1fr) 88px 78px;
}

.pagination-row {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.detail-stack {
  display: grid;
  gap: 18px;
}

.detail-amount {
  font-size: 32px;
  font-weight: 800;
}

@media (max-width: 1320px) {
  .filter-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .filter-grid {
    grid-template-columns: 1fr;
  }

  .pagination-row {
    justify-content: flex-start;
    overflow-x: auto;
  }
}
</style>
