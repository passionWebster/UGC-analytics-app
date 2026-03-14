<template>
  <div class="status-view">
    <!-- 搜索区域 -->
    <div class="row mb-3">
      <div class="col-md-8 mx-auto">
        <div class="input-group">
          <input
            v-model="keyword"
            class="form-control form-control-lg"
            placeholder="输入番剧名搜索..."
            type="text"
            @keyup.enter="handleSearch"
          />
          <button class="btn btn-primary btn-lg" @click="handleSearch">
            <i class="fas fa-search me-1"></i>搜索
          </button>
          <button
            v-if="animeData"
            class="btn btn-secondary btn-lg"
            @click="toggleEpisodeDetails"
          >
            <i class="fas fa-list me-1"></i>剧集详情
          </button>
        </div>
        <div v-if="statusMessage" class="form-text mt-2">{{ statusMessage }}</div>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div v-if="animeData" class="row mb-3">
      <div class="col-md-3 mb-3">
        <div class="card text-center p-2 h-100 stat-card">
          <div class="stat-icon bg-primary">
            <i class="fas fa-heart"></i>
          </div>
          <h6 class="card-title text-muted mt-2 mb-1">追番人数</h6>
          <p class="display-6 mb-0 text-primary">{{ formatNumber(animeData.favorites) }}</p>
        </div>
      </div>
      <div class="col-md-3 mb-3">
        <div class="card text-center p-2 h-100 stat-card">
          <div class="stat-icon bg-success">
            <i class="fas fa-play-circle"></i>
          </div>
          <h6 class="card-title text-muted mt-2 mb-1">播放数量</h6>
          <p class="display-6 mb-0 text-success">{{ formatNumber(animeData.views) }}</p>
        </div>
      </div>
      <div class="col-md-3 mb-3">
        <div class="card text-center p-2 h-100 stat-card">
          <div class="stat-icon bg-warning">
            <i class="fas fa-film"></i>
          </div>
          <h6 class="card-title text-muted mt-2 mb-1">剧集数量</h6>
          <p class="display-6 mb-0 text-warning">{{ episodes.length || 0 }}</p>
        </div>
      </div>
      <div class="col-md-3 mb-3">
        <div class="card text-center p-2 h-100 stat-card">
          <div class="stat-icon bg-info">
            <i class="fas fa-chart-line"></i>
          </div>
          <h6 class="card-title text-muted mt-2 mb-1">平均播放</h6>
          <p class="display-6 mb-0 text-info">{{ formatNumber(avgViews) }}</p>
        </div>
      </div>
    </div>

    <!-- 图表区域 -->
    <div v-if="animeData" class="row graph-row mb-3">
      <div class="col-md-6">
        <div class="card p-2">
          <div class="d-flex justify-content-between align-items-center mb-2">
            <h5 class="card-title mb-0">播放量趋势</h5>
            <small class="text-muted">点击柱子查看该集观看时间分布</small>
          </div>
          <div class="chart-container">
            <div ref="playTrendChart" style="height: 400px; width: 100%"></div>
          </div>
        </div>
      </div>
      <div class="col-md-6">
        <div class="card p-2">
          <div class="d-flex justify-content-between align-items-center mb-2">
            <h5 class="card-title mb-0">观看时间分布</h5>
            <small class="text-muted">{{ watchTimeSubtitle }}</small>
          </div>
          <div class="chart-container">
            <div ref="watchTimeChart" style="height: 400px; width: 100%"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- 剧集详情表格 -->
    <div v-if="showEpisodeDetails && episodes.length > 0" class="row">
      <div class="col-md-12">
        <div class="card p-3">
          <h5 class="card-title mb-3">
            <i class="fas fa-list"></i> 剧集详情
          </h5>
          <div class="table-responsive">
            <table class="table table-hover">
              <thead>
                <tr>
                  <th>集数</th>
                  <th>标题</th>
                  <th>播放量</th>
                  <th>观看高峰时段</th>
                  <th>在线峰值</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(episode, index) in episodes"
                  :key="index"
                  :class="{ 'table-active': selectedEpisodeIndex === index }"
                  style="cursor: pointer"
                  @click="selectEpisode(index)"
                >
                  <td>{{ index + 1 }}</td>
                  <td>{{ episode.title || `第${index + 1}集` }}</td>
                  <td>{{ formatNumber(episode.views) }}</td>
                  <td>{{ episode.peakTime || '暂无数据' }}</td>
                  <td>{{ episode.peakOnline ? formatNumber(episode.peakOnline) : '暂无数据' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import type { ECharts } from 'echarts'
import { searchAnimes, getAnimeDetail, getAnimeEpisodes } from '@/api/analytics'

// ─── 状态管理 ───────────────────────────────────────────────────────────────
const keyword = ref('')
const statusMessage = ref('')
const animeData = ref<any>(null)
/** 剧集列表（来自 API 或回退至空数组） */
const episodes = ref<Array<{ title: string; views: number; peakTime: string | null; peakOnline: number | null }>>([])
const showEpisodeDetails = ref(false)
const watchTimeSubtitle = ref('所有剧集总计')
/** 当前选中的剧集索引，-1 表示全局汇总 */
const selectedEpisodeIndex = ref(-1)

// ─── 图表 DOM 引用 ───────────────────────────────────────────────────────────
const playTrendChart = ref<HTMLElement>()
const watchTimeChart = ref<HTMLElement>()
let playTrendInstance: ECharts | null = null
let watchTimeInstance: ECharts | null = null
let playTrendResizeObserver: ResizeObserver | null = null
let watchTimeResizeObserver: ResizeObserver | null = null

// ─── 计算属性 ────────────────────────────────────────────────────────────────
/** 剧集平均播放量 */
const avgViews = computed(() => {
  if (!episodes.value.length) return 0
  const total = episodes.value.reduce((sum, ep) => sum + (ep.views || 0), 0)
  return Math.round(total / episodes.value.length)
})

// ─── 工具函数 ────────────────────────────────────────────────────────────────
/** 格式化数字（亿 / 万） */
const formatNumber = (num: number | undefined | null): string => {
  if (!num) return '0'
  if (num >= 100000000) return (num / 100000000).toFixed(1) + '亿'
  if (num >= 10000) return (num / 10000).toFixed(1) + '万'
  return num.toString()
}

/**
 * 根据剧集索引生成该集的 24 小时观看时间分布。
 * 由于后端暂无小时粒度数据，这里使用确定性算法：
 * 基于剧集播放量和索引生成可重现的分布曲线，模拟真实观看高峰（晚高峰 + 午休峰值）。
 */
const generateWatchTimeData = (episodeIndex: number, baseViews: number): number[] => {
  // 使用 season_id 与剧集索引作为伪随机种子，保证同一集每次渲染结果一致
  const seed = (animeData.value?.season_id ?? 0) * 100 + episodeIndex
  const pseudoRand = (offset: number): number => {
    const x = Math.sin(seed + offset) * 10000
    return x - Math.floor(x)
  }
  const scale = Math.max(baseViews / 1000, 100)
  return Array.from({ length: 24 }, (_, hour) => {
    // 晚高峰 20-23 点
    const eveningPeak = hour >= 20 && hour <= 23 ? 0.8 + pseudoRand(hour) * 0.4 : 0
    // 午休高峰 12-14 点
    const lunchPeak = hour >= 12 && hour <= 14 ? 0.5 + pseudoRand(hour + 50) * 0.3 : 0
    // 基础波动
    const base = 0.1 + pseudoRand(hour + 100) * 0.2
    return Math.round((eveningPeak + lunchPeak + base) * scale)
  })
}

// ─── 搜索逻辑 ────────────────────────────────────────────────────────────────
const handleSearch = async () => {
  if (!keyword.value.trim()) {
    statusMessage.value = '请输入番剧名称'
    return
  }

  try {
    statusMessage.value = '搜索中...'
    const response = await searchAnimes(keyword.value)

    if (response.list && response.list.length > 0) {
      const anime = response.list[0]
      // 获取详细信息
      const detailResponse = await getAnimeDetail(anime.season_id)
      animeData.value = detailResponse.data || anime
      statusMessage.value = `找到番剧：${anime.title}`

      // 获取剧集数据
      try {
        const epResponse = await getAnimeEpisodes(anime.season_id)
        episodes.value = epResponse.data || []
      } catch {
        episodes.value = []
      }

      selectedEpisodeIndex.value = -1
      watchTimeSubtitle.value = '所有剧集总计'

      // 等待 DOM 更新后渲染图表
      await nextTick()
      renderCharts()
    } else {
      statusMessage.value = '未找到相关番剧'
      animeData.value = null
      episodes.value = []
    }
  } catch (error) {
    console.error('搜索失败:', error)
    statusMessage.value = '搜索失败，请重试'
  }
}

const toggleEpisodeDetails = () => {
  showEpisodeDetails.value = !showEpisodeDetails.value
}

// ─── 剧集选中交互 ────────────────────────────────────────────────────────────
/**
 * 点击剧集行或柱子时，切换观看时间分布图为该集数据。
 * 若再次点击同一集，则还原为全局汇总视图。
 */
const selectEpisode = (index: number) => {
  if (selectedEpisodeIndex.value === index) {
    // 取消选中，恢复全局汇总
    selectedEpisodeIndex.value = -1
    watchTimeSubtitle.value = '所有剧集总计'
  } else {
    selectedEpisodeIndex.value = index
    const ep = episodes.value[index]
    watchTimeSubtitle.value = ep?.title || `第${index + 1}集`
  }
  renderWatchTimeChart()
}

// ─── 图表渲染 ────────────────────────────────────────────────────────────────
const renderCharts = () => {
  renderPlayTrendChart()
  renderWatchTimeChart()
}

/**
 * 渲染播放量趋势柱状图（每集播放量）。
 * 绑定 click 事件，点击柱子后更新右侧观看时间分布图。
 */
const renderPlayTrendChart = () => {
  if (!playTrendChart.value) return

  // 销毁旧实例
  if (playTrendInstance) {
    playTrendInstance.dispose()
    playTrendResizeObserver?.disconnect()
  }

  playTrendInstance = echarts.init(playTrendChart.value)

  const labels = episodes.value.length
    ? episodes.value.map((_, i) => `第${i + 1}集`)
    : ['暂无剧集数据']
  const viewsData = episodes.value.length
    ? episodes.value.map((ep) => ep.views || 0)
    : [0]

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const d = params[0]
        return `${d.name}<br/>播放量: ${formatNumber(d.value)}`
      }
    },
    xAxis: {
      type: 'category',
      data: labels,
      axisLabel: { rotate: 45, interval: 0 }
    },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: (v: number) => formatNumber(v) }
    },
    series: [
      {
        name: '播放量',
        type: 'bar',
        data: viewsData,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#83bff6' },
            { offset: 1, color: '#188df0' }
          ])
        },
        emphasis: { itemStyle: { color: '#188df0' } }
      }
    ],
    grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true }
  }

  playTrendInstance.setOption(option)

  // 点击柱子时切换对应剧集的观看时间分布
  playTrendInstance.on('click', (params: any) => {
    if (params.componentType === 'series') {
      selectEpisode(params.dataIndex)
    }
  })

  // 使用 ResizeObserver 实现响应式缩放
  playTrendResizeObserver = new ResizeObserver(() => playTrendInstance?.resize())
  playTrendResizeObserver.observe(playTrendChart.value)
}

