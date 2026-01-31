<template>
  <div class="home-view">
    <!-- 关键指标卡片 -->
    <div class="row mb-4">
      <div class="col-md-3 mb-3">
        <div class="metric-card pink">
          <div class="metric-icon">
            <i class="fas fa-film"></i>
          </div>
          <div class="metric-content">
            <h5>番剧总数</h5>
            <p class="metric-value">{{ overview.totalAnime || '加载中...' }}</p>
            <p class="metric-growth" :class="getGrowthClass(overview.animeGrowth)">
              {{ formatGrowth(overview.animeGrowth) }} 较上月增长
            </p>
          </div>
        </div>
      </div>

      <div class="col-md-3 mb-3">
        <div class="metric-card blue">
          <div class="metric-icon">
            <i class="fas fa-play-circle"></i>
          </div>
          <div class="metric-content">
            <h5>总播放量</h5>
            <p class="metric-value">{{ formatNumber(overview.totalViews) || '加载中...' }}</p>
            <p class="metric-growth" :class="getGrowthClass(overview.viewsGrowth)">
              {{ formatGrowth(overview.viewsGrowth) }} 较上月增长
            </p>
          </div>
        </div>
      </div>

      <div class="col-md-3 mb-3">
        <div class="metric-card purple">
          <div class="metric-icon">
            <i class="fas fa-heart"></i>
          </div>
          <div class="metric-content">
            <h5>追番人数</h5>
            <p class="metric-value">{{ formatNumber(overview.totalFollowers) || '加载中...' }}</p>
            <p class="metric-growth" :class="getGrowthClass(overview.followersGrowth)">
              {{ formatGrowth(overview.followersGrowth) }} 较上月增长
            </p>
          </div>
        </div>
      </div>

      <div class="col-md-3 mb-3">
        <div class="metric-card yellow">
          <div class="metric-icon">
            <i class="fas fa-star"></i>
          </div>
          <div class="metric-content">
            <h5>收藏占比</h5>
            <p class="metric-value">{{ overview.averageRating || '加载中...' }}</p>
            <p class="metric-growth">
              {{ overview.ratingChange || '0.0' }} 较上月变化
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- 排行榜和图表 -->
    <div class="row">
      <!-- 热门番剧排行 -->
      <div class="col-md-4 mb-3">
        <div class="card h-100">
          <div class="card-header">
            <h5>热门番剧排行</h5>
            <div class="controls">
              <button class="btn btn-sm btn-pink" @click="showPreferences">
                <i class="fas fa-heart me-1"></i>根据偏好推荐
              </button>
              <div class="btn-group btn-group-sm mt-2">
                <button 
                  class="btn"
                  :class="sortBy === 'score' ? 'btn-primary' : 'btn-outline-primary'"
                  @click="sortBy = 'score'"
                >
                  <i class="fas fa-star me-1"></i>评分
                </button>
                <button 
                  class="btn"
                  :class="sortBy === 'views' ? 'btn-primary' : 'btn-outline-primary'"
                  @click="sortBy = 'views'"
                >
                  <i class="fas fa-play-circle me-1"></i>播放量
                </button>
                <button 
                  class="btn"
                  :class="sortBy === 'followers' ? 'btn-primary' : 'btn-outline-primary'"
                  @click="sortBy = 'followers'"
                >
                  <i class="fas fa-heart me-1"></i>追番人数
                </button>
              </div>
            </div>
          </div>
          <div class="rank-list">
            <div v-if="rankings.length === 0" class="text-center py-5">
              <i class="fas fa-spinner fa-spin"></i> 加载中...
            </div>
            <div 
              v-for="(anime, index) in rankings" 
              :key="anime.season_id"
              class="rank-item"
            >
              <div class="rank-number">{{ index + 1 }}</div>
              <img :src="anime.cover" :alt="anime.title" class="rank-cover" />
              <div class="rank-info">
                <div class="rank-title">{{ anime.title }}</div>
                <div class="rank-stats">
                  <span v-if="sortBy === 'score'">评分: {{ anime.rating || 'N/A' }}</span>
                  <span v-if="sortBy === 'views'">播放: {{ formatNumber(anime.views) }}</span>
                  <span v-if="sortBy === 'followers'">追番: {{ formatNumber(anime.favorites) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 图表区域 -->
      <div class="col-md-8">
        <div class="row h-100">
          <!-- 番剧类型分布 -->
          <div class="col-md-6 mb-3">
            <div class="card h-100">
              <div class="card-header">
                <h5>番剧类型分布</h5>
              </div>
              <div class="chart-wrapper">
                <div ref="typeDistChart" class="chart"></div>
              </div>
            </div>
          </div>

          <!-- 口碑热度分布 -->
          <div class="col-md-6 mb-3">
            <div class="card h-100">
              <div class="card-header">
                <h5>口碑热度分布</h5>
                <div class="btn-group btn-group-sm">
                  <button 
                    v-for="area in ['国内', '日本', '美国']"
                    :key="area"
                    class="btn"
                    :class="selectedAreas.includes(area) ? 'btn-primary' : 'btn-outline-primary'"
                    @click="toggleArea(area)"
                  >
                    {{ area }}
                  </button>
                </div>
              </div>
              <div class="chart-wrapper">
                <div ref="reputationChart" class="chart"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { getOverview, getRankings } from '@/api/analytics'

const router = useRouter()

// 数据状态
const overview = ref<any>({})
const rankings = ref<any[]>([])
const sortBy = ref('score')
const selectedAreas = ref(['国内', '日本', '美国'])

// ECharts 实例
const typeDistChart = ref<HTMLElement>()
const reputationChart = ref<HTMLElement>()
let typeChartInstance: any = null
let reputationChartInstance: any = null

// 格式化数字
const formatNumber = (num: number | undefined) => {
  if (!num) return '0'
  if (num >= 100000000) return (num / 100000000).toFixed(1) + '亿'
  if (num >= 10000) return (num / 10000).toFixed(1) + '万'
  return num.toString()
}

// 格式化增长率
const formatGrowth = (growth: number | undefined) => {
  if (growth === undefined) return '0.0%'
  return growth > 0 ? `+${growth}%` : `${growth}%`
}

// 获取增长类样式
const getGrowthClass = (growth: number | undefined) => {
  if (!growth) return ''
  return growth > 0 ? 'positive' : 'negative'
}

// 切换地区
const toggleArea = (area: string) => {
  const index = selectedAreas.value.indexOf(area)
  if (index > -1) {
    selectedAreas.value.splice(index, 1)
  } else {
    selectedAreas.value.push(area)
  }
  updateReputationChart()
}

// 显示偏好设置
const showPreferences = () => {
  router.push('/genre-selection')
}

// 加载数据
const loadData = async () => {
  try {
    // 加载概览数据
    const overviewData = await getOverview()
    overview.value = overviewData

    // 加载排行榜
    await loadRankings()
  } catch (error) {
    console.error('加载数据失败:', error)
  }
}

// 加载排行榜
const loadRankings = async () => {
  try {
    const data = await getRankings(sortBy.value, 10)
    rankings.value = data
  } catch (error) {
    console.error('加载排行榜失败:', error)
  }
}

// 初始化类型分布图表
const initTypeDistChart = () => {
  if (!typeDistChart.value) return
  
  typeChartInstance = echarts.init(typeDistChart.value)
  
  const option = {
    tooltip: {
      trigger: 'item'
    },
    series: [{
      type: 'pie',
      radius: '60%',
      data: [
        { value: 335, name: '热血' },
        { value: 310, name: '日常' },
        { value: 234, name: '恋爱' },
        { value: 135, name: '科幻' },
        { value: 154, name: '奇幻' }
      ],
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowOffsetX: 0,
          shadowColor: 'rgba(0, 0, 0, 0.5)'
        }
      }
    }]
  }
  
  typeChartInstance.setOption(option)
}

