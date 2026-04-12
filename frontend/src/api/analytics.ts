// api/analytics.ts
/**
 * 数据分析相关 API
 */
import apiClient from './axios'

export interface AnimeData {
  season_id: number
  title: string
  cover: string
  area: string
  rating: number | null
  styles: string[]
  release_date: string
  views: number
  favorites: number
  explainability?: {
    jaccard_similarity: number
    combo_bonus_score: number
    reasoning: string
  }
}

export interface AnimeListResponse {
  success: boolean
  total: number
  list: AnimeData[]
}

/** TMDB 扩展信息 */
export interface TmdbInfo {
  tmdb_id: number | null
  original_name: string | null
  overview: string | null
  tmdb_rating: number | null
  backdrop_url: string | null
  logo_url: string | null
  poster_url: string | null
  genres: string[]
  first_air_date: string | null
}

/** 番剧详情（含 TMDB 扩展信息） */
export interface AnimeDetailData extends AnimeData {
  tmdb_info: TmdbInfo | null
}

/** 番剧详情接口响应 */
export interface AnimeDetailResponse {
  success: boolean
  data: AnimeDetailData
}

export interface StatisticsOverview {
  total_animes: number
  total_views: number
  total_favorites: number
  area_distribution: Record<string, number>
  last_update: string | null
}

/**
 * 获取番剧列表
 */
export const getAnimes = async (limit?: number, offset?: number): Promise<AnimeListResponse> => {
  const params: any = {}
  if (limit) params.limit = limit
  if (offset) params.offset = offset
  return apiClient.get('/analytics/animes', { params })
}

/**
 * 获取番剧详情（含 TMDB 扩展信息）
 */
export const getAnimeDetail = async (seasonId: number): Promise<AnimeDetailResponse> => {
  return apiClient.get(`/analytics/animes/${seasonId}`)
}

/**
 * 搜索番剧
 */
export const searchAnimes = async (keyword: string): Promise<AnimeListResponse> => {
  return apiClient.get('/analytics/search', { params: { keyword } })
}

/**
 * 获取排行榜
 */
export const getRankings = async (
  sortBy: string = 'views',
  limit: number = 10,
  area?: string,
  styles?: string,
  season?: string
): Promise<AnimeListResponse> => {
  const params: any = { sort_by: sortBy, limit }
  if (area) params.area = area
  if (styles) params.styles = styles
  if (season) params.season = season
  return apiClient.get('/analytics/rankings', { params })
}

/**
 * 获取数据总览
 */
export const getOverview = async (): Promise<{ success: boolean; data: StatisticsOverview }> => {
  return apiClient.get('/analytics/overview')
}

/**
 * 获取番剧历史数据
 */
export const getAnimeHistory = async (seasonId: number, days: number = 30): Promise<any> => {
  return apiClient.get(`/analytics/animes/${seasonId}/history`, { params: { days } })
}

/**
 * 获取风格分布统计
 */
export const getStyleDistribution = async (area?: string): Promise<{ success: boolean; data: Record<string, number> }> => {
  const params: any = {}
  if (area) params.area = area
  return apiClient.get('/analytics/statistics/styles', { params })
}

/**
 * 获取发布趋势
 */
export const getReleaseTrend = async (area?: string): Promise<{ success: boolean; data: Record<string, number> }> => {
  const params: any = {}
  if (area) params.area = area
  return apiClient.get('/analytics/statistics/trends', { params })
}

/**
 * 获取番剧剧集数据
 */
export const getAnimeEpisodes = async (seasonId: number): Promise<{
  success: boolean
  total: number
  data: Array<{ title: string; views: number; peakTime: string | null; peakOnline: number | null }>
}> => {
  return apiClient.get(`/analytics/animes/${seasonId}/episodes`)
}

// ─── 深度分析相关接口定义 ──────────────────────────────────────────────────────

/** 单集互动指标 */
export interface EpisodeEngagementIndex {
  episode_title: string
  views: number
  coin_rate: number | null
  like_rate: number | null
  danmaku_rate: number | null
  reply_rate: number | null
}

/** 单集受众行为分析完整响应 */
export interface EpisodeBehaviorAnalysis {
  season_id: number
  total_episodes: number
  retention: {
    episode_1_views: number
    episode_3_views: number | null
    final_episode_views: number | null
    retention_ep1_to_ep3: number | null
    retention_ep1_to_final: number | null
  }
  engagement_by_episode: EpisodeEngagementIndex[]
  avg_coin_rate: number | null
  avg_like_rate: number | null
  avg_danmaku_rate: number | null
  avg_reply_rate: number | null
}

