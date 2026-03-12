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

const loading = ref(false)
const transactions = ref<any[]>([])
const total = ref(0)
const categories = ref<any[]>([])
const importFiles = ref<ImportFileOption[]>([])
const filters = reactive({
  page: 1,
  page_size: 20,
  search: '',
  platform: '',
  category_id: undefined as number | undefined,
  uploaded_file_ids: [] as number[],
  date_from: null as string | null,
  date_to: null as string | null,
})

function buildTransactionParams() {
  const params = new URLSearchParams()
  params.append('page', String(filters.page))
  params.append('page_size', String(filters.page_size))

  if (filters.search) {
    params.append('search', filters.search)
  }
  if (filters.platform) {
    params.append('platform', filters.platform)
  }
  if (filters.category_id !== undefined) {
    params.append('category_id', String(filters.category_id))
  }
  if (filters.date_from) {
    params.append('date_from', filters.date_from)
  }
  if (filters.date_to) {
    params.append('date_to', filters.date_to)
  }
  filters.uploaded_file_ids.forEach((fileId) => {
    params.append('uploaded_file_ids', String(fileId))
  })
  return params
}

function formatImportFileLabel(file: ImportFileOption) {
  const platform = file.platform || '未知平台'
  return `[批次 ${file.batch_id}] ${platform} - ${file.filename}`
}

async function loadCategories() {
  const { data } = await api.get('/categories')
  categories.value = data
}

async function loadImportFiles() {
  const { data } = await api.get('/imports/files')
  importFiles.value = data
}

async function loadTransactions() {
  loading.value = true
  try {
    const { data } = await api.get('/transactions', { params: buildTransactionParams() })
    transactions.value = data.items
    total.value = data.total
  } catch {
    ElMessage.error('交易列表加载失败，请检查筛选条件或后端服务')
  } finally {
    loading.value = false
  }
}

async function applyFilters() {
  filters.page = 1
  await loadTransactions()
}

onMounted(async () => {
  await Promise.all([loadCategories(), loadImportFiles(), loadTransactions()])
})
</script>

<template>
  <div class="page-shell">
    <div class="page-title">
      <div>
        <h1>交易列表</h1>
        <p>支持按平台、日期、分类、导入文件和搜索词筛选，并查看自动分类来源和理由。</p>
      </div>
    </div>
    <section class="panel table-card">
      <div class="toolbar toolbar-grid">
        <el-input v-model="filters.search" placeholder="搜索 merchant / item / note" clearable />
        <el-select v-model="filters.platform" clearable placeholder="平台">
          <el-option label="WeChat" value="WeChat" />
          <el-option label="Alipay" value="Alipay" />
        </el-select>
        <el-select v-model="filters.category_id" clearable placeholder="分类">
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
          <el-option
            v-for="file in importFiles"
            :key="file.id"
            :label="formatImportFileLabel(file)"
            :value="file.id"
          />
        </el-select>
        <el-date-picker v-model="filters.date_from" type="date" placeholder="开始日期" value-format="YYYY-MM-DDTHH:mm:ss" />
        <el-date-picker v-model="filters.date_to" type="date" placeholder="结束日期" value-format="YYYY-MM-DDTHH:mm:ss" />
        <el-button type="primary" @click="applyFilters">查询</el-button>
      </div>
      <el-table :data="transactions" v-loading="loading">
        <el-table-column prop="occurred_at" label="时间" width="180" />
        <el-table-column prop="platform" label="平台" width="120" />
        <el-table-column prop="merchant" label="商户" min-width="160" />
        <el-table-column prop="item" label="商品/摘要" min-width="180" />
        <el-table-column prop="amount" label="金额" width="120" />
        <el-table-column prop="auto_provider" label="分类来源" width="140" />
        <el-table-column prop="auto_reason" label="分类理由" min-width="220" />
      </el-table>
      <div class="pagination-row">
        <el-pagination
          background
          layout="prev, pager, next, total"
          :current-page="filters.page"
          :page-size="filters.page_size"
          :total="total"
          @current-change="(page:number) => { filters.page = page; loadTransactions() }"
        />
      </div>
    </section>
  </div>
</template>

<style scoped>
.table-card {
  padding: 20px;
}

.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.toolbar-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
}

.pagination-row {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 1200px) {
  .toolbar-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
