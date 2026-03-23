<template>
  <div class="status-view">
    <!-- 搜索区域 -->
    <div class="row mb-4">
      <div class="col-md-8 mx-auto">
        <div class="status-search-group">
          <div class="status-search-wrap">
            <span class="status-search-icon"><i class="fas fa-search"></i></span>
            <input
              ref="statusSearchInputRef"
              v-model="keyword"
              class="status-search-input"
              placeholder="输入番剧名搜索..."
              type="text"
              autocomplete="off"
              @keyup.enter="handleSearch"
              @focus="onStatusSearchFocus"
              @blur="hideStatusSuggestions"
              @input="onStatusSearchInput"
            />
          </div>
          <button class="status-search-btn" @click="handleSearch">
            <i class="fas fa-search me-1"></i>搜索
          </button>
          <button
            v-if="animeData"
            class="status-detail-btn"
            @click="toggleEpisodeDetails"
          >
            <i class="fas fa-list me-1"></i>剧集详情
          </button>
        </div>

        <Teleport to="body">
          <ul
            v-if="showStatusSuggestions && statusSuggestions.length > 0"
            class="status-dropdown-popup"
            :style="{ top: statusDropdownPos.top + 'px', left: statusDropdownPos.left + 'px', width: statusDropdownPos.width + 'px' }"
          >
            <li
              v-for="item in statusSuggestions"
              :key="item"
              class="status-dropdown-item"
              @mousedown.prevent="selectStatusSuggestion(item)"
            >
              <i class="fas fa-film status-dropdown-icon"></i>{{ item }}
            </li>
          </ul>
        </Teleport>

        <div v-if="statusMessage" class="status-form-text mt-2">{{ statusMessage }}</div>
      </div>
    </div>

    <!-- 番剧标题与生命周期勋章 -->
    <div v-if="animeData" class="anime-header mb-4">
      <h3 class="anime-title">
        {{ animeData.title }}
        <span
          v-for="badge in badges"
          :key="badge.key"
          :class="['lifecycle-badge', badge.className]"
        >{{ badge.label }}</span>
      </h3>
      <p class="anime-meta">
        <span v-if="animeData.area" class="meta-tag">{{ animeData.area }}</span>
        <span v-if="animeData.release_date" class="meta-tag">{{ animeData.release_date }}</span>
        <span v-if="animeData.rating" class="meta-tag rating">⭐ {{ animeData.rating }}</span>
      </p>
    </div>

    <!-- 统计卡片（metric-card 风格，与 Home.vue 统一） -->
    <div v-if="animeData" class="row mb-4">
      <!-- 追番人数 - 粉红渐变 -->
      <div class="col-md-3 mb-3">
        <div class="metric-card pink">
          <div class="metric-icon"><i class="fas fa-heart"></i></div>
          <div class="metric-content">
            <h5>追番人数</h5>
            <p class="metric-value">{{ formatNumber(animeData.favorites) }}</p>
            <p class="metric-sub">Favorites</p>
          </div>
        </div>
      </div>
      <!-- 总播放量 - 蓝色渐变 -->
      <div class="col-md-3 mb-3">
        <div class="metric-card blue">
          <div class="metric-icon"><i class="fas fa-play-circle"></i></div>
          <div class="metric-content">
            <h5>总播放量</h5>
            <p class="metric-value">{{ formatNumber(animeData.views) }}</p>
            <p class="metric-sub">Total Views</p>
          </div>
        </div>
      </div>
      <!-- 剧集数量 - 黄色渐变 -->
      <div class="col-md-3 mb-3">
        <div class="metric-card yellow">
          <div class="metric-icon"><i class="fas fa-film"></i></div>
          <div class="metric-content">
            <h5>剧集数量</h5>
            <p class="metric-value">{{ episodes.length || 0 }}</p>
            <p class="metric-sub">Episodes</p>
          </div>
        </div>
      </div>
      <!-- 平均播放 - 紫色渐变 -->
      <div class="col-md-3 mb-3">
        <div class="metric-card purple">
          <div class="metric-icon"><i class="fas fa-chart-line"></i></div>
          <div class="metric-content">
            <h5>平均播放</h5>
            <p class="metric-value">{{ formatNumber(avgViews) }}</p>
            <p class="metric-sub">Avg Views / Ep</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 图表行：播放趋势+留存 | 受众互动雷达 -->
    <div v-if="animeData" class="row mb-4">
      <!-- 播放趋势与留存分析（升级版：柱状图 + 留存折线叠加） -->
      <div class="col-md-8 mb-3">
        <div class="style-unified">
          <div class="card-header-unified">
            <h5>播放趋势 &amp; 留存率分析</h5>
            <small class="text-muted">点击柱子查看该集观看时间分布</small>
          </div>
          <div ref="playTrendChart" style="height: 400px; width: 100%"></div>
        </div>
      </div>
      <!-- 受众硬核互动雷达图 -->
      <div class="col-md-4 mb-3">
        <div class="style-unified">
          <div class="card-header-unified">
            <h5>受众硬核互动雷达</h5>
            <small class="text-muted">弹幕 / 评论 / 投币 / 点赞密度</small>
          </div>
          <div ref="radarChartRef" style="height: 400px; width: 100%"></div>
        </div>
      </div>
    </div>

    <!-- 观看时间分布 -->
    <div v-if="animeData" class="row mb-4">
      <div class="col-md-12">
        <div class="style-unified">
          <div class="card-header-unified">
            <h5>观看时间分布</h5>
            <small class="text-muted">{{ watchTimeSubtitle }}</small>
          </div>
          <div ref="watchTimeChart" style="height: 280px; width: 100%"></div>
        </div>
      </div>
    </div>

    <!-- 剧集详情表格 -->
    <div v-if="showEpisodeDetails && episodes.length > 0" class="row">
      <div class="col-md-12">
        <div class="style-unified">
          <div class="card-header-unified">
            <h5><i class="fas fa-list me-1"></i>剧集详情</h5>
          </div>
          <div class="p-3">
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
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted, onActivated, onDeactivated, nextTick } from 'vue'
import * as echarts from 'echarts'
import type { ECharts } from 'echarts'
import {
  searchAnimes,
  getAnimeDetail,
  getAnimeEpisodes,
  getEpisodeBehaviorAnalysis,
  getLifecycleAnalysis,
  getCompetitiveAnalysis,
  getWatchTimeDistribution,
} from '@/api/analytics'
import type {
  EpisodeBehaviorAnalysis,
  LifecycleGrowthData,
  CompetitiveLandscapeData,
  WatchTimeDistributionData,
} from '@/api/analytics'

