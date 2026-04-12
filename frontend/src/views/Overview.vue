<template>
  <div class="overview-view">
    <div class="page-header mb-4">
      <h3 class="fw-bold text-dark mb-1">深度市场洞察</h3>
      <p class="text-muted mb-0">聚焦趋势演进、受众差异与题材组合的结构化分析</p>
    </div>

    <div class="mb-3">
      <ul class="nav nav-pills overview-tabs" role="tablist">
        <li v-for="tab in tabs" :key="tab.id" class="nav-item">
          <button class="nav-link" :class="{ active: activeTab === tab.id }" @click="switchTab(tab.id)">
            {{ tab.label }}
          </button>
        </li>
      </ul>
    </div>

    <div class="tab-content">
      <div v-show="activeTab === 'yearly'" class="tab-pane">
        <div class="style-unified h-100">
          <div class="card-header-unified">
            <h5>历年上新趋势（季度对比）</h5>
            <div class="area-btn-group">
              <button
                v-for="option in yearlyOptions"
                :key="option.value"
                class="area-btn"
                :class="{ active: yearlyView === option.value }"
                @click="setYearlyView(option.value)"
              >
                {{ option.label }}
              </button>
            </div>
          </div>
          <div class="chart-fixed-frame">
            <div class="chart-wrapper chart-wrapper--medium position-relative">
              <div v-if="yearlyStatus === 'error'" class="chart-state text-danger">历年趋势加载失败</div>
              <div v-else-if="yearlyStatus === 'empty'" class="chart-state">暂无历年趋势数据</div>
              <div
                ref="yearlyTrendChart"
                class="chart-canvas chart-canvas--medium"
                role="img"
                aria-label="历年上新趋势图（季度对比）"
              ></div>
            </div>
          </div>
        </div>
      </div>

      <div v-show="activeTab === 'seasonal'" class="tab-pane">
        <div class="style-unified h-100">
          <div class="card-header-unified">
            <h5>题材季节性规律</h5>
            <small class="text-muted">新增</small>
          </div>
          <div class="chart-fixed-frame">
            <div class="chart-wrapper chart-wrapper--medium position-relative">
              <div v-if="seasonalStatus === 'error'" class="chart-state text-danger">季节题材图加载失败</div>
              <div v-else-if="seasonalStatus === 'empty'" class="chart-state">暂无季节题材数据</div>
              <div
                ref="seasonalTrendChart"
                class="chart-canvas chart-canvas--medium"
                role="img"
                aria-label="题材季节性规律热力图"
              ></div>
            </div>
          </div>
          <div class="insight-summary">
            <span class="summary-label">季节偏好总结：</span>
            <span>{{ seasonalSummary }}</span>
          </div>
        </div>
      </div>

      <div v-show="activeTab === 'preference'" class="tab-pane">
        <div class="style-unified h-100">
          <div class="card-header-unified">
            <h5>地区受众偏好差异</h5>
            <div class="area-btn-group">
              <button
                v-for="area in prefAreaOptions"
                :key="area"
                class="area-btn"
                :class="{ active: selectedPrefArea === area }"
                @click="setPrefArea(area)"
              >
                {{ area }}
              </button>
            </div>
          </div>
          <div class="chart-fixed-frame">
            <div class="chart-wrapper chart-wrapper--large position-relative">
              <div v-if="preferenceStatus === 'error'" class="chart-state text-danger">偏好差异图加载失败</div>
              <div v-else-if="preferenceStatus === 'empty'" class="chart-state">暂无偏好差异数据</div>
              <div
                ref="preferenceDiffChart"
                class="chart-canvas chart-canvas--large"
                role="img"
                aria-label="地区受众偏好差异图"
              ></div>
            </div>
          </div>
          <div class="insight-summary">
            <span class="summary-label">与你的偏好重合：</span>
            <span>{{ preferenceSummary }}</span>
          </div>
        </div>
      </div>

      <div v-show="activeTab === 'category'" class="tab-pane">
        <div class="style-unified h-100">
          <div class="card-header-unified">
            <h5>爆款风格组合库（黄金搭档）</h5>
            <small class="text-muted">点击矩形查看下钻详情</small>
          </div>
          <div class="chart-fixed-frame chart-fixed-frame--wide">
            <div class="chart-wrapper chart-wrapper--large position-relative overflow-hidden">
              <div v-if="categoryStatus === 'error'" class="chart-state text-danger">风格组合图加载失败</div>
              <div v-else-if="categoryStatus === 'empty'" class="chart-state">暂无风格组合数据</div>
              <div
                ref="categoryTrendChart"
                class="chart-canvas chart-canvas--large"
                role="img"
                aria-label="爆款风格组合库图"
                :class="{ 'combo-chart-dimmed': isComboDetailVisible }"
              ></div>

              <div v-if="isComboDetailVisible" class="combo-backdrop" @click="closeComboDetail"></div>

              <transition name="slide-panel">
                <div v-if="isComboDetailVisible" class="combo-detail-panel">
                  <div class="combo-detail-header">
                    <div class="combo-detail-block" :style="{ backgroundColor: comboDetailColor }"></div>
                    <h5 class="combo-detail-title" :style="{ color: comboDetailColor }">{{ comboDetailData.name }}</h5>
                    <button class="btn-close-detail" @click="closeComboDetail" title="关闭">
                      <i class="fas fa-times"></i>
                    </button>
                  </div>
                  <p class="combo-detail-stats">
                    共 {{ comboDetailData.count }} 部番剧・平均追番 {{ (comboDetailData.value ?? 0).toLocaleString() }}
                  </p>
                  <div class="detail-anime-list">
                    <div v-for="(anime, index) in comboDetailData.animes" :key="index" class="detail-anime-item">
                      <span class="detail-rank">{{ index + 1 }}</span>
                      <img :src="getComboAnimeImageUrl(anime)" :alt="anime.title" class="detail-cover" />
                      <div class="detail-info">
                        <h5>{{ anime.title }}</h5>
                        <p>
                          <i class="fas fa-star text-warning me-1"></i>{{ anime.score ?? '暂无评分' }}
                          <i class="fas fa-heart text-danger ms-2 me-1"></i>{{ formatNumber(anime.favorites) }}
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
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { useEcharts } from '@/composables/useEcharts'
import { useAuthStore } from '@/stores/auth'
import {
  AREA_VALUES,
  type AreaValue,
  type ComboAnimeItem,
  type PreferenceDifferenceItem,
  SEASON_VALUES,
  type SeasonValue,
  getPopularStyleCombinationChart,
  getPreferenceDifferenceChart,
  getSeasonalGenreTrends,
  getYearlyQuantityChart,
} from '@/api/analytics'

