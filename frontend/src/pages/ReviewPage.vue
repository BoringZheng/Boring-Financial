<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Check, Close, MagicStick, Refresh, Select } from '@element-plus/icons-vue'
import api from '../api/client'

type Category = {
  id: number
  name: string
  is_active: boolean
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

const loading = ref(false)
const rows = ref<TransactionRow[]>([])
const categories = ref<Category[]>([])
const selectedId = ref<number | null>(null)
const submittingReview = ref(false)
const reclassifying = ref(false)
const route = useRoute()
const router = useRouter()
const reviewForm = reactive({
  categoryId: undefined as number | undefined,
})

const categoryOptions = computed(() => categories.value.filter((category) => category.is_active))
const categoryMap = computed(() => new Map(categories.value.map((category) => [category.id, category.name])))
const selectedRow = computed(() => rows.value.find((row) => row.id === selectedId.value) ?? rows.value[0] ?? null)
const legacyIncomeType = String.fromCharCode(0x93c0, 0x8dfa, 0x53c6)

watch(selectedRow, (row) => {
  reviewForm.categoryId = row?.final_category_id ?? row?.auto_category_id ?? undefined
})

function money(value: string | number) {
  return `¥ ${Number(value || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function isIncome(row: TransactionRow) {
  return row.type === '收入' || row.type === legacyIncomeType
}

function formatDate(value: string) {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function categoryNameById(categoryId: number | null | undefined) {
  if (categoryId == null) return '未分类'
  return categoryMap.value.get(categoryId) ?? `分类 ${categoryId}`
}

function providerText(provider: string | null) {
  const map: Record<string, string> = {
    rule: '规则',
    composite: '混合分类',
    openai_compatible_api: '外部模型',
    local_model: '本地模型',
    retry_queue: '等待重试',
  }
  return provider ? map[provider] ?? provider : '未分类'
}

function confidencePercent(value: string | null) {
  if (!value) return 0
  const numberValue = Number(value)
  if (Number.isNaN(numberValue)) return 0
  return Math.round(Math.min(numberValue, 1) * 100)
}

async function loadCategories() {
  const { data } = await api.get<Category[]>('/categories')
  categories.value = data
}

async function load() {
  loading.value = true
  try {
    const { data } = await api.get<TransactionListResponse>('/transactions', { params: { needs_review: true, page_size: 100 } })
    rows.value = data.items

    const targetId = route.query.id
    if (targetId != null) {
      const numericId = Number(targetId)
      if (!Number.isNaN(numericId) && !rows.value.some((row) => row.id === numericId)) {
        try {
          const { data: single } = await api.get<TransactionRow>(`/transactions/${numericId}`)
          rows.value.unshift(single)
        } catch {
          // transaction not found or inaccessible — ignore
        }
      }
      selectedId.value = numericId
    } else if (!rows.value.some((row) => row.id === selectedId.value)) {
      selectedId.value = rows.value[0]?.id ?? null
    }
  } finally {
    loading.value = false
  }
}

async function reclassify(provider: string) {
  if (!rows.value.length) {
    ElMessage.info('当前没有待校正交易')
    return
  }
  reclassifying.value = true
  try {
    const { data } = await api.post<{ processed: number; failed: number }>('/classification/reclassify', {
      transaction_ids: rows.value.map((row) => row.id),
      provider,
    })
    if (data.failed) {
      ElMessage.warning(`重分类完成，成功 ${data.processed} 笔，失败 ${data.failed} 笔`)
    } else {
      ElMessage.success(`重分类完成，共处理 ${data.processed} 笔`)
    }
    await load()
  } finally {
    reclassifying.value = false
  }
}

async function confirmCategory(categoryId: number | undefined, successMessage: string) {
  if (!selectedRow.value || categoryId == null) {
    ElMessage.warning('请先选择要确认的分类')
    return
  }
  submittingReview.value = true
  try {
    await api.patch(`/transactions/${selectedRow.value.id}/category`, {
      category_id: categoryId,
      mark_reviewed: true,
    })
    ElMessage.success(successMessage)
    if (route.query.id != null) {
      router.replace({ query: {} })
    }
    await load()
  } catch {
    ElMessage.error('人工复核保存失败，请稍后重试')
  } finally {
    submittingReview.value = false
  }
}

function skipCurrent() {
  if (!rows.value.length) return
  const currentIndex = rows.value.findIndex((row) => row.id === selectedId.value)
  const next = rows.value[currentIndex + 1] ?? rows.value[0]
  selectedId.value = next?.id ?? null
}

onMounted(async () => {
  await Promise.all([loadCategories(), load()])
})
</script>

<template>
  <div class="page-shell">
    <div class="page-heading">
      <div>
        <h1>分类校正工作台</h1>
        <p>集中处理低置信度或规则未命中的交易，展示模型建议、分类理由并完成人工确认。</p>
      </div>
      <div class="heading-actions">
        <el-button :icon="MagicStick" :loading="reclassifying" @click="reclassify('openai_compatible_api')">外部模型重分类</el-button>
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>

    <section class="workbench">
      <aside class="panel card review-list">
        <div class="section-title">
          <h2>待校正交易</h2>
          <el-tag type="warning">{{ rows.length }} 笔</el-tag>
        </div>
        <div v-loading="loading" class="review-items">
          <button
            v-for="row in rows"
            :key="row.id"
            type="button"
            class="review-item"
            :class="{ active: selectedRow?.id === row.id }"
            @click="selectedId = row.id"
          >
            <span>
              <strong>{{ row.merchant || row.item || '未知商家' }}</strong>
              <small>{{ formatDate(row.occurred_at) }}</small>
            </span>
            <span class="item-side">
              <b :class="isIncome(row) ? 'positive' : 'negative'">{{ isIncome(row) ? '+' : '-' }}{{ money(row.amount) }}</b>
              <small>{{ confidencePercent(row.auto_confidence) }}%</small>
            </span>
          </button>
          <el-empty v-if="!rows.length && !loading" description="当前没有待校正交易" :image-size="92" />
        </div>
      </aside>

      <main class="panel card review-detail">
        <template v-if="selectedRow">
          <div class="detail-head">
            <div>
              <div class="muted">交易金额</div>
              <div class="detail-amount" :class="isIncome(selectedRow) ? 'positive' : 'negative'">
                {{ isIncome(selectedRow) ? '+' : '-' }}{{ money(selectedRow.amount) }}
              </div>
            </div>
            <el-tag type="warning">待校正</el-tag>
          </div>

          <div class="detail-grid">
            <div class="info-card">
              <span>交易时间</span>
              <strong>{{ formatDate(selectedRow.occurred_at) }}</strong>
            </div>
            <div class="info-card">
              <span>来源平台</span>
              <strong>{{ selectedRow.platform }}</strong>
            </div>
            <div class="info-card">
              <span>商家</span>
              <strong>{{ selectedRow.merchant || '未知商家' }}</strong>
            </div>
            <div class="info-card">
              <span>分类来源</span>
              <strong>{{ providerText(selectedRow.auto_provider) }}</strong>
            </div>
          </div>

          <section class="suggestion-box">
            <div class="section-title">
              <h2>模型建议</h2>
              <el-progress :percentage="confidencePercent(selectedRow.auto_confidence)" :stroke-width="10" class="confidence" />
            </div>
            <div class="suggestion-category">{{ categoryNameById(selectedRow.auto_category_id) }}</div>
            <p>{{ selectedRow.auto_reason || '暂无分类理由。' }}</p>
          </section>

          <section class="correction-box">
            <el-form label-position="top">
              <el-form-item label="校正后分类">
                <el-select v-model="reviewForm.categoryId" filterable placeholder="请选择确认后的分类">
                  <el-option v-for="category in categoryOptions" :key="category.id" :label="category.name" :value="category.id" />
                </el-select>
              </el-form-item>
            </el-form>
            <div class="review-actions">
              <el-button
                type="primary"
                :icon="Check"
                :loading="submittingReview"
                @click="confirmCategory(selectedRow.auto_category_id ?? undefined, '已按模型建议确认')"
              >
                通过并确认
              </el-button>
              <el-button :icon="Select" :loading="submittingReview" @click="confirmCategory(reviewForm.categoryId, '修改后的分类已确认')">
                修改后确认
              </el-button>
              <el-button :icon="Close" @click="skipCurrent">跳过此条</el-button>
            </div>
          </section>
        </template>
        <el-empty v-else description="请选择一笔待校正交易" :image-size="120" />
      </main>
    </section>
  </div>
</template>

<style scoped>
.heading-actions {
  display: flex;
  gap: 10px;
}

.workbench {
  display: grid;
  grid-template-columns: 360px minmax(0, 1fr);
  gap: 16px;
}

.review-list {
  min-height: 620px;
}

.review-items {
  display: grid;
  gap: 10px;
}

.review-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  width: 100%;
  padding: 12px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: #fff;
  color: var(--color-text);
  text-align: left;
  cursor: pointer;
}

.review-item.active {
  border-color: var(--color-primary);
  background: #f0fdfa;
}

.review-item strong,
.review-item small,
.item-side b {
  display: block;
}

.review-item small {
  margin-top: 5px;
  color: var(--color-muted);
  font-size: 12px;
}

.item-side {
  text-align: right;
}

.review-detail {
  min-height: 620px;
  display: grid;
  align-content: start;
  gap: 18px;
}

.detail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.detail-amount {
  margin-top: 6px;
  font-size: 34px;
  font-weight: 800;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.info-card {
  padding: 14px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: #f8fafc;
}

.info-card span,
.info-card strong {
  display: block;
}

.info-card span {
  color: var(--color-muted);
  font-size: 12px;
}

.info-card strong {
  margin-top: 7px;
  font-weight: 700;
}

.suggestion-box,
.correction-box {
  padding: 18px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
}

.confidence {
  width: 170px;
}

.suggestion-category {
  display: inline-flex;
  margin-bottom: 10px;
  padding: 7px 12px;
  border-radius: 999px;
  background: #e6f7f3;
  color: var(--color-primary);
  font-weight: 700;
}

.suggestion-box p {
  margin: 0;
  color: var(--color-muted);
  line-height: 1.7;
}

.correction-box :deep(.el-select) {
  width: 100%;
}

.review-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

@media (max-width: 1100px) {
  .workbench,
  .detail-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 680px) {
  .heading-actions,
  .review-actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