// 为 KeepAlive 注册组件名
defineOptions({ name: 'StatusView' })

// ─── 状态管理 ───────────────────────────────────────────────────────────────
const keyword = ref('')
const statusMessage = ref('')

// 搜索自动补全相关状态
const statusSuggestions = ref<string[]>([])
const showStatusSuggestions = ref(false)
const statusSearchInputRef = ref<HTMLInputElement | null>(null)
/** 状态页搜索下拉框最小宽度（px） */
const STATUS_MIN_DROPDOWN_WIDTH = 320
/** 搜索联想防抄延迟（ms） */
const SUGGESTION_DEBOUNCE_MS = 300
const statusDropdownPos = ref({ top: 0, left: 0, width: STATUS_MIN_DROPDOWN_WIDTH })
let suggestionDebounceTimer: ReturnType<typeof setTimeout> | null = null
const animeData = ref<any>(null)
/** 剧集列表（来自 API 或回退至空数组） */
const episodes = ref<Array<{ title: string; views: number; peakTime: string | null; peakOnline: number | null }>>([])
const showEpisodeDetails = ref(false)
const watchTimeSubtitle = ref('所有剧集总计')
/** 当前选中的剧集索引，-1 表示全局汇总 */
const selectedEpisodeIndex = ref(-1)

// 真实 24 小时观看时间分布数据（从后端获取），各集的分布数组
const watchTimeDistributionData = ref<WatchTimeDistributionData | null>(null)
// 1 小时轮询定时器
let watchTimeTimer: ReturnType<typeof setInterval> | null = null

// 深度分析数据：请求失败时保持为 null，在界面上做降级展示；错误日志仍由全局 axios 拦截器统一处理
const behaviorData = ref<EpisodeBehaviorAnalysis | null>(null)
const lifecycleData = ref<LifecycleGrowthData | null>(null)
const competitiveData = ref<CompetitiveLandscapeData | null>(null)

