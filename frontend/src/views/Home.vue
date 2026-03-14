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
                  :class="sortBy === 'rating' ? 'btn-primary' : 'btn-outline-primary'"
                  @click="sortBy = 'rating'"
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
                  :class="sortBy === 'favorites' ? 'btn-primary' : 'btn-outline-primary'"
                  @click="sortBy = 'favorites'"
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
                  <span v-if="sortBy === 'rating'">评分: {{ anime.rating || 'N/A' }}</span>
                  <span v-if="sortBy === 'views'">播放: {{ formatNumber(anime.views) }}</span>
                  <span v-if="sortBy === 'favorites'">追番: {{ formatNumber(anime.favorites) }}</span>
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
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { useAnalyticsStore } from '@/stores/analytics'
import type { AnimeData } from '@/api/analytics'

const router = useRouter()

// 使用 Pinia 数据分析 Store
const analyticsStore = useAnalyticsStore()

// 从 Store 中映射概览数据
const storeOverview = computed(() => analyticsStore.overview)

// 将 StatisticsOverview 字段映射到模板所需的展示字段
const overview = computed(() => ({
  totalAnime:      storeOverview.value?.total_animes   ?? 0,
  totalViews:      storeOverview.value?.total_views    ?? 0,
  totalFollowers:  storeOverview.value?.total_favorites ?? 0,
  averageRating:   storeOverview.value?.last_update
    ? new Date(storeOverview.value.last_update).toLocaleDateString('zh-CN')
    : '暂无',
  // 以下增长字段当前 API 暂不提供，保留为 undefined
  animeGrowth:    undefined as number | undefined,
  viewsGrowth:    undefined as number | undefined,
  followersGrowth: undefined as number | undefined,
  ratingChange:   '—',
}))

// 排行榜数据
const rankings = ref<AnimeData[]>([])
// 排序方式：与后端 API 字段保持一致（views / favorites / rating）
const sortBy = ref<'views' | 'favorites' | 'rating'>('rating')
const selectedAreas = ref<string[]>(['国内', '日本', '美国'])

// ECharts DOM 引用
const typeDistChart = ref<HTMLElement>()
const reputationChart = ref<HTMLElement>()
let typeChartInstance: echarts.ECharts | null = null
let reputationChartInstance: echarts.ECharts | null = null

// ResizeObserver 实例，用于自动响应容器尺寸变化
let typeChartResizeObserver: ResizeObserver | null = null
let reputationChartResizeObserver: ResizeObserver | null = null

// 口碑热度散点图的原始番剧数据缓存（供地区切换时复用）
const animeListForScatter = ref<AnimeData[]>([])

// 地区颜色映射（与遗留代码保持一致）
const areaColorMap: Record<string, string> = {
  '国内': '#FB7299',
  '日本': '#23ADE5',
  '美国': '#FFCE56',
}

// 格式化数字
const formatNumber = (num: number | undefined): string => {
  if (!num) return '0'
  if (num >= 100000000) return (num / 100000000).toFixed(1) + '亿'
  if (num >= 10000) return (num / 10000).toFixed(1) + '万'
  return num.toString()
}

// 格式化增长率
const formatGrowth = (growth: number | undefined): string => {
  if (growth === undefined) return '0.0%'
  return growth > 0 ? `+${growth}%` : `${growth}%`
}

// 获取增长类样式
const getGrowthClass = (growth: number | undefined): string => {
  if (!growth) return ''
  return growth > 0 ? 'positive' : 'negative'
}

// 切换地区筛选
const toggleArea = (area: string): void => {
  const index = selectedAreas.value.indexOf(area)
  if (index > -1) {
    selectedAreas.value.splice(index, 1)
  } else {
    selectedAreas.value.push(area)
  }
  updateReputationChart()
}

// 跳转偏好设置页
const showPreferences = (): void => {
  router.push('/genre-selection')
}

// 加载概览数据
const loadData = async (): Promise<void> => {
  await analyticsStore.fetchOverview()
  await loadRankings()
}

// 加载排行榜
const loadRankings = async (): Promise<void> => {
  rankings.value = await analyticsStore.fetchRankings(sortBy.value, 10)
}

/**
 * 使用 ResizeObserver 初始化 ECharts 图表，使其自动适应容器尺寸变化。
 * @param el - 图表容器 DOM 元素
 * @param option - ECharts 配置项
 * @returns [图表实例, ResizeObserver 实例]
 */
