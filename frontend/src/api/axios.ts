// api/axios.ts
/**
 * Axios 配置和拦截器
 * 统一管理 HTTP 请求，包含：
 * - 自动注入 JWT Token
 * - 全局错误处理（500 弹出错误消息，401 自动跳转登录页）
 */
import axios, { type AxiosInstance, type AxiosResponse, type AxiosError } from 'axios'
import { ElMessage } from 'element-plus'

// 创建 Axios 实例
const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器：自动注入 JWT Token
apiClient.interceptors.request.use(
  (config) => {
    // 从 localStorage 获取 token 并注入到 Authorization 请求头
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器：统一处理响应与错误
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    return response.data
  },
  (error: AxiosError) => {
    // 处理有服务器响应的错误
    if (error.response) {
      const status = error.response.status
      if (status === 401) {
        // 未授权：清除本地凭证并跳转到登录页
        localStorage.removeItem('access_token')
        localStorage.removeItem('username')
        ElMessage.warning('登录已过期，请重新登录')
        window.location.href = '/login'
      } else if (status === 403) {
        ElMessage.error('权限不足，无法执行此操作')
      } else if (status === 404) {
        ElMessage.warning('请求的资源不存在')
      } else if (status >= 500) {
        // 服务器端错误：弹出全局错误消息提示
        ElMessage.error('服务器错误，请稍后重试')
      }
    } else if (error.request) {
      // 请求已发出但无响应（网络断开或超时）
      ElMessage.error('网络错误，请检查网络连接')
    }
    return Promise.reject(error)
  }
)

export default apiClient
