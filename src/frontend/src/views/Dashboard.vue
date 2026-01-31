<template>
  <div class="dashboard-container">
    <header class="header">
      <div class="header-content">
        <div class="logo-section">
          <img src="https://www.bilibili.com/favicon.ico" alt="B站Logo" class="logo" />
          <h3>Bilibili 智能分析平台</h3>
        </div>
        <nav class="nav-menu">
          <router-link to="/dashboard" class="nav-link active">首页</router-link>
          <router-link to="/personal-space" class="nav-link">个人空间</router-link>
          <router-link to="/data-screen" class="nav-link">数据大屏</router-link>
        </nav>
        <div class="user-section">
          <span class="username">{{ authStore.username }}</span>
          <el-button type="danger" size="small" @click="handleLogout">退出</el-button>
        </div>
      </div>
    </header>

    <main class="main-content">
      <!-- 数据总览卡片 -->
      <div class="overview-section">
        <h2 class="section-title">数据总览</h2>
        <div class="stats-cards" v-loading="analyticsStore.loading">
          <div class="stat-card">
            <div class="stat-icon" style="background: #409eff">📊</div>
            <div class="stat-content">
              <div class="stat-value">{{ formatNumber(overview?.total_animes || 0) }}</div>
              <div class="stat-label">番剧总数</div>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon" style="background: #67c23a">▶️</div>
            <div class="stat-content">
              <div class="stat-value">{{ formatNumber(overview?.total_views || 0) }}</div>
              <div class="stat-label">总播放量</div>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon" style="background: #e6a23c">⭐</div>
            <div class="stat-content">
              <div class="stat-value">{{ formatNumber(overview?.total_favorites || 0) }}</div>
              <div class="stat-label">总追番数</div>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon" style="background: #f56c6c">🕐</div>
            <div class="stat-content">
              <div class="stat-value">{{ formatDate(overview?.last_update) }}</div>
              <div class="stat-label">最后更新</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 排行榜 -->
      <div class="rankings-section">
        <h2 class="section-title">排行榜</h2>
        <div class="ranking-controls">
          <el-radio-group v-model="sortBy" @change="loadRankings">
            <el-radio-button value="views">播放量</el-radio-button>
            <el-radio-button value="favorites">追番数</el-radio-button>
            <el-radio-button value="rating">评分</el-radio-button>
          </el-radio-group>
        </div>
        <div class="ranking-list" v-loading="loading">
          <div
            v-for="(anime, index) in rankings"
            :key="anime.season_id"
            class="ranking-item"
          >
            <div class="rank-number" :class="getRankClass(index)">{{ index + 1 }}</div>
            <img :src="anime.cover" :alt="anime.title" class="anime-cover" />
            <div class="anime-info">
              <h4 class="anime-title">{{ anime.title }}</h4>
              <div class="anime-meta">
                <span class="area-tag">{{ anime.area }}</span>
                <span class="rating">⭐ {{ anime.rating || 'N/A' }}</span>
              </div>
            </div>
            <div class="anime-stats">
              <div class="stat-item">
                <span class="stat-label">播放</span>
                <span class="stat-value">{{ formatNumber(anime.views) }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">追番</span>
                <span class="stat-value">{{ formatNumber(anime.favorites) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useAnalyticsStore } from '@/stores/analytics'
import type { AnimeData } from '@/api/analytics'

const router = useRouter()
const authStore = useAuthStore()
const analyticsStore = useAnalyticsStore()

const sortBy = ref('views')
const rankings = ref<AnimeData[]>([])
const loading = ref(false)

const overview = computed(() => analyticsStore.overview)

// 加载数据总览
const loadOverview = async () => {
  await analyticsStore.fetchOverview()
}

// 加载排行榜
const loadRankings = async () => {
  loading.value = true
  rankings.value = await analyticsStore.fetchRankings(sortBy.value, 15)
  loading.value = false
}

// 格式化数字
const formatNumber = (num: number): string => {
  if (num >= 100000000) {
    return (num / 100000000).toFixed(1) + '亿'
  } else if (num >= 10000) {
    return (num / 10000).toFixed(1) + '万'
  }
  return num.toString()
}

// 格式化日期
const formatDate = (dateStr: string | null | undefined): string => {
  if (!dateStr) return '未知'
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN')
}

// 获取排名样式
const getRankClass = (index: number): string => {
  if (index === 0) return 'rank-gold'
  if (index === 1) return 'rank-silver'
  if (index === 2) return 'rank-bronze'
  return ''
}

// 登出
const handleLogout = () => {
  authStore.logout()
  ElMessage.success('已退出登录')
  router.push('/login')
}

onMounted(() => {
  loadOverview()
  loadRankings()
})
</script>

<style scoped>
.dashboard-container {
  min-height: 100vh;
  background: #f5f7fa;
}

.header {
  background: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  position: sticky;
  top: 0;
  z-index: 1000;
}

.header-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 15px 30px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.logo-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo {
  width: 40px;
  height: 40px;
}

.logo-section h3 {
  margin: 0;
  font-size: 18px;
  color: #333;
}

.nav-menu {
  display: flex;
  gap: 30px;
}

.nav-link {
  text-decoration: none;
  color: #666;
  font-size: 15px;
  transition: color 0.3s;
}

.nav-link:hover,
.nav-link.active {
  color: #00a1d6;
}

.user-section {
  display: flex;
  align-items: center;
  gap: 15px;
}

.username {
  font-size: 14px;
  color: #666;
}

.main-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 30px;
}

.section-title {
  font-size: 24px;
  color: #333;
  margin-bottom: 20px;
}

.overview-section {
  margin-bottom: 40px;
}

.stats-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
}

.stat-card {
  background: white;
  border-radius: 12px;
  padding: 25px;
  display: flex;
  align-items: center;
  gap: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  transition: transform 0.3s, box-shadow 0.3s;
}

.stat-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
}

.stat-content {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #333;
}

.stat-label {
  font-size: 14px;
  color: #999;
  margin-top: 5px;
}

.rankings-section {
  background: white;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.ranking-controls {
  margin-bottom: 20px;
}

.ranking-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.ranking-item {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 15px;
  background: #f9fafb;
  border-radius: 8px;
  transition: background 0.3s;
}

.ranking-item:hover {
  background: #f0f2f5;
}

.rank-number {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: bold;
  background: #e0e0e0;
  color: #666;
}

.rank-gold {
  background: linear-gradient(135deg, #ffd700, #ffed4e);
  color: white;
}

.rank-silver {
  background: linear-gradient(135deg, #c0c0c0, #e8e8e8);
  color: white;
}

.rank-bronze {
  background: linear-gradient(135deg, #cd7f32, #daa520);
  color: white;
}

.anime-cover {
  width: 80px;
  height: 110px;
  object-fit: cover;
  border-radius: 8px;
}

.anime-info {
  flex: 1;
}

.anime-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin: 0 0 10px 0;
}

.anime-meta {
  display: flex;
  gap: 10px;
  align-items: center;
}

.area-tag {
  padding: 4px 10px;
  background: #e1f0ff;
  color: #409eff;
  border-radius: 4px;
  font-size: 12px;
}

.rating {
  font-size: 14px;
  color: #f56c6c;
}

.anime-stats {
  display: flex;
  gap: 30px;
}

.stat-item {
  text-align: center;
}

.stat-item .stat-label {
  display: block;
  font-size: 12px;
  color: #999;
  margin-bottom: 5px;
}

.stat-item .stat-value {
  display: block;
  font-size: 16px;
  font-weight: 600;
  color: #333;
}
</style>