type LoadState = 'idle' | 'loading' | 'success' | 'empty' | 'error'
type OverviewTab = 'yearly' | 'seasonal' | 'preference' | 'category'

const authStore = useAuthStore()
const tabs: Array<{ id: OverviewTab; label: string }> = [
  { id: 'yearly', label: '历年上新趋势' },
  { id: 'seasonal', label: '题材季节性规律' },
  { id: 'preference', label: '受众偏好差异' },
  { id: 'category', label: '爆款风格组合' },
]
const activeTab = ref<OverviewTab>('yearly')
const renderedTabs = ref(new Set<OverviewTab>())

const yearlyOptions = [
  { value: 'all', label: '全部地区' },
  { value: 'china', label: '国产' },
  { value: 'japan', label: '日本' },
  { value: 'us', label: '美国' },
] as const
type YearlyViewValue = (typeof yearlyOptions)[number]['value']

const prefAreaOptions: AreaValue[] = [...AREA_VALUES]

const yearlyView = ref<YearlyViewValue>('all')
const selectedPrefArea = ref<AreaValue>('国内')
const yearlyStatus = ref<LoadState>('idle')
const seasonalStatus = ref<LoadState>('idle')
const preferenceStatus = ref<LoadState>('idle')
const categoryStatus = ref<LoadState>('idle')
const preferenceRaw = ref<PreferenceDifferenceItem[]>([])
const bestGenreBySeason = ref<Partial<Record<SeasonValue, string>>>({})

