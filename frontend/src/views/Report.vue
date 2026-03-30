<template>
  <div class="report-view">
    <!-- 页面标题 -->
    <div class="report-hero mb-4">
      <h2><i class="fas fa-file-chart-line me-2"></i>番剧数据分析报告生成器</h2>
      <p class="text-muted">选择一部番剧，由 AI 自动生成多维度 EDA 分析报告</p>
    </div>

    <!-- 搜索与控制区 -->
    <div class="row mb-4">
      <div class="col-md-8 mx-auto">
        <div class="report-search-group">
          <div class="report-search-wrap">
            <span class="report-search-icon"><i class="fas fa-search"></i></span>
            <input
              ref="searchInputRef"
              v-model="keyword"
              class="report-search-input"
              placeholder="输入番剧名称搜索..."
              type="text"
              autocomplete="off"
              @keyup.enter="handleSearch"
            />
          </div>
          <button class="report-search-btn" @click="handleSearch" :disabled="searching">
            <i class="fas fa-search me-1"></i>{{ searching ? '搜索中…' : '搜索' }}
          </button>
          <button
            v-if="animeData && !generating"
            class="report-gen-btn"
            @click="generateReport"
          >
            <i class="fas fa-magic me-1"></i>生成报告
          </button>
          <button
            v-if="reportReady"
            class="report-export-btn"
            @click="exportPDF"
          >
            <i class="fas fa-file-pdf me-1"></i>导出 PDF
          </button>
        </div>
        <div v-if="statusMsg" class="report-status-msg mt-2">{{ statusMsg }}</div>
      </div>
    </div>

    <!-- 报告内容区（id="report-content" 用于 PDF 导出） -->
    <div v-if="animeData" id="report-content" class="report-content">
      <!-- 报告封面信息 -->
      <div class="report-cover mb-4">
        <div class="row align-items-center">
          <div class="col-auto">
            <img
              v-if="animeData.cover"
              :src="`/api/image_proxy?url=${encodeURIComponent(String(animeData.cover))}&title=${encodeURIComponent(String(animeData.title))}&season_id=${animeData.season_id}`"
              class="report-cover-img"
              :alt="animeData.title"
            />
          </div>
          <div class="col">
            <h3 class="report-title">{{ animeData.title }}</h3>
            <p class="report-meta">
              <span class="meta-badge">{{ animeData.area }}</span>
              <span v-if="animeData.release_date" class="meta-badge">{{ animeData.release_date }}</span>
              <span v-if="animeData.rating" class="meta-badge rating">⭐ {{ animeData.rating }}</span>
            </p>
            <p class="report-generated-at text-muted" v-if="generatedAt">
              <i class="fas fa-clock me-1"></i>报告生成时间：{{ generatedAt }}
            </p>
          </div>
        </div>
      </div>

      <!-- 数据概览 KPI 卡片 -->
      <div class="row mb-4">
        <div v-for="kpi in kpiCards" :key="kpi.label" class="col-md-3 mb-3">
          <div class="kpi-card" :class="kpi.color">
            <div class="kpi-icon"><i :class="kpi.icon"></i></div>
            <div class="kpi-content">
              <h5>{{ kpi.label }}</h5>
              <p class="kpi-value">{{ kpi.value }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- 左图右文 布局：弹幕情感时间线 + AI 洞察 -->
      <div class="row mb-4">
        <!-- 图表区 -->
        <div class="col-md-7">
          <div class="style-unified">
            <div class="card-header-unified">
              <h5><i class="fas fa-chart-line me-1"></i>弹幕情感时间线</h5>
              <small class="text-muted">各集弹幕情感均分（0=消极 / 1=积极）</small>
            </div>
            <div v-if="sentimentTimeline.length > 0" ref="sentimentChartRef" style="height: 320px; width: 100%"></div>
            <div v-else class="chart-placeholder">
              <i class="fas fa-comment-dots"></i>
              <span>暂无弹幕情感数据</span>
            </div>
          </div>
        </div>

        <!-- AI 洞察文字区 -->
        <div class="col-md-5">
          <div class="style-unified insight-panel">
            <div class="card-header-unified">
              <h5><i class="fas fa-robot me-1"></i>AI 数据洞察</h5>
            </div>
            <div v-if="generating" class="insight-loading">
              <i class="fas fa-spinner fa-spin me-2"></i>豆包正在分析数据，请稍候…
            </div>
            <div v-else-if="insightText" class="insight-text" v-html="formattedInsight"></div>
            <div v-else class="insight-placeholder">
              <i class="fas fa-lightbulb me-2"></i>点击「生成报告」即可获得 AI 洞察报告
            </div>
          </div>
        </div>
      </div>

      <!-- 播放趋势图 -->
      <div class="row mb-4">
        <div class="col-md-12">
          <div class="style-unified">
            <div class="card-header-unified">
              <h5><i class="fas fa-play-circle me-1"></i>剧集播放趋势</h5>
            </div>
            <div v-if="episodeViews.length > 0" ref="viewsTrendChartRef" style="height: 280px; width: 100%"></div>
            <div v-else class="chart-placeholder">
              <i class="fas fa-chart-bar"></i>
              <span>暂无剧集数据</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 高赞评论展示 -->
      <div v-if="topComments.length > 0" class="row mb-4">
        <div class="col-md-12">
          <div class="style-unified">
            <div class="card-header-unified">
              <h5><i class="fas fa-thumbs-up me-1"></i>高赞观众评论（Top 10）</h5>
              <small class="text-muted">颜色越暖表示情感越积极</small>
            </div>
            <div class="comments-grid">
              <div
                v-for="c in topComments.slice(0, 10)"
                :key="c.id"
                class="comment-card"
                :style="{ borderLeftColor: sentimentColor(c.sentiment_score) }"
              >
                <p class="comment-content">{{ c.content }}</p>
                <div class="comment-meta">
                  <span><i class="fas fa-thumbs-up me-1"></i>{{ c.likes }}</span>
                  <span v-if="c.sentiment_score !== null" class="comment-score">
                    情感 {{ (c.sentiment_score * 100).toFixed(0) }}%
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">
      <i class="fas fa-chart-area"></i>
      <h4>请先搜索一部番剧</h4>
      <p>输入番剧名称并点击搜索，然后点击「生成报告」即可获得完整分析报告</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import type { ECharts } from 'echarts'
import { searchAnimes, getAnimeDetail, getAnimeEpisodes } from '@/api/analytics'
import type { AnimeDetailData } from '@/api/analytics'
import {
  generateInsight,
  getSentimentTimeline,
  getTopComments,
} from '@/api/ai'
import type { SentimentPoint, CommentItem } from '@/api/ai'
import { getApiErrorMessage } from '@/utils/errorHandling'

defineOptions({ name: 'ReportView' })

// ─── 状态 ────────────────────────────────────────────────────────────────────
const keyword = ref('')
const statusMsg = ref('')
const searching = ref(false)
const generating = ref(false)
const reportReady = ref(false)
const generatedAt = ref('')
const insightText = ref('')

const animeData = ref<AnimeDetailData | null>(null)
const episodes = ref<Array<{ title: string; views: number }>>([])
const sentimentTimeline = ref<SentimentPoint[]>([])
const topComments = ref<CommentItem[]>([])

// ─── 图表 DOM 引用 ────────────────────────────────────────────────────────────
const sentimentChartRef = ref<HTMLElement>()
const viewsTrendChartRef = ref<HTMLElement>()
let sentimentInstance: ECharts | null = null
let viewsInstance: ECharts | null = null
let sentimentObserver: ResizeObserver | null = null
let viewsObserver: ResizeObserver | null = null
const searchInputRef = ref<HTMLInputElement | null>(null)

// ─── 计算属性 ─────────────────────────────────────────────────────────────────
const episodeViews = computed(() =>
  episodes.value.map((e) => e.views || 0),
)

const kpiCards = computed(() => {
  if (!animeData.value) return []
  const fmt = (n: number | null | undefined) => {
    const num = n ?? 0
    if (!num) return '暂无'
    if (num >= 1e8) return (num / 1e8).toFixed(1) + '亿'
    if (num >= 1e4) return (num / 1e4).toFixed(1) + '万'
    return String(num)
  }
  const d = animeData.value as AnimeDetailData & {
    total_danmakus?: number
    total_danmaku?: number
  }
  return [
    { label: '总播放量', value: fmt(d.views), icon: 'fas fa-play', color: 'blue' },
    { label: '追番人数', value: fmt(d.favorites), icon: 'fas fa-heart', color: 'pink' },
    { label: '总弹幕数', value: fmt(d.total_danmakus ?? d.total_danmaku), icon: 'fas fa-comments', color: 'yellow' },
    { label: '评分', value: d.rating ? String(d.rating) : '暂无', icon: 'fas fa-star', color: 'purple' },
  ]
})

const formattedInsight = computed(() => {
  if (!insightText.value) return ''
  return renderMarkdown(insightText.value)
})

const escapeHtml = (text: string): string =>
  text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')

const sanitizeUrl = (url: string): string | null => {
  try {
    const parsed = new URL(url)
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
      return parsed.toString()
    }
  } catch {
    // 忽略非法 URL，按普通文本渲染
  }
  return null
}

