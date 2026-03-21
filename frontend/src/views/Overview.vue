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
                <h5 class="card-title mb-0">用户偏好差异</h5>
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
                    v-for="area in prefAreaOptions" 
                    :key="area"
                    class="control-btn"
                    :class="{ active: selectedPrefArea === area }"
                    @click="selectedPrefArea = area; renderPreferenceChart()"
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
          <!-- 图表与下钻详情面板的相对容器 -->
          <div class="chart-container h-100 position-relative overflow-hidden">
            <div
              ref="categoryTrendChart"
              style="height: 600px; width: 100%"
              :class="{ 'combo-chart-dimmed': isComboDetailVisible }"
            ></div>

            <!-- 下钻详情侧边面板 -->
            <transition name="slide-panel">
              <div v-if="isComboDetailVisible" class="combo-detail-panel">
                <div class="combo-detail-header">
                  <div
                    class="combo-detail-block"
                    :style="{ backgroundColor: comboDetailColor }"
                  ></div>
                  <h5 class="combo-detail-title" :style="{ color: comboDetailColor }">
                    {{ comboDetailData.name }}
                  </h5>
                  <button class="btn-close-detail" @click="closeComboDetail" title="关闭">
                    <i class="fas fa-times"></i>
                  </button>
                </div>
                <p class="combo-detail-stats">
                  共 {{ comboDetailData.count }} 部番剧・平均追番 {{ (comboDetailData.value ?? 0).toLocaleString() }}
                </p>
                <div class="detail-anime-list">
                  <div
                    v-for="(anime, index) in comboDetailData.animes"
                    :key="index"
                    class="detail-anime-item"
                  >
                    <span class="detail-rank">{{ index + 1 }}</span>
                    <img
                      :src="getComboAnimeImageUrl(anime)"
                      :alt="anime.title"
                      class="detail-cover"
                    />
                    <div class="detail-info">
                      <h5>{{ anime.title }}</h5>
                      <p>
                        <i class="fas fa-star text-warning me-1"></i>
                        {{ anime.score ?? '暂无评分' }}
                        <i class="fas fa-heart text-danger ms-2 me-1"></i>
                        {{ formatNumber(anime.favorites) }}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </transition>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { useEcharts } from '@/composables/useEcharts'
import { useAuthStore } from '@/stores/auth'
import type { ComboAnimeItem } from '@/api/analytics'
import {
  getYearlyQuantityChart,
  getPreferenceDifferenceChart,
  getReputationHeatIndexChart,
  getPopularStyleCombinationChart,
} from '@/api/analytics'

const authStore = useAuthStore()

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
const selectedPrefArea = ref('国内')
const selectedSeason = ref('all')
const ratingView = ref('all')

// ─── 图表 DOM 引用（通过 useEcharts 管理） ──────────────────────────────────
const {
  chartRef: yearlyTrendChart,
  initChart: initYearlyChart,
  setOption: setYearlyOption,
  showLoading: showYearlyLoad,
  hideLoading: hideYearlyLoad,
} = useEcharts()

const {
  chartRef: preferenceDiffChart,
  initChart: initPrefChart,
  setOption: setPrefOption,
  showLoading: showPrefLoad,
  hideLoading: hidePrefLoad,
} = useEcharts()

const {
  chartRef: collectionRatioChart,
  initChart: initRatingChart,
  setOption: setRatingOption,
  showLoading: showRatingLoad,
  hideLoading: hideRatingLoad,
} = useEcharts()

const {
  chartRef: categoryTrendChart,
  initChart: initCategoryChart,
  setOption: setCategoryOption,
  showLoading: showCategoryLoad,
  hideLoading: hideCategoryLoad,
  chartInstance: categoryChartInstance,
} = useEcharts()

// ─── 选项配置 ────────────────────────────────────────────────────────────────
const yearlyOptions = [
  { value: 'all', label: '全部地区' },
  { value: 'china', label: '国产' },
  { value: 'japan', label: '日本' },
  { value: 'us', label: '美国' }
]

const prefAreaOptions = ['国内', '日本', '美国']

const ratingOptions = [
  { value: 'all', label: '全部' },
  { value: 'top10', label: 'Top 10' },
  { value: 'top20', label: 'Top 20' }
]

// ─── 热门风格组合下钻状态 ───────────────────────────────────────────────────
/** 是否显示下钻详情侧边面板 */
const isComboDetailVisible = ref(false)

