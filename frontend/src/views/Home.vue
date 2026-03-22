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
            <p class="metric-value">{{ isLoading ? '加载中...' : overview.totalAnime }}</p>
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
            <p class="metric-value">{{ isLoading ? '加载中...' : formatNumber(overview.totalViews) }}</p>
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
            <p class="metric-value">{{ isLoading ? '加载中...' : formatNumber(overview.totalFollowers) }}</p>
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
            <p class="metric-value">{{ isLoading ? '加载中...' : overview.averageRating }}</p>
            <p class="metric-growth">
              {{ overview.ratingChange || '0.0' }} 较上月变化
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- 排行榜和图表 -->
<div class="row">
      <div class="col-md-8">
        <div class="row">
          <div class="col-12 mb-3">
            <div class="style-unified">
              <div class="card-header-unified">
                <h5>今日推荐</h5>
              </div>
              <div class="d-flex align-items-center justify-content-center" style="min-height: 200px;">
                <div class="text-muted text-center">
                  <i class="fas fa-magic mb-2 d-block text-primary fs-3"></i>
                  <small>暂无推荐数据</small>
                </div>
              </div>
            </div>
          </div>

          <div class="col-12 mb-3">
            <div class="style-unified">
              <div class="card-header-unified">
                <h5>番剧类型分布</h5>
                <div v-if="isTypeDrilledDown" class="d-flex align-items-center gap-2">
                  <button class="btn btn-sm btn-outline-secondary px-2 py-0" @click="backToMainTypeChart">
                    <i class="fas fa-arrow-left me-1"></i>返回
                  </button>
                  <small class="text-muted">已细分合并的部分</small>
                </div>
              </div>
              <div class="chart-wrapper">
                <div ref="typeChartRef" style="height: 380px; width: 100%"></div>
              </div>
            </div>
          </div>

          <div class="col-12 mb-3">
            <div class="style-unified">
              <div class="card-header-unified">
                <h5>口碑热度分布</h5>
                <div class="area-btn-group">
                  <button
                    v-for="area in ['国内', '日本', '美国']"
                    :key="area"
                    class="area-btn"
                    :class="{ active: selectedAreas.includes(area) }"
                    @click="toggleArea(area)"
                  >
                    {{ area }}
                  </button>
                </div>
              </div>
              <div class="chart-wrapper">
                <div ref="scatterChartRef" style="height: 380px; width: 100%"></div>
              </div>
            </div>
          </div>

        </div>
      </div>

      <div class="col-md-4 mb-3">
        <div class="card h-100">
          <div class="card-header">
            <h5>热门番剧排行</h5>
            <div class="controls">
              <button class="btn btn-sm btn-pink" @click="showPreferences">
                <i class="fas fa-heart me-1"></i>根据偏好推荐
              </button>
              <div class="btn-group btn-group-sm mt-2 w-100">
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
                  <i class="fas fa-play-circle me-1"></i>播放
                </button>
                <button
                  class="btn"
                  :class="sortBy === 'favorites' ? 'btn-primary' : 'btn-outline-primary'"
                  @click="sortBy = 'favorites'"
                >
                  <i class="fas fa-heart me-1"></i>追番
                </button>
              </div>
            </div>
          </div>
          <div class="rank-list flex-grow-1">
            <div v-if="isLoading" class="text-center py-5">
              <i class="fas fa-spinner fa-spin"></i> 加载中...
            </div>
            <div v-else-if="rankings.length === 0" class="text-center py-5 text-muted">
              暂无排行榜数据
            </div>
            <div
              v-for="(anime, index) in rankings"
              :key="anime.season_id"
              class="rank-item"
            >
              <div class="rank-number">{{ index + 1 }}</div>
              <img :src="getProxiedImageUrl(anime)" :alt="anime.title" class="rank-cover" />
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
    </div>
  </div>
</template>

<script setup lang="ts">
import {computed, onMounted, ref, watch} from 'vue'
import {useRouter} from 'vue-router'
import type * as echarts from 'echarts'
import {useEcharts} from '@/composables/useEcharts'
import {useAnalyticsStore} from '@/stores/analytics'
import type {AnimeData} from '@/api/analytics'
import {getReputationPopularityChart, getTypeDistributionChart} from '@/api/analytics'
import {getProxiedImageUrl} from '@/utils/imageProxy'

