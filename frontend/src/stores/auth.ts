// stores/auth.ts
/**
 * 用户认证状态管理
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as authAPI from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  // 状态
  const username = ref<string>('')
  const email = ref<string>('')
  const isLoggedIn = ref<boolean>(false)
  const isAdmin = ref<boolean>(false)
  const isActive = ref<boolean>(true)
  const preferences = ref<string[]>([])
  const accessToken = ref<string>('')

  // 计算属性
  const hasPreferences = computed(() => preferences.value.length > 0)
  const user = computed(() => ({
    username: username.value,
    email: email.value,
    isAdmin: isAdmin.value,
    isActive: isActive.value
  }))

  // 初始化：从 localStorage 恢复状态
  const initAuth = () => {
    const savedToken = localStorage.getItem('access_token')
    const savedUsername = localStorage.getItem('username')
    const savedIsAdmin = localStorage.getItem('is_admin')
    
    if (savedToken && savedUsername) {
      accessToken.value = savedToken
      username.value = savedUsername
      isLoggedIn.value = true
      isAdmin.value = savedIsAdmin === 'true'
      
      // 异步加载用户信息
      loadUserInfo(savedUsername)
    }
  }

  // 加载用户信息
  const loadUserInfo = async (usernameParam: string) => {
    try {
      const response = await authAPI.getUserInfo(usernameParam)
      if (response.success && response.user) {
        email.value = response.user.email
        preferences.value = response.user.preferences || []
        isAdmin.value = response.user.is_admin
        isActive.value = response.user.is_active
      }
    } catch (error) {
      console.error('加载用户信息失败:', error)
    }
  }

  // 登录
  const login = async (usernameParam: string, password: string) => {
    try {
      const response = await authAPI.login({ username: usernameParam, password })
      
      if (response.success) {
        // 保存状态
        username.value = response.user.username
        email.value = response.user.email
        isAdmin.value = response.user.is_admin
        isActive.value = response.user.is_active
        accessToken.value = response.access_token
        isLoggedIn.value = true
        
        // 解析偏好设置
        if (response.preferences) {
          try {
            preferences.value = JSON.parse(response.preferences)
          } catch {
            preferences.value = []
          }
        }
        
        // 保存到 localStorage
        localStorage.setItem('access_token', response.access_token)
        localStorage.setItem('username', response.user.username)
        localStorage.setItem('is_admin', String(response.user.is_admin))
        
        return {
          success: true,
          hasPreferences: response.hasPreferences,
          isAdmin: response.user.is_admin
        }
      }
      
      return { success: false, message: response.message }
    } catch (error: any) {
      console.error('登录失败:', error)
      return { 
        success: false, 
        message: error.response?.data?.detail || '登录失败，请稍后重试'
      }
    }
  }

  // 注册
  const register = async (usernameParam: string, emailParam: string, password: string) => {
    try {
      const response = await authAPI.register({ 
        username: usernameParam, 
        email: emailParam, 
        password 
      })
      
      return { success: true }
    } catch (error: any) {
      console.error('注册失败:', error)
      return { 
        success: false, 
        message: error.response?.data?.detail || '注册失败，请稍后重试'
      }
    }
  }

  // 更新偏好设置
  const updatePreferences = async (newPreferences: string[]) => {
    try {
      await authAPI.updatePreferences(username.value, newPreferences)
      preferences.value = newPreferences
      return { success: true }
    } catch (error) {
      console.error('更新偏好设置失败:', error)
      return { success: false }
    }
  }

  // 登出
  const logout = () => {
    username.value = ''
    email.value = ''
    accessToken.value = ''
    isLoggedIn.value = false
    isAdmin.value = false
    isActive.value = true
    preferences.value = []
    
    localStorage.removeItem('access_token')
    localStorage.removeItem('username')
    localStorage.removeItem('is_admin')
  }

  return {
    // 状态
    username,
    email,
    isLoggedIn,
    isAdmin,
    isActive,
    preferences,
    accessToken,
    
    // 计算属性
    hasPreferences,
    user,
    
    // 方法
    initAuth,
    loadUserInfo,
    login,
    register,
    updatePreferences,
    logout
  }
})