const renderInlineMarkdown = (text: string): string => {
  const tokens: string[] = []
  const addToken = (html: string) => {
    const token = `\u0000${tokens.length}\u0000`
    tokens.push(html)
    return token
  }

  let working = text

  working = working.replace(/`([^`]+?)`/g, (_, code: string) =>
    addToken(`<code>${escapeHtml(code)}</code>`),
  )

  working = working.replace(
    /\[([^\]]+?)\]\((https?:\/\/[^\s)]+)\)/g,
    (full: string, label: string, rawUrl: string) => {
      const safeUrl = sanitizeUrl(rawUrl)
      if (!safeUrl) return full
      return addToken(
        `<a href="${escapeHtml(safeUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`,
      )
    },
  )

  working = escapeHtml(working)
    .replace(/\*\*([^*\n]+?)\*\*/g, '<strong>$1</strong>')
    .replace(/__([^_\n]+?)__/g, '<strong>$1</strong>')
    .replace(/(^|[^\*])\*([^*\n]+?)\*(?!\*)/g, '$1<em>$2</em>')
    .replace(/(^|[^_])_([^_\n]+?)_(?!_)/g, '$1<em>$2</em>')

  return working.replace(/\u0000(\d+)\u0000/g, (_, index: string) => tokens[Number(index)] || '')
}

