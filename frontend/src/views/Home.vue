<template>
  <div class="home-view">

    <!-- ── 页面标题 ── -->
    <div class="page-header mb-4">
      <h2 class="page-title">📊 数据总览</h2>
      <p class="page-subtitle">
        {{
          overview?.last_update
            ? '最后更新：' + new Date(overview.last_update).toLocaleDateString('zh-CN')
            : isLoading ? '数据加载中…' : '暂无更新记录'
        }}
      </p>
    </div>

    <!-- ── Row 1：指标卡片 ── -->
    <div class="row mb-4">
      <div class="col-md-3 mb-3">
        <div class="metric-card pink">
          <div class="metric-icon"><i class="fas fa-film"></i></div>
          <div class="metric-content">
            <h5>番剧总数</h5>
            <p class="metric-value">{{ isLoading ? '…' : (overview?.total_animes ?? 0) }}</p>
            <p class="metric-sub">Total Animes</p>
          </div>
        </div>
      </div>
      <div class="col-md-3 mb-3">
        <div class="metric-card blue">
          <div class="metric-icon"><i class="fas fa-play-circle"></i></div>
          <div class="metric-content">
            <h5>总播放量</h5>
            <p class="metric-value">{{ isLoading ? '…' : formatNumber(overview?.total_views) }}</p>
            <p class="metric-sub">Total Views</p>
          </div>
        </div>
      </div>
      <div class="col-md-3 mb-3">
        <div class="metric-card purple">
          <div class="metric-icon"><i class="fas fa-heart"></i></div>
          <div class="metric-content">
            <h5>总追番数</h5>
            <p class="metric-value">{{ isLoading ? '…' : formatNumber(overview?.total_favorites) }}</p>
            <p class="metric-sub">Total Favorites</p>
          </div>
        </div>
      </div>
      <div class="col-md-3 mb-3">
        <div class="metric-card yellow">
          <div class="metric-icon"><i class="fas fa-globe-asia"></i></div>
          <div class="metric-content">
            <h5>主要来源</h5>
            <p class="metric-value">{{ areaDistSummary }}</p>
            <p class="metric-sub">Top Source Region</p>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Row 2：历年上新趋势（左）+ 地区来源甜甜圈（右）── -->
    <div class="row mb-4">
      <div class="col-md-8 mb-3">
        <div class="style-unified">
          <div class="card-header-unified">
            <h5>历年番剧上新数量</h5>
            <div class="area-btn-group">
              <button
                v-for="cat in yearlyCategories"
                :key="cat.value"
                class="area-btn"
                :class="{ active: yearlyCategory === cat.value }"
                @click="setYearlyCategory(cat.value)"
              >{{ cat.label }}
              </button>
            </div>
          </div>
          <div ref="yearlyTrendChartRef" style="height: 300px; width: 100%"></div>
        </div>
      </div>
      <div class="col-md-4 mb-3">
        <div class="style-unified">
          <div class="card-header-unified">
            <h5>地区来源分布</h5>
          </div>
          <div ref="areaDonutChartRef" style="height: 300px; width: 100%"></div>
        </div>
      </div>
    </div>

    <!-- ── Row 3：口碑 × 热度散点图（全宽）── -->
    <div class="row mb-4">
      <div class="col-md-12">
        <div class="style-unified">
          <div class="card-header-unified">
            <h5>口碑 × 热度分布图</h5>
            <small class="text-muted">X 轴：评分（≥2）　Y 轴：追番人数（对数）　点大小：播放量（对数）</small>
            <div class="area-btn-group">
              <button
                v-for="area in allAreas"
                :key="area"
                class="area-btn"
                :class="{ active: selectedScatterAreas.includes(area) }"
                @click="toggleScatterArea(area)"
              >{{ area }}
              </button>
            </div>
            <div class="search-bar mb-2 d-flex align-items-center">
              <div class="scatter-search-wrap">
                <span class="scatter-search-icon"><i class="fas fa-search"></i></span>
                <input
                  ref="scatterSearchInputRef"
                  type="text"
                  class="scatter-search-input"
                  placeholder="搜索番剧名称..."
                  v-model="searchQuery"
                  @keyup.enter="handleSearchAnime"
                  @focus="onScatterSearchFocus"
                  @blur="hideSuggestions"
                />
              </div>

              <Teleport to="body">
                <ul
                  v-if="showSuggestions"
                  class="scatter-dropdown-popup"
                  :style="{ top: dropdownPos.top + 'px', left: dropdownPos.left + 'px', width: dropdownPos.width + 'px' }"
                >
                  <li
                    v-for="item in searchSuggestions"
                    :key="item"
                    class="scatter-dropdown-item"
                    @mousedown.prevent="selectSuggestion(item)"
                  >
                    <i class="fas fa-film scatter-dropdown-icon"></i>{{ item }}
                  </li>
                </ul>
              </Teleport>

              <button class="scatter-locate-btn ms-2" @click="handleSearchAnime">
                <i class="fas fa-crosshairs me-1"></i>定位番剧
              </button>

              <button
                class="scatter-reset-btn ms-2"
                v-if="baselineViews"
                @click="handleResetSearch"
              >
                <i class="fas fa-undo me-1"></i>重置视图
              </button>
            </div>
          </div>
          <div ref="scatterChartRef" style="height: 600px; width: 100%"></div>
        </div>
      </div>
    </div>

    <!-- ── Row 4：口碑热度指数（左）+ 风格分布饼图（右）── -->
    <div class="row mb-4">
      <div class="col-md-6 mb-3">
        <div class="style-unified">
          <div class="card-header-unified">
            <h5>口碑热度指数 Top 15</h5>
            <div class="area-btn-group">
              <button
                v-for="s in heatSeasons"
                :key="s.value"
                class="area-btn"
                :class="{ active: heatSeason === s.value }"
                @click="setHeatSeason(s.value)"
              >{{ s.label }}
              </button>
            </div>
          </div>
          <div ref="heatIndexChartRef" style="height: 460px; width: 100%"></div>
        </div>
      </div>
      <div class="col-md-6 mb-3">
        <div class="style-unified">
          <div class="card-header-unified">
            <h5>番剧风格分布</h5>
            <div v-if="isTypeDrilledDown" class="d-flex align-items-center gap-2">
              <button class="btn btn-sm btn-outline-secondary" @click="backToTopType">
                <i class="fas fa-arrow-left me-1"></i>返回
              </button>
              <small class="text-muted">已展开"其他"</small>
            </div>
          </div>
          <div ref="typePieChartRef" style="height: 460px; width: 100%"></div>
        </div>
      </div>
    </div>

    <!-- ── Row 5：热门番剧排行榜 ── -->
    <div class="row mb-4">
      <div class="col-md-12">
        <div class="style-unified">
          <div class="card-header-unified">
            <h5>热门番剧排行榜</h5>
            <div class="area-btn-group">
              <button
                class="area-btn"
                :class="{ active: sortBy === 'rating' }"
                @click="setSortBy('rating')"
              ><i class="fas fa-star me-1"></i>评分
              </button>
              <button
                class="area-btn"
                :class="{ active: sortBy === 'views' }"
                @click="setSortBy('views')"
              ><i class="fas fa-play-circle me-1"></i>播放量
              </button>
              <button
                class="area-btn"
                :class="{ active: sortBy === 'favorites' }"
                @click="setSortBy('favorites')"
              ><i class="fas fa-heart me-1"></i>追番数
              </button>
            </div>
          </div>
          <div class="p-3">
            <div v-if="isLoading" class="text-center py-4 loading-tip">
              <i class="fas fa-spinner fa-spin me-1"></i>加载中...
            </div>
            <div v-else-if="rankings.length === 0" class="text-center py-4 loading-tip">暂无排行榜数据</div>
            <div v-else class="rank-grid">
              <div
                v-for="(anime, index) in rankings"
                :key="anime.season_id"
                class="rank-item"
              >
                <div
                  class="rank-number"
                  :class="{ 'top-1': index === 0, 'top-2': index === 1, 'top-3': index === 2 }"
                >{{ index + 1 }}
                </div>
                <img :src="getProxiedImageUrl(anime)" :alt="anime.title" class="rank-cover"/>
                <div class="rank-info">
                  <div class="rank-title">{{ anime.title }}</div>
                  <div class="rank-meta-row">
                    <span class="meta-tag">{{ anime.area }}</span>
                    <span v-if="anime.release_date" class="meta-tag">{{ anime.release_date }}</span>
                  </div>
                  <div class="rank-stat">
                    <span v-if="sortBy === 'rating'">⭐ {{ anime.rating ?? 'N/A' }}</span>
                    <span v-if="sortBy === 'views'">▶ {{ formatNumber(anime.views) }}</span>
                    <span v-if="sortBy === 'favorites'">❤ {{ formatNumber(anime.favorites) }}</span>
                  </div>
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
import {computed, nextTick, onActivated, onMounted, onUnmounted, ref, watch} from 'vue'
import type {ECharts} from 'echarts'
import * as echarts from 'echarts'
import type {AnimeData, ReputationHeatIndexItem, StatisticsOverview} from '@/api/analytics'
import {
  getOverview,
  getRankings,
  getReputationHeatIndexChart,
  getReputationPopularityChart,
  getTypeDistributionChart,
  getYearlyQuantityChart,
} from '@/api/analytics'
import {getProxiedImageUrl} from '@/utils/imageProxy'

