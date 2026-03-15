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
}

export interface AnimeListResponse {
  success: boolean
  total: number
  list: AnimeData[]
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
 * 获取番剧详情
 */
export const getAnimeDetail = async (seasonId: number): Promise<any> => {
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