// ─── 图表 DOM 引用 ───────────────────────────────────────────────────────────
const playTrendChart = ref<HTMLElement>()
const watchTimeChart = ref<HTMLElement>()
const radarChartRef = ref<HTMLElement>()

let playTrendInstance: ECharts | null = null
let watchTimeInstance: ECharts | null = null
let radarInstance: ECharts | null = null

let playTrendResizeObserver: ResizeObserver | null = null
let watchTimeResizeObserver: ResizeObserver | null = null
let radarResizeObserver: ResizeObserver | null = null

// ─── 计算属性 ────────────────────────────────────────────────────────────────
/** 剧集平均播放量 */
const avgViews = computed(() => {
  if (!episodes.value.length) return 0
  const total = episodes.value.reduce((sum, ep) => sum + (ep.views || 0), 0)
  return Math.round(total / episodes.value.length)
})

/**
 * 动态计算番剧生命周期与霸榜勋章列表。
 * 规则：
 * - 🔥 黑马预警：日增播放峰值超过当前总播放量的 8%（爆发式增长信号）
 * - 👑 霸榜神作：Top3 霸榜比例 ≥ 15%（长期统治力证明）
 * - 💎 硬核神作：全剧平均投币率 ≥ 4%（观众真金白银认可）
 */
const badges = computed(() => {
  const result: Array<{ key: string; label: string; className: string }> = []

  // 黑马指数判断：峰值日增 / 总播放量 ≥ 8%（无播放量或播放量为 0 时跳过，避免除零误判）
  const peakGrowth = lifecycleData.value?.peak_daily_growth ?? 0
  const totalViews = (animeData.value?.views as number | undefined) ?? 0
  if (peakGrowth > 0 && totalViews > 0 && peakGrowth / totalViews >= 0.08) {
    result.push({ key: 'dark-horse', label: '🔥 黑马预警', className: 'badge-fire' })
  }

  // 霸榜神作判断：Top3 占比 ≥ 15%
  const domTop3 = competitiveData.value?.dominance_top3
  if (domTop3 !== null && domTop3 !== undefined && domTop3 >= 15) {
    result.push({ key: 'champion', label: '👑 霸榜神作', className: 'badge-crown' })
  }

  // 硬核神作判断：平均投币率 ≥ 4%
  const coinRate = behaviorData.value?.avg_coin_rate
  if (coinRate !== null && coinRate !== undefined && coinRate >= 0.04) {
    result.push({ key: 'hardcore', label: '💎 硬核神作', className: 'badge-diamond' })
  }

  return result
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
 * 将互动率（coin/like/danmaku/reply 除以播放量的小数）转换为百分比数值。
 * 例：0.023 → 2.3
 */
const toPercentage = (rate: number | null): number =>
  parseFloat(((rate ?? 0) * 100).toFixed(2))

/**
 * 剧集 X 轴标签超过此数量时旋转标签，避免文字重叠。
 */
const LABEL_ROTATION_THRESHOLD = 12

/**
 * 标签旋转角度（度）。
 */
const LABEL_ROTATION_ANGLE = 45

/**
 * 每小时轮询间隔（毫秒）。
 */
const HOUR_IN_MS = 3_600_000

/**
 * 从后端获取真实 24 小时观看时间分布数据，更新 watchTimeDistributionData 并重新渲染图表。
 * 若接口返回 404（暂无数据）则静默降级，保持当前数据不变。
 */
const fetchWatchTimeDistribution = async (seasonId: number) => {
  try {
    const res = await getWatchTimeDistribution(seasonId)
    watchTimeDistributionData.value = res.data
    renderWatchTimeChart()
  } catch {
    // 暂无分集在线人数数据，保持现有图表不变（降级展示）
  }
}

/**
 * 启动每小时轮询，保持观看时间分布图表数据实时更新。
 * 若已有定时器则先清除，防止重复注册。
 */
const startHourlyFetch = (seasonId: number) => {
  stopHourlyFetch()
  watchTimeTimer = setInterval(() => {
    fetchWatchTimeDistribution(seasonId)
  }, HOUR_IN_MS)
}

/** 清除小时级轮询定时器 */
const stopHourlyFetch = () => {
  if (watchTimeTimer !== null) {
    clearInterval(watchTimeTimer)
    watchTimeTimer = null
  }
}

// ─── 搜索逻辑 ────────────────────────────────────────────────────────────────

// 计算下拉弹出框的 fixed 定位坐标（相对于视口）
const updateStatusDropdownPos = () => {
  if (!statusSearchInputRef.value) return
  const rect = statusSearchInputRef.value.getBoundingClientRect()
  statusDropdownPos.value = {
    top: rect.bottom + 4,
    left: rect.left,
    width: Math.max(rect.width, STATUS_MIN_DROPDOWN_WIDTH),
  }
}

// 输入框获焦时显示已有建议
const onStatusSearchFocus = () => {
  updateStatusDropdownPos()
  if (statusSuggestions.value.length > 0) showStatusSuggestions.value = true
}

// 隐藏联想框
const hideStatusSuggestions = () => {
  showStatusSuggestions.value = false
}

// 输入时防抖查询联想建议
const onStatusSearchInput = () => {
  if (suggestionDebounceTimer !== null) {
    clearTimeout(suggestionDebounceTimer)
  }
  const val = keyword.value.trim()
  if (!val) {
    statusSuggestions.value = []
    showStatusSuggestions.value = false
    return
  }
  suggestionDebounceTimer = setTimeout(async () => {
    try {
      const response = await searchAnimes(val)
      if (response.list && response.list.length > 0) {
        // 优先精确匹配排在前面，其余追加
        const exact: string[] = []
        const fuzzy: string[] = []
        const lowerVal = val.toLowerCase()
        response.list.forEach((item: any) => {
          if (item.title) {
            if (item.title.toLowerCase() === lowerVal) exact.push(item.title)
            else fuzzy.push(item.title)
          }
        })
        statusSuggestions.value = [...exact, ...fuzzy].slice(0, 10)
        updateStatusDropdownPos()
        showStatusSuggestions.value = statusSuggestions.value.length > 0
      } else {
        statusSuggestions.value = []
        showStatusSuggestions.value = false
      }
    } catch {
      statusSuggestions.value = []
    }
  }, SUGGESTION_DEBOUNCE_MS)
}

// 点击联想列表中的某一项：填入精确名称并立即搜索
const selectStatusSuggestion = (title: string) => {
  keyword.value = title
  showStatusSuggestions.value = false
  handleSearch()
}

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

      // 并行获取深度分析数据（任一失败时静默降级，不影响主流程）
      const [behaviorRes, lifecycleRes, competitiveRes] = await Promise.allSettled([
        getEpisodeBehaviorAnalysis(anime.season_id),
        getLifecycleAnalysis(anime.season_id),
        getCompetitiveAnalysis(anime.season_id),
      ])
      behaviorData.value =
        behaviorRes.status === 'fulfilled' ? (behaviorRes.value?.data ?? null) : null
      lifecycleData.value =
        lifecycleRes.status === 'fulfilled' ? (lifecycleRes.value?.data ?? null) : null
      competitiveData.value =
        competitiveRes.status === 'fulfilled' ? (competitiveRes.value?.data ?? null) : null

      selectedEpisodeIndex.value = -1
      watchTimeSubtitle.value = '所有剧集总计'

      // 等待 DOM 更新后渲染所有图表
      await nextTick()
      renderCharts()

      // 获取真实 24 小时观看时间分布，并启动每小时轮询刷新
      watchTimeDistributionData.value = null
      await fetchWatchTimeDistribution(anime.season_id)
      startHourlyFetch(anime.season_id)
    } else {
      statusMessage.value = '未找到相关番剧'
      animeData.value = null
      episodes.value = []
      behaviorData.value = null
      lifecycleData.value = null
      competitiveData.value = null
      watchTimeDistributionData.value = null
      stopHourlyFetch()
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
 * 点击剧集行或柱子时切换该集的观看时间分布图。
 * 再次点击同一集则还原为全局汇总视图。
 */
const selectEpisode = (index: number) => {
  if (selectedEpisodeIndex.value === index) {
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
  renderRadarChart()
}

/**
 * 渲染播放趋势与留存分析组合图（柱状图 + 留存折线叠加，双 Y 轴）。
 * - 左轴柱状图：各集播放量
 * - 右轴折线图：相对第1集的留存率（%），直观展示弃坑趋势
 * 留存数据优先使用行为分析 API，降级方案使用剧集播放量估算。
 */
const renderPlayTrendChart = () => {
  if (!playTrendChart.value) return

  if (playTrendInstance) {
    playTrendInstance.dispose()
    playTrendResizeObserver?.disconnect()
  }

  playTrendInstance = echarts.init(playTrendChart.value)

  // 统一的数据源：优先使用行为分析按集数据，其次降级为 episodes
  const engList = behaviorData.value?.engagement_by_episode ?? []
  const useEngagementAsSource = Array.isArray(engList) && engList.length > 0
  const baseList: Array<{ views?: number }> = useEngagementAsSource
    ? engList
    : episodes.value

  const labels = baseList.length
    ? baseList.map((_, i) => `第${i + 1}集`)
    : ['暂无数据']
  const viewsData = baseList.length
    ? baseList.map((ep) => ep.views || 0)
    : [0]

  // 计算逐集留存率：优先使用行为分析 API，其次用剧集播放量降级估算
  let retentionData: (number | null)[] = []
  if (useEngagementAsSource) {
    const firstViews = engList[0]?.views || 1
    retentionData = engList.map((ep) =>
      ep.views ? parseFloat(((ep.views / firstViews) * 100).toFixed(1)) : null
    )
  } else if (episodes.value.length > 1) {
    const firstViews = episodes.value[0]?.views || 1
    retentionData = episodes.value.map((ep) =>
      ep.views ? parseFloat(((ep.views / firstViews) * 100).toFixed(1)) : null
    )
  }
  const hasRetention = retentionData.length > 0

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params: any) => {
        let html = `<b>${params[0].name}</b><br/>`
        params.forEach((p: any) => {
          if (p.seriesName === '播放量') {
            html += `${p.marker}${p.seriesName}：${formatNumber(p.value)}<br/>`
          } else {
            html += `${p.marker}${p.seriesName}：${p.value !== null ? p.value + '%' : 'N/A'}<br/>`
          }
        })
        return html
      },
    },
    legend: {
      data: hasRetention ? ['播放量', '留存率'] : ['播放量'],
      top: 5,
    },
    grid: { left: '3%', right: hasRetention ? '6%' : '4%', bottom: '15%', containLabel: true },
    xAxis: {
      type: 'category',
      data: labels,
    axisLabel: { rotate: labels.length > LABEL_ROTATION_THRESHOLD ? LABEL_ROTATION_ANGLE : 0, interval: 0 },
    },
    yAxis: [
      {
        type: 'value',
        name: '播放量',
        axisLabel: { formatter: (v: number) => formatNumber(v) },
      },
      ...(hasRetention
        ? [
            {
              type: 'value' as const,
              name: '留存率',
              min: 0,
              max: 105,
              axisLabel: { formatter: '{value}%' },
            },
          ]
        : []),
    ],
    series: [
      {
        name: '播放量',
        type: 'bar',
        yAxisIndex: 0,
        data: viewsData,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#4facfe' },
            { offset: 1, color: '#00f2fe' },
          ]),
        },
        emphasis: {
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#2196F3' },
              { offset: 1, color: '#00BCD4' },
            ]),
          },
        },
      },
      ...(hasRetention
        ? [
            {
              name: '留存率',
              type: 'line' as const,
              yAxisIndex: 1,
              data: retentionData,
              smooth: true,
              symbol: 'circle',
              symbolSize: 6,
              lineStyle: { color: '#f5576c', width: 2.5 },
              itemStyle: { color: '#f5576c' },
              areaStyle: {
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                  { offset: 0, color: 'rgba(245, 87, 108, 0.15)' },
                  { offset: 1, color: 'rgba(245, 87, 108, 0.02)' },
                ]),
              },
            },
          ]
        : []),
    ],
  }

  playTrendInstance.setOption(option)

  // 仅在 episodes 数据可用且与柱状图数据长度匹配时，支持点击查看单集分布
  const canSelectEpisode =
    Array.isArray(episodes.value) &&
    episodes.value.length > 0 &&
    episodes.value.length >= (Array.isArray(viewsData) ? viewsData.length : 0)

  playTrendInstance.on('click', (params: any) => {
    if (!canSelectEpisode) return
    if (params.componentType === 'series') {
      const index = params.dataIndex
      if (typeof index === 'number' && index >= 0 && index < episodes.value.length) {
        selectEpisode(index)
      }
    }
  })

  playTrendResizeObserver = new ResizeObserver(() => playTrendInstance?.resize())
  playTrendResizeObserver.observe(playTrendChart.value)
}