// KeepAlive 组件名注册
defineOptions({name: 'HomeView'})

// ─── 状态 ─────────────────────────────────────────────────────────────────────
const isLoading = ref(true)
const overview = ref<StatisticsOverview | null>(null)
const rankings = ref<AnimeData[]>([])
const sortBy = ref<'views' | 'favorites' | 'rating'>('rating')
const searchQuery = ref('')
const baselineViews = ref<number | null>(null) // 新增：当前定位的“基准番剧播放量”

// 👇 预搜索（联想）相关的状态
const searchSuggestions = ref<string[]>([])
const showSuggestions = ref(false)
const scatterSearchInputRef = ref<HTMLInputElement | null>(null)
/** 散点图搜索下拉框最小宽度（px） */
const SCATTER_MIN_DROPDOWN_WIDTH = 240
const dropdownPos = ref({ top: 0, left: 0, width: SCATTER_MIN_DROPDOWN_WIDTH })
/** 正在通过点击联想项选择，抑制 watch(searchQuery) 重新打开下拉框 */
let isSelectingSuggestion = false

// 👇 监听输入内容，动态生成推荐列表
watch(searchQuery, (newVal: string) => {
  // 若当前是通过点击联想项触发的赋值，跳过本次更新，避免下拉框重新弹出
  if (isSelectingSuggestion) return

  if (!newVal.trim() || !scatterInstance) {
    searchSuggestions.value = []
    showSuggestions.value = false
    return
  }

  const currentOption = scatterInstance.getOption() as any
  const matches = new Set<string>() // 使用 Set 去重，避免重复的番剧名

  // 遍历当前图表中的所有数据点进行模糊匹配
  if (currentOption && currentOption.series) {
    currentOption.series.forEach((seriesItem: any) => {
      if (seriesItem.data) {
        seriesItem.data.forEach((dataPoint: any) => {
          const title = dataPoint[2] as string
          if (title.toLowerCase().includes(newVal.toLowerCase())) {
            matches.add(title)
          }
        })
      }
    })
  }

  // 转换为数组并截取前 10 条（防止弹出的列表太长），如果匹配到则显示下拉框
  searchSuggestions.value = Array.from(matches).slice(0, 10)
  showSuggestions.value = searchSuggestions.value.length > 0
})

