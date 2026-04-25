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

/**
 * 获取任意 URL 的代理图片地址（用于 TMDB 图片等非番剧封面的场景）。
 * 若 url 为空，则返回空字符串。
 *
 * @param url - 原始图片链接（支持某头部弹幕视频网站 CDN 和 image.tmdb.org）
 * @param title - 番剧名（用于生成缓存文件名）
 * @param seasonId - 番剧 season_id（用于生成缓存文件名）
 * @returns 代理后的图片 URL，或空字符串
 */
export const getProxiedUrl = (url: string, title: string, seasonId: number): string => {
  if (!url) return ''
  return `/api/image_proxy?url=${encodeURIComponent(url)}&title=${encodeURIComponent(title)}&season_id=${seasonId}`
}
