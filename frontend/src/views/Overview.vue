<template>
  <div class="overview-view">
    <!-- 标签页导航 -->
    <div class="mb-3">
      <ul class="nav nav-pills" role="tablist">
        <li v-for="tab in tabs" :key="tab.id" class="nav-item">
          <button 
            class="nav-link" 
            :class="{ active: activeTab === tab.id }"
            @click="switchTab(tab.id)"
          >
            {{ tab.label }}
          </button>
        </li>
      </ul>
    </div>

    <!-- 标签页内容 -->
    <div class="tab-content">
      <!-- 历年数量变化 -->
      <div v-show="activeTab === 'yearly'" class="tab-pane">
        <div class="card p-3">
          <div class="d-flex h-100">
            <div class="custom-chart-panel h-100">
              <div class="d-flex justify-content-between align-items-center mb-3">
                <h5 class="card-title mb-0">历年番剧上新数量变化</h5>
              </div>
              <div class="chart-container h-100">
                <div ref="yearlyTrendChart" style="height: 500px; width: 100%"></div>
              </div>
            </div>
            <div class="custom-control-panel h-100">
              <div class="d-flex flex-column h-100">
                <h6 class="control-panel-title">视图选项</h6>
                <div class="flex-grow-1 control-buttons-group">
                  <button 
                    v-for="option in yearlyOptions" 
                    :key="option.value"
                    class="control-btn"
                    :class="{ active: yearlyView === option.value }"
                    @click="yearlyView = option.value; renderYearlyChart()"
                  >
                    {{ option.label }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 偏好差异 -->
      <div v-show="activeTab === 'genre'" class="tab-pane">
        <div class="card p-3">
          <div class="d-flex h-100">
            <div class="custom-chart-panel h-100">
              <div class="d-flex justify-content-between align-items-center mb-3">
                <h5 class="card-title mb-0">偏好差异</h5>
              </div>
              <div class="chart-container h-100">
                <div ref="preferenceDiffChart" style="height: 500px; width: 100%"></div>
              </div>
            </div>
            <div class="custom-control-panel h-100">
              <div class="d-flex flex-column h-100">
                <h6 class="control-panel-title">地区维度</h6>
                <div class="flex-grow-1 control-buttons-group">
                  <button 
                    v-for="area in areaOptions" 
                    :key="area"
                    class="control-btn"
                    :class="{ active: selectedArea === area }"
                    @click="selectedArea = area; renderPreferenceChart()"
                  >
                    {{ area }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 口碑热度指数 -->
      <div v-show="activeTab === 'rating'" class="tab-pane">
        <div class="card p-3">
          <div class="d-flex h-100">
            <div class="custom-chart-panel h-100">
              <div class="d-flex justify-content-between align-items-center mb-3">
                <h5 class="card-title mb-0">综合口碑热度指数排行</h5>
              </div>
              <div class="chart-container h-100">
                <div ref="collectionRatioChart" style="height: 500px; width: 100%"></div>
              </div>
            </div>
            <div class="custom-control-panel h-100">
              <div class="d-flex flex-column h-100">
                <div class="custom-select-wrapper mb-3">
                  <select v-model="selectedSeason" class="form-select" @change="renderRatingChart">
                    <option value="all">全年</option>
                    <option value="spring">春季新番 (4-6月)</option>
                    <option value="summer">夏季新番 (7-9月)</option>
                    <option value="autumn">秋季新番 (10-12月)</option>
                    <option value="winter">冬季新番 (1-3月)</option>
                  </select>
                </div>
                <h6 class="control-panel-title">视图选项</h6>
                <div class="flex-grow-1 control-buttons-group">
                  <button 
                    v-for="option in ratingOptions" 
                    :key="option.value"
                    class="control-btn"
                    :class="{ active: ratingView === option.value }"
                    @click="ratingView = option.value; renderRatingChart()"
                  >
                    {{ option.label }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 热门风格组合 -->
      <div v-show="activeTab === 'category'" class="tab-pane">
        <div class="card p-3">
          <div class="d-flex justify-content-between align-items-center mb-3">
            <h5 class="card-title mb-0">热门风格组合分析 (黄金搭档)</h5>
            <small class="text-muted">点击矩形查看详情</small>
          </div>
          <div class="chart-container h-100 position-relative overflow-hidden">
            <div ref="categoryTrendChart" style="height: 600px; width: 100%"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import type { ECharts } from 'echarts'
import { getReleaseTrend, getStyleDistribution, getRankings } from '@/api/analytics'

// ─── 标签页配置 ──────────────────────────────────────────────────────────────
const tabs = [
  { id: 'yearly', label: '历年数量变化' },
  { id: 'genre', label: '偏好差异' },
  { id: 'rating', label: '口碑热度指数' },
  { id: 'category', label: '热门风格组合' }
]

// ─── 状态管理 ────────────────────────────────────────────────────────────────
const activeTab = ref('yearly')
const yearlyView = ref('all')
const selectedArea = ref('全部')
const selectedSeason = ref('all')
const ratingView = ref('all')

// ─── 图表 DOM 引用 ───────────────────────────────────────────────────────────
const yearlyTrendChart = ref<HTMLElement>()
const preferenceDiffChart = ref<HTMLElement>()
const collectionRatioChart = ref<HTMLElement>()
const categoryTrendChart = ref<HTMLElement>()

// ─── 图表实例 ────────────────────────────────────────────────────────────────
let yearlyInstance: ECharts | null = null
let preferenceInstance: ECharts | null = null
let ratingInstance: ECharts | null = null
let categoryInstance: ECharts | null = null

// ─── ResizeObserver 实例 ─────────────────────────────────────────────────────
let yearlyResizeObserver: ResizeObserver | null = null
let preferenceResizeObserver: ResizeObserver | null = null
let ratingResizeObserver: ResizeObserver | null = null
let categoryResizeObserver: ResizeObserver | null = null

// ─── 选项配置 ────────────────────────────────────────────────────────────────
const yearlyOptions = [
  { value: 'all', label: '全部地区' },
  { value: 'china', label: '国产' },
  { value: 'japan', label: '日本' },
  { value: 'us', label: '美国' }
]

const areaOptions = ['全部', '中国', '日本', '美国', '其他']

const ratingOptions = [
  { value: 'all', label: '全部' },
  { value: 'top10', label: 'Top 10' },
  { value: 'top20', label: 'Top 20' }
]

// ─── 工具函数 ────────────────────────────────────────────────────────────────
/** 格式化数字（亿 / 万） */
const formatNumber = (num: number): string => {
  if (num >= 100000000) return (num / 100000000).toFixed(1) + '亿'
  if (num >= 10000) return (num / 10000).toFixed(1) + '万'
  return num.toString()
}

/**
 * 将前端 yearlyView 值映射为后端可识别的 area 字符串。
 * 'all' → undefined（不过滤），'china' → '国内'，'japan' → '日本'，'us' → '美国'
 */
const yearlyViewToArea = (view: string): string | undefined => {
  const MAP: Record<string, string> = { china: '国内', japan: '日本', us: '美国' }
  return MAP[view]
}

/**
 * 将前端 selectedArea 值映射为后端 area 字符串。
 * '全部' / '中国' → '国内'（数据库存储为"国内"），其余直接传递。
 */
const selectedAreaToParam = (area: string): string | undefined => {
  if (area === '全部') return undefined
  if (area === '中国') return '国内'
  return area
}

/**
 * 初始化或获取图表实例，并绑定 ResizeObserver。
 * 若实例已存在，直接返回（复用实例、避免闪烁）。
 */
const getOrCreateInstance = (
  el: HTMLElement,
  currentInstance: ECharts | null,
  currentObserver: ResizeObserver | null
): [ECharts, ResizeObserver] => {
  if (currentInstance && !currentInstance.isDisposed()) {
    return [currentInstance, currentObserver!]
  }
  const chart = echarts.init(el)
  const observer = new ResizeObserver(() => chart.resize())
  observer.observe(el)
  return [chart, observer]
}

// ─── 切换标签页 ──────────────────────────────────────────────────────────────
const switchTab = (tabId: string) => {
  activeTab.value = tabId
  // 等待 v-show 更新 DOM 后再渲染/刷新图表
  nextTick(() => {
    switch (tabId) {
      case 'yearly':    renderYearlyChart();     break
      case 'genre':     renderPreferenceChart(); break
      case 'rating':    renderRatingChart();     break
      case 'category':  renderCategoryChart();   break
    }
  })
}

// ─── 历年数量变化图（折线图） ────────────────────────────────────────────────
const renderYearlyChart = async () => {
  if (!yearlyTrendChart.value) return

  ;[yearlyInstance, yearlyResizeObserver] = getOrCreateInstance(
    yearlyTrendChart.value, yearlyInstance, yearlyResizeObserver
  )

  try {
    // 将视图选项映射为地区参数传递给 API
    const area = yearlyViewToArea(yearlyView.value)
    const response = await getReleaseTrend(area)
    const data = response.data || {}

    const labels = Object.keys(data).sort()
    const counts = labels.map((k) => data[k])

    const option: echarts.EChartsOption = {
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => `${params[0].name}<br/>上新数量: ${params[0].value} 部`
      },
      xAxis: {
        type: 'category',
        data: labels,
        axisLabel: { rotate: 45 }
      },
      yAxis: {
        type: 'value',
        name: '番剧数量'
      },
      series: [
        {
          name: '上新数量',
          type: 'line',
          data: counts,
          smooth: true,
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(88, 160, 253, 0.5)' },
              { offset: 1, color: 'rgba(88, 160, 253, 0.1)' }
            ])
          },
          lineStyle: { color: '#58a0fd', width: 3 },
          itemStyle: { color: '#58a0fd' }
        }
      ],
      grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true }
    }

    // 使用 setOption 更新而非 dispose/reinit，保留动画过渡
    yearlyInstance.setOption(option, true)
  } catch (error) {
    console.error('加载历年趋势失败:', error)
  }
}

