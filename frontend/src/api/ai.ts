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
