// api/axios.ts
/**
 * Axios 配置和拦截器
 * 统一管理 HTTP 请求
 */
import axios, { type AxiosInstance, type AxiosResponse, type AxiosError } from 'axios'

// 创建 Axios 实例
const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    // 从 localStorage 获取 token
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

// 响应拦截器
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    return response.data
  },
  (error: AxiosError) => {
    // 处理错误响应
    if (error.response) {
      const status = error.response.status
      if (status === 401) {
        // 未授权，清除 token 并跳转到登录页
        localStorage.removeItem('access_token')
        localStorage.removeItem('username')
        window.location.href = '/login'
      } else if (status === 403) {
        console.error('权限不足')
      } else if (status === 404) {
        console.error('资源不存在')
      } else if (status === 500) {
        console.error('服务器错误')
      }
    } else if (error.request) {
      console.error('网络错误，请检查网络连接')
    }
    return Promise.reject(error)
  }
)

export default apiClient