// ─── 偏好差异图（横向柱状图） ────────────────────────────────────────────────
const renderPreferenceChart = async () => {
  if (!preferenceDiffChart.value) return

  ;[preferenceInstance, preferenceResizeObserver] = getOrCreateInstance(
    preferenceDiffChart.value, preferenceInstance, preferenceResizeObserver
  )

  try {
    // 将地区选项映射为 API area 参数
    const area = selectedAreaToParam(selectedArea.value)
    const response = await getStyleDistribution(area)
    const data = response.data || {}

    // 按数量降序排列，最多展示前 20 个风格
    const sorted = Object.entries(data)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 20)
    const styles = sorted.map(([name]) => name)
    const values = sorted.map(([, v]) => v)

    const option: echarts.EChartsOption = {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' }
      },
      xAxis: { type: 'value' },
      yAxis: {
        type: 'category',
        data: styles,
        axisLabel: { interval: 0 }
      },
      series: [
        {
          name: '番剧数量',
          type: 'bar',
          data: values,
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
              { offset: 0, color: '#83bff6' },
              { offset: 1, color: '#188df0' }
            ])
          },
          label: { show: true, position: 'right' }
        }
      ],
      grid: { left: '15%', right: '10%', bottom: '3%', top: '3%', containLabel: true }
    }

    preferenceInstance.setOption(option, true)
  } catch (error) {
    console.error('加载偏好差异失败:', error)
  }
}