/** 生命周期与增长分析完整响应 */
export interface LifecycleGrowthData {
  season_id: number
  growth_data: Array<{
    date: string
    views: number
    favorites: number
    views_growth: number | null
    views_acceleration: number | null
    favorites_growth: number | null
    favorites_acceleration: number | null
  }>
  long_tail: {
    avg_daily_views_30d: number | null
    avg_daily_views_90d: number | null
  }
  peak_daily_growth: number | null
  peak_date: string | null
}

/** 竞争态势分析完整响应 */
export interface CompetitiveLandscapeData {
  season_id: number
  total_ranking_days: number
  top3_days: number
  top10_days: number
  dominance_top3: number | null
  dominance_top10: number | null
  avg_rank: number | null
  rank_volatility: number | null
}

/**
 * 获取单集受众行为分析（留存率、硬核指数、互动密度）。
 * HTTP 4xx/5xx 时 axios 会抛出异常；调用方应使用 try/catch 或 Promise.allSettled 处理。
 * 若番剧暂无分集数据，后端返回 404，此时 axios 会拒绝 Promise。
 */
export const getEpisodeBehaviorAnalysis = async (
  seasonId: number
): Promise<{ success: boolean; data: EpisodeBehaviorAnalysis }> => {
  return apiClient.get(`/analytics/animes/${seasonId}/episode-behavior`)
}

/**
 * 获取番剧生命周期与增长分析（黑马指数、长尾效应）。
 * HTTP 4xx/5xx 时 axios 会抛出异常；调用方应使用 try/catch 或 Promise.allSettled 处理。
 * 若番剧不存在，后端返回 404，此时 axios 会拒绝 Promise。
 */
export const getLifecycleAnalysis = async (
  seasonId: number
): Promise<{ success: boolean; data: LifecycleGrowthData }> => {
  return apiClient.get(`/analytics/animes/${seasonId}/lifecycle`)
}

/**
 * 获取番剧竞争态势分析（霸榜指数、排名波动率）。
 * HTTP 4xx/5xx 时 axios 会抛出异常；调用方应使用 try/catch 或 Promise.allSettled 处理。
 */
export const getCompetitiveAnalysis = async (
  seasonId: number
): Promise<{ success: boolean; data: CompetitiveLandscapeData }> => {
  return apiClient.get(`/analytics/animes/${seasonId}/competitive`)
}

/** 单集 24 小时观看时间分布 */
export interface EpisodeWatchTimeDistribution {
  episode_title: string
  /** 长度为 24 的整数数组，索引对应 0~23 时 */
  distribution: number[]
}

/** 观看时间分布接口响应 */
export interface WatchTimeDistributionData {
  season_id: number
  episodes_data: EpisodeWatchTimeDistribution[]
}

/**
 * 获取番剧各集的 24 小时观看时间分布（真实数据）。
 * 若番剧暂无分集在线人数数据，后端返回 404，axios 会拒绝 Promise。
 */
export const getWatchTimeDistribution = async (
  seasonId: number
): Promise<{ success: boolean; data: WatchTimeDistributionData }> => {
  return apiClient.get(`/analytics/animes/${seasonId}/watch-time`)
}

// ─── 图表专用接口 ─────────────────────────────────────────────────────────────

/** 口碑热度散点图单条数据 */
export interface ReputationPopularityItem {
  title: string
  rating: number
  ratingRaw: number
  favorites: number
  views: number
  area: string
}

/** 偏好差异矩形树图单条数据 */
export interface PreferenceDifferenceItem {
  style: string
  preferenceIndex: number
  regionCount: number
  globalCount: number
}

/** 口碑热度指数条形图单条数据 */
export interface ReputationHeatIndexItem {
  title: string
  qualityScore: number
  rating: number
  favorites: number
  views: number
  area: string
  cover: string
}

/** 热门风格组合矩形树图单条代表番剧 */
export interface ComboAnimeItem {
  title: string
  cover: string
  season_id: number
  score: number | null
  favorites: number
}

/** 热门风格组合矩形树图单条数据 */
export interface PopularStyleCombinationItem {
  combination: string
  totalFavorites: number
  animeCount: number
  avgFavorites: number
  representativeAnimes: ComboAnimeItem[]
}

/**
 * 获取番剧类型（风格）分布数据，用于首页饼图（含"其他"下钻功能）。
 * 返回按数量降序排列的 [name, value] 二元组数组。
 */
export const getTypeDistributionChart = async (): Promise<Array<[string, number]>> => {
  const response = await apiClient.get<any>('/analytics/statistics/styles')
  const data: Record<string, number> = response.data || {}
  return Object.entries(data).sort((a, b) => b[1] - a[1]) as Array<[string, number]>
}