// 👇 隐藏联想框（当输入框失焦时触发）
const hideSuggestions = () => {
  showSuggestions.value = false
}

// 👇 页面滚动时同步更新下拉框位置（仅在下拉框可见时执行，减少无效计算）
const onWindowScrollForScatter = () => {
  if (showSuggestions.value) updateDropdownPos()
}

// 👇 输入框获焦时计算弹出位置并显示联想框
const onScatterSearchFocus = () => {
  updateDropdownPos()
  if (searchSuggestions.value.length > 0) showSuggestions.value = true
}

// 👇 计算下拉弹出框的 fixed 定位坐标（相对于视口）
const updateDropdownPos = () => {
  const parent = scatterSearchInputRef.value?.parentElement
  if (!parent) return
  const rect = parent.getBoundingClientRect()
  dropdownPos.value = {
    top: rect.bottom + 4,
    left: rect.left,
    width: rect.width,
  }
}

// 👇 点击选中联想列表中的某一项
const selectSuggestion = (title: string) => {
  // 设置标志位，抑制 watch(searchQuery) 在赋值后重新打开下拉框
  isSelectingSuggestion = true
  searchQuery.value = title
  showSuggestions.value = false
  // 用 nextTick 等 Vue 清空 watch 队列后再重置标志位
  nextTick(() => {
    isSelectingSuggestion = false
  })
  handleSearchAnime()
}
// 历年趋势筛选
const yearlyCategory = ref<string>('all')
const yearlyCategories: Array<{ value: string; label: string }> = [
  {value: 'all', label: '全部'},
  {value: 'china', label: '国内'},
  {value: 'japan', label: '日本'},
  {value: 'us', label: '美国'},
]

// 散点图地区筛选
const allAreas = ['国内', '日本', '美国']
const selectedScatterAreas = ref<string[]>(['国内', '日本', '美国'])
const areaColorMap: Record<string, string> = {
  '国内': '#FB7299',
  '日本': '#23ADE5',
  '美国': '#FFCE56',
}

// 口碑热度指数筛选
const heatSeason = ref<string>('all')
const heatSeasons: Array<{ value: string; label: string }> = [
  {value: 'all', label: '全年'},
  {value: 'spring', label: '春'},
  {value: 'summer', label: '夏'},
  {value: 'autumn', label: '秋'},
  {value: 'winter', label: '冬'},
]

// 风格分布下钻状态
const isTypeDrilledDown = ref(false)
let typeTopLevelData: { name: string; value: number }[] = []
let typeOtherData: { name: string; value: number }[] = []
const MAX_SLICES = 18
/** 下钻算法最少保留的顶级扇区数量 */
const MIN_VISIBLE_SLICES = 21
/** 横向柱状图 Y 轴标签截断最大字符数 */
const MAX_TITLE_LENGTH = 10

// ─── 图表 DOM 引用 ────────────────────────────────────────────────────────────
const yearlyTrendChartRef = ref<HTMLElement>()
const areaDonutChartRef = ref<HTMLElement>()
const scatterChartRef = ref<HTMLElement>()
const heatIndexChartRef = ref<HTMLElement>()
const typePieChartRef = ref<HTMLElement>()

let yearlyTrendInstance: ECharts | null = null
let areaDonutInstance: ECharts | null = null
let scatterInstance: ECharts | null = null
let heatIndexInstance: ECharts | null = null
let typePieInstance: ECharts | null = null

let yearlyResizeObserver: ResizeObserver | null = null
let areaDonutResizeObserver: ResizeObserver | null = null
let scatterResizeObserver: ResizeObserver | null = null
let heatIndexResizeObserver: ResizeObserver | null = null
let typePieResizeObserver: ResizeObserver | null = null

// ─── 计算属性 ─────────────────────────────────────────────────────────────────
const areaDistSummary = computed(() => {
  if (!overview.value?.area_distribution) return '—'
  const entries = Object.entries(overview.value.area_distribution)
  if (!entries.length) return '—'
  const top = entries.sort((a, b) => b[1] - a[1])[0]
  return top ? `${top[0]} 为主` : '—'
})

// ─── 工具函数 ─────────────────────────────────────────────────────────────────
const formatNumber = (num: number | undefined | null): string => {
  if (!num) return '0'
  if (num >= 100_000_000) return (num / 100_000_000).toFixed(1) + '亿'
  if (num >= 10_000) return (num / 10_000).toFixed(1) + '万'
  return num.toString()
}

