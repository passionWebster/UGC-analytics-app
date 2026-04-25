<template>
  <div class="recommendation-view">
    <div class="recommendation-content">
      <!-- 头部控制区 -->
      <div class="recommendation-header">
        <div class="preference-status">
          <button class="btn btn-lg btn-pink" @click="togglePreferences">
            <i class="fas fa-heart me-2"></i>
            <span>{{ preferenceStatus }}</span>
          </button>
          <div v-if="showPreferencesTooltip" class="preference-tooltip">
            {{ preferencesText }}
          </div>
        </div>

        <!-- 排序控制 -->
        <div class="sort-controls">
          <label class="sort-label">排序方式：</label>
          <div class="btn-group" role="group">
            <button
              v-for="sort in sortOptions"
              :key="sort.value"
              class="btn"
              :class="currentSort === sort.value ? 'btn-primary active' : 'btn-outline-primary'"
              @click="handleSortChange(sort.value)"
            >
              <i :class="sort.icon + ' me-1'"></i>{{ sort.label }}
            </button>
          </div>
        </div>
      </div>

      <!-- 主从联动布局 -->
      <div class="master-detail-layout" v-loading="loading && allAnimes.length === 0">

        <!-- 左侧：番剧列表 (Master) -->
        <div class="master-panel">
          <div v-if="recommendations.length === 0 && !loading" class="empty-tip">
            暂无推荐数据
          </div>

          <div
            v-for="anime in recommendations"
            :key="anime.season_id"
            class="anime-list-item"
            :class="{ active: selectedAnime?.season_id === anime.season_id }"
            @click="selectAnime(anime)"
          >
            <div class="item-cover">
              <img :src="getProxiedImageUrl(anime) || '/placeholder.jpg'" :alt="anime.title" />
            </div>
            <div class="item-info">
              <div class="item-title" :title="anime.title">{{ anime.title }}</div>
              <div class="item-meta">
                <span class="item-rating">
                  <i class="fas fa-star"></i> {{ anime.rating?.toFixed(1) || 'N/A' }}
                </span>
                <span class="item-area">{{ anime.area }}</span>
              </div>
            </div>
          </div>

          <!-- 加载更多按钮（备用操作） -->
          <div v-if="hasMore && !loading" class="load-more-container">
            <button class="btn btn-outline-secondary btn-sm" @click="loadMore">
              <i class="fas fa-plus-circle me-1"></i>加载更多
            </button>
          </div>

          <!-- 无限滚动哨兵：当此元素进入视口时自动触发 loadMore -->
          <div ref="sentinel" class="scroll-sentinel"></div>
        </div>

        <!-- 右侧：番剧详情 (Detail) -->
        <div class="detail-panel">
          <!-- 加载中 -->
          <div v-if="detailLoading" class="detail-loading">
            <i class="fas fa-spinner fa-spin fa-2x"></i>
            <p>加载详情中…</p>
          </div>

          <!-- 未选中提示 -->
          <div v-else-if="!selectedDetail" class="detail-placeholder">
            <i class="fas fa-hand-pointer fa-3x"></i>
            <p>选择左侧番剧查看详情</p>
          </div>

          <!-- 详情内容 -->
          <div v-else class="detail-content">
            <div class="detail-inner">

              <!-- 海报区域 -->
              <div class="detail-poster">
                <img
                  :src="currentPosterUrl"
                  :alt="selectedDetail.title"
                  @error="useFallbackPoster"
                />
              </div>

              <!-- 右侧内容区 -->
              <div class="detail-right">

                <!-- 上方：剧照 + 透明 Logo -->
                <div class="backdrop-container">
                  <img
                    v-if="selectedDetail.tmdb_info?.backdrop_url"
                    :src="proxyTmdb(selectedDetail.tmdb_info.backdrop_url)"
                    :alt="selectedDetail.title + ' 剧照'"
                    class="backdrop-image"
                  />
                  <div v-else class="backdrop-fallback">
                    <span>{{ selectedDetail.title }}</span>
                  </div>

                  <!-- 透明 Logo 叠加在剧照左下角 -->
                  <img
                    v-if="selectedDetail.tmdb_info?.logo_url && !logoError"
                    :src="proxyTmdb(selectedDetail.tmdb_info.logo_url)"
                    :alt="selectedDetail.title + ' Logo'"
                    class="anime-logo"
                    @error="logoError = true"
                  />
                  <!-- Logo 加载失败时降级显示标题文字 -->
                  <span
                    v-else-if="selectedDetail.tmdb_info?.backdrop_url"
                    class="anime-logo-text"
                  >{{ selectedDetail.title }}</span>
                </div>

                <!-- 绿色分割线 -->
                <div class="green-divider"></div>

                <!-- 下方：番剧简介（紫色框） -->
                <div class="overview-box">
                  <p v-if="selectedDetail.tmdb_info?.overview">
                    {{ selectedDetail.tmdb_info.overview }}
                  </p>
                  <p v-else class="overview-empty">
                    暂无简介
                  </p>
                </div>

                <div v-if="selectedExplanation" class="explainability-box">
                  <h5>推荐解释</h5>
                  <p class="explain-reason">{{ selectedExplanation.explainability.reasoning }}</p>
                  <div class="explain-metrics">
                    <span>匹配分：{{ selectedExplanation.match_score.toFixed(2) }}</span>
                    <span>Jaccard：{{ selectedExplanation.explainability.jaccard_similarity.toFixed(2) }}</span>
                    <span>组合奖励：{{ selectedExplanation.explainability.combo_bonus_score.toFixed(2) }}</span>
                    <span>热度分位：{{ (selectedExplanation.explainability.views_percentile * 100).toFixed(1) }}%</span>
                  </div>
                  <div v-if="selectedExplanation.explainability.matched_styles?.length" class="matched-styles">
                    匹配风格：{{ selectedExplanation.explainability.matched_styles.join('、') }}
                  </div>
                  <div v-if="selectedExplanation.explainability.strategy_weights" class="strategy-block">
                    <button
                      class="strategy-toggle"
                      type="button"
                      :aria-expanded="isStrategyWeightsExpanded"
                      @click="isStrategyWeightsExpanded = !isStrategyWeightsExpanded"
                    >
                      <span class="strategy-title">策略权重（{{ selectedExplanation.explainability.strategy_enabled ? '已启用' : '未启用' }}）</span>
                      <span class="strategy-toggle-icon">{{ isStrategyWeightsExpanded ? '▾' : '▸' }}</span>
                    </button>
                    <div v-show="isStrategyWeightsExpanded">
                      <div class="explain-metrics">
                        <abbr class="explain-tip" :title="getSignalTooltip('views', 'weight')" tabindex="0">Views 权重：{{ formatExplainabilityNumber(selectedExplanation.explainability.strategy_weights?.views_weight) }}</abbr>
                        <abbr class="explain-tip" :title="getSignalTooltip('ai', 'weight')" tabindex="0">AI 权重：{{ formatExplainabilityNumber(selectedExplanation.explainability.strategy_weights?.ai_weight) }}</abbr>
                        <abbr class="explain-tip" :title="getSignalTooltip('tmdb', 'weight')" tabindex="0">TMDB 权重：{{ formatExplainabilityNumber(selectedExplanation.explainability.strategy_weights?.tmdb_weight) }}</abbr>
                        <abbr class="explain-tip" :title="getSignalTooltip('diversity', 'weight')" tabindex="0">Diversity 权重：{{ formatExplainabilityNumber(selectedExplanation.explainability.strategy_weights?.diversity_weight) }}</abbr>
                      </div>
                      <div class="metric-bars">
                        <div class="metric-bar-item">
                          <abbr class="metric-bar-label" :title="getSignalTooltip('views', 'weight')" tabindex="0">Views ⓘ</abbr>
                          <div
                            class="metric-bar-track"
                            role="progressbar"
                            aria-label="Views 权重"
                            aria-valuemin="0"
                            aria-valuemax="100"
                            :aria-valuenow="getExplainabilityPercentValue(selectedExplanation.explainability.strategy_weights?.views_weight)"
                          ><span class="metric-bar-fill" :style="{ width: formatExplainabilityPercent(selectedExplanation.explainability.strategy_weights?.views_weight) }"></span></div>
                        </div>
                        <div class="metric-bar-item">
                          <abbr class="metric-bar-label" :title="getSignalTooltip('ai', 'weight')" tabindex="0">AI ⓘ</abbr>
                          <div
                            class="metric-bar-track"
                            role="progressbar"
                            aria-label="AI 权重"
                            aria-valuemin="0"
                            aria-valuemax="100"
                            :aria-valuenow="getExplainabilityPercentValue(selectedExplanation.explainability.strategy_weights?.ai_weight)"
                          ><span class="metric-bar-fill" :style="{ width: formatExplainabilityPercent(selectedExplanation.explainability.strategy_weights?.ai_weight) }"></span></div>
                        </div>
                        <div class="metric-bar-item">
                          <abbr class="metric-bar-label" :title="getSignalTooltip('tmdb', 'weight')" tabindex="0">TMDB ⓘ</abbr>
                          <div
                            class="metric-bar-track"
                            role="progressbar"
                            aria-label="TMDB 权重"
                            aria-valuemin="0"
                            aria-valuemax="100"
                            :aria-valuenow="getExplainabilityPercentValue(selectedExplanation.explainability.strategy_weights?.tmdb_weight)"
                          ><span class="metric-bar-fill" :style="{ width: formatExplainabilityPercent(selectedExplanation.explainability.strategy_weights?.tmdb_weight) }"></span></div>
                        </div>
                        <div class="metric-bar-item">
                          <abbr class="metric-bar-label" :title="getSignalTooltip('diversity', 'weight')" tabindex="0">Diversity ⓘ</abbr>
                          <div
                            class="metric-bar-track"
                            role="progressbar"
                            aria-label="Diversity 权重"
                            aria-valuemin="0"
                            aria-valuemax="100"
                            :aria-valuenow="getExplainabilityPercentValue(selectedExplanation.explainability.strategy_weights?.diversity_weight)"
                          ><span class="metric-bar-fill" :style="{ width: formatExplainabilityPercent(selectedExplanation.explainability.strategy_weights?.diversity_weight) }"></span></div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div v-if="selectedExplanation.explainability.component_scores" class="strategy-block">
                    <button
                      class="strategy-toggle"
                      type="button"
                      :aria-expanded="isComponentSignalsExpanded"
                      @click="isComponentSignalsExpanded = !isComponentSignalsExpanded"
                    >
                      <span class="strategy-title">分项信号</span>
                      <span class="strategy-toggle-icon">{{ isComponentSignalsExpanded ? '▾' : '▸' }}</span>
                    </button>
                    <div v-show="isComponentSignalsExpanded">
                      <div class="explain-metrics">
                        <abbr class="explain-tip" :title="getSignalTooltip('views', 'signal')" tabindex="0">Views 信号：{{ formatExplainabilityNumber(selectedExplanation.explainability.component_scores?.views_signal) }}</abbr>
                        <abbr class="explain-tip" :title="getSignalTooltip('ai', 'signal')" tabindex="0">AI 信号：{{ formatExplainabilityNumber(selectedExplanation.explainability.component_scores?.ai_signal) }}</abbr>
                        <abbr class="explain-tip" :title="getSignalTooltip('tmdb', 'signal')" tabindex="0">TMDB 信号：{{ formatExplainabilityNumber(selectedExplanation.explainability.component_scores?.tmdb_signal) }}</abbr>
                        <abbr class="explain-tip" :title="getSignalTooltip('diversity', 'signal')" tabindex="0">Diversity 信号：{{ formatExplainabilityNumber(selectedExplanation.explainability.component_scores?.diversity_signal) }}</abbr>
                      </div>
                      <div class="metric-bars">
                        <div class="metric-bar-item">
                          <abbr class="metric-bar-label" :title="getSignalTooltip('views', 'signal')" tabindex="0">Views ⓘ</abbr>
                          <div
                            class="metric-bar-track"
                            role="progressbar"
                            aria-label="Views 信号"
                            aria-valuemin="0"
                            aria-valuemax="100"
                            :aria-valuenow="getExplainabilityPercentValue(selectedExplanation.explainability.component_scores?.views_signal)"
                          ><span class="metric-bar-fill metric-bar-fill-signal" :style="{ width: formatExplainabilityPercent(selectedExplanation.explainability.component_scores?.views_signal) }"></span></div>
                        </div>
                        <div class="metric-bar-item">
                          <abbr class="metric-bar-label" :title="getSignalTooltip('ai', 'signal')" tabindex="0">AI ⓘ</abbr>
                          <div
                            class="metric-bar-track"
                            role="progressbar"
                            aria-label="AI 信号"
                            aria-valuemin="0"
                            aria-valuemax="100"
                            :aria-valuenow="getExplainabilityPercentValue(selectedExplanation.explainability.component_scores?.ai_signal)"
                          ><span class="metric-bar-fill metric-bar-fill-signal" :style="{ width: formatExplainabilityPercent(selectedExplanation.explainability.component_scores?.ai_signal) }"></span></div>
                        </div>
                        <div class="metric-bar-item">
                          <abbr class="metric-bar-label" :title="getSignalTooltip('tmdb', 'signal')" tabindex="0">TMDB ⓘ</abbr>
                          <div
                            class="metric-bar-track"
                            role="progressbar"
                            aria-label="TMDB 信号"
                            aria-valuemin="0"
                            aria-valuemax="100"
                            :aria-valuenow="getExplainabilityPercentValue(selectedExplanation.explainability.component_scores?.tmdb_signal)"
                          ><span class="metric-bar-fill metric-bar-fill-signal" :style="{ width: formatExplainabilityPercent(selectedExplanation.explainability.component_scores?.tmdb_signal) }"></span></div>
                        </div>
                        <div class="metric-bar-item">
                          <abbr class="metric-bar-label" :title="getSignalTooltip('diversity', 'signal')" tabindex="0">Diversity ⓘ</abbr>
                          <div
                            class="metric-bar-track"
                            role="progressbar"
                            aria-label="Diversity 信号"
                            aria-valuemin="0"
                            aria-valuemax="100"
                            :aria-valuenow="getExplainabilityPercentValue(selectedExplanation.explainability.component_scores?.diversity_signal)"
                          ><span class="metric-bar-fill metric-bar-fill-signal" :style="{ width: formatExplainabilityPercent(selectedExplanation.explainability.component_scores?.diversity_signal) }"></span></div>
                        </div>
                      </div>
                    </div>
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
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue'
import {
  getRankings,
  getAnimeDetail,
  getPersonalizedRecommendations,
  getRecommendationExplanation,
  type RecommendationExplanationResponse,
  type AnimeData,
  type AnimeDetailData
} from '@/api/analytics'
import { getProxiedImageUrl, getProxiedUrl } from '@/utils/imageProxy'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

