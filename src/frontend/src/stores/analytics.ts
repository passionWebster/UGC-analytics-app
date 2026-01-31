// stores/analytics.ts
/**
 * 数据分析状态管理
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as analyticsAPI from '@/api/analytics'
import type { AnimeData, StatisticsOverview } from '@/api/analytics'

export const useAnalyticsStore = defineStore('analytics', () => {
  // 状态
  const animeList = ref<AnimeData[]>([])
  const currentAnime = ref<AnimeData | null>(null)
  const overview = ref<StatisticsOverview | null>(null)
  const loading = ref<boolean>(false)

  // 获取番剧列表
  const fetchAnimes = async (limit?: number, offset?: number) => {
    loading.value = true
    try {
      const response = await analyticsAPI.getAnimes(limit, offset)
      if (response.success) {
        animeList.value = response.list
      }
    } catch (error) {
      console.error('获取番剧列表失败:', error)
    } finally {
      loading.value = false
    }
  }

  // 获取番剧详情
  const fetchAnimeDetail = async (seasonId: number) => {
    loading.value = true
    try {
      const response = await analyticsAPI.getAnimeDetail(seasonId)
      if (response.success) {
        currentAnime.value = response.data
      }
    } catch (error) {
      console.error('获取番剧详情失败:', error)
    } finally {
      loading.value = false
    }
  }

  // 搜索番剧
  const searchAnimes = async (keyword: string) => {
    loading.value = true
    try {
      const response = await analyticsAPI.searchAnimes(keyword)
      if (response.success) {
        return response.list
      }
      return []
    } catch (error) {
      console.error('搜索番剧失败:', error)
      return []
    } finally {
      loading.value = false
    }
  }

  // 获取排行榜
  const fetchRankings = async (
    sortBy: string = 'views',
    limit: number = 10,
    area?: string,
    styles?: string
  ) => {
    loading.value = true
    try {
      const response = await analyticsAPI.getRankings(sortBy, limit, area, styles)
      if (response.success) {
        return response.list
      }
      return []
    } catch (error) {
      console.error('获取排行榜失败:', error)
      return []
    } finally {
      loading.value = false
    }
  }

  // 获取数据总览
  const fetchOverview = async () => {
    loading.value = true
    try {
      const response = await analyticsAPI.getOverview()
      if (response.success) {
        overview.value = response.data
      }
    } catch (error) {
      console.error('获取数据总览失败:', error)
    } finally {
      loading.value = false
    }
  }

  // 获取番剧历史数据
  const fetchAnimeHistory = async (seasonId: number, days: number = 30) => {
    try {
      const response = await analyticsAPI.getAnimeHistory(seasonId, days)
      if (response.success) {
        return response.data
      }
      return []
    } catch (error) {
      console.error('获取番剧历史数据失败:', error)
      return []
    }
  }

  // 获取风格分布
  const fetchStyleDistribution = async () => {
    try {
      const response = await analyticsAPI.getStyleDistribution()
      if (response.success) {
        return response.data
      }
      return {}
    } catch (error) {
      console.error('获取风格分布失败:', error)
      return {}
    }
  }

  // 获取发布趋势
  const fetchReleaseTrend = async () => {
    try {
      const response = await analyticsAPI.getReleaseTrend()
      if (response.success) {
        return response.data
      }
      return {}
    } catch (error) {
      console.error('获取发布趋势失败:', error)
      return {}
    }
  }

  return {
    // 状态
    animeList,
    currentAnime,
    overview,
    loading,

    // 方法
    fetchAnimes,
    fetchAnimeDetail,
    searchAnimes,
    fetchRankings,
    fetchOverview,
    fetchAnimeHistory,
    fetchStyleDistribution,
    fetchReleaseTrend
  }
})
