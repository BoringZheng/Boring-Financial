<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api/client'

const loading = ref(false)
const rows = ref<any[]>([])
const categories = ref<any[]>([])
const reviewDialogVisible = ref(false)
const submittingReview = ref(false)
const reviewingRow = ref<any | null>(null)
const reviewForm = reactive({
  categoryId: undefined as number | undefined,
})

const categoryOptions = computed(() => categories.value.filter((category) => category.is_active))

async function loadCategories() {
  const { data } = await api.get('/categories')
  categories.value = data
}

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/transactions', { params: { needs_review: true, page_size: 100 } })
    rows.value = data.items
  } finally {
    loading.value = false
  }
}

function categoryNameById(categoryId: number | null | undefined) {
  if (categoryId == null) return '未分类'
  return categories.value.find((category) => category.id === categoryId)?.name ?? `分类 ${categoryId}`
}

async function reclassify(provider: string) {
  if (!rows.value.length) return
  const { data } = await api.post('/classification/reclassify', {
    transaction_ids: rows.value.map((row) => row.id),
    provider,
  })
  if (data.failed) {
    ElMessage.warning(`重分类完成，成功 ${data.processed} 条，失败 ${data.failed} 条`)
  } else {
    ElMessage.success(`已完成重分类，共处理 ${data.processed} 条`)
  }
  await load()
}

function openReviewDialog(row: any) {
  reviewingRow.value = row
  reviewForm.categoryId = row.final_category_id ?? row.auto_category_id ?? undefined
  reviewDialogVisible.value = true
}

async function submitManualReview() {
  if (!reviewingRow.value || reviewForm.categoryId == null) {
    ElMessage.warning('请选择人工确认后的分类')
    return
  }
  submittingReview.value = true
  try {
    await api.patch(`/transactions/${reviewingRow.value.id}/category`, {
      category_id: reviewForm.categoryId,
      mark_reviewed: true,
    })
    ElMessage.success('人工复核已保存')
    reviewDialogVisible.value = false
    reviewingRow.value = null
    reviewForm.categoryId = undefined
    await load()
  } catch {
    ElMessage.error('人工复核保存失败，请稍后重试')
  } finally {
    submittingReview.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadCategories(), load()])
})
</script>

<template>
  <div class="page-shell">
    <div class="page-title">
      <div>
        <h1>分类校正工作台</h1>
        <p>展示规则未命中、低置信度或需要人工复核的交易。</p>
      </div>
      <div class="actions">
        <el-button @click="reclassify('openai_compatible_api')">用外部模型重分类</el-button>
        <el-button @click="reclassify('rule')">仅按规则重分类</el-button>
      </div>
    </div>
    <section class="panel table-card">
      <el-table :data="rows" v-loading="loading" empty-text="当前没有待人工复核的交易">
        <el-table-column prop="occurred_at" label="时间" width="180" />
        <el-table-column prop="merchant" label="商户" min-width="160" />
        <el-table-column prop="item" label="摘要" min-width="180" />
        <el-table-column prop="amount" label="金额" width="120" />
        <el-table-column prop="auto_provider" label="来源" width="140" />
        <el-table-column prop="auto_confidence" label="置信度" width="120" />
        <el-table-column label="建议分类" width="160">
          <template #default="{ row }">
            {{ categoryNameById(row.auto_category_id) }}
          </template>
        </el-table-column>
        <el-table-column prop="auto_reason" label="理由" min-width="220" />
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button type="primary" text @click="openReviewDialog(row)">人工复核</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="reviewDialogVisible" title="人工复核" width="520px">
      <div v-if="reviewingRow" class="review-dialog">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="时间">{{ reviewingRow.occurred_at }}</el-descriptions-item>
          <el-descriptions-item label="商户">{{ reviewingRow.merchant || '无' }}</el-descriptions-item>
          <el-descriptions-item label="摘要">{{ reviewingRow.item || reviewingRow.note || '无' }}</el-descriptions-item>
          <el-descriptions-item label="金额">{{ reviewingRow.amount }}</el-descriptions-item>
          <el-descriptions-item label="模型建议">
            {{ categoryNameById(reviewingRow.auto_category_id) }}
          </el-descriptions-item>
          <el-descriptions-item label="分类理由">
            {{ reviewingRow.auto_reason || '无' }}
          </el-descriptions-item>
        </el-descriptions>

        <el-form label-position="top" class="review-form">
          <el-form-item label="人工确认分类">
            <el-select v-model="reviewForm.categoryId" filterable placeholder="请选择分类" style="width: 100%">
              <el-option
                v-for="category in categoryOptions"
                :key="category.id"
                :label="category.name"
                :value="category.id"
              />
            </el-select>
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="reviewDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submittingReview" @click="submitManualReview">确认复核</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.actions {
  display: flex;
  gap: 12px;
}

.table-card {
  padding: 20px;
}

.review-dialog {
  display: grid;
  gap: 16px;
}

.review-form {
  margin-top: 8px;
}
</style>
