<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  UserFilled,
  Plus,
  Delete,
  RefreshRight,
  DataAnalysis,
  MagicStick,
  Refresh,
} from '@element-plus/icons-vue'
import {
  fetchOrganizations,
  createOrganization,
  updateOrganization,
  fetchOrganizationMembers,
  addOrganizationMember,
  updateMemberRole,
  removeOrganizationMember,
  fetchFamilyDashboard,
  fetchFamilyPersonality,
  orgRetryAll,
} from '../api/client'
import type { Organization, OrganizationMember } from '../types/models'

const organizations = ref<Organization[]>([])
const selectedOrgId = ref<number | null>(null)
const members = ref<OrganizationMember[]>([])
const dashboardData = ref<any>(null)
const personalityData = ref<any>(null)
const loading = ref(false)
const showCreateDialog = ref(false)
const newOrgName = ref('')
const showAddMemberDialog = ref(false)
const newMemberUsername = ref('')
const editingPlan = ref(false)

const selectedOrg = computed(() =>
  organizations.value.find((o) => o.id === selectedOrgId.value) ?? null
)

const isOwnerOrAdmin = computed(() => {
  if (!selectedOrg.value) return false
  return selectedOrg.value.role === 'owner' || selectedOrg.value.role === 'admin'
})

onMounted(async () => {
  try {
    const { data } = await fetchOrganizations()
    organizations.value = data
    if (data.length > 0) {
      selectedOrgId.value = data[0].id
    }
  } catch {
    ElMessage.error('加载组织列表失败')
  }
})

watch(selectedOrgId, async (newId) => {
  if (!newId) return
  await loadOrgData()
})

async function loadOrgData() {
  if (!selectedOrgId.value) return
  loading.value = true
  try {
    const [membersRes, dashRes, persRes] = await Promise.all([
      fetchOrganizationMembers(selectedOrgId.value),
      fetchFamilyDashboard(selectedOrgId.value),
      fetchFamilyPersonality(selectedOrgId.value),
    ])
    members.value = membersRes.data
    dashboardData.value = dashRes.data
    personalityData.value = persRes.data
  } catch {
    ElMessage.error('加载家庭数据失败')
  } finally {
    loading.value = false
  }
}

async function handleCreateOrg() {
  if (!newOrgName.value.trim()) return
  try {
    const { data } = await createOrganization({ name: newOrgName.value.trim() })
    organizations.value.push(data)
    selectedOrgId.value = data.id
    showCreateDialog.value = false
    newOrgName.value = ''
    ElMessage.success('家庭组织创建成功')
  } catch {
    ElMessage.error('创建失败')
  }
}

async function handleAddMember() {
  if (!newMemberUsername.value.trim() || !selectedOrgId.value) return
  try {
    const { data } = await addOrganizationMember(selectedOrgId.value, {
      username: newMemberUsername.value.trim(),
    })
    members.value.push(data)
    newMemberUsername.value = ''
    showAddMemberDialog.value = false
    ElMessage.success('成员添加成功')
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || '添加失败')
  }
}

async function handleChangeRole(member: OrganizationMember, newRole: 'admin' | 'member') {
  if (!selectedOrgId.value) return
  try {
    await updateMemberRole(selectedOrgId.value, member.user_id, { role: newRole })
    member.role = newRole
    ElMessage.success('角色已更新')
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || '更新失败')
  }
}

async function handleRemoveMember(member: OrganizationMember) {
  if (!selectedOrgId.value) return
  try {
    await ElMessageBox.confirm(`确定要移除 ${member.username} 吗？`, '移除成员', {
      type: 'warning',
    })
    await removeOrganizationMember(selectedOrgId.value, member.user_id)
    members.value = members.value.filter((m) => m.user_id !== member.user_id)
    ElMessage.success('成员已移除')
  } catch {
    // user cancelled
  }
}

async function handleRetryAll() {
  if (!selectedOrgId.value) return
  try {
    const { data } = await orgRetryAll(selectedOrgId.value)
    ElMessage.success(`已将 ${data.queued} 笔交易重新放入重试池`)
  } catch {
    ElMessage.error('操作失败')
  }
}

async function handleUpdatePlan() {
  if (!selectedOrgId.value || !selectedOrg.value) return
  try {
    await updateOrganization(selectedOrgId.value, {
      name: selectedOrg.value.name,
      plan: selectedOrg.value.plan,
      subscription_status: selectedOrg.value.subscription_status,
    })
    editingPlan.value = false
    ElMessage.success('已更新')
  } catch {
    ElMessage.error('更新失败')
  }
}