/**
 * 渲染受众硬核互动雷达图。
 * 四个维度（每100次播放的互动次数，以百分比展示）：
 * - 弹幕密度：avg_danmaku_rate × 100
 * - 评论密度：avg_reply_rate × 100
 * - 投币率：avg_coin_rate × 100
 * - 点赞率：avg_like_rate × 100
 * 若暂无行为分析数据则展示占位提示。
 */
const renderRadarChart = () => {
  if (!radarChartRef.value) return

  if (radarInstance) {
    radarInstance.dispose()
    radarResizeObserver?.disconnect()
  }

  radarInstance = echarts.init(radarChartRef.value)

  // 暂无行为数据时展示占位图
  if (!behaviorData.value) {
    radarInstance.setOption({
      title: {
        text: '暂无互动数据',
        subtext: '需要剧集级统计数据',
        left: 'center',
        top: 'center',
        textStyle: { color: '#9ca3af', fontSize: 16 },
        subtextStyle: { color: '#d1d5db' },
      },
    })
    radarResizeObserver = new ResizeObserver(() => radarInstance?.resize())
    radarResizeObserver.observe(radarChartRef.value)
    return
  }

  // 各率转换为百分比（每100次播放的互动次数），复用 toPercentage 工具函数
  const danmakuPct = toPercentage(behaviorData.value.avg_danmaku_rate)
  const replyPct   = toPercentage(behaviorData.value.avg_reply_rate)
  const coinPct    = toPercentage(behaviorData.value.avg_coin_rate)
  const likePct    = toPercentage(behaviorData.value.avg_like_rate)

  // 计算各维度最大值：取数据值的 2 倍，不低于兜底下限，确保雷达图形始终可见
  const computeDynamicMax = (v: number, floor: number) => Math.max(v * 2.0, floor)

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        const [d, r, c, l] = params.value as number[]
        return [
          `<b>${params.name}</b>`,
          `弹幕密度：${d}%`,
          `评论密度：${r}%`,
          `投币率：${c}%`,
          `点赞率：${l}%`,
        ].join('<br/>')
      },
    },
    radar: {
      indicator: [
        { name: '弹幕密度', max: computeDynamicMax(danmakuPct, 5) },
        { name: '评论密度', max: computeDynamicMax(replyPct,   2) },
        { name: '投币率',   max: computeDynamicMax(coinPct,    5) },
        { name: '点赞率',   max: computeDynamicMax(likePct,   15) },
      ],
      radius: '62%',
      center: ['50%', '55%'],
      splitNumber: 4,
      axisName: { color: '#374151', fontSize: 13, fontWeight: 500 },
      splitArea: {
        areaStyle: {
          color: [
            'rgba(79, 172, 254, 0.03)',
            'rgba(79, 172, 254, 0.07)',
            'rgba(79, 172, 254, 0.11)',
            'rgba(79, 172, 254, 0.16)',
          ],
        },
      },
      splitLine: { lineStyle: { color: 'rgba(79, 172, 254, 0.2)' } },
      axisLine: { lineStyle: { color: 'rgba(79, 172, 254, 0.25)' } },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: [danmakuPct, replyPct, coinPct, likePct],
            name: animeData.value?.title || '当前番剧',
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(79, 172, 254, 0.45)' },
                { offset: 1, color: 'rgba(0, 242, 254, 0.1)' },
              ]),
            },
            lineStyle: { color: '#4facfe', width: 2.5 },
            itemStyle: { color: '#4facfe' },
            symbol: 'circle',
            symbolSize: 6,
          },
        ],
      },
    ],
  }

  radarInstance.setOption(option)

  radarResizeObserver = new ResizeObserver(() => radarInstance?.resize())
  radarResizeObserver.observe(radarChartRef.value)
}