const router = useRouter()

// 使用 Pinia 数据分析 Store
const analyticsStore = useAnalyticsStore()
const isLoading = ref(true)

// 从 Store 中映射概览数据
const storeOverview = computed(() => analyticsStore.overview)

// 将 StatisticsOverview 字段映射到模板所需的展示字段
const overview = computed(() => ({
  totalAnime: storeOverview.value?.total_animes ?? 0,
  totalViews: storeOverview.value?.total_views ?? 0,
  totalFollowers: storeOverview.value?.total_favorites ?? 0,
  averageRating: storeOverview.value?.last_update
    ? new Date(storeOverview.value.last_update).toLocaleDateString('zh-CN')
    : '暂无',
  // 以下增长字段当前 API 暂不提供，保留为 undefined
  animeGrowth: undefined as number | undefined,
  viewsGrowth: undefined as number | undefined,
  followersGrowth: undefined as number | undefined,
  ratingChange: '—',
}))

// 排行榜数据
const rankings = ref<AnimeData[]>([])
// 排序方式：与后端 API 字段保持一致（views / favorites / rating）
const sortBy = ref<'views' | 'favorites' | 'rating'>('rating')

// ─── 类型分布饼图逻辑 ──────────────────────────────────────────────────────────
const {
  chartRef: typeChartRef,
  initChart: initTypeChart,
  setOption: setTypeOption,
  chartInstance: typeChartInstance
} = useEcharts()

/** 当前是否处于"其他"类别的下钻视图 */
const isTypeDrilledDown = ref(false)
/** 顶级视图数据（包含"其他"节点） */
let typeTopLevelData: { name: string; value: number }[] = []
/** "其他"下钻视图数据 */
let typeOtherData: { name: string; value: number }[] = []

/** 最大显示扇区数，超出部分合并为"其他" */
const MAX_SLICES = 21

/**
 * 初始化类型分布饼图配置（空配置，后续通过 setOption 更新）
 * 并绑定点击事件以支持"其他"下钻功能。
 */
const initTypeDistChart = async (): Promise<void> => {
  // 初始化空图表占位
  initTypeChart({
    tooltip: {trigger: 'item', formatter: '{b}: {c} ({d}%)'},
    legend: [
      {orient: 'vertical', left: '5%', top: 'center'},
      {orient: 'vertical', right: '5%', top: 'center'}
    ],
    series: [{
      name: '类型分布',
      type: 'pie',
      radius: ['35%', '60%'],
      center: ['60%', '50%'],
      avoidLabelOverlap: false,
      itemStyle: {borderRadius: 8, borderColor: '#fff', borderWidth: 2},
      label: {show: false},
      emphasis: {
        label: {show: true, fontSize: 16, fontWeight: 'bold' as const},
        itemStyle: {shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.5)'}
      },
      labelLine: {show: false},
      data: []
    }]
  })

  // 绑定点击事件：点击"其他"扇区时进入下钻视图
  typeChartInstance.value?.on('click', (params: any) => {
    if (!isTypeDrilledDown.value && params.name === '其他' && typeOtherData.length > 0) {
      isTypeDrilledDown.value = true
      renderTypeChart(typeOtherData)
    }
  })

  await loadTypeDistribution()
}

/** 从 API 加载类型分布数据，区分顶级视图和"其他"细分视图 */
const loadTypeDistribution = async (): Promise<void> => {
  try {
    const sortedStyles = await getTypeDistributionChart()

    if (sortedStyles.length === 0) {
      typeTopLevelData = []
      typeOtherData = []
      renderTypeChart([])
      return
    }

    if (sortedStyles.length <= MAX_SLICES) {
      // 数量未超过上限，直接全部展示
      typeTopLevelData = sortedStyles.map(([name, value]) => ({name, value}))
      typeOtherData = []
    } else {
      // 动态确定最优分割点：确保"其他"不超过最小的已显示类别
      let numToShow = 4
      while (numToShow < MAX_SLICES) {
        const otherCount = sortedStyles.slice(numToShow).reduce((acc, [, c]) => acc + c, 0)
        const smallestTopCount = sortedStyles[numToShow - 1][1]
        if (otherCount <= smallestTopCount) break
        numToShow++
      }

      const topData = sortedStyles.slice(0, numToShow)
      const otherItems = sortedStyles.slice(numToShow)
      const otherTotal = otherItems.reduce((acc, [, c]) => acc + c, 0)

      typeTopLevelData = topData.map(([name, value]) => ({name, value}))
      if (otherTotal > 0) {
        typeTopLevelData.push({name: '其他', value: otherTotal})
        typeOtherData = otherItems.map(([name, value]) => ({name, value}))
      } else {
        typeOtherData = []
      }
    }

    isTypeDrilledDown.value = false
    renderTypeChart(typeTopLevelData)
  } catch (error) {
    console.error('加载类型分布失败:', error)
  }
}

