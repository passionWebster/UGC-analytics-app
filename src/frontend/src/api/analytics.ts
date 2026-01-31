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
  styles?: string
): Promise<AnimeListResponse> => {
  const params: any = { sort_by: sortBy, limit }
  if (area) params.area = area
  if (styles) params.styles = styles
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
export const getStyleDistribution = async (): Promise<{ success: boolean; data: Record<string, number> }> => {
  return apiClient.get('/analytics/statistics/styles')
}

/**
 * 获取发布趋势
 */
export const getReleaseTrend = async (): Promise<{ success: boolean; data: Record<string, number> }> => {
  return apiClient.get('/analytics/statistics/trends')
}