const renderMarkdown = (text: string): string => {
  const lines = text.replace(/\r\n?/g, '\n').split('\n')
  const html: string[] = []
  let inUl = false
  let inOl = false

  const closeLists = () => {
    if (inUl) {
      html.push('</ul>')
      inUl = false
    }
    if (inOl) {
      html.push('</ol>')
      inOl = false
    }
  }

  for (const line of lines) {
    if (!line.trim()) {
      closeLists()
      continue
    }

    const headingMatch = line.match(/^(#{1,6})\s*(.+)$/)
    if (headingMatch) {
      closeLists()
      const level = headingMatch[1].length
      html.push(`<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`)
      continue
    }

    const ulMatch = line.match(/^\s*[-*+]\s+(.+)$/)
    if (ulMatch) {
      if (inOl) {
        html.push('</ol>')
        inOl = false
      }
      if (!inUl) {
        html.push('<ul>')
        inUl = true
      }
      html.push(`<li>${renderInlineMarkdown(ulMatch[1])}</li>`)
      continue
    }

    const olMatch = line.match(/^\s*\d+\.\s+(.+)$/)
    if (olMatch) {
      if (inUl) {
        html.push('</ul>')
        inUl = false
      }
      if (!inOl) {
        html.push('<ol>')
        inOl = true
      }
      html.push(`<li>${renderInlineMarkdown(olMatch[1])}</li>`)
      continue
    }

    closeLists()
    html.push(`<p>${renderInlineMarkdown(line)}</p>`)
  }

  closeLists()
  return html.join('')
}

// ─── 方法 ─────────────────────────────────────────────────────────────────────
const handleSearch = async () => {
  if (!keyword.value.trim()) {
    statusMsg.value = '请输入番剧名称'
    return
  }
  searching.value = true
  statusMsg.value = '搜索中…'
  reportReady.value = false
  insightText.value = ''
  try {
    const res = await searchAnimes(keyword.value)
    if (res.list && res.list.length > 0) {
      const anime = res.list[0]
      const detail = await getAnimeDetail(anime.season_id)
      animeData.value = detail.data || anime as unknown as AnimeDetailData
      statusMsg.value = `找到番剧：${anime.title}`

      // 获取剧集
      try {
        const epRes = await getAnimeEpisodes(anime.season_id)
        episodes.value = epRes.data || []
      } catch {
        episodes.value = []
      }

      // 尝试加载弹幕情感 & 评论
      const [stRes, cmRes] = await Promise.allSettled([
        getSentimentTimeline(anime.season_id),
        getTopComments(anime.season_id),
      ])
      sentimentTimeline.value =
        stRes.status === 'fulfilled' ? stRes.value.timeline || [] : []
      topComments.value =
        cmRes.status === 'fulfilled' ? cmRes.value.comments || [] : []

      await nextTick()
      renderCharts()
    } else {
      statusMsg.value = '未找到相关番剧'
      animeData.value = null
    }
  } catch {
    statusMsg.value = '搜索失败，请重试'
  } finally {
    searching.value = false
  }
}

const generateReport = async () => {
  if (!animeData.value) return
  generating.value = true
  insightText.value = ''
  const d = animeData.value as AnimeDetailData & { total_danmakus?: number }
  try {
    const contextData = {
      title: d.title,
      rating: d.rating,
      views: d.views,
      favorites: d.favorites,
      total_danmakus: d.total_danmakus,
      sentiment_timeline: sentimentTimeline.value.slice(0, 12),
      episode_count: episodes.value.length,
    }
    const res = await generateInsight({
      data: contextData,
      context_hint: d.title,
    })
    if (!res?.success) {
      throw new Error('后端未返回成功状态')
    }
    insightText.value = res.insight || ''
    generatedAt.value = new Date().toLocaleString('zh-CN')
    reportReady.value = true
  } catch (error: unknown) {
    insightText.value = `洞察生成失败：${getApiErrorMessage(error, '请检查 AI 服务配置后重试。')}`
    reportReady.value = true
  } finally {
    generating.value = false
  }
}

const exportPDF = async () => {
  // 动态导入，避免影响首屏加载
  const html2pdf = (await import('html2pdf.js')).default
  const element = document.getElementById('report-content')
  if (!element) return
  // 过滤掉文件系统不安全字符，防止非法文件名
  const safeTitle = String(animeData.value?.title ?? 'report').replace(/[/\\:*?"<>|]/g, '_')
  const opt = {
    margin: 10,
    filename: `${safeTitle}_分析报告.pdf`,
    image: { type: 'jpeg' as const, quality: 0.95 },
    html2canvas: { scale: 2, useCORS: true },
    jsPDF: { unit: 'mm' as const, format: 'a4', orientation: 'portrait' as const },
  }
  html2pdf().set(opt).from(element).save()
}

const sentimentColor = (score: number | null): string => {
  if (score === null) return '#ccc'
  if (score >= 0.7) return '#4caf50'
  if (score >= 0.5) return '#ffb74d'
  return '#ef5350'
}

// ─── 图表渲染 ─────────────────────────────────────────────────────────────────
const renderCharts = () => {
  renderSentimentChart()
  renderViewsChart()
}

const renderSentimentChart = () => {
  if (!sentimentChartRef.value || sentimentTimeline.value.length === 0) return
  sentimentInstance?.dispose()
  sentimentObserver?.disconnect()
  sentimentInstance = echarts.init(sentimentChartRef.value)

  const labels = sentimentTimeline.value.map((p) => `第${p.episode_number}集`)
  const scores = sentimentTimeline.value.map((p) =>
    p.avg_sentiment !== null ? parseFloat(p.avg_sentiment.toFixed(3)) : null,
  )

  sentimentInstance.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: labels },
    yAxis: { type: 'value', min: 0, max: 1, name: '情感均分' },
    series: [
      {
        name: '情感均分',
        type: 'line',
        data: scores,
        smooth: true,
        symbol: 'circle',
        symbolSize: 7,
        lineStyle: { color: '#fa709a', width: 2.5 },
        itemStyle: { color: '#fa709a' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(250,112,154,0.3)' },
            { offset: 1, color: 'rgba(250,112,154,0.03)' },
          ]),
        },
        markLine: {
          silent: true,
          data: [{ yAxis: 0.5, name: '中性' }],
          lineStyle: { type: 'dashed', color: '#aaa' },
        },
      },
    ],
    grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
  })

  sentimentObserver = new ResizeObserver(() => sentimentInstance?.resize())
  sentimentObserver.observe(sentimentChartRef.value)
}