// 分页参数
const PAGE_SIZE = 12
const BATCH_SIZE = 100
const SCROLL_TRIGGER_MARGIN = '100px'

// 状态
const loading = ref(false)
const detailLoading = ref(false)
const allAnimes = ref<AnimeData[]>([])
const visibleCount = ref<number>(PAGE_SIZE)
const currentSort = ref('score')
const showPreferencesTooltip = ref(false)
const sentinel = ref<HTMLElement | null>(null)

// 当前选中的番剧（基础数据，用于高亮左侧列表项）
const selectedAnime = ref<AnimeData | null>(null)
// 当前选中番剧的详情（含 TMDB 信息）
const selectedDetail = ref<AnimeDetailData | null>(null)
// Logo 图片加载失败标记
const logoError = ref(false)
// 海报降级标记（TMDB 海报失败时回退到某头部弹幕视频网站封面）
const posterFallback = ref(false)
const selectedExplanation = ref<RecommendationExplanationResponse['data'] | null>(null)
const isStrategyWeightsExpanded = ref(true)
const isComponentSignalsExpanded = ref(true)

let scrollObserver: IntersectionObserver | null = null

// 当前可见的番剧列表（客户端分页）
const recommendations = computed<AnimeData[]>(() =>
  allAnimes.value.slice(0, visibleCount.value)
)