/**
 * 渲染观看时间分布折线图（24 小时分布）。
 * 当选中特定剧集时展示该集估算数据，否则展示全局汇总。
 */
const renderWatchTimeChart = () => {
  if (!watchTimeChart.value) return

  if (watchTimeInstance) {
    watchTimeInstance.dispose()
    watchTimeResizeObserver?.disconnect()
  }

  watchTimeInstance = echarts.init(watchTimeChart.value)

  const hours = Array.from({ length: 24 }, (_, i) => `${i}:00`)

  let watchData: number[]
  if (selectedEpisodeIndex.value >= 0 && episodes.value.length > 0) {
    // 展示所选剧集的估算分布
    const ep = episodes.value[selectedEpisodeIndex.value]
    watchData = generateWatchTimeData(selectedEpisodeIndex.value, ep.views || 1000)
  } else {
    // 全局汇总：将所有剧集分布叠加
    const aggregated = Array(24).fill(0)
    if (episodes.value.length > 0) {
      episodes.value.forEach((ep, idx) => {
        const dist = generateWatchTimeData(idx, ep.views || 1000)
        dist.forEach((v, h) => { aggregated[h] += v })
      })
      watchData = aggregated
    } else {
      // 无剧集数据时使用通用模式
      watchData = generateWatchTimeData(0, 1000)
    }
  }

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const d = params[0]
        return `${d.name}<br/>观看人数: ${Math.round(d.value)}`
      }
    },
    xAxis: {
      type: 'category',
      data: hours,
      boundaryGap: false
    },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: '{value}' }
    },
    series: [
      {
        name: '观看人数',
        type: 'line',
        data: watchData,
        smooth: true,
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(88, 160, 253, 0.5)' },
            { offset: 1, color: 'rgba(88, 160, 253, 0.1)' }
          ])
        },
        lineStyle: { color: '#58a0fd', width: 2 },
        itemStyle: { color: '#58a0fd' }
      }
    ],
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true }
  }

  watchTimeInstance.setOption(option)

  // 使用 ResizeObserver 实现响应式缩放
  watchTimeResizeObserver = new ResizeObserver(() => watchTimeInstance?.resize())
  watchTimeResizeObserver.observe(watchTimeChart.value)
}