// ─── 口碑热度排行图（柱线混合图） ───────────────────────────────────────────
const renderRatingChart = async () => {
  if (!collectionRatioChart.value) return

  ;[ratingInstance, ratingResizeObserver] = getOrCreateInstance(
    collectionRatioChart.value, ratingInstance, ratingResizeObserver
  )

  try {
    const limit = ratingView.value === 'top10' ? 10 : 20
    // 将季节选项作为 season 参数传递，'all' 时不过滤
    const season = selectedSeason.value !== 'all' ? selectedSeason.value : undefined

    const response = await getRankings('rating', limit, undefined, undefined, season)
    const animes = response.list || []

    const names = animes.map((anime: any) => anime.title)
    const ratings = animes.map((anime: any) => anime.rating || 0)
    const views = animes.map((anime: any) => anime.views || 0)

    const option: echarts.EChartsOption = {
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const anime = animes[params[0].dataIndex]
          return `${anime.title}<br/>评分: ${anime.rating?.toFixed(1)}<br/>播放量: ${formatNumber(anime.views || 0)}`
        }
      },
      legend: { data: ['评分', '热度指数'] },
      xAxis: {
        type: 'category',
        data: names,
        axisLabel: {
          rotate: 45,
          interval: 0,
          formatter: (value: string) => (value.length > 8 ? value.substring(0, 8) + '…' : value)
        }
      },
      yAxis: [
        { type: 'value', name: '评分', min: 0, max: 10 },
        {
          type: 'value',
          name: '热度',
          axisLabel: { formatter: (value: number) => formatNumber(value) }
        }
      ],
      series: [
        {
          name: '评分',
          type: 'bar',
          data: ratings,
          itemStyle: { color: '#f5a623' }
        },
        {
          name: '热度指数',
          type: 'line',
          yAxisIndex: 1,
          data: views,
          smooth: true,
          lineStyle: { color: '#58a0fd', width: 2 },
          itemStyle: { color: '#58a0fd' }
        }
      ],
      grid: { left: '3%', right: '4%', bottom: '20%', containLabel: true }
    }

    ratingInstance.setOption(option, true)
  } catch (error) {
    console.error('加载口碑热度失败:', error)
  }
}