const {
  chartRef: yearlyTrendChart,
  chartInstance: yearlyChartInstance,
  initChart: initYearlyChart,
  setOption: setYearlyOption,
  showLoading: showYearlyLoad,
  hideLoading: hideYearlyLoad,
} = useEcharts()

const {
  chartRef: seasonalTrendChart,
  chartInstance: seasonalChartInstance,
  initChart: initSeasonalChart,
  setOption: setSeasonalOption,
  showLoading: showSeasonalLoad,
  hideLoading: hideSeasonalLoad,
} = useEcharts()

const {
  chartRef: preferenceDiffChart,
  chartInstance: prefChartInstance,
  initChart: initPrefChart,
  setOption: setPrefOption,
  showLoading: showPrefLoad,
  hideLoading: hidePrefLoad,
} = useEcharts()

const {
  chartRef: categoryTrendChart,
  chartInstance: categoryChartInstance,
  initChart: initCategoryChart,
  setOption: setCategoryOption,
  showLoading: showCategoryLoad,
  hideLoading: hideCategoryLoad,
} = useEcharts()

const isComboDetailVisible = ref(false)
const comboDetailData = ref<{ name: string; value: number; count: number; animes: ComboAnimeItem[] }>({
  name: '',
  value: 0,
  count: 0,
  animes: [],
})
const comboDetailColor = ref('#667eea')

const seasonLabelMap: Record<SeasonValue, string> = {
  winter: '冬季(1-3月)',
  spring: '春季(4-6月)',
  summer: '夏季(7-9月)',
  autumn: '秋季(10-12月)',
}

const formatNumber = (num: number | null | undefined): string => {
  if (num == null) return '0'
  if (num >= 100000000) return `${(num / 100000000).toFixed(1)}亿`
  if (num >= 10000) return `${(num / 10000).toFixed(1)}万`
  return num.toLocaleString()
}

const getComboAnimeImageUrl = (anime: ComboAnimeItem): string => {
  if (!anime.cover) return ''
  return `/api/image_proxy?url=${encodeURIComponent(anime.cover)}&title=${encodeURIComponent(anime.title)}&season_id=${anime.season_id}`
}

const seasonalSummary = computed(() => {
  const order: SeasonValue[] = ['winter', 'spring', 'summer', 'autumn']
  const chunks = order
    .map(season => {
      const genre = bestGenreBySeason.value[season]
      return genre ? `${seasonLabelMap[season]}：${genre}` : ''
    })
    .filter(Boolean)
  return chunks.length ? chunks.join('；') : '暂无可用结论'
})

const preferenceSummary = computed(() => {
  const data = preferenceRaw.value
  if (!data.length) return '暂无可用结论'

  const userPrefs = new Set(authStore.preferences || [])
  if (!userPrefs.size) return '你尚未设置偏好，可先在偏好页配置'

  const topStyles = [...data]
    .sort((a, b) => b.preferenceIndex - a.preferenceIndex)
    .slice(0, 8)
    .map(item => item.style)

  const overlap = topStyles.filter(style => userPrefs.has(style))
  if (!overlap.length) return `在「${selectedPrefArea.value}」的 Top 题材中暂未命中你的偏好`
  return `在「${selectedPrefArea.value}」的 Top 题材中命中 ${overlap.length} 个：${overlap.join('、')}`
})

const ensureYearlyChart = () => {
  if (!yearlyChartInstance.value) initYearlyChart({})
}

const ensureSeasonalChart = () => {
  if (!seasonalChartInstance.value) initSeasonalChart({})
}

const ensurePrefChart = () => {
  if (!prefChartInstance.value) initPrefChart({})
}

const ensureCategoryChart = () => {
  if (!categoryChartInstance.value) initCategoryChart({})
}