const renderViewsChart = () => {
  if (!viewsTrendChartRef.value || episodeViews.value.length === 0) return
  viewsInstance?.dispose()
  viewsObserver?.disconnect()
  viewsInstance = echarts.init(viewsTrendChartRef.value)

  const labels = episodes.value.map((_, i) => `第${i + 1}集`)
  const fmt = (v: number) => {
    if (v >= 1e8) return (v / 1e8).toFixed(1) + '亿'
    if (v >= 1e4) return (v / 1e4).toFixed(1) + '万'
    return String(v)
  }

  viewsInstance.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: (p: unknown) => {
        const arr = p as Array<{ name: string; marker: string; value: number }>
        return arr.map((d) => `${d.marker}${d.name}：${fmt(d.value)}`).join('<br/>')
      },
    },
    xAxis: { type: 'category', data: labels },
    yAxis: { type: 'value', axisLabel: { formatter: fmt } },
    series: [
      {
        name: '播放量',
        type: 'bar',
        data: episodeViews.value,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#4facfe' },
            { offset: 1, color: '#00f2fe' },
          ]),
        },
      },
    ],
    grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
  })

  viewsObserver = new ResizeObserver(() => viewsInstance?.resize())
  viewsObserver.observe(viewsTrendChartRef.value)
}

