<template>
  <div class="stats-board">
    <el-card>
      <template #header>
        <span>本周追番播放量增长</span>
      </template>
      <div class="summary">
        <div class="item">
          <label>当前总播放量</label>
          <strong>{{ formatNumber(data?.weekly_views_summary.latest_views_total || 0) }}</strong>
        </div>
        <div class="item">
          <label>7天前总播放量</label>
          <strong>{{ formatNumber(data?.weekly_views_summary.week_ago_views_total || 0) }}</strong>
        </div>
        <div class="item">
          <label>本周增长</label>
          <strong>
            {{ formatNumber(data?.weekly_views_summary.weekly_growth || 0) }}
            <span v-if="data?.weekly_views_summary.weekly_growth_rate !== null">
              ({{ data?.weekly_views_summary.weekly_growth_rate }}%)
            </span>
          </strong>
        </div>
      </div>
    </el-card>

    <div class="charts">
      <el-card>
        <template #header><span>追番状态占比</span></template>
        <div ref="statusPieRef" class="chart"></div>
      </el-card>
      <el-card>
        <template #header><span>偏好类型雷达图</span></template>
        <div ref="genreRadarRef" class="chart"></div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import type { EChartsOption } from 'echarts'
import { useEcharts } from '@/composables/useEcharts'
import { getUserSpaceAnalytics } from '@/api/userSpace'

const data = ref<Awaited<ReturnType<typeof getUserSpaceAnalytics>>['data'] | null>(null)
const { chartRef: statusPieRef, initChart: initStatusPie } = useEcharts()
const { chartRef: genreRadarRef, initChart: initGenreRadar } = useEcharts()

const formatNumber = (value: number) => value.toLocaleString('zh-CN')

const renderCharts = async () => {
  if (!data.value) return
  await nextTick()

  const statusMap = data.value.status_distribution
  const statusOption: EChartsOption = {
    tooltip: { trigger: 'item' },
    series: [
      {
        type: 'pie',
        radius: ['35%', '70%'],
        data: [
          { name: '想看', value: statusMap.plan || 0 },
          { name: '在看', value: statusMap.watching || 0 },
          { name: '看过', value: statusMap.completed || 0 },
        ],
      },
    ],
  }

  const topGenres = (data.value.genre_distribution || []).slice(0, 6)
  const maxValue = Math.max(1, ...topGenres.map((item) => item.count))
  const radarOption: EChartsOption = {
    tooltip: {},
    radar: {
      indicator: topGenres.map((item) => ({ name: item.genre, max: maxValue })),
    },
    series: [
      {
        type: 'radar',
        data: [{ value: topGenres.map((item) => item.count), name: '偏好类型强度' }],
      },
    ],
  }

  initStatusPie(statusOption)
  initGenreRadar(radarOption)
}

const loadData = async () => {
  const response = await getUserSpaceAnalytics()
  data.value = response.data
  await renderCharts()
}

onMounted(loadData)
</script>

<style scoped>
.stats-board {
  display: grid;
  gap: 16px;
}

.summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.item {
  padding: 12px;
  background: #f5f7fa;
  border-radius: 8px;
}

.item label {
  display: block;
  color: #909399;
  margin-bottom: 6px;
}

.charts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.chart {
  width: 100%;
  height: 320px;
}

@media (max-width: 900px) {
  .summary,
  .charts {
    grid-template-columns: 1fr;
  }
}
</style>