/** 详情面板绑定的数据（包含 name、value、count、animes） */
const comboDetailData = ref<{
  name: string
  value: number
  count: number
  animes: ComboAnimeItem[]
}>({ name: '', value: 0, count: 0, animes: [] })

/** 当前点击矩形的颜色（用于标题色块同步） */
const comboDetailColor = ref('#667eea')

// ─── 工具函数 ────────────────────────────────────────────────────────────────
/** 格式化数字（亿 / 万） */
const formatNumber = (num: number | null | undefined): string => {
  if (num == null) return '0'
  if (num >= 100000000) return (num / 100000000).toFixed(1) + '亿'
  if (num >= 10000) return (num / 10000).toFixed(1) + '万'
  return num.toLocaleString()
}

/**
 * 获取风格组合详情中番剧封面的代理图片 URL。
 * 通过后端 image_proxy 绕过 CDN 防盗链。
 */
const getComboAnimeImageUrl = (anime: ComboAnimeItem): string => {
  if (!anime.cover) return ''
  return `/api/image_proxy?url=${encodeURIComponent(anime.cover)}&title=${encodeURIComponent(anime.title)}&season_id=${anime.season_id}`
}

// ─── 切换标签页 ──────────────────────────────────────────────────────────────
const switchTab = (tabId: string) => {
  activeTab.value = tabId
  // 等待 v-show 更新 DOM 后再渲染/刷新图表
  nextTick(() => {
    switch (tabId) {
      case 'yearly':   renderYearlyChart();    break
      case 'genre':    renderPreferenceChart(); break
      case 'rating':   renderRatingChart();    break
      case 'category': renderCategoryChart();  break
    }
  })
}

// ─── 历年数量变化图（多系列折线图，X 轴为季度） ─────────────────────────────
const renderYearlyChart = async () => {
  if (!yearlyTrendChart.value) return

  // 若实例尚未初始化，先创建空实例
  initYearlyChart({})

  try {
    showYearlyLoad()
    const yearlyData = await getYearlyQuantityChart(yearlyView.value)
    const xData = ['春季(1-3月)', '夏季(4-6月)', '秋季(7-9月)', '冬季(10-12月)']

    // 年份降序排列，最新年份在图例最前
    const legendData = Object.keys(yearlyData).sort((a, b) => Number(b) - Number(a))

    const seriesData: echarts.SeriesOption[] = legendData.map(year => ({
      name: year,
      type: 'line',
      smooth: true,
      data: yearlyData[year],
    }))

    setYearlyOption({
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
      },
      legend: { data: legendData, type: 'scroll' },
      xAxis: { type: 'category', data: xData },
      yAxis: { type: 'value', name: '番剧数量' },
      series: seriesData,
      grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
    }, { notMerge: true })
  } catch (error) {
    console.error('加载历年趋势失败:', error)
  } finally {
    hideYearlyLoad()
  }
}

// ─── 偏好差异图（矩形树图，按地区偏好指数着色） ─────────────────────────────
const renderPreferenceChart = async () => {
  if (!preferenceDiffChart.value) return

  initPrefChart({})

  try {
    showPrefLoad()
    const response = await getPreferenceDifferenceChart(selectedPrefArea.value)
    const chartData = response.data || []

    // 获取用户偏好列表，用于高亮匹配的风格
    const userPreferences: string[] = authStore.preferences || []

    const treeData = chartData.map(d => ({
      name: d.style,
      value: d.preferenceIndex,
      regionCount: d.regionCount,
      globalCount: d.globalCount,
      itemStyle: {
        color: userPreferences.includes(d.style) ? '#fb7299' : '#87CEFA',
        borderRadius: 4,
        borderWidth: 2,
        borderColor: '#fff',
        gapWidth: 2,
      },
    }))

    setPrefOption({
      tooltip: {
        trigger: 'item',
        formatter: (params: any) => {
          // 跳过父节点
          if (params.data?.children?.length > 0 || params.data?.value == null) return ''
          const d = params.data
          const compText =
            d.value > 1.1
              ? `<span style="color:#28a745;">(高于全球)</span>`
              : d.value < 0.9
              ? `<span style="color:#dc3545;">(低于全球)</span>`
              : `<span>(与全球持平)</span>`
          return `<b>${d.name}</b><br/>
地区偏好指数: <b style="font-size:1.2em;">${d.value}</b> ${compText}<br/>
<hr style="margin:4px 0;">
该地区番剧数: ${d.regionCount}<br/>
全球番剧数: ${d.globalCount}`
        },
      },
      series: [{
        type: 'treemap',
        roam: false,
        nodeClick: false,
        breadcrumb: { show: false },
        label: {
          show: true,
          position: 'inside',
          formatter: (p: any) => `${p.name}\n${p.value}`,
          color: '#fff',
          fontSize: 14,
        },
        data: treeData,
      }],
    }, { notMerge: true })
  } catch (error) {
    console.error('加载偏好差异失败:', error)
  } finally {
    hidePrefLoad()
  }
}