// ─── 生命周期 ─────────────────────────────────────────────────────────────────
onUnmounted(() => {
  sentimentObserver?.disconnect()
  viewsObserver?.disconnect()
  sentimentInstance?.dispose()
  viewsInstance?.dispose()
})
</script>

<style scoped>
.report-view {
  padding: 1.5rem 1rem;
}

.report-hero {
  text-align: center;
  padding: 2rem 0 1rem;
}

.report-hero h2 {
  font-size: 1.8rem;
  font-weight: 700;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* ── 搜索区 ── */
.report-search-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.report-search-wrap {
  flex: 1;
  position: relative;
  min-width: 200px;
}

.report-search-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: #9ca3af;
}

.report-search-input {
  width: 100%;
  padding: 0.55rem 1rem 0.55rem 2.5rem;
  border: 1.5px solid #e5e7eb;
  border-radius: 8px;
  font-size: 0.95rem;
  outline: none;
  transition: border-color 0.2s;
}

.report-search-input:focus {
  border-color: #667eea;
}

.report-search-btn,
.report-gen-btn,
.report-export-btn {
  padding: 0.55rem 1.1rem;
  border: none;
  border-radius: 8px;
  font-size: 0.9rem;
  cursor: pointer;
  white-space: nowrap;
  transition: opacity 0.2s;
}