// 初始化口碑热度图表
const initReputationChart = () => {
  if (!reputationChart.value) return
  
  reputationChartInstance = echarts.init(reputationChart.value)
  updateReputationChart()
}

// 更新口碑热度图表
const updateReputationChart = () => {
  if (!reputationChartInstance) return
  
  const option = {
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      data: selectedAreas.value
    },
    xAxis: {
      type: 'category',
      data: ['1月', '2月', '3月', '4月', '5月', '6月']
    },
    yAxis: {
      type: 'value'
    },
    series: selectedAreas.value.map(area => ({
      name: area,
      type: 'line',
      data: Array.from({ length: 6 }, () => Math.floor(Math.random() * 100))
    }))
  }
  
  reputationChartInstance.setOption(option)
}

// 监听排序变化
watch(sortBy, () => {
  loadRankings()
})

// 初始化
onMounted(() => {
  loadData()
  initTypeDistChart()
  initReputationChart()
  
  // 响应式调整图表大小
  window.addEventListener('resize', () => {
    typeChartInstance?.resize()
    reputationChartInstance?.resize()
  })
})
</script>

<style scoped>
.home-view {
  padding: 2rem 0;
}

.metric-card {
  padding: 1.5rem;
  border-radius: 10px;
  color: white;
  display: flex;
  align-items: center;
  gap: 1rem;
  height: 100%;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
  transition: transform 0.3s;
}

.metric-card:hover {
  transform: translateY(-5px);
}

.metric-card.pink {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}

.metric-card.blue {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
}

.metric-card.purple {
  background: linear-gradient(135deg, #a18cd1 0%, #fbc2eb 100%);
}

.metric-card.yellow {
  background: linear-gradient(135deg, #fad0c4 0%, #ffd1ff 100%);
}

.metric-icon {
  font-size: 3rem;
  opacity: 0.8;
}

.metric-content h5 {
  margin: 0;
  font-size: 0.9rem;
  opacity: 0.9;
}

.metric-value {
  margin: 0.5rem 0;
  font-size: 2rem;
  font-weight: bold;
}

.metric-growth {
  margin: 0;
  font-size: 0.85rem;
  opacity: 0.9;
}

.metric-growth.positive {
  color: #4ade80;
}

.metric-growth.negative {
  color: #f87171;
}

.card {
  border: none;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  border-radius: 10px;
  overflow: hidden;
}

.card-header {
  background: white;
  border-bottom: 1px solid #e5e7eb;
  padding: 1rem 1.5rem;
}

.card-header h5 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
}

.controls {
  margin-top: 1rem;
}

.btn-pink {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  color: white;
  border: none;
}

.rank-list {
  max-height: 500px;
  overflow-y: auto;
  padding: 1rem;
}

.rank-item {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem;
  border-radius: 8px;
  margin-bottom: 0.5rem;
  transition: background 0.3s;
}

.rank-item:hover {
  background: #f3f4f6;
}

.rank-number {
  font-size: 1.5rem;
  font-weight: bold;
  color: #6366f1;
  min-width: 30px;
}

.rank-cover {
  width: 60px;
  height: 80px;
  object-fit: cover;
  border-radius: 5px;
}

.rank-info {
  flex: 1;
}

.rank-title {
  font-weight: 600;
  margin-bottom: 0.25rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rank-stats {
  font-size: 0.85rem;
  color: #6b7280;
}

.chart-wrapper {
  padding: 1rem;
  height: 300px;
}

.chart {
  width: 100%;
  height: 100%;
}
</style>