const hasMore = computed<boolean>(() =>
  visibleCount.value < allAnimes.value.length
)

const sortOptions = [
  { value: 'score', label: '评分', icon: 'fas fa-star' },
  { value: 'views', label: '播放量', icon: 'fas fa-play-circle' },
  { value: 'followers', label: '追番人数', icon: 'fas fa-heart' }
]

const preferenceStatus = computed<string>(() =>
  showPreferencesTooltip.value ? '已启用偏好推荐' : '根据偏好推荐'
)

const preferencesText = computed<string>(() => {
  const genres = authStore.preferences.join('、')
  return genres
    ? `已根据您的偏好（${genres}）筛选推荐`
    : '根据您的观看历史和偏好，为您推荐相似的番剧'
})

/** 当前海报 URL：优先使用 TMDB poster，降级使用某头部弹幕视频网站封面 */
const currentPosterUrl = computed<string>(() => {
  const detail = selectedDetail.value
  if (!detail) return '/placeholder.jpg'

  if (!posterFallback.value) {
    const posterUrl = detail.tmdb_info?.poster_url
    if (posterUrl) {
      return proxyTmdb(posterUrl)
    }
  }

  return getProxiedUrl(detail.cover, detail.title, detail.season_id) || '/placeholder.jpg'
})

/** 将 TMDB 图片 URL 转换为代理地址 */
const proxyTmdb = (url: string): string => {
  if (!selectedDetail.value) return url
  return getProxiedUrl(url, selectedDetail.value.title, selectedDetail.value.season_id)
}

