import type { AnimeData } from '@/api/analytics'

/**
 * 获取代理图片 URL，通过后端 /api/image_proxy 接口绕过防盗链限制并缓存图片。
 * 若番剧封面地址为空，则返回空字符串。
 *
 * @param anime - 番剧数据对象
 * @returns 代理后的图片 URL，或空字符串
 */
export const getProxiedImageUrl = (anime: AnimeData): string => {
  if (!anime.cover) return ''
  return `/api/image_proxy?url=${encodeURIComponent(anime.cover)}&title=${encodeURIComponent(anime.title)}&season_id=${anime.season_id}`
}
