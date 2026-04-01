// api/admin.ts
/**
 * 后台管理接口
 */
import apiClient from './axios'

export interface AdminUser {
  id: number
  username: string
  email: string
  is_admin: boolean
  is_active: boolean
  created_at: string
}

export const fetchUsers = async (): Promise<{ success: boolean; users: AdminUser[] }> => {
  return apiClient.get('/admin/users')
}

export const updateUserStatus = async (
  userId: number,
  isActive: boolean
): Promise<{ success: boolean; is_active: boolean }> => {
  return apiClient.patch(`/admin/users/${userId}/status`, { is_active: isActive })
}

export const resetUserPassword = async (
  userId: number,
  newPassword: string
): Promise<{ success: boolean }> => {
  return apiClient.post(`/admin/users/${userId}/reset-password`, { new_password: newPassword })
}

export const fetchOverview = async (): Promise<any> => {
  return apiClient.get('/admin/overview')
}

export const fetchCrawlerLogs = async (limit = 20): Promise<any> => {
  return apiClient.get('/admin/crawler/logs', { params: { limit } })
}

export const triggerCrawlerUpdate = async (): Promise<any> => {
  return apiClient.post('/admin/crawler/trigger')
}

export const fetchAiStats = async (): Promise<any> => {
  return apiClient.get('/admin/ai/stats')
}

export interface RecommendationStrategyConfig {
  id?: number
  views_weight: number
  ai_weight: number
  tmdb_weight: number
  diversity_weight: number
  enabled: boolean
  updated_at?: string
}

export const fetchRecommendationStrategy = async (): Promise<{
  success: boolean
  data: RecommendationStrategyConfig
}> => {
  return apiClient.get('/admin/recommendation-strategy')
}

export const updateRecommendationStrategy = async (
  payload: RecommendationStrategyConfig
): Promise<{ success: boolean; message: string; data: RecommendationStrategyConfig }> => {
  return apiClient.put('/admin/recommendation-strategy', payload)
}