/**
 * 渲染观看时间分布折线图（24 小时分布）。
 * 优先使用后端真实数据（watchTimeDistributionData），暂无数据时展示全零占位图。
 * 选中特定剧集时展示该集的分布，否则展示全剧汇总（各集逐小时求和）。
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
  const distData = watchTimeDistributionData.value?.episodes_data

  if (distData && distData.length > 0) {
    if (selectedEpisodeIndex.value >= 0 && selectedEpisodeIndex.value < distData.length) {
      // 单集分布
      watchData = distData[selectedEpisodeIndex.value].distribution
    } else {
      // 全剧汇总：各集逐小时求和
      watchData = Array(24).fill(0)
      distData.forEach((ep) => {
        ep.distribution.forEach((v, h) => { watchData[h] += v })
      })
    }
  } else {
    // 暂无真实数据，展示全零占位
    watchData = Array(24).fill(0)
  }

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const d = params[0]
        return `${d.name}<br/>观看人数: ${Math.round(d.value)}`
      },
    },
    xAxis: { type: 'category', data: hours, boundaryGap: false },
    yAxis: { type: 'value', axisLabel: { formatter: '{value}' } },
    series: [
      {
        name: '观看人数',
        type: 'line',
        data: watchData,
        smooth: true,
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(88, 160, 253, 0.5)' },
            { offset: 1, color: 'rgba(88, 160, 253, 0.1)' },
          ]),
        },
        lineStyle: { color: '#58a0fd', width: 2 },
        itemStyle: { color: '#58a0fd' },
      },
    ],
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
  }

  watchTimeInstance.setOption(option)

  watchTimeResizeObserver = new ResizeObserver(() => watchTimeInstance?.resize())
  watchTimeResizeObserver.observe(watchTimeChart.value)
}

// ─── 生命周期 ────────────────────────────────────────────────────────────────
onUnmounted(() => {
  // 断开所有 ResizeObserver，销毁所有 ECharts 实例，防止内存泄漏
  playTrendResizeObserver?.disconnect()
  watchTimeResizeObserver?.disconnect()
  radarResizeObserver?.disconnect()
  playTrendInstance?.dispose()
  watchTimeInstance?.dispose()
  radarInstance?.dispose()
  // 清除轮询定时器
  stopHourlyFetch()
})

// KeepAlive 激活：从缓存恢复时触发图表 resize，并根据当前番剧恢复小时轮询
onActivated(() => {
  // 恢复图表尺寸
  playTrendInstance?.resize()
  watchTimeInstance?.resize()
  radarInstance?.resize()

  // 根据当前 animeData / season_id 重新启动小时轮询（避免从其它路由返回后不再自动刷新）
  let seasonId: any | undefined
  // 兼容 animeData 为普通对象或 ref 的情况
  if (animeData) {
    // @ts-ignore: 运行时兼容两种结构
    seasonId = (animeData as any).season_id ?? (animeData as any).value?.season_id
  }
  if (seasonId) {
    // 使用现有的轮询启动方法，保持与初始加载时一致的行为
    // 若 startHourlyFetch 支持「立即拉取」选项，可在其内部处理
    // @ts-ignore: 依赖于现有函数签名
    startHourlyFetch(seasonId)
  }
})

// KeepAlive 失活：页面切走时停止轮询，避免后台持续请求
onDeactivated(() => {
  stopHourlyFetch()
})
</script>

<style scoped>
.status-view {
  padding: 20px;
}

/* ── 番剧标题与勋章区域 ── */
.anime-header {
  border-left: 4px solid #4facfe;
  padding-left: 1rem;
}