/** 海报图片加载失败时降级到某头部弹幕视频网站封面 */
const useFallbackPoster = () => {
  posterFallback.value = true
}

/** 当前详情请求的标记，用于避免乱序响应覆盖最新选择 */
let detailRequestToken = 0

/** 选择番剧并加载详情 */
const selectAnime = async (anime: AnimeData) => {
  if (selectedAnime.value?.season_id === anime.season_id) return

  // 为本次请求生成独立标记
  detailRequestToken += 1
  const currentToken = detailRequestToken

  // 先设 detailLoading，再清空 selectedDetail，确保显示加载态而非空占位
  detailLoading.value = true
  selectedAnime.value = anime
  selectedDetail.value = null
  selectedExplanation.value = null
  logoError.value = false
  posterFallback.value = false
  try {
    const detailPromise = getAnimeDetail(anime.season_id)
    const explainPromise = authStore.username
      ? getRecommendationExplanation(authStore.username, anime.season_id)
      : Promise.resolve(null)

    const [resp, explainResp] = await Promise.all([detailPromise, explainPromise])
    // 如果期间发起了新的详情请求，则丢弃本次结果
    if (currentToken !== detailRequestToken) {
      return
    }
    selectedDetail.value = resp.data
    selectedExplanation.value = explainResp?.data || null
  } catch (error) {
    // 如果期间发起了新的详情请求，则不覆盖最新错误/数据状态
    if (currentToken !== detailRequestToken) {
      return
    }
    console.error('加载番剧详情失败:', error)
    // 降级：用基础数据展示，不含 TMDB 信息
    selectedDetail.value = { ...anime, tmdb_info: null }
  } finally {
    // 仅在当前请求仍是最新时更新加载状态
    if (currentToken === detailRequestToken) {
      detailLoading.value = false
    }
  }
}