// ─── 口碑热度指数排行图（渐变条形图） ────────────────────────────────────────
const renderRatingChart = async () => {
  if (!collectionRatioChart.value) return

  initRatingChart({})

  try {
    showRatingLoad()
    const season = selectedSeason.value !== 'all' ? selectedSeason.value : ''
    const response = await getReputationHeatIndexChart(season)
    const topAnimes = response.data || []

    // 根据 ratingView 控制展示数量
    const limit = ratingView.value === 'top10' ? 10 : 20
    const displayAnimes = topAnimes.slice(0, limit)

    // 倒序显示（最高分在顶部）
    const yAxisData = displayAnimes.map(a => a.title).reverse()
    const seriesData = displayAnimes
      .map(a => ({
        value: parseFloat(a.qualityScore.toFixed(0)),
        score: a.rating,
        views: a.views,
        favorites: a.favorites,
      }))
      .reverse()

    setRatingOption({
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        backgroundColor: 'rgba(30, 41, 59, 0.9)',
        borderColor: 'rgba(255, 255, 255, 0.1)',
        textStyle: { color: '#f0f0f0' },
        formatter: (params: any) => {
          if (!params?.length) return ''
          const d = params[0].data
          return `<b>${params[0].name}</b><br/>
<span style="font-size:1.2em;color:#fde047;font-weight:bold;">口碑热度指数: ${formatNumber(d.value)}</span><br/>
<hr style="margin:4px 0;border-color:rgba(255,255,255,0.2);">
B站评分: ${d.score}<br/>
追番数: ${formatNumber(d.favorites)}<br/>
播放量: ${formatNumber(d.views)}`
        },
      },
      grid: { left: '5%', right: '10%', bottom: '3%', top: '3%', containLabel: true },
      xAxis: { type: 'value', name: '口碑热度指数' },
      yAxis: {
        type: 'category',
        data: yAxisData,
        axisLabel: { show: false },
        axisTick: { show: false },
        axisLine: { show: false },
      },
      series: [{
        name: '口碑热度指数',
        type: 'bar',
        barWidth: '60%',
        data: seriesData,
        itemStyle: {
          borderRadius: [0, 5, 5, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: '#f97316' },
            { offset: 1, color: '#facc15' },
          ]),
        },
        emphasis: {
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
              { offset: 0, color: '#fb923c' },
              { offset: 1, color: '#fde047' },
            ]),
          },
        },
        label: {
          show: true,
          position: 'insideLeft',
          formatter: '{b}',
          color: '#fff',
          fontSize: 12,
        },
      }],
    }, { notMerge: true })
  } catch (error) {
    console.error('加载口碑热度失败:', error)
  } finally {
    hideRatingLoad()
  }
}