.anime-title {
  font-size: 1.6rem;
  font-weight: 700;
  color: #1f2937;
  margin-bottom: 0.5rem;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.anime-meta {
  margin: 0;
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.meta-tag {
  background: #f3f4f6;
  color: #374151;
  padding: 2px 10px;
  border-radius: 20px;
  font-size: 0.85rem;
}

.meta-tag.rating {
  background: linear-gradient(135deg, #fad0c4 0%, #ffd1ff 100%);
  color: #6b21a8;
}

/* ── 生命周期与霸榜勋章 ── */
.lifecycle-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 12px;
  border-radius: 20px;
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.3px;
  white-space: nowrap;
}

.badge-fire {
  background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%);
  color: #9d174d;
}

.badge-crown {
  background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%);
  color: #78350f;
}

.badge-diamond {
  background: linear-gradient(135deg, #a1c4fd 0%, #c2e9fb 100%);
  color: #1e3a5f;
}

/* ── Metric 卡片（与 Home.vue 统一设计语言） ── */
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

.metric-card.yellow {
  background: linear-gradient(135deg, #fad0c4 0%, #ffd1ff 100%);
  color: #6b21a8;
}

.metric-card.purple {
  background: linear-gradient(135deg, #a18cd1 0%, #fbc2eb 100%);
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

/* ── 统一图表容器（style-unified） ── */
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

/* ── 搜索栏 ── */
.status-search-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.status-search-wrap {
  flex: 1;
  min-width: 200px;
  display: flex;
  align-items: center;
  background: #f8fafc;
  border: 1.5px solid #d1d5db;
  border-radius: 28px;
  padding: 0 1rem;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.status-search-wrap:focus-within {
  border-color: #4facfe;
  box-shadow: 0 0 0 3px rgba(79, 172, 254, 0.15);
  background: #fff;
}

.status-search-icon {
  color: #9ca3af;
  font-size: 0.9rem;
  flex-shrink: 0;
  margin-right: 0.5rem;
  transition: color 0.2s;
}

.status-search-wrap:focus-within .status-search-icon {
  color: #4facfe;
}

.status-search-input {
  flex: 1;
  border: none;
  background: transparent;
  outline: none;
  font-size: 1rem;
  color: #1f2937;
  padding: 0.65rem 0;
  min-width: 0;
}

.status-search-input::placeholder {
  color: #b0b7c3;
}

.status-search-btn {
  display: inline-flex;
  align-items: center;
  padding: 0.65rem 1.4rem;
  border-radius: 28px;
  border: none;
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  color: #fff;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 2px 10px rgba(79, 172, 254, 0.35);
  transition: box-shadow 0.2s, transform 0.15s;
  white-space: nowrap;
}

.status-search-btn:hover {
  box-shadow: 0 4px 18px rgba(79, 172, 254, 0.5);
  transform: translateY(-1px);
}

.status-detail-btn {
  display: inline-flex;
  align-items: center;
  padding: 0.65rem 1.2rem;
  border-radius: 28px;
  border: 1.5px solid #d1d5db;
  background: transparent;
  color: #6b7280;
  font-size: 0.95rem;
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s, background 0.2s;
  white-space: nowrap;
}

.status-detail-btn:hover {
  border-color: #9ca3af;
  background: #f3f4f6;
  color: #374151;
}

.status-form-text {
  color: #6c757d;
  font-size: 0.9rem;
}

/* ── 剧集表格 ── */
.table-responsive {
  max-height: 600px;
  overflow-y: auto;
}

.table-hover tbody tr:hover {
  background-color: rgba(79, 172, 254, 0.07);
  cursor: pointer;
}

.table-active {
  background-color: rgba(79, 172, 254, 0.12) !important;
}

@media (max-width: 768px) {
  .anime-title {
    font-size: 1.2rem;
  }

  .metric-value {
    font-size: 1.4rem;
  }
}
</style>

<style>
/* ── 全局：番剧状态页搜索弹出下拉列表（Teleport 到 body，scoped 样式无效） ── */
.status-dropdown-popup {
  position: fixed;
  z-index: 9999;
  background: #fff;
  border: 1px solid rgba(79, 172, 254, 0.25);
  border-radius: 14px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12), 0 2px 8px rgba(79, 172, 254, 0.08);
  padding: 0.4rem 0;
  max-height: 300px;
  overflow-y: auto;
  list-style: none;
  margin: 0;
}

.status-dropdown-popup::-webkit-scrollbar {
  width: 4px;
}

.status-dropdown-popup::-webkit-scrollbar-thumb {
  background: rgba(79, 172, 254, 0.3);
  border-radius: 4px;
}

.status-dropdown-item {
  padding: 0.55rem 1.2rem;
  font-size: 0.9rem;
  color: #374151;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.55rem;
  transition: background 0.15s;
}

.status-dropdown-item:hover {
  background: linear-gradient(90deg, rgba(79, 172, 254, 0.08) 0%, rgba(0, 242, 254, 0.05) 100%);
  color: #2563eb;
}

.status-dropdown-icon {
  font-size: 0.8rem;
  color: #9ca3af;
  flex-shrink: 0;
}
</style>