const togglePreferences = () => {
  showPreferencesTooltip.value = !showPreferencesTooltip.value
  loadRecommendations()
}

const handleSortChange = (sortValue: string) => {
  if (currentSort.value === sortValue) return
  currentSort.value = sortValue
  loadRecommendations()
}

const loadRecommendations = async () => {
  try {
    loading.value = true
    visibleCount.value = PAGE_SIZE
    selectedAnime.value = null
    selectedDetail.value = null
    selectedExplanation.value = null

    if (authStore.username) {
      const response = await getPersonalizedRecommendations(authStore.username)
      allAnimes.value = response.data?.recommendations || []
    } else {
      let sortBy = currentSort.value
      if (sortBy === 'followers') sortBy = 'favorites'
      if (sortBy === 'score') sortBy = 'rating'

      const stylesFilter =
        showPreferencesTooltip.value && authStore.preferences.length > 0
          ? authStore.preferences.join(',')
          : undefined

      const response = await getRankings(sortBy, BATCH_SIZE, undefined, stylesFilter)
      allAnimes.value = response.list || []
    }
  } catch (error) {
    console.error('加载推荐失败:', error)
  } finally {
    loading.value = false
    await nextTick()
    triggerSentinelCheck()
    // 自动选中第一条（独立的 try-catch，不影响已完成的列表加载）
    if (allAnimes.value.length > 0) {
      try {
        await selectAnime(allAnimes.value[0])
      } catch (err) {
        console.error('自动选中第一条失败:', err)
      }
    }
  }
}

