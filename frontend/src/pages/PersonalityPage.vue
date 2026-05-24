<script setup lang="ts">
import * as echarts from 'echarts'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { Refresh, Warning } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '../api/client'

// ---------------------------------------------------------------------------
// types
// ---------------------------------------------------------------------------
type DimensionScore = {
  name: string
  value: number
  side: string
  label: string
  theory_ref: string
  interpretation: string
}

type PersonalityProfile = {
  code: string
  name: string
  tagline: string
  quote: string
  match_percent: number
  secondary_code: string
  secondary_name: string
  dimensions: DimensionScore[]
}

type HealthDimension = {
  name: string
  value: number
  label: string
}

type FinancialHealth = {
  total_score: number
  grade: string
  dimensions: HealthDimension[]
  suggestions: string[]
}

type PersonalityResponse = {
  personality: PersonalityProfile
  financial_health: FinancialHealth
  has_data: boolean
}

type QuizOption = {
  value: number
  text: string
}

type QuizQuestion = {
  id: number
  dimension: string
  text: string
  options: QuizOption[]
}

type BiggestGap = {
  dimension: string
  self_score: number
  data_score: number
  gap: number
  analysis: string
  theory_ref: string
}

type QuizComparison = {
  cosine_similarity: number
  biggest_gap: BiggestGap
  bias_analysis: string
}

type QuizResultResponse = {
  self_assessment: { dimensions: Record<string, number> }
  data_profile: PersonalityProfile
  comparison: QuizComparison
}

// ---------------------------------------------------------------------------
// state
// ---------------------------------------------------------------------------
const activeTab = ref('profile')
const loading = ref(false)
const profile = ref<PersonalityProfile | null>(null)
const health = ref<FinancialHealth | null>(null)
const hasData = ref(true)

// quiz
const questions = ref<QuizQuestion[]>([])
const answers = reactive<Record<number, number>>({})
const quizResult = ref<QuizResultResponse | null>(null)
const submitting = ref(false)

// chart refs
const profileRadarRef = ref<HTMLDivElement | null>(null)
const dualRadarRef = ref<HTMLDivElement | null>(null)
const healthRadarRef = ref<HTMLDivElement | null>(null)

// chart instances
let profileRadarChart: echarts.ECharts | null = null
let dualRadarChart: echarts.ECharts | null = null
let healthRadarChart: echarts.ECharts | null = null

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------
function dimensionLabel(dim: DimensionScore): string {
  const labels: Record<string, string> = {
    time_preference: '现时偏好',
    mental_accounting: '心理账户',
    conspicuous_consumption: '炫耀性消费',
    openness: '消费开放性',
  }
  return labels[dim.name] ?? dim.name
}

function healthDimensionLabel(hd: HealthDimension): string {
  return hd.label ?? hd.name
}

function gradeColor(grade: string): string {
  const colors: Record<string, string> = {
    S: '#F59E0B',
    A: '#00A884',
    B: '#3B82F6',
    C: '#F97316',
    D: '#EF4444',
  }
  return colors[grade] ?? '#6B7280'
}

function gradeText(grade: string): string {
  const texts: Record<string, string> = {
    S: '财务自由的种子选手',
    A: '财务状况良好',
    B: '有一定优化空间',
    C: '需要注意',
    D: '需要重新审视消费习惯',
  }
  return texts[grade] ?? ''
}

// ---------------------------------------------------------------------------
// data loading
// ---------------------------------------------------------------------------
async function loadProfile() {
  loading.value = true
  try {
    const { data } = await api.get<PersonalityResponse>('/personality/profile')
    profile.value = data.personality
    health.value = data.financial_health
    hasData.value = data.has_data
    await nextTick()
    renderCharts()
  } catch (err: any) {
    const msg = err?.response?.data?.detail ?? err?.message ?? '加载失败'
    ElMessage.error(msg)
    hasData.value = false
  } finally {
    loading.value = false
  }
}

async function loadQuiz() {
  if (questions.value.length > 0) return
  try {
    const { data } = await api.get<QuizQuestion[]>('/personality/quiz')
    questions.value = data
    // initialize answers
    for (const q of data) {
      if (!(q.id in answers)) {
        answers[q.id] = 0
      }
    }
  } catch (err: any) {
    const msg = err?.response?.data?.detail ?? err?.message ?? '加载失败'
    ElMessage.error(msg)
  }
}