const renderYearlyChart = async () => {
  if (!yearlyTrendChart.value) return
  ensureYearlyChart()
  yearlyStatus.value = 'loading'
  showYearlyLoad()

  try {
    const yearlyData = await getYearlyQuantityChart(yearlyView.value)
    const xData = ['冬季(1-3月)', '春季(4-6月)', '夏季(7-9月)', '秋季(10-12月)']
    const legendData = Object.keys(yearlyData).sort((a, b) => Number(b) - Number(a))

    if (!legendData.length) {
      yearlyStatus.value = 'empty'
      setYearlyOption({ series: [] }, { notMerge: true })
      return
    }

    const seriesData: echarts.SeriesOption[] = legendData.map(year => ({
      name: year,
      type: 'line',
      smooth: true,
      data: yearlyData[year],
    }))

    setYearlyOption(
      {
        tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
        legend: { data: legendData, type: 'scroll' },
        xAxis: { type: 'category', data: xData },
        yAxis: { type: 'value', name: '番剧数量' },
        grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
        series: seriesData,
      },
      { notMerge: true }
    )
    yearlyStatus.value = 'success'
  } catch (error) {
    console.error('加载历年趋势失败:', error)
    yearlyStatus.value = 'error'
  } finally {
    hideYearlyLoad()
  }
}

const renderSeasonalChart = async () => {
  if (!seasonalTrendChart.value) return
  ensureSeasonalChart()
  seasonalStatus.value = 'loading'
  showSeasonalLoad()

  try {
    const response = await getSeasonalGenreTrends()
    const trends = response.data?.trends || []
    bestGenreBySeason.value = response.data?.best_genre_by_season || {}

    if (!trends.length) {
      seasonalStatus.value = 'empty'
      setSeasonalOption({ series: [] }, { notMerge: true })
      return
    }

    const seasonOrder: SeasonValue[] = [...SEASON_VALUES]
    const genreTotals = new Map<string, number>()
    for (const item of trends) {
      genreTotals.set(item.genre, (genreTotals.get(item.genre) || 0) + item.total_views)
    }

    const topGenres = [...genreTotals.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 12)
      .map(([genre]) => genre)

    if (!topGenres.length) {
      seasonalStatus.value = 'empty'
      setSeasonalOption({ series: [] }, { notMerge: true })
      return
    }

    const topGenreSet = new Set(topGenres)
    const pairMap = new Map<string, { avgViews: number; animeCount: number }>()
    const heatmapData: Array<[number, number, number]> = []

    for (const item of trends) {
      if (!topGenreSet.has(item.genre)) continue
      const x = seasonOrder.indexOf(item.season)
      const y = topGenres.indexOf(item.genre)
      if (x < 0 || y < 0) continue
      pairMap.set(`${item.season}|${item.genre}`, {
        avgViews: item.avg_views,
        animeCount: item.anime_count,
      })
      heatmapData.push([x, y, item.avg_views])
    }

    const values = heatmapData.map(([, , value]) => value)
    const min = values.length ? Math.min(...values) : 0
    const max = values.length ? Math.max(...values) : 0

    setSeasonalOption(
      {
        tooltip: {
          trigger: 'item',
          formatter: (params: any) => {
            const season = seasonOrder[params.value[0]]
            const genre = topGenres[params.value[1]]
            const detail = pairMap.get(`${season}|${genre}`)
            if (!detail) return ''
            return `<b>${seasonLabelMap[season]}</b><br/>题材：${genre}<br/>平均播放：${formatNumber(detail.avgViews)}<br/>番剧数：${detail.animeCount}`
          },
        },
        grid: { left: '3%', right: '8%', bottom: '10%', top: '8%', containLabel: true },
        xAxis: {
          type: 'category',
          data: seasonOrder.map(s => seasonLabelMap[s]),
          splitArea: { show: true },
        },
        yAxis: {
          type: 'category',
          data: topGenres,
          splitArea: { show: true },
        },
        visualMap: {
          min,
          max,
          calculable: true,
          orient: 'vertical',
          right: 0,
          top: 'middle',
          inRange: {
            color: ['#e0f2fe', '#7dd3fc', '#38bdf8', '#0ea5e9', '#0369a1'],
          },
        },
        series: [
          {
            type: 'heatmap',
            data: heatmapData,
            label: {
              show: false,
            },
            emphasis: {
              itemStyle: {
                shadowBlur: 8,
                shadowColor: 'rgba(0, 0, 0, 0.35)',
              },
            },
          },
        ],
      },
      { notMerge: true }
    )
    seasonalStatus.value = 'success'
  } catch (error) {
    console.error('加载季节题材趋势失败:', error)
    seasonalStatus.value = 'error'
  } finally {
    hideSeasonalLoad()
  }
}