/**
 * 渲染类型分布饼图。
 * 图例始终保持左右两列布局，与遗留版本行为一致。
 *
 * @param dataToShow - 要渲染的数据项数组
 */
const renderTypeChart = (dataToShow: { name: string; value: number }[]): void => {
  if (dataToShow.length === 0) {
    setTypeOption({series: [{data: []}], legend: [{}, {}]}, {replaceMerge: ['legend']})
    return
  }

  const legendNames = dataToShow.map(item => item.name)
  const midIndex = Math.ceil(legendNames.length / 2)

  setTypeOption({
    legend: [
      {orient: 'vertical', left: '5%', top: 'center', data: legendNames.slice(0, midIndex)},
      {orient: 'vertical', right: '5%', top: 'center', data: legendNames.slice(midIndex)}
    ],
    series: [{data: dataToShow}]
  }, {replaceMerge: ['legend']})
}

/** 返回类型分布顶级视图 */
const backToMainTypeChart = (): void => {
  isTypeDrilledDown.value = false
  renderTypeChart(typeTopLevelData)
}

// ─── 口碑热度散点图逻辑 ────────────────────────────────────────────────────────
const {chartRef: scatterChartRef, initChart: initScatterChart, setOption: setScatterOption} = useEcharts()

/** 当前选中的地区列表（用于多选过滤） */
const selectedAreas = ref<string[]>(['国内', '日本', '美国'])

/** 地区颜色映射 */
const areaColorMap: Record<string, string> = {
  '国内': '#FB7299',
  '日本': '#23ADE5',
  '美国': '#FFCE56',
}

/** 初始化口碑热度散点图并加载数据 */
const initReputationScatterChart = async (): Promise<void> => {
  // 初始化空图表占位
  initScatterChart({
    tooltip: {trigger: 'item'},
    grid: {left: '3%', right: '4%', bottom: '12%', containLabel: true},
    xAxis: {
      type: 'value',
      name: '评分',
      splitLine: {lineStyle: {type: 'dashed' as const}},
      min: 7  // B 站评分普遍 7 分以上，截断低分噪点
    },
    yAxis: {
      type: 'log',
      name: '追番人数',
      splitLine: {lineStyle: {type: 'dashed' as const}},
      min: 1000  // 追番不足 1000 的番剧不具代表性
    },
    series: []
  })

  await loadScatterChart()
}