const loadMore = () => {
  visibleCount.value = Math.min(
    visibleCount.value + PAGE_SIZE,
    allAnimes.value.length
  )
}

const initScrollObserver = () => {
  if (scrollObserver) scrollObserver.disconnect()
  scrollObserver = new IntersectionObserver(
    (entries) => {
      if (entries[0].isIntersecting && hasMore.value && !loading.value) {
        loadMore()
      }
    },
    { rootMargin: SCROLL_TRIGGER_MARGIN, threshold: 0 }
  )
  if (sentinel.value) scrollObserver.observe(sentinel.value)
}

const triggerSentinelCheck = () => {
  if (scrollObserver && sentinel.value) {
    scrollObserver.unobserve(sentinel.value)
    scrollObserver.observe(sentinel.value)
  }
}

const formatExplainabilityNumber = (value?: number) =>
  typeof value === 'number' && Number.isFinite(value) ? value.toFixed(2) : '--'

const boundExplainabilityRatio = (value: number) => Math.max(0, Math.min(1, value))

const formatExplainabilityPercent = (value?: number) => {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '0%'
  if ((value < 0 || value > 1) && import.meta.env.DEV) {
    console.warn('explainability value out of range [0,1]:', value)
  }
  const bounded = boundExplainabilityRatio(value)
  return `${(bounded * 100).toFixed(0)}%`
}

const getExplainabilityPercentValue = (value?: number) => {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 0
  return Math.round(boundExplainabilityRatio(value) * 100)
}

const signalTooltipMap = {
  views: {
    weight: 'Views 权重：该项在综合推荐分中的占比，越高说明系统越重视播放热度相关信号。',
    signal: 'Views 信号：当前番剧在热度维度的标准化表现，结合热度分位进行衡量。'
  },
  ai: {
    weight: 'AI 权重：AI 偏好匹配项在综合推荐分中的占比。',
    signal: 'AI 信号：当前番剧与用户偏好的语义匹配强度。'
  },
  tmdb: {
    weight: 'TMDB 权重：外部评分质量信号在综合推荐分中的占比。',
    signal: 'TMDB 信号：基于 TMDB 评分相关数据计算出的质量表现。'
  },
  diversity: {
    weight: 'Diversity 权重：多样性补偿项在综合推荐分中的占比。',
    signal: 'Diversity 信号：当前番剧对推荐列表多样性的贡献程度。'
  }
} as const

const getSignalTooltip = (
  key: keyof typeof signalTooltipMap,
  type: 'weight' | 'signal'
) => signalTooltipMap[key][type]

onMounted(async () => {
  await loadRecommendations()
  await nextTick()
  initScrollObserver()
})

onUnmounted(() => {
  scrollObserver?.disconnect()
})
</script>

