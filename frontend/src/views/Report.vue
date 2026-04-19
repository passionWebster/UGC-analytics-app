<template>
  <div class="report-view">
    <div class="report-hero">
      <h2>番剧数据分析报告生成器</h2>
      <p class="text-muted">阶段四可视化：高能心电图、动态词云、情绪雷达与观点卡片</p>
    </div>

    <div class="search-bar">
      <input
        v-model="keyword"
        type="text"
        placeholder="输入番剧名称搜索..."
        autocomplete="off"
        @keyup.enter="handleSearch"
      />
      <button :disabled="searching" @click="handleSearch">{{ searching ? '搜索中…' : '搜索' }}</button>
    </div>
    <p v-if="statusMsg" class="status-msg">{{ statusMsg }}</p>

    <div v-if="animeData" class="report-content">
      <div class="report-cover">
        <img
          v-if="animeData.cover"
          :src="`/api/image_proxy?url=${encodeURIComponent(String(animeData.cover))}&title=${encodeURIComponent(String(animeData.title))}&season_id=${animeData.season_id}`"
          :alt="animeData.title"
        />
        <div class="meta">
          <h3>{{ animeData.title }}</h3>
          <div class="tags">
            <span>{{ animeData.area }}</span>
            <span v-if="animeData.release_date">{{ animeData.release_date }}</span>
            <span v-if="animeData.rating">⭐ {{ animeData.rating }}</span>
          </div>
          <div class="kpis">
            <div class="kpi"><strong>播放量</strong><span>{{ formatNumber(animeData.views) }}</span></div>
            <div class="kpi"><strong>追番</strong><span>{{ formatNumber(animeData.favorites) }}</span></div>
            <div class="kpi"><strong>集数</strong><span>{{ episodes.length }}</span></div>
          </div>
        </div>
      </div>

      <section class="module-card">
        <header>
          <h4>模块 A：单集高能心电图</h4>
          <small>双 Y 轴 + dataZoom，悬浮展示高频关键词</small>
        </header>
        <div class="module-grid-a">
          <aside class="episode-sidebar">
            <p>单集选择</p>
            <div class="episode-list fixed-height-list">
              <button
                v-for="ep in episodes"
                :key="ep.title + (ep.cid || '')"
                :class="{ active: selectedCid === ep.cid }"
                :disabled="!ep.cid"
                @click="onEpisodeSelect(ep.cid || '')"
              >
                {{ ep.title }}
              </button>
            </div>
          </aside>
          <div class="chart-wrap fixed-height-chart-lg">
            <VChart :option="microTimelineOption" autoresize class="chart" />
          </div>
        </div>
      </section>

      <section class="module-card">
        <header>
          <h4>模块 B：受众情绪与内容词云画像</h4>
          <small>词云随集数切换重组 + 情绪雷达图</small>
        </header>
        <div class="module-grid-b">
          <div class="chart-wrap fixed-height-chart-lg">
            <VChart :option="wordcloudOption" autoresize class="chart" />
          </div>
          <div class="chart-wrap fixed-height-chart-md">
            <VChart :option="radarOption" autoresize class="chart" />
          </div>
        </div>
      </section>

      <section class="module-card">
        <header>
          <h4>模块 C：热门评论观点提取卡片</h4>
          <small>基于高赞评论聚合，展示观点支持率</small>
        </header>
        <div class="insight-columns fixed-height-cards">
          <article v-for="card in insightCards" :key="card.topic" class="insight-card">
            <h5>{{ card.topic }}</h5>
            <div class="support-row">
              <span>支持率 {{ (card.support_rate * 100).toFixed(1) }}%</span>
              <span>{{ card.comment_count }} 条评论</span>
            </div>
            <ul>
              <li v-for="sample in card.samples" :key="sample">{{ sample }}</li>
            </ul>
          </article>
          <div v-if="insightCards.length === 0" class="empty-hint">暂无观点卡片数据</div>
        </div>
      </section>
    </div>

    <div v-else class="empty-state">
      <h4>请先搜索一部番剧</h4>
      <p>搜索后将自动加载阶段四可视化分析模块。</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, shallowRef } from 'vue'
import VChart from 'vue-echarts'
import 'echarts'
import 'echarts-wordcloud'
import {
  getAnimeDetail,
  getAnimeEpisodes,
  getEpisodeAnalysisBundle,
  getSeasonCharacters,
  getSeasonInsightCards,
  getSeasonWordcloud,
  searchAnimes,
} from '@/api/analytics'
import type {
  AnimeDetailData,
  SeasonCharacterItem,
  SeasonInsightCard,
  SeasonWordcloudItem,
} from '@/api/analytics'