async function submitQuizAnswers() {
  const answerList = questions.value.map((q) => answers[q.id] || 0)
  if (answerList.some((a) => a < 1 || a > 4)) {
    ElMessage.warning('请完成全部 10 道题后再提交')
    return
  }
  submitting.value = true
  try {
    const { data } = await api.post<QuizResultResponse>('/personality/quiz/result', { answers: answerList })
    quizResult.value = data
    await nextTick()
    initCharts()
    renderDualRadar()
  } catch (err: any) {
    const msg = err?.response?.data?.detail ?? err?.message ?? '提交失败'
    ElMessage.error(msg)
  } finally {
    submitting.value = false
  }
}

function resetQuiz() {
  quizResult.value = null
  for (const q of questions.value) {
    answers[q.id] = 0
  }
}

// ---------------------------------------------------------------------------
// charts
// ---------------------------------------------------------------------------
function initCharts() {
  if (profileRadarRef.value && !profileRadarChart) {
    profileRadarChart = echarts.init(profileRadarRef.value)
  }
  if (dualRadarRef.value && !dualRadarChart) {
    dualRadarChart = echarts.init(dualRadarRef.value)
  }
  if (healthRadarRef.value && !healthRadarChart) {
    healthRadarChart = echarts.init(healthRadarRef.value)
  }
}

function resizeCharts() {
  profileRadarChart?.resize()
  dualRadarChart?.resize()
  healthRadarChart?.resize()
}

function wrapChartLabel(label: string): string {
  return label.length > 4 ? label.replace(/(.{4})/g, '$1\n').trim() : label
}

function renderCharts() {
  renderProfileRadar()
  renderHealthRadar()
}

function renderProfileRadar() {
  if (!profileRadarChart || !profile.value) return

  const dims = profile.value.dimensions
  profileRadarChart.setOption({
    color: ['#00A884'],
    tooltip: {},
    legend: { show: false },
    radar: {
      center: ['50%', '50%'],
      radius: '65%',
      indicator: dims.map((d) => ({ name: dimensionLabel(d), max: 100 })),
      axisName: { color: '#334155', fontSize: 13 },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: dims.map((d) => d.value),
            name: '数据人格',
            areaStyle: { color: 'rgba(0, 168, 132, 0.2)' },
            lineStyle: { color: '#00A884', width: 2 },
            itemStyle: { color: '#00A884' },
          },
        ],
      },
    ],
  })
}

function renderDualRadar() {
  if (!dualRadarChart || !quizResult.value) return

  const dimOrder = ['time_preference', 'mental_accounting', 'conspicuous_consumption', 'openness']
  const dimLabels = ['现时偏好', '心理账户', '炫耀性消费', '消费开放性']
  const dataDims = quizResult.value.data_profile.dimensions
  const selfDims = quizResult.value.self_assessment.dimensions

  dualRadarChart.setOption({
    color: ['#00A884', '#3B82F6'],
    tooltip: {},
    legend: { top: 0, right: 0, data: ['数据人格', '自评人格'] },
    radar: {
      center: ['50%', '55%'],
      radius: '60%',
      indicator: dimLabels.map((label) => ({ name: label, max: 100 })),
      axisName: { color: '#334155', fontSize: 13 },
    },
    series: [
      {
        type: 'radar',
        name: '数据人格',
        data: [
          {
            value: dimOrder.map((d) => dataDims.find((item) => item.name === d)?.value ?? 50),
            name: '数据人格',
            areaStyle: { color: 'rgba(0, 168, 132, 0.15)' },
            lineStyle: { color: '#00A884', width: 2 },
            itemStyle: { color: '#00A884' },
          },
        ],
      },
      {
        type: 'radar',
        name: '自评人格',
        data: [
          {
            value: dimOrder.map((d) => selfDims[d] ?? 50),
            name: '自评人格',
            areaStyle: { color: 'rgba(59, 130, 246, 0.1)' },
            lineStyle: { color: '#3B82F6', width: 2, type: 'dashed' },
            itemStyle: { color: '#3B82F6' },
          },
        ],
      },
    ],
  })
}