/** 将 #RRGGBB 颜色转换为带透明度的 rgba() 字符串 */
const hexToRgba = (hex: string, alpha: number): string => {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

// ─── 数据加载 ─────────────────────────────────────────────────────────────────
const loadOverview = async () => {
  try {
    const res = await getOverview()
    if (res.success) overview.value = res.data
  } catch (e) {
    console.error('获取总览失败:', e)
  }
}

const loadRankings = async () => {
  try {
    const res = await getRankings(sortBy.value, 16)
    if (res.success) rankings.value = res.list
  } catch (e) {
    console.error('获取排行榜失败:', e)
    rankings.value = []
  }
}

const loadData = async () => {
  isLoading.value = true
  await Promise.allSettled([loadOverview(), loadRankings()])
  isLoading.value = false
}

// ─── 图表渲染 ─────────────────────────────────────────────────────────────────

/** 渲染历年番剧上新趋势折线图（四季度多系列） */
const renderYearlyTrendChart = async () => {
  if (!yearlyTrendChartRef.value) return

  if (yearlyTrendInstance) {
    yearlyTrendInstance.dispose()
    yearlyResizeObserver?.disconnect()
  }

  yearlyTrendInstance = echarts.init(yearlyTrendChartRef.value)
  yearlyResizeObserver = new ResizeObserver(() => yearlyTrendInstance?.resize())
  yearlyResizeObserver.observe(yearlyTrendChartRef.value)

  try {
    const data = await getYearlyQuantityChart(yearlyCategory.value)
    const years = Object.keys(data).sort()
    const quarterColors = ['#fa709a', '#43e97b', '#f7971e', '#4facfe']
    const quarterNames = ['Q1（冬/春）', 'Q2（春/夏）', 'Q3（夏/秋）', 'Q4（秋/冬）']
    const series: echarts.SeriesOption[] = quarterNames.map((name, qIdx) => ({
      name,
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: {color: quarterColors[qIdx], width: 2.5},
      itemStyle: {color: quarterColors[qIdx]},
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          {offset: 0, color: hexToRgba(quarterColors[qIdx], 0.25)},
          {offset: 1, color: hexToRgba(quarterColors[qIdx], 0.03)},
        ]),
      },
      data: years.map(y => data[y]?.[qIdx] ?? 0),
    }))

    yearlyTrendInstance.setOption({
      tooltip: {trigger: 'axis'},
      legend: {data: quarterNames, top: 5, textStyle: {fontSize: 11}},
      grid: {left: '3%', right: '4%', bottom: '3%', top: '14%', containLabel: true},
      xAxis: {type: 'category', data: years, boundaryGap: false, axisLabel: {interval: 1}},
      yAxis: {type: 'value', name: '数量', splitLine: {lineStyle: {type: 'dashed'}}},
      series,
    }, {notMerge: true})
  } catch (e) {
    console.error('历年趋势图加载失败:', e)
  }
}

/** 渲染地区来源甜甜圈图 */
const renderAreaDonutChart = () => {
  if (!areaDonutChartRef.value || !overview.value?.area_distribution) return

  if (areaDonutInstance) {
    areaDonutInstance.dispose()
    areaDonutResizeObserver?.disconnect()
  }

  areaDonutInstance = echarts.init(areaDonutChartRef.value)
  areaDonutResizeObserver = new ResizeObserver(() => areaDonutInstance?.resize())
  areaDonutResizeObserver.observe(areaDonutChartRef.value)

  const dist = overview.value.area_distribution
  const data = Object.entries(dist)
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({name, value}))

  areaDonutInstance.setOption({
    tooltip: {trigger: 'item', formatter: '{b}: {c} ({d}%)'},
    legend: {orient: 'vertical', left: '5%', top: 'center', textStyle: {fontSize: 12}},
    series: [{
      name: '地区分布',
      type: 'pie',
      radius: ['42%', '68%'],
      center: ['62%', '52%'],
      avoidLabelOverlap: false,
      itemStyle: {borderRadius: 8, borderColor: '#fff', borderWidth: 2},
      label: {show: false},
      emphasis: {
        label: {show: true, fontSize: 14, fontWeight: 'bold' as const},
        itemStyle: {shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.3)'},
      },
      labelLine: {show: false},
      data,
    }],
  })
}

