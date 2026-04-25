<template>
  <div class="admin-panel">
    <div class="admin-header">
      <div class="admin-title-group">
        <h3 class="admin-title">运营控制台</h3>
        <p class="admin-subtitle">面向管理员的数据治理与监控中心</p>
      </div>
      <ul class="nav nav-pills admin-tabs" role="tablist">
        <li v-for="tab in tabs" :key="tab.id" class="nav-item">
          <button
            class="nav-link"
            :class="{ active: activeMenu === tab.id }"
            role="tab"
            :aria-selected="activeMenu === tab.id"
            @click="switchTab(tab.id)"
          >
            {{ tab.label }}
          </button>
        </li>
      </ul>
    </div>

    <div class="style-unified">
      <div class="card-header-unified">
        <h5>{{ currentTabTitle }}</h5>
        <div class="section-actions" v-if="activeMenu === 'users'">
          <el-button :loading="loadingUsers" type="primary" @click="loadUsers">刷新列表</el-button>
        </div>
        <div class="section-actions" v-else-if="activeMenu === 'crawler'">
          <el-button type="primary" :loading="triggeringUpdate" @click="triggerUpdate">
            手动同步热门番剧
          </el-button>
          <el-button :loading="loadingCrawler" @click="loadCrawler">刷新状态</el-button>
        </div>
        <div class="section-actions" v-else>
          <el-button :loading="loadingOverview" @click="loadOverview">刷新看板</el-button>
        </div>
      </div>

      <div class="panel-body">
        <section v-if="activeMenu === 'users'">
          <p class="section-desc">查看注册用户、封禁/解封、重置密码</p>
          <el-table v-loading="loadingUsers" :data="users" border stripe>
            <el-table-column prop="username" label="用户名" width="160" />
            <el-table-column prop="email" label="邮箱" />
            <el-table-column prop="is_admin" label="角色" width="120">
              <template #default="{ row }">
                <el-tag type="warning" v-if="row.is_admin">管理员</el-tag>
                <el-tag v-else>普通用户</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="is_active" label="状态" width="120">
              <template #default="{ row }">
                <el-tag type="success" v-if="row.is_active">正常</el-tag>
                <el-tag type="danger" v-else>已封禁</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="注册时间" width="200">
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="260" fixed="right">
              <template #default="{ row }">
                <el-button
                  size="small"
                  :type="row.is_active ? 'danger' : 'success'"
                  @click="toggleUser(row)"
                >
                  {{ row.is_active ? '封禁' : '解封' }}
                </el-button>
                <el-button size="small" @click="resetPassword(row)">重置密码</el-button>
              </template>
            </el-table-column>
          </el-table>
        </section>

        <section v-else-if="activeMenu === 'crawler'">
          <p class="section-desc">查看定时任务状态，手动触发同步，检查日志</p>
          <el-row :gutter="16">
            <el-col :span="8">
              <el-card shadow="never" class="rounded-card">
                <h4>最近任务</h4>
                <div class="stat-line">
                  <span>状态：</span>
                  <el-tag :type="latestCrawl.status === 'success' ? 'success' : 'info'">
                    {{ latestCrawl.status || '无记录' }}
                  </el-tag>
                </div>
                <div class="stat-line">
                  <span>任务类型：</span>
                  <span>{{ latestCrawl.task_type || '--' }}</span>
                </div>
                <div class="stat-line">
                  <span>同步条数：</span>
                  <span>{{ latestCrawl.items_count ?? 0 }}</span>
                </div>
                <div class="stat-line">
                  <span>开始时间：</span>
                  <span>{{ formatDate(latestCrawl.started_at) || '--' }}</span>
                </div>
                <div class="stat-line">
                  <span>结束时间：</span>
                  <span>{{ formatDate(latestCrawl.completed_at) || '--' }}</span>
                </div>
                <div class="stat-line" v-if="latestCrawl.error_message">
                  <span>错误：</span>
                  <el-text type="danger">{{ latestCrawl.error_message }}</el-text>
                </div>
              </el-card>
            </el-col>
            <el-col :span="16">
              <el-card shadow="never" class="rounded-card">
                <div class="card-header">
                  <h4>最近数据同步日志</h4>
                  <el-button text type="primary" @click="loadCrawler">刷新</el-button>
                </div>
                <el-table v-loading="loadingCrawler" :data="crawlerLogs" border height="320">
                  <el-table-column prop="started_at" label="开始时间" width="190">
                    <template #default="{ row }">
                      {{ formatDate(row.started_at) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="task_type" label="类型" width="130" />
                  <el-table-column prop="status" label="状态" width="120">
                    <template #default="{ row }">
                      <el-tag :type="row.status === 'success' ? 'success' : row.status === 'failed' ? 'danger' : 'info'">
                        {{ row.status }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="items_count" label="条数" width="100" />
                  <el-table-column prop="error_message" label="错误信息" />
                </el-table>
              </el-card>
            </el-col>
          </el-row>
        </section>

        <section v-else>
          <p class="section-desc">洞察标签分布、用户规模与 AI 服务状态</p>

          <el-row :gutter="16" class="metric-row">
            <el-col :span="6">
              <el-card shadow="never" class="rounded-card">
                <p class="metric-title">总用户</p>
                <p class="metric-value">{{ overview.metrics.total_users ?? '-' }}</p>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="never" class="rounded-card">
                <p class="metric-title">活跃用户</p>
                <p class="metric-value">{{ overview.metrics.active_users ?? '-' }}</p>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="never" class="rounded-card">
                <p class="metric-title">管理员</p>
                <p class="metric-value">{{ overview.metrics.admin_users ?? '-' }}</p>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="never" class="rounded-card">
                <p class="metric-title">番剧总量</p>
                <p class="metric-value">{{ overview.metrics.total_anime ?? '-' }}</p>
              </el-card>
            </el-col>
          </el-row>

          <el-row :gutter="16" class="chart-row">
            <el-col :span="12">
              <el-card shadow="never" class="rounded-card">
                <div class="card-header">
                  <h4>最常选择的 Genre</h4>
                  <span class="hint">按出现次数统计</span>
                </div>
                <div ref="genreChartRef" class="chart-box"></div>
              </el-card>
            </el-col>
            <el-col :span="12">
              <el-card shadow="never" class="rounded-card">
                <div class="card-header">
                  <h4>AI 服务状态</h4>
                  <el-tag :type="aiStats.ai_enabled ? 'success' : 'warning'">
                    {{ aiStats.ai_enabled ? '已启用' : '未配置/已降级' }}
                  </el-tag>
                </div>
                <ul class="ai-stats">
                  <li>
                    <span>提示</span>
                    <span>{{ aiStats.message }}</span>
                  </li>
                  <li>
                    <span>调用次数</span>
                    <span>{{ aiStats.call_stats?.call_count ?? 0 }}</span>
                  </li>
                  <li>
                    <span>平均延迟</span>
                    <span>{{ aiStats.call_stats?.avg_latency_ms ? aiStats.call_stats.avg_latency_ms + ' ms' : '--' }}</span>
                  </li>
                  <li>
                    <span>最近错误</span>
                    <span>{{ aiStats.call_stats?.last_error || '暂无' }}</span>
                  </li>
                </ul>
              </el-card>
            </el-col>
          </el-row>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { AdminUser } from '@/api/admin'
import {
  fetchUsers,
  updateUserStatus,
  resetUserPassword,
  fetchCrawlerLogs,
  triggerCrawlerUpdate,
  fetchOverview,
  fetchAiStats,
} from '@/api/admin'
import { useEcharts } from '@/composables/useEcharts'

type AdminTab = 'users' | 'crawler' | 'analytics'

const tabs: Array<{ id: AdminTab; label: string }> = [
  { id: 'users', label: '用户管理' },
  { id: 'crawler', label: '数据与同步监控' },
  { id: 'analytics', label: '推荐与 AI 监控' },
]
const activeMenu = ref<AdminTab>('users')
const currentTabTitle = computed(() => tabs.find((item) => item.id === activeMenu.value)?.label || '后台管理')

// 用户管理
const users = ref<AdminUser[]>([])
const loadingUsers = ref(false)

const loadUsers = async () => {
  try {
    loadingUsers.value = true
    const res = await fetchUsers()
    if (res.success) {
      users.value = res.users
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '加载用户失败')
  } finally {
    loadingUsers.value = false
  }
}

const toggleUser = async (row: AdminUser) => {
  try {
    const target = !row.is_active
    await updateUserStatus(row.id, target)
    row.is_active = target
    ElMessage.success(target ? '已解封' : '已封禁')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '更新状态失败')
  }
}

const resetPassword = async (row: AdminUser) => {
  try {
    const result = await ElMessageBox.prompt('请输入新密码（至少8位，需包含字母和数字）', `重置密码：${row.username}`, {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      inputType: 'password',
      inputPattern: /^(?=.*[A-Za-z])(?=.*\d).{8,}$/,
      inputErrorMessage: '需包含字母和数字，长度至少 8 位',
    })
    const newPassword = (result as any).value as string
    await resetUserPassword(row.id, newPassword)
    ElMessage.success('密码已重置')
  } catch (err: any) {
    if (err === 'cancel') return
    ElMessage.error(err?.response?.data?.detail || '重置失败')
  }
}

// 数据同步监控
const crawlerLogs = ref<any[]>([])
const latestCrawl = reactive<any>({})
const loadingCrawler = ref(false)
const triggeringUpdate = ref(false)

const loadCrawler = async () => {
  try {
    loadingCrawler.value = true
    const res = await fetchCrawlerLogs()
    if (res.success) {
      crawlerLogs.value = res.logs
      if (res.logs && res.logs.length > 0) {
        Object.assign(latestCrawl, res.logs[0])
      }
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '加载数据同步日志失败')
  } finally {
    loadingCrawler.value = false
  }
}

const triggerUpdate = async () => {
  try {
    triggeringUpdate.value = true
    await triggerCrawlerUpdate()
    ElMessage.success('已触发更新任务')
    loadCrawler()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '触发失败')
  } finally {
    triggeringUpdate.value = false
  }
}

// 运营/AI 看板
const overview = reactive<any>({
  metrics: {},
  top_genres: [],
  latest_crawl: {},
})
const aiStats = reactive<any>({
  ai_enabled: false,
  call_stats: {},
  by_api_type: [],
  top_errors: [],
  message: '',
})
const loadingOverview = ref(false)

const { chartRef: genreChartRef, initChart: initGenreChart, setOption: setGenreOption } = useEcharts()
const chartInitialized = ref(false)

const renderGenreChart = (topGenres: { name: string; count: number }[]) => {
  if (!topGenres || topGenres.length === 0) {
    setGenreOption({
      title: { text: '暂无数据', left: 'center', top: 'middle' },
    })
    return
  }
  setGenreOption({
    tooltip: { trigger: 'item' },
    legend: { top: 'bottom' },
    series: [
      {
        name: 'Genre 频次',
        type: 'pie',
        radius: ['30%', '70%'],
        data: topGenres.map((item) => ({ name: item.name, value: item.count })),
      },
    ],
  })
}

const loadOverview = async () => {
  try {
    loadingOverview.value = true
    await nextTick()
    if (!chartInitialized.value && genreChartRef.value) {
      initGenreChart({
        title: { text: 'Genre 分布', left: 'center' },
        series: [{ type: 'pie', data: [] }],
      })
      chartInitialized.value = true
    }
    const [overviewRes, aiRes] = await Promise.all([fetchOverview(), fetchAiStats()])
    if (overviewRes.success) {
      Object.assign(overview, overviewRes)
      renderGenreChart(overviewRes.top_genres || [])
    }
    if (aiRes.success) {
      Object.assign(aiStats, aiRes)
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '加载看板失败')
  } finally {
    loadingOverview.value = false
  }
}

const switchTab = (tab: AdminTab) => {
  if (activeMenu.value === tab) return
  activeMenu.value = tab
  if (tab === 'users') loadUsers()
  else if (tab === 'crawler') loadCrawler()
  else loadOverview()
}

const formatDate = (dateStr?: string | null) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleString('zh-CN')
}