function renderHealthRadar() {
  if (!healthRadarChart || !health.value) return

  const dims = health.value.dimensions
  healthRadarChart.resize()
  healthRadarChart.setOption({
    color: ['#8B5CF6'],
    tooltip: {},
    legend: { show: false },
    radar: {
      center: ['50%', '53%'],
      radius: '54%',
      indicator: dims.map((d) => ({ name: wrapChartLabel(healthDimensionLabel(d)), max: 100 })),
      axisName: {
        color: '#334155',
        fontSize: 12,
        lineHeight: 16,
        width: 72,
        overflow: 'break',
      },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: dims.map((d) => d.value),
            name: '财务健康',
            areaStyle: { color: 'rgba(139, 92, 246, 0.2)' },
            lineStyle: { color: '#8B5CF6', width: 2 },
            itemStyle: { color: '#8B5CF6' },
          },
        ],
      },
    ],
  })
}

// ---------------------------------------------------------------------------
// lifecycle
// ---------------------------------------------------------------------------
const dimNames = ['time_preference', 'mental_accounting', 'conspicuous_consumption', 'openness']

onMounted(async () => {
  await loadProfile()
  await nextTick()
  initCharts()
  renderCharts()
  window.addEventListener('resize', resizeCharts)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  profileRadarChart?.dispose()
  dualRadarChart?.dispose()
  healthRadarChart?.dispose()
})

watch(activeTab, async (tab) => {
  await nextTick()
  if (tab === 'profile') {
    initCharts()
    resizeCharts()
    renderProfileRadar()
    renderHealthRadar()
  } else if (tab === 'quiz') {
    await loadQuiz()
    initCharts()
    resizeCharts()
    if (quizResult.value) renderDualRadar()
  } else if (tab === 'health') {
    initCharts()
    resizeCharts()
    renderHealthRadar()
  }
})
</script>

