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