const renderPreferenceChart = async () => {
  if (!preferenceDiffChart.value) return
  ensurePrefChart()
  preferenceStatus.value = 'loading'
  showPrefLoad()

  try {
    const response = await getPreferenceDifferenceChart(selectedPrefArea.value)
    const chartData = response.data || []
    preferenceRaw.value = chartData

    if (!chartData.length) {
      preferenceStatus.value = 'empty'
      setPrefOption({ series: [] }, { notMerge: true })
      return
    }

    const userPreferences = authStore.preferences || []
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

    setPrefOption(
      {
        tooltip: {
          trigger: 'item',
          formatter: (params: any) => {
            if (params.data?.children?.length > 0 || params.data?.value == null) return ''
            const d = params.data
            const compText =
              d.value > 1.1
                ? `<span style="color:#28a745;">(高于全球)</span>`
                : d.value < 0.9
                  ? `<span style="color:#dc3545;">(低于全球)</span>`
                  : `<span>(与全球持平)</span>`
            return `<b>${d.name}</b><br/>地区偏好指数: <b style="font-size:1.1em;">${d.value}</b> ${compText}<br/><hr style="margin:4px 0;">该地区番剧数: ${d.regionCount}<br/>全球番剧数: ${d.globalCount}`
          },
        },
        series: [
          {
            type: 'treemap',
            roam: false,
            nodeClick: false,
            breadcrumb: { show: false },
            label: {
              show: true,
              position: 'inside',
              formatter: (p: any) => `${p.name}\n${p.value}`,
              color: '#fff',
              fontSize: 13,
            },
            data: treeData,
          },
        ],
      },
      { notMerge: true }
    )
    preferenceStatus.value = 'success'
  } catch (error) {
    console.error('加载偏好差异失败:', error)
    preferenceStatus.value = 'error'
  } finally {
    hidePrefLoad()
  }
}

const renderCategoryChart = async () => {
  if (!categoryTrendChart.value) return
  ensureCategoryChart()
  categoryStatus.value = 'loading'
  showCategoryLoad()
  categoryChartInstance.value?.off('click')

  try {
    const response = await getPopularStyleCombinationChart()
    const topCombinations = response.data || []

    if (!topCombinations.length) {
      categoryStatus.value = 'empty'
      setCategoryOption({ series: [] }, { notMerge: true })
      return
    }

    const seriesData = topCombinations.map(combo => ({
      name: combo.combination,
      value: Math.round(combo.avgFavorites),
      count: combo.animeCount,
      animes: combo.representativeAnimes,
    }))

    setCategoryOption(
      {
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
              animeListHtml = `<hr style="margin:4px 0;border-color:rgba(255,255,255,0.2);"><span style="color:#d1d5db;">包含番剧（部分）:</span><ul style="padding-left:15px;margin:5px 0 0;">${items}${more}</ul>`
            }
            return `<b>${name}</b><br/><span style="font-size:1.1em;color:#34d399;font-weight:bold;">平均追番: ${value?.toLocaleString()}</span><br/><hr style="margin:4px 0;border-color:rgba(255,255,255,0.2);">包含番剧数: ${count}${animeListHtml}`
          },
        },
        series: [
          {
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
          },
        ],
      },
      { notMerge: true }
    )

    categoryChartInstance.value?.on('click', (params: any) => {
      if (!params.data?.animes) return
      comboDetailData.value = {
        name: params.data.name,
        value: params.data.value,
        count: params.data.count,
        animes: params.data.animes,
      }
      comboDetailColor.value = params.color ?? '#667eea'
      isComboDetailVisible.value = true
      categoryChartInstance.value?.dispatchAction({ type: 'hideTip' })
      setCategoryOption({ series: [{ silent: true }] })
    })

    categoryStatus.value = 'success'
  } catch (error) {
    console.error('加载风格组合失败:', error)
    categoryStatus.value = 'error'
  } finally {
    hideCategoryLoad()
  }
}

const closeComboDetail = () => {
  isComboDetailVisible.value = false
  setCategoryOption({ series: [{ silent: false }] })
}

