// api/auth.ts
/**
 * 用户认证相关 API
 */
import apiClient from './axios'

export interface UserLoginData {
  username: string
  password: string
}

export interface UserRegisterData {
  username: string
  email: string
  password: string
}

export interface LoginResponse {
  success: boolean
  message: string
  access_token: string
  token_type: string
  hasPreferences: boolean
  preferences: string | null
  user: {
    id: number
    username: string
    email: string
    is_admin: boolean
    is_active: boolean
    preferences: string | null
    created_at: string
  }
}

export interface UserInfoResponse {
  success: boolean
  user: {
    id: number
    username: string
    email: string
    is_admin: boolean
    is_active: boolean
    preferences: string[]
    created_at: string
  }
}

/**
 * 用户登录
 */
export const login = async (data: UserLoginData): Promise<LoginResponse> => {
  return apiClient.post('/login', data)
}

/**
 * 用户注册
 */
export const register = async (data: UserRegisterData): Promise<any> => {
  return apiClient.post('/register', data)
}

/**
 * 获取用户信息
 */
export const getUserInfo = async (username: string): Promise<UserInfoResponse> => {
  return apiClient.get('/user-info', { params: { username } })
}

/**
 * 更新用户偏好设置
 */
export const updatePreferences = async (username: string, preferences: string[]): Promise<any> => {
  return apiClient.post('/updatePreferences', { username, preferences })
}