/** 渲染口碑 × 热度散点图 */
const renderScatterChart = async () => {
  if (!scatterChartRef.value) return

  if (scatterInstance) {
    scatterInstance.dispose()
    scatterResizeObserver?.disconnect()
  }

  scatterInstance = echarts.init(scatterChartRef.value)
  scatterResizeObserver = new ResizeObserver(() => scatterInstance?.resize())
  scatterResizeObserver.observe(scatterChartRef.value)

  try {
    const areasQuery = selectedScatterAreas.value.join(',')
    const response = await getReputationPopularityChart(areasQuery)
    const chartData = response.data || []

    const seriesByArea: Record<string, Array<[number, number, string, number, number, string]>> = {}
    for (const area of selectedScatterAreas.value) seriesByArea[area] = []
    for (const item of chartData) {
      if (seriesByArea[item.area]) {
        seriesByArea[item.area].push([
          item.rating, item.favorites, item.title, item.views, item.ratingRaw, item.area,
        ])
      }
    }

    const series: echarts.SeriesOption[] = selectedScatterAreas.value.map(area => ({
      name: area,
      type: 'scatter',
      symbolSize: function (data) {
        const views = data[3] || 1;

        // 👇 动态比例核心逻辑
        if (baselineViews.value) {
          // 局部基准模式：以搜索到的番剧为基准，使用【面积正比于播放量】的方式计算相对大小
          const targetViews = baselineViews.value;
          const baseRadius = 50; // 被定位的目标番剧，固定给一个 50px 的舒适半径

          // 面积比 = views / targetViews，因此半径比 = Math.sqrt(views / targetViews)
          let r = baseRadius * Math.sqrt(views / targetViews);

          // 限制极限大小（最小 3px，最大 80px），防止局部出现破亿播放的巨无霸神作遮蔽屏幕
          return Math.max(3, Math.min(r, 100));
        } else {
          // 全局默认模式：对数映射（防重叠）
          const minSize = 1;
          const maxSize = 50;
          const minLog = 5;
          const maxLog = 10;

          const currentLog = Math.log10(views);
          let size = ((currentLog - minLog) / (maxLog - minLog)) * (maxSize - minSize) + minSize;

          return Math.max(minSize, Math.min(size, maxSize));
        }
      },

      itemStyle: {
        // 👇 调整点 2：透明度进一步降低，哪怕重叠 10 层也不会变成纯黑
        color: areaColorMap[area] ?? '#cccccc',
        opacity: 0.45,

        // 👇 调整点 3：【核心技巧】加上描边！
        // 描边使用原本的实色（不透明），这样每个气泡的轮廓就清晰可见了
        borderColor: areaColorMap[area] ?? '#cccccc',
        borderWidth: 0.6
      },
      data: seriesByArea[area],
      emphasis: {
        focus: 'series',
      },
    }))

    scatterInstance.setOption({
      tooltip: {
        trigger: 'item',
        formatter: (params: any) => {
          if (!params.value) return '无数据'
          const [, followers, title, views, originalScore, area] = params.value as
            [number, number, string, number, number, string]
          return (
            `${params.marker}<b>${title}</b><br/>` +
            `地区: <b>${area || '未知'}</b><br/>` +
            `评分: <b>${(originalScore ?? 0).toFixed(1)}</b><br/>` +
            `追番: <b>${formatNumber(followers)}</b><br/>` +
            `播放: <b>${formatNumber(views)}</b>`
          )
        },
      },
      legend: {
        top: 0, tooltip: {
          show: false
        }
      },
      grid: {left: '3%', right: '4%', bottom: '10%', containLabel: true},
      xAxis: {
        type: 'value',
        nameLocation: 'middle',
        nameGap: 25,
        splitLine: {lineStyle: {type: 'dashed' as const}},
        min: 2,
      },
      yAxis: {
        type: 'log',
        min: 10000,
        max: 17000000,
        axisLabel: {
          formatter: function (value: number) {
            // 1. 还原真实的追番数
            const realValue = value;

            // 2. 格式化并强制取整，约掉小数点
            if (realValue >= 100000000) {
              // 达到亿级别
              return Math.round(realValue / 100000000) + '亿';
            } else if (realValue >= 10000) {
              // 达到万级别
              return Math.round(realValue / 10000) + '万';
            } else {
              // 小于1万的直接取整
              return Math.round(realValue);
            }
          }
        }
      },
      series,
      dataZoom: [
        {
          type: 'slider',       // 设置为内置型，无可见UI，全靠鼠标交互
          xAxisIndex: [0],      // 绑定到第 1 个 X 轴
          preventDefaultMouseMove: true // 阻止拖拽图表时页面的默认滚动
        },
        {
          type: 'slider',
          yAxisIndex: [0],
          preventDefaultMouseMove: true
        },
        {
          type: 'inside',
          xAxisIndex: [0],      // 绑定到 X 轴
        },
        {
          type: 'inside',
          yAxisIndex: [0],      // 绑定到 Y 轴
        },
      ]
    }, {notMerge: true})
  } catch (e) {
    console.error('散点图加载失败:', e)
  }
}

/** 渲染口碑热度指数横向柱状图（Top 15） */
const renderHeatIndexChart = async () => {
  if (!heatIndexChartRef.value) return

  if (heatIndexInstance) {
    heatIndexInstance.dispose()
    heatIndexResizeObserver?.disconnect()
  }

  heatIndexInstance = echarts.init(heatIndexChartRef.value)
  heatIndexResizeObserver = new ResizeObserver(() => heatIndexInstance?.resize())
  heatIndexResizeObserver.observe(heatIndexChartRef.value)

  try {
    const response = await getReputationHeatIndexChart(heatSeason.value)
    const items: ReputationHeatIndexItem[] = (response.data || []).slice(0, 16)

    if (items.length === 0) {
      heatIndexInstance.setOption({
        title: {
          text: '暂无数据',
          left: 'center',
          top: 'center',
          textStyle: {color: '#9ca3af', fontSize: 16},
        },
      })
      return
    }

    // 横向柱状图：Y 轴为番剧名，X 轴为综合指数
    const titles = items.map(i => (i.title.length > MAX_TITLE_LENGTH ? i.title.slice(0, MAX_TITLE_LENGTH) + '…' : i.title))
    const scores = items.map(i => parseFloat(i.qualityScore.toFixed(2)))
    const gradientColors = [
      ['#4facfe', '#00f2fe'],
      ['#43e97b', '#38f9d7'],
      ['#fa709a', '#fee140'],
      ['#a18cd1', '#fbc2eb'],
      ['#f7971e', '#ffd200'],
    ]

    heatIndexInstance.setOption({
      tooltip: {
        trigger: 'axis',
        axisPointer: {type: 'shadow'},
        formatter: (params: any) => {
          const p = params[0]
          const item = items[p.dataIndex]
          return (
            `<b>${item.title}</b><br/>` +
            `口碑热度指数：<b>${item.qualityScore.toFixed(2)}</b><br/>` +
            `评分：${item.rating}　` +
            `追番：${formatNumber(item.favorites)}`
          )
        },
      },
      grid: {left: '3%', right: '3%', bottom: '3%', containLabel: true},
      xAxis: {
        type: 'value',
        splitLine: {lineStyle: {type: 'dashed' as const}},
      },
      yAxis: {
        type: 'category',
        data: titles,
        axisLabel: {fontSize: 11},
        inverse: true,
      },
      series: [{
        name: '口碑热度指数',
        type: 'bar',
        data: scores.map((v, i) => ({
          value: v,
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
              {offset: 0, color: gradientColors[i % gradientColors.length][0]},
              {offset: 1, color: gradientColors[i % gradientColors.length][1]},
            ]),
            borderRadius: [0, 4, 4, 0],
          },
        })),
        label: {
          show: true,
          position: 'right' as const,
          formatter: (p: any) => String(p.value),
          fontSize: 11,
        },
        barMaxWidth: 24,
      }],
    }, {notMerge: true})
  } catch (e) {
    console.error('口碑热度图加载失败:', e)
  }
}