<style scoped>
.recommendation-view {
  padding: 20px;
}

.recommendation-content {
  max-width: 1400px;
  margin: 0 auto;
}

/* ── 头部控制区 ─────────────────────────────────── */
.recommendation-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding: 20px;
  background: white;
  border-radius: 10px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  flex-wrap: wrap;
  gap: 20px;
}

.preference-status {
  position: relative;
}

.btn-pink {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  color: white;
  border: none;
  padding: 12px 24px;
  font-size: 16px;
  border-radius: 8px;
  transition: all 0.3s ease;
}

.btn-pink:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(245, 87, 108, 0.4);
}

.preference-tooltip {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 10px;
  padding: 10px 15px;
  background: #333;
  color: white;
  border-radius: 6px;
  font-size: 14px;
  white-space: nowrap;
  z-index: 10;
  animation: fadeIn 0.3s ease;
}

.preference-tooltip::before {
  content: '';
  position: absolute;
  bottom: 100%;
  left: 20px;
  border: 6px solid transparent;
  border-bottom-color: #333;
}

.sort-controls {
  display: flex;
  align-items: center;
  gap: 15px;
}

.sort-label {
  font-weight: 500;
  margin: 0;
  color: #666;
}

.btn-group .btn {
  padding: 8px 16px;
  font-size: 14px;
  border-radius: 6px;
  margin: 0 4px;
  transition: all 0.3s ease;
}

.btn-group .btn:hover {
  transform: translateY(-2px);
}

/* ── 主从联动布局 ─────────────────────────────── */
.master-detail-layout {
  display: flex;
  gap: 20px;
  align-items: flex-start;
  --detail-min-height: 480px;
}

/* ── 左侧：番剧列表 (Master) ─────────────────── */
.master-panel {
  width: 340px;
  flex-shrink: 0;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  overflow-y: auto;
  /* 220px ≈ 页面标题栏(64px) + 推荐页头部区域(~130px) + 页面边距(~26px) */
  max-height: calc(100vh - 220px);
  display: flex;
  flex-direction: column;
}

.anime-list-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  cursor: pointer;
  transition: background 0.2s ease, border-left-color 0.2s ease;
  border-left: 4px solid transparent;
  border-bottom: 1px solid #f0f0f0;
}

.anime-list-item:last-child {
  border-bottom: none;
}

.anime-list-item:hover {
  background: #fef6f6;
  border-left-color: #f5576c80;
}

.anime-list-item.active {
  background: #fff0f0;
  border-left-color: #f5576c;
}

.item-cover {
  width: 48px;
  height: 64px;
  border-radius: 6px;
  overflow: hidden;
  flex-shrink: 0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.item-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.item-info {
  flex: 1;
  min-width: 0;
}

.item-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 6px;
  line-height: 1.4;
}

.item-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
}

.item-rating {
  color: #f5a623;
  font-weight: 500;
}

.item-area {
  color: #999;
}

.load-more-container {
  display: flex;
  justify-content: center;
  padding: 12px;
  border-top: 1px solid #f0f0f0;
}

.scroll-sentinel {
  height: 1px;
  width: 100%;
}

.empty-tip {
  text-align: center;
  padding: 40px 20px;
  color: #999;
  font-size: 14px;
}

/* ── 右侧：番剧详情 (Detail) ────────────────── */
.detail-panel {
  flex: 1;
  min-width: 0;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  min-height: var(--detail-min-height);
  overflow: hidden;
}

.detail-loading,
.detail-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: var(--detail-min-height);
  color: #bbb;
  gap: 16px;
  font-size: 15px;
}

/* 详情内容整体容器 */
.detail-content {
  padding: 20px;
  height: 100%;
}

/* 海报 + 右侧内容 两列布局 */
.detail-inner {
  display: flex;
  gap: 20px;
  align-items: flex-start;
}