const initChartWithResizeObserver = (
  el: HTMLElement,
  option: echarts.EChartsOption
): [echarts.ECharts, ResizeObserver] => {
  // 销毁已有实例，防止重复初始化
  const existing = echarts.getInstanceByDom(el)
  if (existing) existing.dispose()

  const chart = echarts.init(el)
  chart.setOption(option)

  const observer = new ResizeObserver(() => chart.resize())
  observer.observe(el)

  return [chart, observer]
}

// 初始化类型分布饼图
const initTypeDistChart = async (): Promise<void> => {
  if (!typeDistChart.value) return

  // 获取真实的风格分布数据
  const styleData = await analyticsStore.fetchStyleDistribution()
  const chartData = Object.entries(styleData).map(([name, value]) => ({ name, value }))

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      left: '5%',
      top: 'center',
      type: 'scroll'
    },
    series: [{
      name: '类型分布',
      type: 'pie',
      // 环形饼图，更美观
      radius: ['35%', '60%'],
      center: ['60%', '50%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 8, borderColor: '#fff', borderWidth: 2 },
      label: { show: false, position: 'center' },
      emphasis: {
        label: { show: true, fontSize: 16, fontWeight: 'bold' },
        itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.5)' }
      },
      labelLine: { show: false },
      data: chartData.length > 0 ? chartData : [
        { value: 335, name: '热血' },
        { value: 310, name: '日常' },
        { value: 234, name: '恋爱' },
        { value: 135, name: '科幻' },
        { value: 154, name: '奇幻' }
      ]
    }]
  }

  ;[typeChartInstance, typeChartResizeObserver] = initChartWithResizeObserver(typeDistChart.value, option)
}

// 初始化口碑热度散点图（评分 vs 追番人数，按地区着色）
const initReputationChart = async (): Promise<void> => {
  if (!reputationChart.value) return

  // 获取较多番剧数据，供散点图使用
  const list = await analyticsStore.fetchRankings('rating', 100)
  animeListForScatter.value = list

  // 初始化空图表实例
  const initOption: echarts.EChartsOption = {
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'value', name: '评分', splitLine: { lineStyle: { type: 'dashed' } }, min: 0 },
    yAxis: { type: 'value', name: '追番人数', splitLine: { lineStyle: { type: 'dashed' } } }
  }

  ;[reputationChartInstance, reputationChartResizeObserver] = initChartWithResizeObserver(
    reputationChart.value,
    initOption
  )

  updateReputationChart()
}

// 更新口碑热度散点图（根据选中地区重新渲染）
const updateReputationChart = (): void => {
  if (!reputationChartInstance) return

  // 按选中地区分组，每个地区为一个 series
  const seriesMap: Record<string, [number, number, string][]> = {}
  selectedAreas.value.forEach(area => { seriesMap[area] = [] })

  animeListForScatter.value.forEach(anime => {
    if (!selectedAreas.value.includes(anime.area)) return
    // 评分或追番人数无效时跳过（对数轴不能绘制 ≤0 的值）
    if (anime.rating === null || anime.favorites <= 0) return
    seriesMap[anime.area]?.push([anime.rating, anime.favorites, anime.title])
  })

  const series: echarts.SeriesOption[] = selectedAreas.value.map(area => ({
    name: area,
    type: 'scatter',
    symbolSize: 10,
    itemStyle: { color: areaColorMap[area] ?? '#aaaaaa' },
    data: seriesMap[area] ?? [],
    emphasis: {
      focus: 'series',
      label: {
        show: true,
        formatter: (params: any) => params.value[2],
        position: 'top'
      }
    }
  }))

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        const [rating, favorites, title] = params.value as [number, number, string]
        return `${params.marker}<b>${title}</b><br/>地区：<b>${params.seriesName}</b><br/>评分：<b>${rating}</b><br/>追番：<b>${formatNumber(favorites)}</b>`
      }
    },
    legend: { data: selectedAreas.value, bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '12%', containLabel: true },
    xAxis: {
      type: 'value',
      name: '评分',
      splitLine: { lineStyle: { type: 'dashed' } },
      min: 0
    },
    yAxis: {
      type: 'log',
      name: '追番人数',
      splitLine: { lineStyle: { type: 'dashed' } },
      min: 1
    },
    series
  }

  reputationChartInstance.setOption(option, true)
}

// 监听排序变化，重新加载排行榜
watch(sortBy, () => {
  loadRankings()
})

// 组件挂载时初始化
onMounted(async () => {
  await loadData()
  await initTypeDistChart()
  await initReputationChart()
})

// 组件卸载时清理 ECharts 实例和 ResizeObserver，防止内存泄漏
onUnmounted(() => {
  typeChartResizeObserver?.disconnect()
  reputationChartResizeObserver?.disconnect()
  typeChartInstance?.dispose()
  reputationChartInstance?.dispose()
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