/** 渲染风格分布甜甜圈饼图（支持"其他"下钻） */
const renderTypePieChart = async () => {
  if (!typePieChartRef.value) return

  if (typePieInstance) {
    typePieInstance.dispose()
    typePieResizeObserver?.disconnect()
  }

  typePieInstance = echarts.init(typePieChartRef.value)
  typePieResizeObserver = new ResizeObserver(() => typePieInstance?.resize())
  typePieResizeObserver.observe(typePieChartRef.value)

  try {
    const sortedStyles = await getTypeDistributionChart()
    if (sortedStyles.length === 0) return

    if (sortedStyles.length <= MAX_SLICES) {
      typeTopLevelData = sortedStyles.map(([name, value]) => ({name, value}))
      typeOtherData = []
    } else {
      let numToShow = MIN_VISIBLE_SLICES
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
    applyTypePieOption(typeTopLevelData)

    typePieInstance.on('click', (params: any) => {
      if (!isTypeDrilledDown.value && params.name === '其他' && typeOtherData.length > 0) {
        isTypeDrilledDown.value = true
        applyTypePieOption(typeOtherData)
      }
    })
  } catch (e) {
    console.error('风格分布图加载失败:', e)
  }
}

/** 将指定数据应用到风格饼图（含左右双列图例） */
const applyTypePieOption = (dataToShow: { name: string; value: number }[]) => {
  if (!typePieInstance) return
  const legendNames = dataToShow.map(i => i.name)
  const mid = Math.ceil(legendNames.length / 2)
  typePieInstance.setOption({
    tooltip: {trigger: 'item', formatter: '{b}: {c} ({d}%)'},
    legend: [
      {
        orient: 'vertical',
        left: '2%',
        top: 'center',
        data: legendNames.slice(0, mid),
        textStyle: {fontSize: 11},
      },
      {
        orient: 'vertical',
        right: '2%',
        top: 'center',
        data: legendNames.slice(mid),
        textStyle: {fontSize: 11},
      },
    ],
    series: [{
      name: '风格分布',
      type: 'pie',
      radius: ['35%', '60%'],
      center: ['50%', '55%'],
      avoidLabelOverlap: false,
      itemStyle: {borderRadius: 6, borderColor: '#fff', borderWidth: 2},
      label: {show: false},
      emphasis: {
        label: {show: true, fontSize: 14, fontWeight: 'bold' as const},
        itemStyle: {shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.3)'},
      },
      labelLine: {show: false},
      data: dataToShow,
    }],
  }, {notMerge: true})
}

/** 返回风格分布顶级视图 */
const backToTopType = () => {
  isTypeDrilledDown.value = false
  applyTypePieOption(typeTopLevelData)
}

/** 统一入口：渲染所有图表 */
const renderAllCharts = () => {
  renderYearlyTrendChart()
  renderAreaDonutChart()
  renderScatterChart()
  renderHeatIndexChart()
  renderTypePieChart()
}

// ─── 交互处理 ─────────────────────────────────────────────────────────────────
const setSortBy = async (val: 'views' | 'favorites' | 'rating') => {
  sortBy.value = val
  await loadRankings()
}
// 👇 新增/修改：搜索并定位番剧，同时建立局部比例基准
const handleSearchAnime = () => {
  if (!searchQuery.value.trim() || !scatterInstance) return

  const currentOption = scatterInstance.getOption() as any
  let targetData: any = null
  let targetSeriesIndex = -1
  let targetDataIndex = -1

  // 1. 从 ECharts 实例当前的 series 数据中查找匹配的番剧（优先精确匹配）
  if (currentOption && currentOption.series) {
    // 改用标准的 for 循环，以便找到精确匹配时可以直接 break 停止检索
    for (let sIndex = 0; sIndex < currentOption.series.length; sIndex++) {
      const seriesItem = currentOption.series[sIndex]
      if (!seriesItem.data) continue

      for (let dIndex = 0; dIndex < seriesItem.data.length; dIndex++) {
        const dataPoint = seriesItem.data[dIndex]
        const title = dataPoint[2] as string
        const searchVal = searchQuery.value.toLowerCase()
        const targetTitle = title.toLowerCase()

        // 优先级 1：完全精确匹配（点击下拉列表时触发）
        if (targetTitle === searchVal) {
          targetData = dataPoint
          targetSeriesIndex = sIndex
          targetDataIndex = dIndex
          break // 找到精确匹配，直接跳出内层循环
        }
        // 优先级 2：模糊匹配（敲回车搜索时触发，只保留第一个匹配上的，防止被后面的覆盖）
        else if (!targetData && targetTitle.includes(searchVal)) {
          targetData = dataPoint
          targetSeriesIndex = sIndex
          targetDataIndex = dIndex
        }
      }

      // 如果已经找到了精确匹配，直接跳出外层循环，停止多余的搜索
      if (targetData && targetData[2].toLowerCase() === searchQuery.value.toLowerCase()) {
        break
      }
    }
  }

  if (!targetData) {
    alert('未找到该番剧，请检查名称是否正确，或尝试在上方选中该番剧对应的地区！')
    return
  }

  const rating = targetData[0]
  const favorites = targetData[1]

  // 1. 【核心】设置基准播放量，并触发 series 重新走一遍 symbolSize 算法！
  baselineViews.value = targetData[3]
  scatterInstance.setOption({series: currentOption.series})

  // 2. 镜头缩放
  const xMin = rating - 0.1
  const xMax = rating + 0.1
  const yMin = favorites * 0.5
  const yMax = favorites * 2.5

  scatterInstance.dispatchAction({type: 'dataZoom', dataZoomIndex: 0, startValue: xMin, endValue: xMax})
  scatterInstance.dispatchAction({
    type: 'dataZoom',
    dataZoomIndex: 1,
    startValue: Math.max(10000, yMin),
    endValue: yMax
  })

  // 3. 高亮显示
  scatterInstance.dispatchAction({type: 'downplay'})
  setTimeout(() => {
    scatterInstance!.dispatchAction({type: 'highlight', seriesIndex: targetSeriesIndex, dataIndex: targetDataIndex})
    scatterInstance!.dispatchAction({type: 'showTip', seriesIndex: targetSeriesIndex, dataIndex: targetDataIndex})
  }, 300)
}

// 👇 新增：重置视图与比例逻辑
const handleResetSearch = () => {
  searchQuery.value = ''
  baselineViews.value = null // 清除基准点，恢复全局对数缩放模式

  if (scatterInstance) {
    // 恢复坐标轴全量显示（start: 0, end: 100）
    scatterInstance.dispatchAction({type: 'dataZoom', dataZoomIndex: 0, start: 0, end: 100})
    scatterInstance.dispatchAction({type: 'dataZoom', dataZoomIndex: 1, start: 0, end: 100})

    // 重新应用全局对数比例
    const currentOption = scatterInstance.getOption() as any
    scatterInstance.setOption({series: currentOption.series})
    scatterInstance.dispatchAction({type: 'downplay'}) // 取消高亮
  }
}

const setYearlyCategory = (cat: string) => {
  yearlyCategory.value = cat
  renderYearlyTrendChart()
}

const toggleScatterArea = (area: string) => {
  const idx = selectedScatterAreas.value.indexOf(area)
  if (idx > -1) selectedScatterAreas.value.splice(idx, 1)
  else selectedScatterAreas.value.push(area)
  renderScatterChart()
}

const setHeatSeason = (season: string) => {
  heatSeason.value = season
  renderHeatIndexChart()
}

// ─── 生命周期 ─────────────────────────────────────────────────────────────────
onMounted(async () => {
  await loadData()
  // 等待 DOM 完成渲染（包括布局排版），确保容器尺寸正确后再初始化 ECharts
  await nextTick()
  renderAllCharts()
  // 注册滚动监听，使散点图搜索下拉框跟随输入框位置
  window.addEventListener('scroll', onWindowScrollForScatter, { passive: true, capture: true })
})

// KeepAlive 激活：从缓存恢复时触发所有图表 resize
onActivated(() => {
  yearlyTrendInstance?.resize()
  areaDonutInstance?.resize()
  scatterInstance?.resize()
  heatIndexInstance?.resize()
  typePieInstance?.resize()
})

// 卸载时断开所有观察器并销毁所有图表实例，防止内存泄漏
onUnmounted(() => {
  yearlyResizeObserver?.disconnect()
  areaDonutResizeObserver?.disconnect()
  scatterResizeObserver?.disconnect()
  heatIndexResizeObserver?.disconnect()
  typePieResizeObserver?.disconnect()
  yearlyTrendInstance?.dispose()
  areaDonutInstance?.dispose()
  scatterInstance?.dispose()
  heatIndexInstance?.dispose()
  typePieInstance?.dispose()
  window.removeEventListener('scroll', onWindowScrollForScatter, { capture: true })
})
</script>

<style scoped>
.home-view {
  padding: 1.5rem 0;
}

/* ── 页面标题 ── */
.page-header {
  border-left: 4px solid #4facfe;
  padding-left: 1rem;
}

.page-title {
  font-size: 1.7rem;
  font-weight: 700;
  color: #1f2937;
  margin: 0 0 0.25rem;
}

.page-subtitle {
  margin: 0;
  font-size: 0.88rem;
  color: #9ca3af;
}

/* ── 指标卡片 ── */
.metric-card {
  padding: 1.5rem;
  border-radius: 12px;
  color: white;
  display: flex;
  align-items: center;
  gap: 1rem;
  height: 100%;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.metric-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.18);
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
  color: #6b21a8;
}