defineOptions({ name: 'ReportView' })

const keyword = ref('')
const statusMsg = ref('')
const searching = ref(false)

const animeData = ref<AnimeDetailData | null>(null)
const episodes = ref<Array<{ title: string; cid?: string; views: number }>>([])
const selectedCid = ref('')

const microTimelineOption = shallowRef<Record<string, unknown>>({})
const wordcloudOption = shallowRef<Record<string, unknown>>({})
const radarOption = shallowRef<Record<string, unknown>>({})
const insightCards = ref<SeasonInsightCard[]>([])

const escapeText = (value: unknown): string =>
  String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')

const formatNumber = (n?: number | null) => {
  const num = n ?? 0
  if (num >= 1e8) return `${(num / 1e8).toFixed(1)}亿`
  if (num >= 1e4) return `${(num / 1e4).toFixed(1)}万`
  return String(num)
}

const buildMicroTimelineOption = (timeline: Array<{ time_start: number; danmaku_count: number; avg_sentiment: number; top_keywords: string[] }>) => {
  if (!timeline.length) {
    return {
      title: { text: '暂无单集时间轴数据', left: 'center', top: 'middle', textStyle: { color: '#9ca3af', fontSize: 14 } },
    }
  }

  const labels = timeline.map((item) => {
    const min = Math.floor(item.time_start / 60)
    const sec = item.time_start % 60
    return `${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
  })

  return {
    animationDurationUpdate: 450,
    tooltip: {
      trigger: 'axis',
      formatter: (tooltipParams: Array<{ seriesName: string; value: number; data?: { keywords?: string[] } }>) => {
        const bar = tooltipParams.find((p) => p.seriesName === '弹幕密度')
        const line = tooltipParams.find((p) => p.seriesName === '情感值')
        const keywords = (bar?.data?.keywords || []).slice(0, 3).map(escapeText).join('、') || '无'
        return [
          `弹幕：${bar?.value ?? 0}`,
          `情感：${line?.value ?? 0}`,
          `关键词：${keywords}`,
        ].join('<br/>')
      },
    },
    legend: { top: 0 },
    grid: { left: 56, right: 56, top: 36, bottom: 66 },
    xAxis: { type: 'category', data: labels, axisLabel: { interval: 'auto' } },
    yAxis: [
      { type: 'value', name: '弹幕密度' },
      { type: 'value', name: '情感值', min: -1, max: 1 },
    ],
    dataZoom: [
      { type: 'inside', throttle: 50 },
      { type: 'slider', height: 18, bottom: 16 },
    ],
    series: [
      {
        name: '弹幕密度',
        type: 'bar',
        large: true,
        data: timeline.map((item) => ({ value: item.danmaku_count, keywords: item.top_keywords || [] })),
        itemStyle: { color: '#6ea8fe' },
      },
      {
        name: '情感值',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        symbol: 'none',
        data: timeline.map((item) => Math.round((item.avg_sentiment ?? 0) * 10000) / 10000),
        lineStyle: { color: '#ef476f', width: 2 },
      },
    ],
  }
}

const buildWordcloudOption = (items: SeasonWordcloudItem[]) => ({
  animationDurationUpdate: 450,
  tooltip: {
    formatter: (param: { data: { name: string; value: number } }) =>
      `${escapeText(param.data.name)}：${param.data.value}`,
  },
  series: [
    {
      type: 'wordCloud',
      shape: 'circle',
      left: 'center',
      top: 'center',
      width: '100%',
      height: '100%',
      sizeRange: [12, 48],
      rotationRange: [-45, 45],
      gridSize: 8,
      drawOutOfBound: false,
      textStyle: {
        color: () => {
          const palette = ['#5B8FF9', '#5AD8A6', '#5D7092', '#F6BD16', '#E8684A', '#6DC8EC', '#9270CA']
          return palette[Math.floor(Math.random() * palette.length)]
        },
      },
      data: items.map((item) => ({ name: item.text, value: item.weight })),
    },
  ],
})

const radarDimensions = [
  { label: '搞笑偏好', words: ['哈哈', '搞笑', '乐', '整活', '有趣'] },
  { label: '剧情讨论', words: ['剧情', '设定', '反转', '伏笔', '节奏'] },
  { label: '作画赞赏', words: ['作画', '画面', '镜头', '特效', '分镜'] },
  { label: '配乐共鸣', words: ['配乐', '音乐', 'op', 'ed', '声优'] },
  { label: '角色代入', words: ['角色', '主角', '人设', '成长', '关系'] },
]

const buildRadarOption = (wordItems: SeasonWordcloudItem[], characterItems: SeasonCharacterItem[]) => {
  const weightMap = new Map(wordItems.map((item) => [item.text.toLowerCase(), item.weight]))
  const maxWeight = Math.max(...wordItems.map((item) => item.weight), 1)

  const values = radarDimensions.map((dim) => {
    const hitWeight = dim.words.reduce((sum, word) => sum + (weightMap.get(word.toLowerCase()) || 0), 0)
    return Math.min(100, Math.round((hitWeight / maxWeight) * 25))
  })

  if (characterItems.length > 0) {
    values[4] = Math.min(100, values[4] + 20)
  }

  return {
    tooltip: { trigger: 'item' },
    radar: {
      indicator: radarDimensions.map((dim) => ({ name: dim.label, max: 100 })),
      radius: '63%',
    },
    series: [
      {
        type: 'radar',
        data: [{
          value: values,
          name: '整体画像',
          areaStyle: { color: 'rgba(91,143,249,0.25)' },
          lineStyle: { color: '#5B8FF9' },
        }],
      },
    ],
  }
}

const onEpisodeSelect = async (cid: string) => {
  if (!animeData.value || !cid) return
  selectedCid.value = cid
  statusMsg.value = '分析中…'

  try {
    const analysisRes = await getEpisodeAnalysisBundle(
      animeData.value.season_id,
      cid,
      { bin_size: 15, keyword_topk: 3, top_n: 100 },
    )
    if (!analysisRes.success || analysisRes.pending) {
      statusMsg.value = analysisRes.message || '该集暂无可分析数据，已触发后台抓取'
      microTimelineOption.value = buildMicroTimelineOption([])
      wordcloudOption.value = buildWordcloudOption([])
      return
    }
    microTimelineOption.value = buildMicroTimelineOption(analysisRes.data?.timeline?.timeline || [])
    wordcloudOption.value = buildWordcloudOption(analysisRes.data?.wordcloud?.items || [])
    statusMsg.value = analysisRes.refresh_scheduled
      ? '已加载缓存图表，后台正在刷新最新分析'
      : `已加载：${animeData.value.title}`
  } catch {
    microTimelineOption.value = buildMicroTimelineOption([])
    wordcloudOption.value = buildWordcloudOption([])
    statusMsg.value = '分析失败，请稍后重试'
  }
}

const handleSearch = async () => {
  if (!keyword.value.trim()) {
    statusMsg.value = '请输入番剧名称'
    return
  }

  searching.value = true
  statusMsg.value = '搜索中…'

  try {
    const searchRes = await searchAnimes(keyword.value.trim())
    if (!searchRes.list?.length) {
      animeData.value = null
      episodes.value = []
      statusMsg.value = '未找到相关番剧'
      return
    }

    const target = searchRes.list[0]
    const detail = await getAnimeDetail(target.season_id)
    animeData.value = detail.data || (target as AnimeDetailData)

    const [epRes, seasonWordcloudRes, characterRes, cardsRes] = await Promise.allSettled([
      getAnimeEpisodes(target.season_id),
      getSeasonWordcloud(target.season_id, { top_n: 120 }),
      getSeasonCharacters(target.season_id, { top_n: 8 }),
      getSeasonInsightCards(target.season_id, { limit: 300, top_n: 8 }),
    ])

    episodes.value = epRes.status === 'fulfilled' ? (epRes.value.data || []) : []

    const seasonWordItems = seasonWordcloudRes.status === 'fulfilled' ? (seasonWordcloudRes.value.data.items || []) : []
    const characterItems = characterRes.status === 'fulfilled' ? (characterRes.value.data.items || []) : []
    insightCards.value = cardsRes.status === 'fulfilled' ? (cardsRes.value.data || []) : []

    radarOption.value = buildRadarOption(seasonWordItems, characterItems)

    const initialCid = episodes.value.find((ep) => ep.cid)?.cid || ''
    if (initialCid) {
      await onEpisodeSelect(initialCid)
    } else {
      microTimelineOption.value = buildMicroTimelineOption([])
      wordcloudOption.value = buildWordcloudOption(seasonWordItems)
    }

    statusMsg.value = `已加载：${animeData.value?.title || target.title}`
  } catch {
    animeData.value = null
    episodes.value = []
    statusMsg.value = '搜索失败，请重试'
  } finally {
    searching.value = false
  }
}
</script>

<style scoped>
.report-view {
  padding: 1.5rem 1rem;
}

.report-hero {
  text-align: center;
  margin-bottom: 1rem;
}

.report-hero h2 {
  margin-bottom: 0.35rem;
  font-size: 1.8rem;
  font-weight: 700;
  background: linear-gradient(135deg, #5b8ff9, #7f56d9);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.search-bar {
  display: flex;
  gap: 0.65rem;
  max-width: 760px;
  margin: 0 auto;
}

.search-bar input {
  flex: 1;
  border: 1px solid #dbe2ea;
  border-radius: 10px;
  padding: 0.65rem 0.8rem;
}

.search-bar button {
  border: none;
  border-radius: 10px;
  background: #5b8ff9;
  color: #fff;
  padding: 0.65rem 1rem;
}

.status-msg {
  text-align: center;
  color: #6b7280;
  margin: 0.65rem 0 1rem;
}

.report-content {
  display: grid;
  gap: 1rem;
}

.report-cover {
  display: grid;
  grid-template-columns: 90px 1fr;
  gap: 1rem;
  border: 1px solid #e7ecf3;
  border-radius: 12px;
  padding: 1rem;
  background: #fff;
}

.report-cover img {
  width: 90px;
  height: 120px;
  object-fit: cover;
  border-radius: 8px;
}

.tags {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-bottom: 0.65rem;
}

.tags span {
  background: #f4f6fb;
  border-radius: 999px;
  padding: 0.15rem 0.6rem;
  font-size: 0.8rem;
}

.kpis {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.6rem;
}

.kpi {
  background: #f8fbff;
  border: 1px solid #eaf1fb;
  border-radius: 8px;
  padding: 0.5rem 0.65rem;
  display: flex;
  justify-content: space-between;
}

.module-card {
  border: 1px solid #e7ecf3;
  border-radius: 12px;
  background: #fff;
  padding: 0.9rem;
}

.module-card > header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 0.8rem;
}

.module-card h4 {
  margin: 0;
  font-size: 1.06rem;
}

.module-card small {
  color: #6b7280;
}

.module-grid-a {
  display: grid;
  grid-template-columns: 210px 1fr;
  gap: 0.8rem;
}

.module-grid-b {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: 0.8rem;
}

.episode-sidebar {
  border: 1px solid #edf1f6;
  border-radius: 10px;
  padding: 0.7rem;
}

.episode-sidebar p {
  margin: 0 0 0.45rem;
  font-weight: 600;
}

.episode-list {
  display: grid;
  gap: 0.4rem;
}

.episode-list button {
  border: 1px solid #dbe2ea;
  background: #fff;
  border-radius: 8px;
  text-align: left;
  padding: 0.45rem 0.6rem;
  font-size: 0.84rem;
}

.episode-list button.active {
  border-color: #5b8ff9;
  background: #eef4ff;
  color: #2455c3;
}

.chart-wrap {
  border: 1px solid #edf1f6;
  border-radius: 10px;
  overflow: hidden;
}

.chart {
  width: 100%;
  height: 100%;
}

.fixed-height-chart-lg {
  height: 380px;
}

.fixed-height-chart-md {
  height: 320px;
}

.fixed-height-list {
  height: 340px;
  overflow: auto;
}

.insight-columns {
  column-count: 3;
  column-gap: 0.75rem;
}

.insight-card {
  break-inside: avoid;
  margin: 0 0 0.75rem;
  border: 1px solid #edf1f6;
  border-radius: 10px;
  padding: 0.75rem;
  background: #fbfcff;
}

.insight-card h5 {
  margin: 0 0 0.5rem;
}

.support-row {
  display: flex;
  justify-content: space-between;
  color: #4b5563;
  font-size: 0.8rem;
  margin-bottom: 0.45rem;
}

.insight-card ul {
  margin: 0;
  padding-left: 1.05rem;
}

.insight-card li {
  margin-bottom: 0.35rem;
  color: #374151;
  font-size: 0.84rem;
}

.fixed-height-cards {
  min-height: 260px;
}

.empty-hint {
  color: #9ca3af;
  padding: 0.6rem;
}

.empty-state {
  text-align: center;
  padding: 3rem 0;
  color: #9ca3af;
}

@media (max-width: 1100px) {
  .module-grid-b {
    grid-template-columns: 1fr;
  }

  .insight-columns {
    column-count: 2;
  }
}

@media (max-width: 900px) {
  .module-grid-a {
    grid-template-columns: 1fr;
  }

  .kpis {
    grid-template-columns: 1fr;
  }

  .insight-columns {
    column-count: 1;
  }
}
</style>