const setYearlyView = (value: YearlyViewValue) => {
  yearlyView.value = value
  renderedTabs.value.delete('yearly')
  void renderByTab('yearly', true).catch(error => {
    console.error('刷新历年趋势失败:', error)
  })
}

const setPrefArea = (value: AreaValue) => {
  selectedPrefArea.value = value
  renderedTabs.value.delete('preference')
  void renderByTab('preference', true).catch(error => {
    console.error('刷新地区偏好差异失败:', error)
  })
}

const resizeTabChart = (tab: OverviewTab) => {
  switch (tab) {
    case 'yearly':
      yearlyChartInstance.value?.resize()
      break
    case 'seasonal':
      seasonalChartInstance.value?.resize()
      break
    case 'preference':
      prefChartInstance.value?.resize()
      break
    case 'category':
      categoryChartInstance.value?.resize()
      break
  }
}

const renderByTab = async (tab: OverviewTab, force = false) => {
  if (!force && renderedTabs.value.has(tab)) {
    resizeTabChart(tab)
    return
  }

  switch (tab) {
    case 'yearly':
      await renderYearlyChart()
      break
    case 'seasonal':
      await renderSeasonalChart()
      break
    case 'preference':
      await renderPreferenceChart()
      break
    case 'category':
      await renderCategoryChart()
      break
  }

  renderedTabs.value.add(tab)
}

const switchTab = async (tab: OverviewTab) => {
  if (activeTab.value === tab) return
  activeTab.value = tab
  await nextTick()
  try {
    await renderByTab(tab)
  } catch (error) {
    console.error(`切换标签 ${tab} 渲染失败:`, error)
  }
}

onMounted(async () => {
  await renderByTab(activeTab.value)
})
</script>

<style scoped>
.overview-view {
  padding: 20px;
  --overview-chart-frame-width: 1000px;
  --overview-chart-frame-wide-width: 1080px;
}

.overview-tabs {
  gap: 0.5rem;
}

.overview-tabs .nav-link {
  border-radius: 999px;
  padding: 0.35rem 0.9rem;
  font-size: 0.88rem;
}

.overview-tabs .nav-link.active {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
}

.style-unified {
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  overflow: hidden;
  height: 100%;
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

.area-btn-group {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.area-btn {
  padding: 3px 12px;
  border-radius: 20px;
  border: 1px solid #d1d5db;
  background: transparent;
  color: #6b7280;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.area-btn:hover {
  border-color: #4facfe;
  color: #4facfe;
}

.area-btn.active {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  border-color: transparent;
  color: white;
  font-weight: 600;
}

.chart-wrapper {
  padding: 0.75rem 1rem 1rem;
}

.chart-fixed-frame {
  width: var(--overview-chart-frame-width);
  max-width: 100%;
  margin: 0 auto;
}

.chart-fixed-frame--wide {
  width: var(--overview-chart-frame-wide-width);
}

.chart-canvas {
  width: 100%;
}

.chart-canvas--medium {
  height: 420px;
}

.chart-canvas--large {
  height: 460px;
}

.chart-wrapper--medium {
  min-height: 448px;
}

.chart-wrapper--large {
  min-height: 488px;
}

.chart-state {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  font-size: 0.95rem;
  z-index: 1;
  pointer-events: none;
}

.insight-summary {
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  padding: 0.7rem 1rem 0.9rem;
  font-size: 0.86rem;
  color: #4b5563;
  line-height: 1.45;
}

.summary-label {
  color: #1f2937;
  font-weight: 600;
}

.combo-chart-dimmed {
  opacity: 0.4;
  pointer-events: none;
  transition: opacity 0.3s ease;
}

.combo-backdrop {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 9;
  cursor: pointer;
}

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

.slide-panel-enter-active,
.slide-panel-leave-active {
  transition: transform 0.3s ease, opacity 0.3s ease;
}

.slide-panel-enter-from,
.slide-panel-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

@media (max-width: 992px) {
  .chart-wrapper {
    padding: 0.5rem 0.75rem 0.75rem;
  }

  .combo-detail-panel {
    width: min(86vw, 320px);
  }
}
</style>
