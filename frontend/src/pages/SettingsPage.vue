<script setup lang="ts">
import { reactive } from 'vue'

const settingsForm = reactive({
  provider: 'composite',
  lowConfidenceThreshold: 0.75,
  openaiModel: 'gpt-4.1-mini',
  localModel: 'Qwen2.5-7B-Instruct',
})
</script>

<template>
  <div class="page-shell">
    <div class="page-title">
      <div>
        <h1>系统设置</h1>
        <p>这里聚焦分类 provider、阈值和模型切换的课程演示配置。</p>
      </div>
    </div>
    <section class="panel settings-card">
      <el-form label-position="top">
        <el-form-item label="分类策略">
          <el-select v-model="settingsForm.provider">
            <el-option label="composite" value="composite" />
            <el-option label="openai_compatible_api" value="openai_compatible_api" />
            <el-option label="local_model" value="local_model" />
            <el-option label="rule" value="rule" />
          </el-select>
        </el-form-item>
        <el-form-item label="低置信度阈值">
          <el-slider v-model="settingsForm.lowConfidenceThreshold" :min="0.1" :max="1" :step="0.05" />
        </el-form-item>
        <el-form-item label="外部模型">
          <el-input v-model="settingsForm.openaiModel" />
        </el-form-item>
        <el-form-item label="本地模型">
          <el-input v-model="settingsForm.localModel" />
        </el-form-item>
      </el-form>
    </section>
  </div>
</template>

<style scoped>
.settings-card {
  padding: 20px;
  max-width: 700px;
}
</style>
