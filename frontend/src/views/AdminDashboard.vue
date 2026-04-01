<template>
  <div class="admin-layout">
    <el-container class="admin-container">
      <el-aside width="220px" class="admin-aside">
        <h3 class="aside-title">后台管理</h3>
        <el-menu :default-active="activeMenu" @select="handleMenuSelect">
          <el-menu-item index="users">用户管理</el-menu-item>
          <el-menu-item index="crawler">数据与爬虫监控</el-menu-item>
          <el-menu-item index="analytics">推荐与 AI 监控</el-menu-item>
        </el-menu>
      </el-aside>
      <el-container>
        <el-header class="admin-header">
          <div class="header-left">
            <span class="title">运营控制台</span>
            <span class="subtitle">面向管理员的数据治理与监控中心</span>
          </div>
        </el-header>
        <el-main class="admin-main">
          <section v-if="activeMenu === 'users'">
            <div class="section-header">
              <div>
                <h3>用户管理</h3>
                <p class="section-desc">查看注册用户、封禁/解封、重置密码</p>
              </div>
              <el-button :loading="loadingUsers" type="primary" @click="loadUsers">
                刷新列表
              </el-button>
            </div>
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
            <div class="section-header">
              <div>
                <h3>数据源与爬虫监控</h3>
                <p class="section-desc">查看定时任务状态，手动触发同步，检查日志</p>
              </div>
              <div class="section-actions">
                <el-button type="primary" :loading="triggeringUpdate" @click="triggerUpdate">
                  手动更新热门番剧
                </el-button>
                <el-button :loading="loadingCrawler" @click="loadCrawler">刷新状态</el-button>
              </div>
            </div>

            <el-row :gutter="16">
              <el-col :span="8">
                <el-card shadow="hover">
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
                    <span>抓取条数：</span>
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
                <el-card shadow="hover">
                  <div class="card-header">
                    <h4>最近爬虫日志</h4>
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
            <div class="section-header">
              <div>
                <h3>推荐与 AI 监控</h3>
                <p class="section-desc">洞察标签分布、用户规模与 AI 服务状态</p>
              </div>
              <el-button :loading="loadingOverview" @click="loadOverview">刷新看板</el-button>
            </div>

            <el-row :gutter="16" class="metric-row">
              <el-col :span="6">
                <el-card shadow="hover">
                  <p class="metric-title">总用户</p>
                  <p class="metric-value">{{ overview.metrics.total_users ?? '-' }}</p>
                </el-card>
              </el-col>
              <el-col :span="6">
                <el-card shadow="hover">
                  <p class="metric-title">活跃用户</p>
                  <p class="metric-value">{{ overview.metrics.active_users ?? '-' }}</p>
                </el-card>
              </el-col>
              <el-col :span="6">
                <el-card shadow="hover">
                  <p class="metric-title">管理员</p>
                  <p class="metric-value">{{ overview.metrics.admin_users ?? '-' }}</p>
                </el-card>
              </el-col>
              <el-col :span="6">
                <el-card shadow="hover">
                  <p class="metric-title">番剧总量</p>
                  <p class="metric-value">{{ overview.metrics.total_anime ?? '-' }}</p>
                </el-card>
              </el-col>
            </el-row>

            <el-row :gutter="16" class="chart-row">
              <el-col :span="12">
                <el-card shadow="hover">
                  <div class="card-header">
                    <h4>最常选择的 Genre</h4>
                    <span class="hint">按出现次数统计</span>
                  </div>
                  <div ref="genreChartRef" class="chart-box"></div>
                </el-card>
              </el-col>
              <el-col :span="12">
                <el-card shadow="hover">
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
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, reactive, ref } from 'vue'
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
  fetchRecommendationStrategy,
  updateRecommendationStrategy
} from '@/api/admin'
import { useEcharts } from '@/composables/useEcharts'

const activeMenu = ref('users')

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
      inputErrorMessage: '需包含字母和数字，长度至少 8 位'
    })
    const newPassword = (result as any).value as string
    await resetUserPassword(row.id, newPassword)
    ElMessage.success('密码已重置')
  } catch (err: any) {
    if (err === 'cancel') return
    ElMessage.error(err?.response?.data?.detail || '重置失败')
  }
}

// 爬虫监控
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
    ElMessage.error(err?.response?.data?.detail || '加载爬虫日志失败')
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
  latest_crawl: {}
})
const aiStats = reactive<any>({
  ai_enabled: false,
  call_stats: {},
  by_api_type: [],
  top_errors: [],
  message: ''
})
const loadingOverview = ref(false)

const { chartRef: genreChartRef, initChart: initGenreChart, setOption: setGenreOption } = useEcharts()
const chartInitialized = ref(false)

const renderGenreChart = (topGenres: { name: string; count: number }[]) => {
  if (!topGenres || topGenres.length === 0) {
    setGenreOption({
      title: { text: '暂无数据', left: 'center', top: 'middle' }
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
        data: topGenres.map((item) => ({ name: item.name, value: item.count }))
      }
    ]
  })
}

const loadOverview = async () => {
  try {
    loadingOverview.value = true
    await nextTick()
    if (!chartInitialized.value && genreChartRef.value) {
      initGenreChart({
        title: { text: 'Genre 分布', left: 'center' },
        series: [{ type: 'pie', data: [] }]
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

const strategyForm = reactive({
  views_weight: 0.35,
  ai_weight: 0.35,
  tmdb_weight: 0.2,
  diversity_weight: 0.1,
  enabled: true
})
const savingStrategy = ref(false)

const loadStrategy = async () => {
  try {
    const res = await fetchRecommendationStrategy()
    if (res.success) {
      Object.assign(strategyForm, res.data)
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '加载推荐策略失败')
  }
}

const saveStrategy = async () => {
  try {
    savingStrategy.value = true
    await updateRecommendationStrategy(strategyForm as any)
    ElMessage.success('推荐策略已更新')
    await loadStrategy()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '保存推荐策略失败')
  } finally {
    savingStrategy.value = false
  }
}

const handleMenuSelect = (key: string) => {
  activeMenu.value = key
  if (key === 'users') {
    loadUsers()
  } else if (key === 'crawler') {
    loadCrawler()
  } else {
    Promise.all([loadOverview(), loadStrategy()])
  }
}

const formatDate = (dateStr?: string | null) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return isNaN(d.getTime()) ? '' : d.toLocaleString()
}

onMounted(() => {
  loadUsers()
})
</script>

<style scoped>
.admin-layout {
  background: #f5f7fa;
  min-height: 100vh;
}

.admin-container {
  height: 100%;
}

.admin-aside {
  background: #fff;
  border-right: 1px solid #ebeef5;
  padding: 16px 12px;
}

.aside-title {
  margin: 0 0 12px;
  font-weight: 600;
}

.admin-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
}

.header-left .title {
  font-weight: 600;
  font-size: 18px;
  margin-right: 12px;
}

.header-left .subtitle {
  color: #909399;
}

.admin-main {
  padding: 20px 24px 32px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.section-desc {
  margin: 4px 0 0;
  color: #909399;
}

.section-actions {
  display: flex;
  gap: 8px;
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
</style>