// ─── 热门风格组合树图 ────────────────────────────────────────────────────────
const renderCategoryChart = async () => {
  if (!categoryTrendChart.value) return

  ;[categoryInstance, categoryResizeObserver] = getOrCreateInstance(
    categoryTrendChart.value, categoryInstance, categoryResizeObserver
  )

  try {
    // 风格组合图不区分地区，展示全局数据
    const response = await getStyleDistribution()
    const data = response.data || {}

    const treeData = Object.entries(data)
      .sort((a, b) => b[1] - a[1])
      .map(([name, value]) => ({ name, value }))

    const option: echarts.EChartsOption = {
      tooltip: {
        formatter: (info: any) => `${info.name}<br/>数量: ${info.value} 部`
      },
      series: [
        {
          type: 'treemap',
          data: treeData,
          leafDepth: 1,
          label: { show: true, formatter: '{b}\n{c}' },
          upperLabel: { show: true, height: 30 },
          itemStyle: {
            borderColor: '#fff',
            borderWidth: 2,
            gapWidth: 2
          },
          levels: [
            {
              itemStyle: { borderColor: '#555', borderWidth: 4, gapWidth: 4 }
            },
            {
              colorSaturation: [0.35, 0.5],
              itemStyle: { borderWidth: 5, gapWidth: 1, borderColorSaturation: 0.6 }
            }
          ]
        }
      ]
    }

    categoryInstance.setOption(option, true)
  } catch (error) {
    console.error('加载风格组合失败:', error)
  }
}

// ─── 生命周期 ────────────────────────────────────────────────────────────────
onMounted(() => {
  // 挂载后渲染默认标签页图表
  renderYearlyChart()
})

onUnmounted(() => {
  // 断开所有 ResizeObserver 并销毁图表实例，防止内存泄漏
  yearlyResizeObserver?.disconnect()
  preferenceResizeObserver?.disconnect()
  ratingResizeObserver?.disconnect()
  categoryResizeObserver?.disconnect()
  yearlyInstance?.dispose()
  preferenceInstance?.dispose()
  ratingInstance?.dispose()
  categoryInstance?.dispose()
})
</script>

<style scoped>
.overview-view {
  padding: 20px;
}

.nav-pills {
  background: white;
  padding: 15px;
  border-radius: 10px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.nav-pills .nav-link {
  color: #666;
  padding: 12px 24px;
  border-radius: 8px;
  transition: all 0.3s ease;
  font-weight: 500;
}

.nav-pills .nav-link:hover {
  background: #f0f0f0;
}

.nav-pills .nav-link.active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.card {
  border-radius: 10px;
  border: none;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  min-height: 600px;
}

.d-flex {
  display: flex;
}

.h-100 {
  height: 100%;
}

.custom-chart-panel {
  flex: 1;
  padding-right: 20px;
}

.custom-control-panel {
  width: 200px;
  border-left: 1px solid #e0e0e0;
  padding-left: 20px;
}

.control-panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 15px;
  padding-bottom: 10px;
  border-bottom: 2px solid #667eea;
}

.control-buttons-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.control-btn {
  padding: 10px 15px;
  background: white;
  border: 1px solid #ddd;
  border-radius: 6px;
  color: #666;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.3s ease;
  text-align: left;
}

.control-btn:hover {
  background: #f8f9fa;
  border-color: #667eea;
}

.control-btn.active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-color: #667eea;
}

.custom-select-wrapper {
  width: 100%;
}

.form-select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.form-select:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.chart-container {
  min-height: 500px;
}

.position-relative {
  position: relative;
}

.overflow-hidden {
  overflow: hidden;
}

@media (max-width: 992px) {
  .d-flex {
    flex-direction: column;
  }
  
  .custom-chart-panel {
    padding-right: 0;
    margin-bottom: 20px;
  }
  
  .custom-control-panel {
    width: 100%;
    border-left: none;
    border-top: 1px solid #e0e0e0;
    padding-left: 0;
    padding-top: 20px;
  }
  
  .control-buttons-group {
    flex-direction: row;
    flex-wrap: wrap;
  }
  
  .control-btn {
    flex: 1;
    min-width: 120px;
  }
}

@media (max-width: 768px) {
  .nav-pills {
    overflow-x: auto;
    white-space: nowrap;
  }
  
  .nav-pills .nav-link {
    display: inline-block;
    padding: 10px 16px;
    font-size: 14px;
  }
}
</style>
