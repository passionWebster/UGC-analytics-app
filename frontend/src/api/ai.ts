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
  configured: boolean
  model: string
}

export interface InsightRequest {
  data: unknown
  context_hint?: string
}

export interface InsightResponse {
  success: boolean
  insight: string
}

export interface TextToSQLRequest {
  query: string
  schema_hint?: string
}

export interface TextToSQLResponse {
  success: boolean
  sql: string
  columns: string[]
  rows: Record<string, unknown>[]
}

export interface SentimentPoint {
  episode_number: number
  avg_sentiment: number | null
  danmu_count: number
}

export interface SentimentTimelineResponse {
  success: boolean
  timeline: SentimentPoint[]
}

export interface CommentItem {
  id: number
  content: string
  likes: number
  replies: number
  sentiment_score: number | null
}

export interface TopCommentsResponse {
  success: boolean
  comments: CommentItem[]
}

const AI_REQUEST_TIMEOUT = 60000
const AI_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

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
  return apiClient.post('/chat', { message }, { timeout: AI_REQUEST_TIMEOUT })
}

interface StreamEvent {
  type?: string
  content?: string
  error?: string
}

export const chatWithAIStream = async (
  message: string,
  handlers: {
    onChunk: (chunk: string) => void
    onError?: (error: string) => void
    onDone?: () => void
  },
): Promise<void> => {
  const token = localStorage.getItem('access_token')
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), AI_REQUEST_TIMEOUT)

  try {
    const response = await fetch(`${AI_BASE_URL}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ message }),
      signal: controller.signal,
    })

    if (!response.ok) {
      let errMsg = `流式请求失败（HTTP ${response.status}）`
      try {
        const err = (await response.json()) as { detail?: string; msg?: string }
        errMsg = err.detail || err.msg || errMsg
      } catch {
        // ignore parse error
      }
      throw new Error(errMsg)
    }

    if (!response.body) {
      throw new Error('浏览器不支持流式响应')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const events = buffer.split('\n\n')
      buffer = events.pop() || ''

      for (const event of events) {
        const dataLine = event
          .split('\n')
          .find((line) => line.startsWith('data:'))
          ?.slice(5)
          .trim()
        if (!dataLine) continue

        let payload: StreamEvent | null = null
        try {
          payload = JSON.parse(dataLine) as StreamEvent
        } catch {
          handlers.onChunk(dataLine)
          continue
        }

        if (payload.type === 'delta' && typeof payload.content === 'string') {
          handlers.onChunk(payload.content)
        } else if (payload.type === 'error') {
          const errorMsg = payload.error || 'AI 流式请求失败'
          handlers.onError?.(errorMsg)
          throw new Error(errorMsg)
        } else if (payload.type === 'done') {
          handlers.onDone?.()
          return
        }
      }
    }

    handlers.onDone?.()
  } finally {
    window.clearTimeout(timeoutId)
  }
}

/**
 * Auto-EDA：生成数据洞察报告
 */
export const generateInsight = async (req: InsightRequest): Promise<InsightResponse> => {
  return apiClient.post('/ai/generate-insight', req, { timeout: AI_REQUEST_TIMEOUT })
}

/**
 * Text-to-SQL：自然语言转 SQL 并执行
 */
export const textToSQL = async (req: TextToSQLRequest): Promise<TextToSQLResponse> => {
  return apiClient.post('/ai/text-to-sql', req, { timeout: AI_REQUEST_TIMEOUT })
}

/**
 * 获取番剧弹幕情感时间线（按集数聚合）
 */
export const getSentimentTimeline = async (
  seasonId: number,
): Promise<SentimentTimelineResponse> => {
  return apiClient.get(`/ai/sentiment-timeline/${seasonId}`)
}

/**
 * 获取番剧高赞评论列表
 */
export const getTopComments = async (
  seasonId: number,
  limit = 50,
): Promise<TopCommentsResponse> => {
  return apiClient.get(`/ai/top-comments/${seasonId}`, { params: { limit } })
}