/* 海报区域 */
.detail-poster {
  width: 160px;
  flex-shrink: 0;
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
  aspect-ratio: 2 / 3;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.detail-poster img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

/* 右侧内容区（上下分割） */
.detail-right {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0;
}

/* 剧照容器（相对定位，供 Logo 绝对定位叠加） */
.backdrop-container {
  position: relative;
  width: 100%;
  border-radius: 8px;
  overflow: hidden;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  aspect-ratio: 16 / 7;
}

.backdrop-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.backdrop-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  color: rgba(255, 255, 255, 0.6);
  font-size: 18px;
  font-weight: 600;
  padding: 16px;
  text-align: center;
}

/* 透明 Logo 叠加在剧照左下角 */
.anime-logo {
  position: absolute;
  bottom: 14px;
  left: 16px;
  max-height: 48px;
  max-width: 50%;
  object-fit: contain;
  filter: drop-shadow(0 2px 6px rgba(0, 0, 0, 0.8));
}

/* Logo 加载失败时的文字降级 */
.anime-logo-text {
  position: absolute;
  bottom: 14px;
  left: 16px;
  color: white;
  font-size: 18px;
  font-weight: 700;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.8);
  max-width: 80%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 绿色分割线 */
.green-divider {
  height: 2px;
  background: #10b981;
  margin: 14px 0;
  border-radius: 1px;
}

/* 简介区域（紫色框） */
.overview-box {
  background: rgba(139, 92, 246, 0.08);
  border-left: 3px solid #8b5cf6;
  border-radius: 0 6px 6px 0;
  padding: 14px 16px;
  max-height: 160px;
  overflow-y: auto;
  font-size: 14px;
  line-height: 1.8;
  color: #444;
}

.overview-box p {
  margin: 0;
}

.overview-empty {
  color: #bbb;
  font-style: italic;
}

.explainability-box {
  margin-top: 14px;
  padding: 12px 14px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
}

.explainability-box h5 {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 700;
}

.explain-reason {
  margin: 0 0 8px;
  font-size: 13px;
  color: #374151;
}

.explain-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  font-size: 12px;
  color: #4b5563;
}

.matched-styles {
  margin-top: 8px;
  font-size: 12px;
  color: #111827;
}

.strategy-block {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #d1d5db;
}

.strategy-title {
  font-size: 12px;
  font-weight: 600;
  color: #1f2937;
}

.strategy-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: none;
  background: transparent;
  padding: 0;
  margin-bottom: 6px;
  cursor: pointer;
  text-align: left;
}

.strategy-toggle-icon {
  font-size: 12px;
  color: #6b7280;
}

.explain-tip {
  cursor: help;
  text-decoration: none;
  border-bottom: none;
}

.metric-bars {
  margin-top: 8px;
  display: grid;
  gap: 6px;
  width: 100%;
}

.metric-bar-item {
  display: grid;
  grid-template-columns: 60px 1fr;
  gap: 8px;
  align-items: center;
  width: 100%;
}

.metric-bar-label {
  font-size: 11px;
  color: #6b7280;
  cursor: help;
  text-decoration: none;
  border-bottom: none;
}

.explain-tip:focus-visible,
.metric-bar-label:focus-visible {
  outline: 1px solid #3b82f6;
  outline-offset: 1px;
}

.metric-bar-track {
  width: 100%;
  height: 6px;
  background: #e5e7eb;
  border-radius: 999px;
  overflow: hidden;
}

.metric-bar-fill {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #2563eb);
  transition: width 0.25s ease;
}

.metric-bar-fill-signal {
  background: linear-gradient(90deg, #10b981, #059669);
}

/* ── 动画 ──────────────────────────────────── */
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ── 响应式 ────────────────────────────────── */
@media (max-width: 900px) {
  .recommendation-header {
    flex-direction: column;
    align-items: stretch;
  }

  .sort-controls {
    flex-direction: column;
    align-items: stretch;
  }

  .btn-group {
    display: flex;
    width: 100%;
  }

  .btn-group .btn {
    flex: 1;
  }

  .master-detail-layout {
    flex-direction: column;
  }

  .master-panel {
    width: 100%;
    max-height: 320px;
  }

  .detail-poster {
    width: 120px;
  }
}
</style>