.report-search-btn { background: #667eea; color: #fff; }
.report-gen-btn    { background: linear-gradient(135deg, #fa709a, #fee140); color: #fff; font-weight: 600; }
.report-export-btn { background: #ef4444; color: #fff; }

.report-search-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.report-status-msg {
  color: #6b7280;
  font-size: 0.85rem;
}

/* ── 报告封面 ── */
.report-cover {
  background: linear-gradient(135deg, #f8f9ff 0%, #fff 100%);
  border-radius: 12px;
  padding: 1.5rem;
  border: 1px solid #e5e7eb;
}

.report-cover-img {
  width: 80px;
  height: 110px;
  object-fit: cover;
  border-radius: 6px;
}

.report-title {
  font-size: 1.4rem;
  font-weight: 700;
  margin-bottom: 0.4rem;
}

.report-meta {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
  margin-bottom: 0.4rem;
}

.meta-badge {
  background: #f3f4f6;
  color: #374151;
  padding: 2px 10px;
  border-radius: 20px;
  font-size: 0.82rem;
}

.meta-badge.rating {
  background: linear-gradient(135deg, #fad0c4 0%, #ffd1ff 100%);
  color: #6b21a8;
}

.report-generated-at { font-size: 0.82rem; }

/* ── KPI 卡片 ── */
.kpi-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem 1.2rem;
  border-radius: 10px;
  color: white;
}

.kpi-card.blue   { background: linear-gradient(135deg, #4facfe, #00f2fe); }
.kpi-card.pink   { background: linear-gradient(135deg, #f093fb, #f5576c); }
.kpi-card.yellow { background: linear-gradient(135deg, #43e97b, #38f9d7); }
.kpi-card.purple { background: linear-gradient(135deg, #667eea, #764ba2); }

.kpi-icon { font-size: 1.8rem; opacity: 0.9; }

.kpi-content h5 { margin: 0; font-size: 0.85rem; opacity: 0.9; }

.kpi-value { margin: 0; font-size: 1.4rem; font-weight: 700; }

/* ── 风格统一卡片（复用 global） ── */
.style-unified {
  background: #fff;
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  overflow: hidden;
}

.card-header-unified {
  padding: 0.8rem 1.2rem;
  border-bottom: 1px solid #f3f4f6;
}

.card-header-unified h5 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
}

/* ── AI 洞察面板 ── */
.insight-panel {
  height: 100%;
}

.insight-loading,
.insight-placeholder {
  padding: 1.5rem;
  color: #9ca3af;
  font-size: 0.9rem;
  display: flex;
  align-items: center;
}

.insight-text {
  padding: 1rem 1.2rem;
  font-size: 0.9rem;
  line-height: 1.7;
  color: #374151;
  max-height: 320px;
  overflow-y: auto;
}

.insight-text :deep(h1),
.insight-text :deep(h2),
.insight-text :deep(h3),
.insight-text :deep(h4),
.insight-text :deep(h5),
.insight-text :deep(h6) {
  margin: 0.6rem 0 0.4rem;
  font-weight: 700;
  line-height: 1.4;
}

.insight-text :deep(p) {
  margin: 0 0 0.5rem;
}

.insight-text :deep(ul),
.insight-text :deep(ol) {
  margin: 0 0 0.6rem;
  padding-left: 1.2rem;
}

.insight-text :deep(li) {
  margin: 0.2rem 0;
}

.insight-text :deep(code) {
  background: #f3f4f6;
  border-radius: 4px;
  padding: 0.08rem 0.35rem;
  font-size: 0.82rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

.insight-text :deep(a) {
  color: #4f46e5;
  text-decoration: underline;
}

/* ── 图表占位 ── */
.chart-placeholder {
  height: 320px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  color: #9ca3af;
  font-size: 2rem;
}

.chart-placeholder span {
  font-size: 0.9rem;
}

/* ── 高赞评论 ── */
.comments-grid {
  padding: 1rem;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 0.8rem;
}

.comment-card {
  background: #f9fafb;
  border-left: 4px solid #ccc;
  border-radius: 6px;
  padding: 0.8rem;
}

.comment-content {
  font-size: 0.85rem;
  color: #374151;
  margin-bottom: 0.4rem;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.comment-meta {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #9ca3af;
}

.comment-score { color: #667eea; font-weight: 600; }

/* ── 空状态 ── */
.empty-state {
  text-align: center;
  padding: 5rem 0;
  color: #9ca3af;
}

.empty-state i {
  font-size: 4rem;
  margin-bottom: 1rem;
  display: block;
}

.empty-state h4 { color: #6b7280; }
</style>