<template>
  <div class="page-shell">
    <div class="page-heading">
      <div>
        <h1>消费人格分析</h1>
        <p>基于消费行为数据，结合行为经济学理论，挖掘你的消费人格画像</p>
      </div>
      <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadProfile">刷新数据</el-button>
    </div>

    <el-tabs v-model="activeTab" class="personality-tabs">
      <!-- ================================================================ -->
      <!-- Tab 1: 人格画像 -->
      <!-- ================================================================ -->
      <el-tab-pane label="人格画像" name="profile">
        <el-empty v-if="!hasData && !loading" description="暂无足够交易数据，请先导入账单后再查看人格分析" :image-size="120" />

        <template v-if="profile && hasData">
          <!-- personality card -->
          <div class="personality-hero">
            <div class="personality-card">
              <div class="personality-code">{{ profile.code }}</div>
              <div class="personality-name">{{ profile.name }}</div>
              <div class="personality-tagline">{{ profile.tagline }}</div>
              <div style="margin-top: 16px">
                <div style="display: flex; justify-content: space-between; color: var(--color-muted); font-size: 12px; margin-bottom: 4px">
                  <span>匹配度</span>
                  <span>{{ Math.round(profile.match_percent) }}%</span>
                </div>
                <el-progress :percentage="Math.round(profile.match_percent)" :stroke-width="8" :show-text="false" />
              </div>
              <div class="personality-quote">"{{ profile.quote }}"</div>
              <div v-if="profile.secondary_code" class="secondary-type">
                次匹配人格：{{ profile.secondary_code }} {{ profile.secondary_name }}
              </div>
            </div>

            <div class="panel card">
              <div class="section-title"><h2>消费人格雷达</h2></div>
              <div ref="profileRadarRef" class="chart-shell"></div>
            </div>
          </div>

          <!-- dimension cards -->
          <div class="dimension-grid">
            <div v-for="dim in profile.dimensions" :key="dim.name" class="panel card dimension-card">
              <div class="dimension-header">
                <span class="dimension-name">{{ dimensionLabel(dim) }}</span>
                <span class="dimension-side" :class="dim.side">{{ dim.label }}</span>
              </div>
              <div class="dimension-score-row">
                <span class="dimension-score-value">{{ Math.round(dim.value) }}</span>
                <span class="dimension-score-unit">/ 100</span>
              </div>
              <el-progress :percentage="Math.round(dim.value)" :stroke-width="6" :show-text="false" />
              <div class="dimension-theory">{{ dim.theory_ref }}</div>
              <div class="dimension-interpretation">{{ dim.interpretation }}</div>
            </div>
          </div>
        </template>
      </el-tab-pane>

      <!-- ================================================================ -->
      <!-- Tab 2: 人格测试 -->
      <!-- ================================================================ -->
      <el-tab-pane label="人格测试" name="quiz">
        <!-- quiz questions (before submit) -->
        <template v-if="!quizResult">
          <div class="quiz-intro panel card">
            <p>以下 10 道题将帮助你了解自己对消费习惯的自我认知。请根据真实感受选择最符合的选项，完成后与数据驱动的人格画像进行对比。</p>
          </div>

          <div v-for="(q, idx) in questions" :key="q.id" class="panel card quiz-item">
            <div class="quiz-question-header">
              <span class="quiz-number">{{ idx + 1 }}</span>
              <div>
                <div class="quiz-question-text">{{ q.text }}</div>
                <div class="quiz-dimension-tag">
                  <el-tag size="small" type="info">{{ dimensionLabel({ name: q.dimension } as DimensionScore) }}</el-tag>
                </div>
              </div>
            </div>
            <el-radio-group v-model="answers[q.id]" class="quiz-options">
              <el-radio v-for="opt in q.options" :key="opt.value" :value="opt.value" class="quiz-option-item">
                {{ opt.text }}
              </el-radio>
            </el-radio-group>
          </div>

          <div class="quiz-actions">
            <el-button type="primary" size="large" :loading="submitting" @click="submitQuizAnswers">
              {{ submitting ? '分析中...' : '提交评估' }}
            </el-button>
          </div>
        </template>

        <!-- quiz result -->
        <template v-if="quizResult">
          <div class="quiz-result-header">
            <div class="panel card similarity-card">
              <div class="similarity-ring">
                <span class="similarity-value">{{ Math.round(quizResult.comparison.cosine_similarity * 100) }}%</span>
                <span class="similarity-label">认知一致度</span>
              </div>
              <div class="similarity-desc">
                你的自评人格与数据人格的余弦相似度为 {{ Math.round(quizResult.comparison.cosine_similarity * 100) }}%，认知偏差分析如下。
              </div>
            </div>

            <div class="panel card gap-card">
              <div class="gap-title">最大认知偏差</div>
              <div class="gap-dimension">{{ dimensionLabel({ name: quizResult.comparison.biggest_gap.dimension } as DimensionScore) }}</div>
              <div class="gap-scores">
                <div class="gap-score-item">
                  <span class="gap-score-label">自评</span>
                  <span class="gap-score-val">{{ Math.round(quizResult.comparison.biggest_gap.self_score) }}</span>
                </div>
                <div class="gap-score-divider"></div>
                <div class="gap-score-item">
                  <span class="gap-score-label">数据</span>
                  <span class="gap-score-val">{{ Math.round(quizResult.comparison.biggest_gap.data_score) }}</span>
                </div>
                <div class="gap-diff">差 {{ Math.round(quizResult.comparison.biggest_gap.gap) }} 分</div>
              </div>
              <div class="gap-theory">{{ quizResult.comparison.biggest_gap.theory_ref }}</div>
            </div>
          </div>

          <!-- dual radar -->
          <div class="panel card" style="margin-top: 16px">
            <div class="section-title"><h2>数据人格 vs 自评人格</h2></div>
            <div ref="dualRadarRef" class="chart-shell" style="height: 380px"></div>
          </div>

          <!-- gap analysis -->
          <div class="panel card" style="margin-top: 16px">
            <div class="section-title"><h2>偏差分析</h2></div>
            <div class="bias-text">{{ quizResult.comparison.biggest_gap.analysis }}</div>
            <div class="bias-text" style="margin-top: 12px">{{ quizResult.comparison.bias_analysis }}</div>
          </div>

          <div class="quiz-actions" style="margin-top: 16px">
            <el-button :icon="Refresh" @click="resetQuiz">重新测试</el-button>
          </div>
        </template>
      </el-tab-pane>

      <!-- ================================================================ -->
      <!-- Tab 3: 财务健康 -->
      <!-- ================================================================ -->
      <el-tab-pane label="财务健康" name="health">
        <el-empty v-if="!hasData && !loading" description="暂无足够交易数据，请先导入账单后再查看财务健康评分" :image-size="120" />

        <template v-if="health && hasData">
          <!-- grade badge -->
          <div class="health-hero">
            <div class="grade-badge" :style="{ borderColor: gradeColor(health.grade), color: gradeColor(health.grade) }">
              <span class="grade-letter">{{ health.grade }}</span>
              <span class="grade-total">{{ Math.round(health.total_score) }} 分</span>
            </div>
            <div class="grade-desc">
              <div class="grade-title">财务健康等级</div>
              <div class="grade-text">{{ gradeText(health.grade) }}</div>
            </div>
          </div>

          <!-- health radar -->
          <div class="panel card" style="margin-top: 16px">
            <div class="section-title"><h2>五维健康雷达</h2></div>
            <div ref="healthRadarRef" class="chart-shell health-chart-shell"></div>
          </div>

          <!-- suggestions -->
          <div class="panel card" style="margin-top: 16px">
            <div class="section-title"><h2>改善建议</h2></div>
            <div v-for="(suggestion, idx) in health.suggestions" :key="idx" class="suggestion-item">
              <el-icon class="suggestion-icon"><Warning /></el-icon>
              <span>{{ suggestion }}</span>
            </div>
            <el-empty v-if="!health.suggestions.length" description="暂无建议" :image-size="80" />
          </div>
        </template>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