function formatMoney(val: string | number): string {
  return `¥${Number(val).toFixed(2)}`
}

function roleLabel(role: string): string {
  return role === 'owner' ? '拥有者' : role === 'admin' ? '管理员' : '成员'
}
</script>

<template>
  <div class="page-shell">
    <div class="page-heading">
      <div>
        <h1>家庭组织</h1>
        <p>管理家庭账单组织，查看聚合财务概览与消费人格分析。</p>
      </div>
      <div class="heading-actions">
        <el-button :icon="Refresh" :loading="loading" @click="loadOrgData">刷新数据</el-button>
        <el-button type="primary" :icon="Plus" @click="showCreateDialog = true">新建家庭</el-button>
      </div>
    </div>

    <div v-if="organizations.length === 0" class="empty-state">
      <el-result icon="info" title="尚未加入任何家庭组织"
        sub-title="创建一个家庭组织来开始管理家庭账单">
        <template #extra>
          <el-button type="primary" @click="showCreateDialog = true">创建家庭组织</el-button>
        </template>
      </el-result>
    </div>

    <template v-else>
      <!-- Org selector -->
      <section class="panel card filter-card">
        <div class="toolbar-grid org-filter-grid">
          <el-select v-model="selectedOrgId" placeholder="选择家庭" size="large">
            <el-option v-for="org in organizations" :key="org.id" :label="org.name" :value="org.id">
              <span>{{ org.name }}</span>
              <el-tag size="small" style="margin-left: 8px"
                :type="org.role === 'owner' ? '' : 'info'">
                {{ roleLabel(org.role) }}
              </el-tag>
            </el-option>
          </el-select>
        </div>
      </section>

      <div v-if="selectedOrg" v-loading="loading">
        <!-- Metrics -->
        <div v-if="dashboardData" class="metric-grid org-metrics">
          <section class="panel metric-card metric-negative">
            <div class="metric-label">总支出</div>
            <div class="metric-value">{{ formatMoney(dashboardData.expense_total) }}</div>
            <div class="metric-foot">家庭合计</div>
          </section>
          <section class="panel metric-card metric-positive">
            <div class="metric-label">总收入</div>
            <div class="metric-value">{{ formatMoney(dashboardData.income_total) }}</div>
            <div class="metric-foot">家庭合计</div>
          </section>
          <section class="panel metric-card">
            <div class="metric-label">净流入</div>
            <div class="metric-value">{{ formatMoney(dashboardData.net_total) }}</div>
            <div class="metric-foot">收入减支出</div>
          </section>
          <section class="panel metric-card metric-info">
            <div class="metric-label">交易笔数</div>
            <div class="metric-value">{{ dashboardData.transaction_count }}</div>
            <div class="metric-foot">家庭全部成员</div>
          </section>
        </div>

        <!-- Organization info -->
        <section v-if="isOwnerOrAdmin" class="panel card">
          <div class="section-title">
            <h2>组织信息</h2>
            <span v-if="!editingPlan">
              <el-button size="small" @click="editingPlan = true">编辑</el-button>
            </span>
            <span v-else>
              <el-button size="small" type="primary" @click="handleUpdatePlan">保存</el-button>
            </span>
          </div>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="名称">
              <span v-if="!editingPlan">{{ selectedOrg.name }}</span>
              <el-input v-else v-model="selectedOrg.name" size="small" />
            </el-descriptions-item>
            <el-descriptions-item label="方案">
              <span v-if="!editingPlan">{{ selectedOrg.plan || 'free' }}</span>
              <el-input v-else v-model="selectedOrg.plan" size="small" />
            </el-descriptions-item>
            <el-descriptions-item label="订阅状态">
              <el-tag v-if="!editingPlan"
                :type="selectedOrg.subscription_status === 'active' ? 'success' : 'warning'"
                size="small">
                {{ selectedOrg.subscription_status || 'active' }}
              </el-tag>
              <el-input v-else v-model="selectedOrg.subscription_status" size="small" />
            </el-descriptions-item>
          </el-descriptions>
        </section>

        <!-- Personality -->
        <section v-if="personalityData?.personality" class="panel card">
          <div class="section-title">
            <h2><el-icon><MagicStick /></el-icon> 家庭消费人格</h2>
            <span>基于家庭全体成员数据计算</span>
          </div>
          <div class="personality-display">
            <div class="personality-main">
              <span class="personality-code">{{ personalityData.personality.code }}</span>
              <span class="personality-name">{{ personalityData.personality.name }}</span>
              <span class="personality-tagline">{{ personalityData.personality.tagline }}</span>
            </div>
            <div class="personality-dims">
              <div v-for="dim in personalityData.personality.dimensions" :key="dim.name" class="dim-row">
                <span class="dim-label">{{ dim.label }}</span>
                <el-progress :percentage="dim.value" :stroke-width="8" :show-text="false" color="#00A884" />
                <span class="dim-value">{{ dim.value.toFixed(0) }}</span>
              </div>
            </div>
            <div v-if="personalityData.financial_health" class="health-tag-row">
              <el-tag size="large"
                :type="personalityData.financial_health.grade === 'A' || personalityData.financial_health.grade === 'S' ? 'success' : 'warning'">
                财务健康: {{ personalityData.financial_health.grade }}
                ({{ personalityData.financial_health.total_score?.toFixed(0) }})
              </el-tag>
            </div>
          </div>
        </section>

        <!-- Members -->
        <section class="panel card">
          <div class="section-title">
            <h2><el-icon><UserFilled /></el-icon> 家庭成员 ({{ members.length }})</h2>
            <el-button v-if="isOwnerOrAdmin" size="small" type="primary"
              :icon="Plus" @click="showAddMemberDialog = true">添加成员</el-button>
          </div>
          <el-table :data="members" stripe size="small">
            <el-table-column prop="username" label="用户名" />
            <el-table-column prop="role" label="角色" width="150">
              <template #default="{ row }">
                <template v-if="isOwnerOrAdmin && row.role !== 'owner'">
                  <el-select :model-value="row.role" size="small" style="width: 100px"
                    @change="(val: 'admin' | 'member') => handleChangeRole(row, val)">
                    <el-option label="管理员" value="admin" />
                    <el-option label="成员" value="member" />
                  </el-select>
                </template>
                <el-tag v-else size="small" :type="row.role === 'owner' ? '' : 'info'">
                  {{ roleLabel(row.role) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column v-if="isOwnerOrAdmin" label="操作" width="100">
              <template #default="{ row }">
                <el-button v-if="row.role !== 'owner'" size="small" type="danger" :icon="Delete"
                  text @click="handleRemoveMember(row)" />
              </template>
            </el-table-column>
          </el-table>
        </section>

        <!-- Admin actions -->
        <section v-if="isOwnerOrAdmin" class="panel card">
          <div class="section-title">
            <h2>管理操作</h2>
            <span>将失败的分类任务重新放入重试池</span>
          </div>
          <el-button :icon="RefreshRight" @click="handleRetryAll">
            重试所有失败的分类
          </el-button>
        </section>
      </div>
    </template>

    <!-- Dialogs -->
    <el-dialog v-model="showCreateDialog" title="创建家庭组织" width="420px">
      <el-form @submit.prevent="handleCreateOrg">
        <el-form-item label="家庭名称">
          <el-input v-model="newOrgName" placeholder="例如：张家财务" maxlength="128" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreateOrg" :disabled="!newOrgName.trim()">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showAddMemberDialog" title="添加成员" width="420px">
      <el-form @submit.prevent="handleAddMember">
        <el-form-item label="用户名">
          <el-input v-model="newMemberUsername" placeholder="输入已有用户的用户名" maxlength="64" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddMemberDialog = false">取消</el-button>
        <el-button type="primary" @click="handleAddMember" :disabled="!newMemberUsername.trim()">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.heading-actions {
  display: flex;
  gap: 8px;
}

.empty-state {
  margin-top: 60px;
}

.org-filter-grid {
  grid-template-columns: minmax(240px, 320px);
}

.org-metrics {
  grid-template-columns: repeat(4, 1fr);
}

.personality-display {
  padding: 8px 0;
}

.personality-main {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 16px;
}

.personality-code {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-primary);
  font-family: monospace;
}

.personality-name {
  font-size: 18px;
  font-weight: 600;
}

.personality-tagline {
  color: var(--color-muted);
  font-size: 14px;
}

.personality-dims {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dim-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.dim-label {
  width: 100px;
  font-size: 13px;
  color: var(--color-muted);
}

.dim-value {
  width: 36px;
  text-align: right;
  font-size: 13px;
  font-weight: 600;
}

.health-tag-row {
  margin-top: 16px;
}
</style>