// ─── 热门风格组合矩形树图（含点击下钻详情面板） ─────────────────────────────
const renderCategoryChart = async () => {
  if (!categoryTrendChart.value) return

  initCategoryChart({})

  // 移除旧的点击监听，防止重复绑定
  categoryChartInstance.value?.off('click')

  try {
    showCategoryLoad()
    const response = await getPopularStyleCombinationChart()
    const topCombinations = response.data || []

    const seriesData = topCombinations.map(combo => ({
      name: combo.combination,
      value: Math.round(combo.avgFavorites),
      count: combo.animeCount,
      animes: combo.representativeAnimes,
    }))

    setCategoryOption({
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(30, 41, 59, 0.9)',
        borderColor: 'rgba(255, 255, 255, 0.1)',
        textStyle: { color: '#f0f0f0' },
        formatter: (params: any) => {
          if (params.data?.children?.length > 0 || params.data?.value == null) return ''
          const { name, value, count, animes } = params.data
          let animeListHtml = ''
          if (animes?.length > 0) {
            const preview = animes.slice(0, 5)
            const items = preview.map((a: any) => `<li>${a.title || '未知标题'}</li>`).join('')
            const more = animes.length > 5 ? `<li>等 ${animes.length} 部番剧...</li>` : ''
            animeListHtml = `<hr style="margin:4px 0;border-color:rgba(255,255,255,0.2);">
<span style="color:#d1d5db;">包含番剧（部分）:</span>
<ul style="padding-left:15px;margin:5px 0 0;">${items}${more}</ul>`
          }
          return `<b>${name}</b><br/>
<span style="font-size:1.2em;color:#34d399;font-weight:bold;">平均追番: ${value?.toLocaleString()}</span><br/>
<hr style="margin:4px 0;border-color:rgba(255,255,255,0.2);">
包含番剧数: ${count}${animeListHtml}`
        },
      },
      series: [{
        type: 'treemap',
        roam: false,
        nodeClick: false,
        breadcrumb: { show: false },
        label: {
          show: true,
          position: 'inside',
          formatter: '{b}',
          color: '#fff',
          fontSize: 14,
          fontWeight: 'bold',
        },
        itemStyle: { gapWidth: 3, borderColor: '#fff', borderRadius: 5 },
        data: seriesData,
      }],
    }, { notMerge: true })

    // 绑定点击事件：打开下钻详情面板
    categoryChartInstance.value?.on('click', (params: any) => {
      if (params.data?.animes) {
        comboDetailData.value = {
          name: params.data.name,
          value: params.data.value,
          count: params.data.count,
          animes: params.data.animes,
        }
        comboDetailColor.value = params.color ?? '#667eea'
        isComboDetailVisible.value = true

        // 隐藏 tooltip 并将图表设为静默（防止遮挡面板）
        categoryChartInstance.value?.dispatchAction({ type: 'hideTip' })
        setCategoryOption({ series: [{ silent: true }] })
      }
    })
  } catch (error) {
    console.error('加载风格组合失败:', error)
  } finally {
    hideCategoryLoad()
  }
}

/** 关闭风格组合下钻详情面板，恢复图表交互 */
const closeComboDetail = () => {
  isComboDetailVisible.value = false
  setCategoryOption({ series: [{ silent: false }] })
}

// ─── 生命周期 ────────────────────────────────────────────────────────────────
onMounted(() => {
  // 挂载后渲染默认标签页图表
  renderYearlyChart()
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
/* ─── 热门风格组合：图表变暗效果 ─────────────────────────────────────────── */
.combo-chart-dimmed {
  opacity: 0.4;
  pointer-events: none;
  transition: opacity 0.3s ease;
}

/* ─── 热门风格组合：下钻详情侧边面板 ────────────────────────────────────── */
.combo-detail-panel {
  position: absolute;
  top: 0;
  right: 0;
  height: 100%;
  width: 320px;
  background: #fff;
  box-shadow: -4px 0 20px rgba(0, 0, 0, 0.15);
  border-radius: 10px 0 0 10px;
  padding: 20px 16px;
  overflow-y: auto;
  z-index: 10;
}

.combo-detail-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.combo-detail-block {
  width: 18px;
  height: 18px;
  border-radius: 4px;
  flex-shrink: 0;
}

.combo-detail-title {
  flex: 1;
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.btn-close-detail {
  background: none;
  border: none;
  color: #9ca3af;
  cursor: pointer;
  font-size: 16px;
  padding: 2px 4px;
  transition: color 0.2s;
}

.btn-close-detail:hover {
  color: #ef4444;
}

.combo-detail-stats {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 12px;
}

.detail-anime-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.detail-anime-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.detail-rank {
  font-size: 14px;
  font-weight: 700;
  color: #667eea;
  min-width: 20px;
  text-align: center;
  padding-top: 2px;
}

.detail-cover {
  width: 52px;
  height: 68px;
  object-fit: cover;
  border-radius: 5px;
  flex-shrink: 0;
}

.detail-info {
  flex: 1;
  overflow: hidden;
}

.detail-info h5 {
  font-size: 13px;
  font-weight: 600;
  margin: 0 0 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-info p {
  font-size: 12px;
  color: #6b7280;
  margin: 0;
}

/* 面板滑入/滑出动画 */
.slide-panel-enter-active,
.slide-panel-leave-active {
  transition: transform 0.3s ease, opacity 0.3s ease;
}

.slide-panel-enter-from,
.slide-panel-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

</style>