/* ------------------------------------------------------------------ */
/* personality hero */
/* ------------------------------------------------------------------ */
.personality-hero {
  display: grid;
  grid-template-columns: 380px minmax(0, 1fr);
  gap: 18px;
  margin-bottom: 18px;
}

.personality-card {
  padding: 28px 24px;
  border-radius: 12px;
  background: linear-gradient(135deg, #00A884 0%, #007A60 100%);
  color: #fff;
  display: flex;
  flex-direction: column;
}

.personality-code {
  font-size: 36px;
  font-weight: 800;
  letter-spacing: 0.04em;
  font-family: 'SF Mono', 'Cascadia Code', monospace;
}

.personality-name {
  margin-top: 8px;
  font-size: 22px;
  font-weight: 700;
}

.personality-tagline {
  margin-top: 6px;
  font-size: 14px;
  opacity: 0.82;
}

.personality-quote {
  margin-top: 18px;
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  font-size: 14px;
  font-style: italic;
  line-height: 1.6;
}

.secondary-type {
  margin-top: 14px;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  font-size: 12px;
}

/* ------------------------------------------------------------------ */
/* dimension grid */
/* ------------------------------------------------------------------ */
.dimension-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.dimension-card {
  padding: 18px;
}

.dimension-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.dimension-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
}

.dimension-side {
  padding: 2px 10px;
  border-radius: 99px;
  font-size: 12px;
  font-weight: 500;
}

.dimension-side.Impulsive,
.dimension-side.Veblen,
.dimension-side.Exploratory {
  background: #fef2f2;
  color: #dc2626;
}

.dimension-side.Patient,
.dimension-side.Utilitarian,
.dimension-side.Stable {
  background: #ecfdf5;
  color: #059669;
}

.dimension-side.Flexible {
  background: #eff6ff;
  color: #2563eb;
}

.dimension-side.Rigid {
  background: #fefce8;
  color: #ca8a04;
}

.dimension-score-row {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-bottom: 8px;
}

.dimension-score-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-text);
}

.dimension-score-unit {
  font-size: 13px;
  color: var(--color-muted);
}

.dimension-theory {
  margin-top: 12px;
  padding: 4px 8px;
  background: var(--color-bg);
  border-radius: 4px;
  font-size: 11px;
  color: var(--color-muted);
}

.dimension-interpretation {
  margin-top: 10px;
  font-size: 13px;
  color: var(--color-text);
  line-height: 1.6;
}