.metric-icon {
  font-size: 2.5rem;
  opacity: 0.85;
  flex-shrink: 0;
}

.metric-content h5 {
  margin: 0;
  font-size: 0.88rem;
  opacity: 0.9;
  font-weight: 500;
}

.metric-value {
  margin: 0.4rem 0 0.2rem;
  font-size: 1.8rem;
  font-weight: 700;
  line-height: 1;
}

.metric-sub {
  margin: 0;
  font-size: 0.78rem;
  opacity: 0.75;
}

/* ── 统一图表卡片（与 Status.vue 一致） ── */
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

/* ── 地区 / 筛选按钮组 ── */
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

/* ── 回退按钮 ── */
.btn {
  padding: 0.25rem 0.75rem;
  border-radius: 5px;
  border: 1px solid #d1d5db;
  background: transparent;
  color: #6b7280;
  font-size: 0.82rem;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-sm {
  padding: 2px 8px;
  font-size: 0.8rem;
}

.btn-outline-secondary:hover {
  background: #f3f4f6;
  border-color: #9ca3af;
}

/* ── 排行榜网格 ── */
.rank-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 0.75rem;
}

.rank-item {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.75rem;
  border-radius: 10px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  background: #fafafa;
  transition: box-shadow 0.2s, transform 0.2s;
}