/**
 * 获取口碑热度散点图数据。
 * @param areas - 地区列表，逗号分隔（如 "国内,日本"），为空则返回全部地区
 */
export const getReputationPopularityChart = async (
  areas: string = ''
): Promise<{ success: boolean; total: number; data: ReputationPopularityItem[] }> => {
  const params: Record<string, string> = {}
  if (areas) params.areas = areas
  return apiClient.get('/analytics/charts/reputation-popularity', { params })
}

/**
 * 获取地区偏好差异矩形树图数据。
 * @param region - 地区名称（如 "国内"、"日本"、"美国"），默认 "国内"
 */
export const getPreferenceDifferenceChart = async (
  region: string = '国内'
): Promise<{ success: boolean; total: number; data: PreferenceDifferenceItem[] }> => {
  return apiClient.get('/analytics/charts/preference-difference', { params: { region } })
}

/**
 * 获取历年番剧上新数量变化数据，用于折线图（多系列，X 轴为季度）。
 * 将 "/analytics/statistics/trends" 返回的 `{"YYYY-MM": count}` 转换为
 * `{"YYYY": [Q1, Q2, Q3, Q4]}` 格式。
 *
 * @param category - 地区分类（all / china / japan / us），默认 "all"
 */
export const getYearlyQuantityChart = async (
  category: string = 'all'
): Promise<Record<string, number[]>> => {
  const categoryToArea: Record<string, string | undefined> = {
    all: undefined,
    china: '国内',
    japan: '日本',
    us: '美国',
  }
  const area = categoryToArea[category]
  const response = await apiClient.get<any>(
    '/analytics/statistics/trends',
    area ? { params: { area } } : {}
  )
  const trends: Record<string, number> = response.data || {}

  // 月份 → 季度索引映射（与 B 站上新季度对应）
  const monthToIdx: Record<string, number> = { '01': 0, '04': 1, '07': 2, '10': 3 }
  const yearlyData: Record<string, number[]> = {}

  for (const [dateStr, count] of Object.entries(trends)) {
    const parts = dateStr.split('-')
    if (parts.length !== 2) continue
    const [year, month] = parts
    if (!yearlyData[year]) yearlyData[year] = [0, 0, 0, 0]
    const idx = monthToIdx[month]
    if (idx !== undefined) yearlyData[year][idx] = count
  }

  return yearlyData
}

/**
 * 获取综合口碑热度指数条形图数据（前 15 名）。
 * @param season   - 季节筛选（spring / summer / autumn / winter），为空则全部
 * @param category - 风格/类型筛选，为空则全部
 */
export const getReputationHeatIndexChart = async (
  season: string = '',
  category: string = ''
): Promise<{ success: boolean; total: number; data: ReputationHeatIndexItem[] }> => {
  const params: Record<string, string> = {}
  if (season && season !== 'all') params.season = season
  if (category && category !== 'all') params.category = category
  return apiClient.get('/analytics/charts/reputation-heat-index', { params })
}

/**
 * 获取热门风格组合矩形树图数据（前 20 组合，含代表番剧完整信息）。
 */
export const getPopularStyleCombinationChart = async (): Promise<{
  success: boolean
  total: number
  data: PopularStyleCombinationItem[]
}> => {
  return apiClient.get('/analytics/charts/popular-style-combination')
}

export interface PersonalizedRecommendationsResponse {
  success: boolean
  total: number
  data: {
    username: string
    preferences: string[]
    recommendations: AnimeData[]
  }
}

export const getPersonalizedRecommendations = async (
  username: string
): Promise<PersonalizedRecommendationsResponse> => {
  return apiClient.get(`/analytics/users/${username}/recommendations`)
}

export interface RecommendationExplanationResponse {
  success: boolean
  data: {
    username: string
    season_id: number
    title: string
    match_score: number
    explainability: {
      jaccard_similarity: number
      combo_bonus_score: number
      views_percentile: number
      matched_styles: string[]
      reasoning: string
      strategy_enabled: boolean
      strategy_weights: {
        views_weight: number
        ai_weight: number
        tmdb_weight: number
        diversity_weight: number
      }
      component_scores: {
        views_signal: number
        ai_signal: number
        tmdb_signal: number
        diversity_signal: number
      }
    }
    stats: {
      views: number
      favorites: number
    }
  }
}

export const getRecommendationExplanation = async (
  username: string,
  seasonId: number
): Promise<RecommendationExplanationResponse> => {
  return apiClient.get(`/analytics/users/${username}/recommendations/${seasonId}/explanation`)
}