onMounted(() => {
  loadUsers()
})
</script>

<style scoped>
.admin-panel {
  display: grid;
  gap: 14px;
}

.admin-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.9rem;
  padding: 0.95rem 1.1rem;
  border-radius: 12px;
  background: #ffffff;
  border: 1px solid rgba(0, 0, 0, 0.06);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
}

.admin-title-group {
  min-width: 0;
  flex: 1;
}

.admin-title {
  margin: 0 0 0.2rem;
  font-size: 1.1rem;
  font-weight: 700;
  color: #1f2937;
}

.admin-subtitle {
  margin: 0;
  color: #6b7280;
  font-size: 0.86rem;
}

.admin-tabs {
  margin: 0;
  padding: 0.25rem;
  gap: 0.45rem;
  border-radius: 12px;
  background: linear-gradient(180deg, #f8fbff 0%, #f1f6ff 100%);
  flex: 1 1 500px;
  max-width: 620px;
  margin-left: auto;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  list-style: none;
}

.admin-tabs .nav-link {
  width: 100%;
  border-radius: 999px;
  border: none;
  padding: 0.42rem 0.7rem;
  font-size: 0.85rem;
  font-weight: 500;
  color: #334155;
  background: transparent;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.admin-tabs .nav-link.active {
  background: linear-gradient(135deg, #1d4ed8 0%, #0369a1 100%);
  color: #fff;
  box-shadow: 0 6px 16px rgba(29, 78, 216, 0.3);
}

.admin-tabs .nav-link:hover:not(.active) {
  background: rgba(79, 172, 254, 0.14);
  color: #1d4ed8;
}

.style-unified {
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

.card-header-unified {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 0.9rem 1.25rem;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.card-header-unified h5 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: #1f2937;
}

.panel-body {
  padding: 1rem 1.25rem 1.2rem;
}

.section-desc {
  margin: 0 0 12px;
  color: #909399;
}

.section-actions {
  display: flex;
  gap: 8px;
}

.rounded-card {
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.06);
}

.stat-line {
  display: flex;
  justify-content: space-between;
  margin: 6px 0;
  color: #606266;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.chart-box {
  width: 100%;
  height: 320px;
}

.metric-row .metric-title {
  margin: 0;
  color: #909399;
}

.metric-row .metric-value {
  margin: 4px 0 0;
  font-size: 28px;
  font-weight: 600;
}

.ai-stats {
  list-style: none;
  padding: 0;
  margin: 0;
  line-height: 28px;
  color: #606266;
}

.ai-stats li {
  display: flex;
  justify-content: space-between;
}

@media (max-width: 1200px) {
  .admin-header {
    flex-wrap: wrap;
  }

  .admin-tabs {
    width: 100%;
    max-width: none;
    margin-left: 0;
  }
}

@media (max-width: 768px) {
  .admin-tabs {
    grid-template-columns: 1fr;
  }
}
</style>