/* ------------------------------------------------------------------ */
/* quiz */
/* ------------------------------------------------------------------ */
.quiz-intro {
  padding: 18px 20px;
  margin-bottom: 16px;
  font-size: 14px;
  color: var(--color-text);
  line-height: 1.6;
}

.quiz-item {
  padding: 20px 24px;
  margin-bottom: 12px;
}

.quiz-question-header {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  margin-bottom: 14px;
}

.quiz-number {
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: var(--color-primary);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
}

.quiz-question-text {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
}

.quiz-dimension-tag {
  margin-top: 6px;
}

.quiz-options {
  display: grid;
  gap: 8px;
  margin-left: 42px;
}

.quiz-option-item {
  padding: 10px 14px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  transition: border-color 0.2s;
}

.quiz-option-item:hover {
  border-color: var(--color-primary);
}

.quiz-actions {
  display: flex;
  justify-content: center;
  margin-top: 8px;
}

/* quiz result */
.quiz-result-header {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.similarity-card {
  padding: 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.similarity-ring {
  width: 120px;
  height: 120px;
  border-radius: 99px;
  border: 6px solid var(--color-primary);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.similarity-value {
  font-size: 28px;
  font-weight: 800;
  color: var(--color-primary);
}

.similarity-label {
  font-size: 12px;
  color: var(--color-muted);
}

.similarity-desc {
  text-align: center;
  font-size: 13px;
  color: var(--color-text);
  line-height: 1.5;
}

.gap-card {
  padding: 24px;
}

.gap-title {
  font-size: 14px;
  color: var(--color-muted);
  margin-bottom: 6px;
}

.gap-dimension {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-text);
  margin-bottom: 16px;
}

.gap-scores {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
}

.gap-score-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.gap-score-label {
  font-size: 12px;
  color: var(--color-muted);
}

.gap-score-val {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-text);
}

.gap-score-divider {
  width: 1px;
  height: 40px;
  background: var(--color-border);
}

.gap-diff {
  margin-left: auto;
  padding: 6px 14px;
  background: #fef2f2;
  color: #dc2626;
  border-radius: 99px;
  font-size: 13px;
  font-weight: 600;
}

.gap-theory {
  padding: 6px 10px;
  background: var(--color-bg);
  border-radius: 4px;
  font-size: 12px;
  color: var(--color-muted);
}

.bias-text {
  font-size: 14px;
  color: var(--color-text);
  line-height: 1.7;
}

/* ------------------------------------------------------------------ */
/* health */
/* ------------------------------------------------------------------ */
.health-hero {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 20px 0;
}

.grade-badge {
  width: 110px;
  height: 110px;
  border-radius: 99px;
  border: 6px solid;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.grade-letter {
  font-size: 36px;
  font-weight: 800;
  line-height: 1;
}

.grade-total {
  margin-top: 4px;
  font-size: 13px;
}

.grade-desc {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.grade-title {
  font-size: 14px;
  color: var(--color-muted);
}

.grade-text {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text);
}

/* suggestion */
.suggestion-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 16px;
  border-left: 3px solid var(--color-warning);
  background: #fffbeb;
  border-radius: 0 8px 8px 0;
  font-size: 14px;
  color: var(--color-text);
  line-height: 1.6;
}

.suggestion-item + .suggestion-item {
  margin-top: 10px;
}

.suggestion-icon {
  margin-top: 2px;
  color: var(--color-warning);
  flex-shrink: 0;
}

/* ------------------------------------------------------------------ */
/* shared */
/* ------------------------------------------------------------------ */
.chart-shell {
  width: 100%;
  height: 320px;
}

.health-chart-shell {
  height: 420px;
  min-height: 420px;
}

.personality-tabs {
  margin-top: 4px;
}

/* ------------------------------------------------------------------ */
/* responsive */
/* ------------------------------------------------------------------ */
@media (max-width: 1180px) {
  .personality-hero {
    grid-template-columns: 1fr;
  }

  .dimension-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .quiz-result-header {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .dimension-grid {
    grid-template-columns: 1fr;
  }

  .health-hero {
    flex-direction: column;
    text-align: center;
  }

  .health-chart-shell {
    height: 360px;
    min-height: 360px;
  }
}
</style>
