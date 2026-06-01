<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import api from '../api/client'

type Category = {
  id: number
  user_id: number | null
  parent_id: number | null
  name: string
  description: string | null
  is_system: boolean
  is_active: boolean
}

const loading = ref(false)
const creating = ref(false)
const categories = ref<Category[]>([])
const form = reactive({ name: '', description: '' })

const systemCount = computed(() => categories.value.filter((category) => category.is_system).length)
const customCount = computed(() => categories.value.filter((category) => !category.is_system).length)
const activeCount = computed(() => categories.value.filter((category) => category.is_active).length)

async function load() {
  loading.value = true
  try {
    const { data } = await api.get<Category[]>('/categories')
    categories.value = data
  } finally {
    loading.value = false
  }
}

async function createCategory() {
  if (!form.name.trim()) {
    ElMessage.warning('请输入分类名称')
    return
  }
  creating.value = true
  try {
    await api.post('/categories', {
      name: form.name.trim(),
      description: form.description.trim() || null,
    })
    form.name = ''
    form.description = ''
    ElMessage.success('分类已创建')
    await load()
  } catch {
    ElMessage.error('分类创建失败，请稍后重试')
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <div class="page-shell">
    <div class="page-heading">
      <div>
        <h1>分类管理</h1>
        <p>系统分类与用户自定义分类共存，为自动分类、人工校正和报表统计提供统一口径。</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
    </div>

    <div class="metric-grid category-metrics">
      <section class="panel metric-card">
        <div class="metric-label">系统分类</div>
        <div class="metric-value">{{ systemCount }}</div>
        <div class="metric-foot">内置分类体系</div>
      </section>
      <section class="panel metric-card">
        <div class="metric-label">自定义分类</div>
        <div class="metric-value">{{ customCount }}</div>
        <div class="metric-foot">用户扩展分类</div>
      </section>
      <section class="panel metric-card">
        <div class="metric-label">启用分类</div>
        <div class="metric-value">{{ activeCount }}</div>
        <div class="metric-foot">参与筛选与校正</div>
      </section>
    </div>

    <section class="panel card create-card">
      <div class="section-title">
        <h2>新增分类</h2>
        <span>用于补充课程 demo 中的个性化消费场景</span>
      </div>
      <div class="toolbar-grid create-grid">
        <el-input v-model="form.name" placeholder="分类名称，例如：宠物、学习、旅行" />
        <el-input v-model="form.description" placeholder="描述（可选）" />
        <el-button type="primary" :icon="Plus" :loading="creating" @click="createCategory">新增分类</el-button>
      </div>
    </section>

    <section class="panel card">
      <div class="section-title">
        <h2>分类列表</h2>
        <span>共 {{ categories.length }} 个分类</span>
      </div>
      <el-table :data="categories" v-loading="loading" empty-text="暂无分类">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column prop="description" label="描述" min-width="240">
          <template #default="{ row }">{{ row.description || '-' }}</template>
        </el-table-column>
        <el-table-column label="类型" width="130">
          <template #default="{ row }">
            <el-tag :type="row.is_system ? 'info' : 'success'">{{ row.is_system ? '系统分类' : '自定义分类' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="启用状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" class="status-tag">{{ row.is_active ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>

<style scoped>
.category-metrics {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.create-grid {
  grid-template-columns: minmax(180px, 0.8fr) minmax(260px, 1.4fr) 120px;
}

@media (max-width: 900px) {
  .category-metrics,
  .create-grid {
    grid-template-columns: 1fr;
  }
}
</style>