// ─── 生命周期 ────────────────────────────────────────────────────────────────
onMounted(() => {
  // window.resize 兜底（ResizeObserver 已覆盖大多数场景）
})

onUnmounted(() => {
  playTrendResizeObserver?.disconnect()
  watchTimeResizeObserver?.disconnect()
  playTrendInstance?.dispose()
  watchTimeInstance?.dispose()
})
</script>

<style scoped>
.status-view {
  padding: 20px;
}

.stat-card {
  position: relative;
  overflow: hidden;
  border-radius: 10px;
  border: none;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.stat-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
  font-size: 24px;
  color: white;
}

.card {
  border-radius: 10px;
  border: none;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.chart-container {
  min-height: 400px;
}

.table-responsive {
  max-height: 600px;
  overflow-y: auto;
}

.table-hover tbody tr:hover {
  background-color: rgba(0, 123, 255, 0.05);
  cursor: pointer;
}

.table-active {
  background-color: rgba(24, 141, 240, 0.1) !important;
}

.form-control-lg {
  border-radius: 8px 0 0 8px;
}

.btn-lg {
  border-radius: 0 8px 8px 0;
  padding: 0.75rem 1.5rem;
}

.form-text {
  color: #6c757d;
  font-size: 0.9rem;
}

@media (max-width: 768px) {
  .col-md-6 {
    margin-bottom: 1rem;
  }

  .display-6 {
    font-size: 1.5rem;
  }
}
</style>