/** 从 API 加载口碑热度散点图数据，根据 selectedAreas 过滤地区 */
const loadScatterChart = async (): Promise<void> => {
  try {
    const areasQuery = selectedAreas.value.join(',')
    const response = await getReputationPopularityChart(areasQuery)
    const chartData = response.data || []

    const formatNum = (num: number): string => {
      if (num >= 100000000) return (num / 100000000).toFixed(1) + '亿'
      if (num >= 10000) return (num / 10000).toFixed(1) + '万'
      return num.toLocaleString()
    }

    // 按地区分组，每个地区独立为一个 series，使 legend 与 series 一一对应
    const seriesByArea: Record<string, Array<[number, number, string, number, number, string]>> = {}
    for (const area of selectedAreas.value) {
      seriesByArea[area] = []
    }
    for (const item of chartData) {
      if (seriesByArea[item.area]) {
        seriesByArea[item.area].push([
          item.rating, item.favorites, item.title, item.views, item.ratingRaw, item.area,
        ])
      }
    }

    const series: echarts.SeriesOption[] = selectedAreas.value.map(area => ({
      name: area,
      type: 'scatter',
      symbolSize: 10,
      itemStyle: {color: areaColorMap[area] ?? '#cccccc'},
      data: seriesByArea[area],
      emphasis: {
        focus: 'series',
        label: {show: true, formatter: (p: any) => p.value[2], position: 'top' as const},
      },
    }))

    setScatterOption({
      tooltip: {
        trigger: 'item',
        formatter: (params: any) => {
          if (!params.value) return '无数据'
          const [, followers, title, views, originalScore, area] = params.value as
            [number, number, string, number, number, string]
          return `${params.marker}<b>${title}</b><br/>
地区: <b>${area || '未知'}</b><br/>
评分: <b>${(originalScore ?? 0).toFixed(1)}</b><br/>
追番: <b>${formatNum(followers)}</b><br/>
播放: <b>${formatNum(views)}</b>`
        }
      },
      legend: {
        data: selectedAreas.value,
        bottom: 0
      },
      grid: {left: '3%', right: '4%', bottom: '12%', containLabel: true},
      xAxis: {
        type: 'value',
        name: '评分',
        nameLocation: 'middle',
        nameGap: 25,
        splitLine: {lineStyle: {type: 'dashed' as const}},
        min: 7,
      },
      yAxis: {
        type: 'log',
        name: '追番人数',
        splitLine: {lineStyle: {type: 'dashed' as const}},
        min: 1000,
      },
      series,
    }, {notMerge: true})
  } catch (error) {
    console.error('加载口碑热度散点图失败:', error)
  }
}

// ─── 通用工具函数 ──────────────────────────────────────────────────────────────

/** 格式化数字（亿 / 万） */
const formatNumber = (num: number | undefined): string => {
  if (!num) return '0'
  if (num >= 100000000) return (num / 100000000).toFixed(1) + '亿'
  if (num >= 10000) return (num / 10000).toFixed(1) + '万'
  return num.toString()
}

/** 格式化增长率 */
const formatGrowth = (growth: number | undefined): string => {
  if (growth === undefined) return '0.0%'
  return growth > 0 ? `+${growth}%` : `${growth}%`
}

/** 获取增长类样式 */
const getGrowthClass = (growth: number | undefined): string => {
  if (!growth) return ''
  return growth > 0 ? 'positive' : 'negative'
}

/** 切换地区筛选，重新加载散点图 */
const toggleArea = (area: string): void => {
  const index = selectedAreas.value.indexOf(area)
  if (index > -1) {
    selectedAreas.value.splice(index, 1)
  } else {
    selectedAreas.value.push(area)
  }
  loadScatterChart()
}

/** 跳转偏好设置页 */
const showPreferences = (): void => {
  router.push('/genre-selection')
}

/** 加载概览数据与排行榜 */
const loadData = async (): Promise<void> => {
  isLoading.value = true
  await analyticsStore.fetchOverview()
  await loadRankings()
  isLoading.value = false
}

/** 加载排行榜 */
const loadRankings = async (): Promise<void> => {
  rankings.value = await analyticsStore.fetchRankings(sortBy.value, 10)
}

// 监听排序变化，重新加载排行榜
watch(sortBy, () => {
  loadRankings()
})

// 组件挂载时初始化所有图表和数据
onMounted(async () => {
  await loadData()
  await initTypeDistChart()
  await initReputationScatterChart()
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
  flex-grow: 1;
  height: 0;
  min-height: 100%;
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
  width: 100%;
}

/* ── 统一图表容器（参照 Status 页面风格） ── */
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
  padding: 0.9rem 1.25rem;
  background: transparent;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.card-header-unified h5 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: #1f2937;
}

/* ── 地区筛选按钮（口碑热度分布） ── */
.area-btn-group {
  display: flex;
  gap: 6px;
}

.area-btn {
  padding: 4px 12px;
  border: 1px solid #d1d5db;
  border-radius: 20px;
  background: white;
  font-size: 0.8rem;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.2s ease;
}

.area-btn:hover {
  border-color: #4facfe;
  color: #4facfe;
}

.area-btn.active {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  border-color: transparent;
  color: white;
  font-weight: 500;
}
</style>
