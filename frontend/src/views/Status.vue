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
          <p class="display-6 mb-0 text-warning">{{ animeData.episodes?.length || 0 }}</p>
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
            <small class="text-muted">点击柱子查看该集在线分布</small>
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
    <div v-if="showEpisodeDetails && animeData?.episodes" class="row">
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
                <tr v-for="(episode, index) in animeData.episodes" :key="index">
                  <td>{{ index + 1 }}</td>
                  <td>{{ episode.title || `第${index + 1}集` }}</td>
                  <td>{{ formatNumber(episode.views) }}</td>
                  <td>{{ episode.peakTime || '暂无数据' }}</td>
                  <td>{{ formatNumber(episode.peakOnline) || '暂无数据' }}</td>
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
import { searchAnimes, getAnimeDetail } from '@/api/analytics'

// 状态管理
const keyword = ref('')
const statusMessage = ref('')
const animeData = ref<any>(null)
const showEpisodeDetails = ref(false)
const watchTimeSubtitle = ref('所有剧集总计')

// 图表实例
const playTrendChart = ref<HTMLElement>()
const watchTimeChart = ref<HTMLElement>()
let playTrendInstance: ECharts | null = null
let watchTimeInstance: ECharts | null = null

// 计算平均播放量
const avgViews = computed(() => {
  if (!animeData.value?.episodes?.length) return 0
  const total = animeData.value.episodes.reduce((sum: number, ep: any) => sum + (ep.views || 0), 0)
  return Math.round(total / animeData.value.episodes.length)
})

// 格式化数字
const formatNumber = (num: number | undefined | null): string => {
  if (!num) return '0'
  if (num >= 100000000) return (num / 100000000).toFixed(1) + '亿'
  if (num >= 10000) return (num / 10000).toFixed(1) + '万'
  return num.toString()
}

// 搜索番剧
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
      
      // 渲染图表
      await nextTick()
      renderCharts()
    } else {
      statusMessage.value = '未找到相关番剧'
      animeData.value = null
    }
  } catch (error) {
    console.error('搜索失败:', error)
    statusMessage.value = '搜索失败，请重试'
  }
}

// 切换剧集详情显示
const toggleEpisodeDetails = () => {
  showEpisodeDetails.value = !showEpisodeDetails.value
}

// 渲染图表
const renderCharts = () => {
  renderPlayTrendChart()
  renderWatchTimeChart()
}

// 渲染播放量趋势图
const renderPlayTrendChart = () => {
  if (!playTrendChart.value || !animeData.value?.episodes) return

  if (playTrendInstance) {
    playTrendInstance.dispose()
  }

  playTrendInstance = echarts.init(playTrendChart.value)
  
  const episodes = animeData.value.episodes || []
  const episodeNumbers = episodes.map((_: any, index: number) => `第${index + 1}集`)
  const viewsData = episodes.map((ep: any) => ep.views || 0)

  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const data = params[0]
        return `${data.name}<br/>播放量: ${formatNumber(data.value)}`
      }
    },
    xAxis: {
      type: 'category',
      data: episodeNumbers,
      axisLabel: {
        rotate: 45,
        interval: 0
      }
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: (value: number) => formatNumber(value)
      }
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
        emphasis: {
          itemStyle: {
            color: '#188df0'
          }
        }
      }
    ],
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      containLabel: true
    }
  }

  playTrendInstance.setOption(option)
}

// 渲染观看时间分布图
const renderWatchTimeChart = () => {
  if (!watchTimeChart.value) return

  if (watchTimeInstance) {
    watchTimeInstance.dispose()
  }

  watchTimeInstance = echarts.init(watchTimeChart.value)

  // TODO: 替换为真实的观看时间分布数据
  // 应该从番剧详情 API 获取实际的24小时观看分布数据
  // 模拟观看时间分布数据（0-23小时）
  const hours = Array.from({ length: 24 }, (_, i) => `${i}:00`)
  const watchData = Array.from({ length: 24 }, (_, i) => {
    // 模拟数据：晚上8-11点和中午12-2点是高峰
    if (i >= 20 && i <= 23) return Math.random() * 1000 + 800
    if (i >= 12 && i <= 14) return Math.random() * 600 + 400
    return Math.random() * 300 + 100
  })

  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const data = params[0]
        return `${data.name}<br/>观看人数: ${Math.round(data.value)}`
      }
    },
    xAxis: {
      type: 'category',
      data: hours,
      boundaryGap: false
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: '{value}'
      }
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
        lineStyle: {
          color: '#58a0fd',
          width: 2
        },
        itemStyle: {
          color: '#58a0fd'
        }
      }
    ],
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    }
  }

  watchTimeInstance.setOption(option)
}

// 响应式调整
const handleResize = () => {
  playTrendInstance?.resize()
  watchTimeInstance?.resize()
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
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
