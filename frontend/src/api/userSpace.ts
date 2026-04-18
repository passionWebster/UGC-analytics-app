import apiClient from './axios'

export type FavoriteStatus = 'watching' | 'plan' | 'completed'

export interface UserFavoriteItem {
  id: number
  season_id: number
  title: string
  cover: string | null
  status: FavoriteStatus
  rating: number | null
  created_at: string
}

export interface UserFavoritesResponse {
  success: boolean
  total: number
  data: UserFavoriteItem[]
}

export interface UserSpaceAnalyticsResponse {
  success: boolean
  data: {
    watchlist_count: number
    status_distribution: Record<FavoriteStatus, number>
    genre_distribution: Array<{ genre: string; count: number }>
    weekly_views_summary: {
      latest_views_total: number
      week_ago_views_total: number
      weekly_growth: number
      weekly_growth_rate: number | null
    }
  }
}

export const getUserFavorites = async (status?: FavoriteStatus): Promise<UserFavoritesResponse> => {
  const params = status ? { status } : undefined
  return apiClient.get('/user/favorites', { params })
}

export const toggleFavorite = async (
  seasonId: number,
  status: FavoriteStatus = 'watching',
): Promise<{ success: boolean; action: 'added' | 'removed'; message: string }> => {
  return apiClient.post('/user/favorites', { season_id: seasonId, status })
}

export const updateFavoriteStatus = async (
  seasonId: number,
  status: FavoriteStatus,
): Promise<{ success: boolean; message: string }> => {
  return apiClient.put(`/user/favorites/${seasonId}/status`, { status })
}

export const updatePassword = async (
  oldPassword: string,
  newPassword: string,
): Promise<{ success: boolean; message: string }> => {
  return apiClient.put('/user/password', { old_password: oldPassword, new_password: newPassword })
}

export const getUserSpaceAnalytics = async (): Promise<UserSpaceAnalyticsResponse> => {
  return apiClient.get('/user/analytics')
}