.rank-item:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.rank-number {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #e5e7eb;
  color: #6b7280;
  font-size: 0.85rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.rank-number.top-1 {
  background: linear-gradient(135deg, #fad0c4, #ffd1ff);
  color: #7c3aed;
}

.rank-number.top-2 {
  background: linear-gradient(135deg, #c9cdd4, #e5e7eb);
  color: #1f2937;
}

.rank-number.top-3 {
  background: linear-gradient(135deg, #fde68a, #fbbf24);
  color: #78350f;
}

.rank-cover {
  width: 52px;
  height: 72px;
  object-fit: cover;
  border-radius: 6px;
  flex-shrink: 0;
  background: #f3f4f6;
}

.rank-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.rank-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: #1f2937;
  line-height: 1.3;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.rank-meta-row {
  display: flex;
  gap: 0.3rem;
  flex-wrap: wrap;
}

.meta-tag {
  background: #f3f4f6;
  color: #374151;
  padding: 1px 8px;
  border-radius: 20px;
  font-size: 0.78rem;
}

.rank-stat {
  font-size: 0.85rem;
  color: #4facfe;
  font-weight: 500;
}

/* ── 散点图搜索栏 ── */
.scatter-search-wrap {
  position: relative;
  display: flex;
  align-items: center;
  min-width: 220px;
  max-width: 320px;
  background: #f8fafc;
  border: 1.5px solid #d1d5db;
  border-radius: 24px;
  padding: 0 0.75rem;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.scatter-search-wrap:focus-within {
  border-color: #4facfe;
  box-shadow: 0 0 0 3px rgba(79, 172, 254, 0.15);
  background: #fff;
}

.scatter-search-icon {
  color: #9ca3af;
  font-size: 0.85rem;
  flex-shrink: 0;
  margin-right: 0.4rem;
  transition: color 0.2s;
}

.scatter-search-wrap:focus-within .scatter-search-icon {
  color: #4facfe;
}

.scatter-search-input {
  flex: 1;
  border: none;
  background: transparent;
  outline: none;
  font-size: 0.85rem;
  color: #1f2937;
  padding: 0.45rem 0;
  min-width: 0;
}

.scatter-search-input::placeholder {
  color: #b0b7c3;
}

/* 定位按钮 */
.scatter-locate-btn {
  display: inline-flex;
  align-items: center;
  padding: 0.42rem 0.9rem;
  border-radius: 20px;
  border: none;
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  color: #fff;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(79, 172, 254, 0.35);
  transition: box-shadow 0.2s, transform 0.15s;
  white-space: nowrap;
}

.scatter-locate-btn:hover {
  box-shadow: 0 4px 16px rgba(79, 172, 254, 0.5);
  transform: translateY(-1px);
}

/* 重置按钮 */
.scatter-reset-btn {
  display: inline-flex;
  align-items: center;
  padding: 0.42rem 0.9rem;
  border-radius: 20px;
  border: 1.5px solid #d1d5db;
  background: transparent;
  color: #6b7280;
  font-size: 0.82rem;
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s, background 0.2s;
  white-space: nowrap;
}

.scatter-reset-btn:hover {
  border-color: #9ca3af;
  background: #f3f4f6;
  color: #374151;
}


.gap-2 {
  gap: 0.5rem;
}

.p-3 {
  padding: 1rem;
}

.py-4 {
  padding-top: 1.5rem;
  padding-bottom: 1.5rem;
}

.text-muted {
  color: #9ca3af;
  font-size: 0.85rem;
}

.loading-tip {
  color: #9ca3af;
}

@media (max-width: 768px) {
  .page-title {
    font-size: 1.3rem;
  }

  .metric-value {
    font-size: 1.4rem;
  }

  .rank-grid {
    grid-template-columns: 1fr;
  }

  .card-header-unified {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>

<style>
/* ── 全局：散点图搜索弹出下拉列表（Teleport 到 body，scoped 样式无效） ── */
.scatter-dropdown-popup {
  position: fixed;
  z-index: 9999;
  background: #fff;
  border: 1px solid rgba(79, 172, 254, 0.25);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12), 0 2px 8px rgba(79, 172, 254, 0.08);
  padding: 0.4rem 0;
  max-height: 280px;
  overflow-y: auto;
  list-style: none;
  margin: 0;
}

.scatter-dropdown-popup::-webkit-scrollbar {
  width: 4px;
}

.scatter-dropdown-popup::-webkit-scrollbar-thumb {
  background: rgba(79, 172, 254, 0.3);
  border-radius: 4px;
}

.scatter-dropdown-item {
  padding: 0.45rem 1rem;
  font-size: 0.85rem;
  color: #374151;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: background 0.15s;
}

.scatter-dropdown-item:hover {
  background: linear-gradient(90deg, rgba(79, 172, 254, 0.08) 0%, rgba(0, 242, 254, 0.05) 100%);
  color: #2563eb;
}

.scatter-dropdown-icon {
  font-size: 0.75rem;
  color: #9ca3af;
  flex-shrink: 0;
}
</style>