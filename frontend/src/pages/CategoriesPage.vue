<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api/client'

const categories = ref<any[]>([])
const form = reactive({ name: '', description: '' })

async function load() {
  const { data } = await api.get('/categories')
  categories.value = data
}

async function createCategory() {
  await api.post('/categories', form)
  form.name = ''
  form.description = ''
  ElMessage.success('分类已创建')
  await load()
}

onMounted(load)
</script>

<template>
  <div class="page-shell">
    <div class="page-title">
      <div>
        <h1>分类管理</h1>
        <p>系统分类与用户自定义分类共存，便于后续模型映射与人工校正。</p>
      </div>
    </div>
    <section class="panel table-card">
      <div class="toolbar">
        <el-input v-model="form.name" placeholder="新增分类名称" />
        <el-input v-model="form.description" placeholder="描述（可选）" />
        <el-button type="primary" @click="createCategory">新增分类</el-button>
      </div>
      <el-table :data="categories">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="description" label="描述" />
        <el-table-column prop="is_system" label="系统分类" width="120" />
        <el-table-column prop="is_active" label="启用" width="100" />
      </el-table>
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
</style>
