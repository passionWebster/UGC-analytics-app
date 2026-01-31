// api/ai.ts
/**
 * AI 助手相关 API
 */
import apiClient from './axios'

export interface ChatMessage {
  message: string
}

export interface ChatResponse {
  success: boolean
  reply: string
}

export interface AIServiceStatus {
  status: string
  timestamp: string
  version: string
}

/**
 * 获取 AI 服务状态
 */
export const checkAIServiceStatus = async (): Promise<AIServiceStatus> => {
  return apiClient.get('/aiservicestatus')
}

/**
 * 发送聊天消息
 */
export const chatWithAI = async (message: string): Promise<ChatResponse> => {
  return apiClient.post('/chat', { message })
}
