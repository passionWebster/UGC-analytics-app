<template>
  <div class="recommendation-view">
    <div class="recommendation-content">
      <!-- 头部控制区 -->
      <div class="recommendation-header">
        <div class="preference-status">
          <button class="btn btn-lg btn-pink" @click="togglePreferences">
            <i class="fas fa-heart me-2"></i>
            <span>{{ preferenceStatus }}</span>
          </button>
          <div v-if="showPreferencesTooltip" class="preference-tooltip">
            {{ preferencesText }}
          </div>
        </div>
        
        <!-- 排序控制 -->
        <div class="sort-controls">
          <label class="sort-label">排序方式：</label>
          <div class="btn-group" role="group">
            <button 
              v-for="sort in sortOptions" 
              :key="sort.value"
              class="btn" 
              :class="currentSort === sort.value ? 'btn-primary active' : 'btn-outline-primary'"
              @click="handleSortChange(sort.value)"
            >
              <i :class="sort.icon + ' me-1'"></i>{{ sort.label }}
            </button>
          </div>
        </div>
      </div>

      <!-- 推荐网格：响应式 CSS Grid，最小列宽 250px -->
      <div v-loading="loading" class="recommendation-grid">
        <div v-if="recommendations.length === 0 && !loading" class="empty-tip">
          暂无推荐数据
        </div>
        
        <div 
          v-for="anime in recommendations" 
          :key="anime.season_id" 
          class="anime-card"
          @click="handleAnimeClick(anime)"
        >
          <div class="anime-cover">
            <img :src="anime.cover || '/placeholder.jpg'" :alt="anime.title" />
            <div class="anime-overlay">
              <div class="anime-stats">
                <span><i class="fas fa-play-circle"></i> {{ formatNumber(anime.views) }}</span>
                <span><i class="fas fa-heart"></i> {{ formatNumber(anime.favorites) }}</span>
              </div>
            </div>
          </div>
          
          <div class="anime-info">
            <h6 class="anime-title" :title="anime.title">{{ anime.title }}</h6>
            <div class="anime-meta">
              <span class="anime-rating">
                <i class="fas fa-star"></i> {{ anime.rating?.toFixed(1) || 'N/A' }}
              </span>
              <span class="anime-area">{{ anime.area }}</span>
            </div>
            <div class="anime-tags">
              <span v-for="style in anime.styles?.slice(0, 3)" :key="style" class="tag">
                {{ style }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- 加载更多按钮（备用操作，与无限滚动并存） -->
      <div v-if="hasMore && !loading" class="load-more-container">
        <button class="btn btn-outline-primary" @click="loadMore">
          <i class="fas fa-plus-circle me-1"></i>加载更多
        </button>
      </div>

      <!-- 无限滚动哨兵：当此元素进入视口时自动触发 loadMore -->
      <div ref="sentinel" class="scroll-sentinel"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue'
import { getRankings, type AnimeData } from '@/api/analytics'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'

// 路由与认证 Store
const router = useRouter()
const authStore = useAuthStore()

// 分页参数：每次展示的步长
const PAGE_SIZE = 12
// 单次从服务器拉取的最大条数（客户端分页的数据池大小）
const BATCH_SIZE = 100
// 触发无限滚动的提前量（距底部多少像素时开始加载）
const SCROLL_TRIGGER_MARGIN = '100px'

// 状态
const loading = ref(false)
const allAnimes = ref<AnimeData[]>([])         // 全量数据缓存（一次性从服务器拉取）
const visibleCount = ref<number>(PAGE_SIZE)    // 当前可见数量（客户端分页）
const currentSort = ref('score')
const showPreferencesTooltip = ref(false)      // 是否启用偏好过滤 & 是否显示提示气泡
const sentinel = ref<HTMLElement | null>(null) // 无限滚动哨兵元素

// IntersectionObserver 实例（组件级变量，不需要响应式）
let scrollObserver: IntersectionObserver | null = null

// 计算属性：当前可见的番剧列表（对全量缓存做切片）
const recommendations = computed<AnimeData[]>(() =>
  allAnimes.value.slice(0, visibleCount.value)
)

// 计算属性：是否仍有更多数据可以展示
const hasMore = computed<boolean>(() =>
  visibleCount.value < allAnimes.value.length
)

// 排序选项配置
const sortOptions = [
  { value: 'score', label: '评分', icon: 'fas fa-star' },
  { value: 'views', label: '播放量', icon: 'fas fa-play-circle' },
  { value: 'followers', label: '追番人数', icon: 'fas fa-heart' }
]

// 偏好按钮文本：根据启用状态动态显示
const preferenceStatus = computed<string>(() =>
  showPreferencesTooltip.value ? '已启用偏好推荐' : '根据偏好推荐'
)

// 偏好提示内容：展示用户的偏好标签
const preferencesText = computed<string>(() => {
  const genres = authStore.preferences.join('、')
  return genres
    ? `已根据您的偏好（${genres}）筛选推荐`
    : '根据您的观看历史和偏好，为您推荐相似的番剧'
})

// 格式化大数字：亿 / 万 / 原始值
const formatNumber = (num: number | undefined): string => {
  if (!num) return '0'
  if (num >= 100000000) return (num / 100000000).toFixed(1) + '亿'
  if (num >= 10000) return (num / 10000).toFixed(1) + '万'
  return num.toString()
}

// 切换偏好推荐开关，同时重新加载数据
const togglePreferences = () => {
  showPreferencesTooltip.value = !showPreferencesTooltip.value
  loadRecommendations()
}

// 处理排序方式变化
const handleSortChange = (sortValue: string) => {
  if (currentSort.value === sortValue) return
  currentSort.value = sortValue
  loadRecommendations()
}

// 加载推荐数据：一次性拉取最多 100 条到本地缓存，再通过客户端分页逐步展示
const loadRecommendations = async () => {
  try {
    loading.value = true
    visibleCount.value = PAGE_SIZE // 重置到第一页

    // 映射前端排序字段到后端参数
    let sortBy = currentSort.value
    if (sortBy === 'followers') sortBy = 'favorites'
    if (sortBy === 'score') sortBy = 'rating'

    // 启用偏好推荐时，将用户偏好标签传入过滤参数
    const stylesFilter =
      showPreferencesTooltip.value && authStore.preferences.length > 0
        ? authStore.preferences.join(',')
        : undefined

    const response = await getRankings(sortBy, BATCH_SIZE, undefined, stylesFilter)
    allAnimes.value = response.list || []
  } catch (error) {
    console.error('加载推荐失败:', error)
  } finally {
    loading.value = false
    // 数据更新后重新触发 IntersectionObserver，自动填满初始视口
    await nextTick()
    triggerSentinelCheck()
  }
}

// 加载更多：仅增加本地可见数量，无需额外网络请求
const loadMore = () => {
  visibleCount.value = Math.min(
    visibleCount.value + PAGE_SIZE,
    allAnimes.value.length
  )
}

// 初始化 IntersectionObserver：当哨兵元素进入视口时自动调用 loadMore
const initScrollObserver = () => {
  if (scrollObserver) scrollObserver.disconnect()
  scrollObserver = new IntersectionObserver(
    (entries) => {
      if (entries[0].isIntersecting && hasMore.value && !loading.value) {
        loadMore()
      }
    },
    { rootMargin: SCROLL_TRIGGER_MARGIN, threshold: 0 }
  )
  if (sentinel.value) scrollObserver.observe(sentinel.value)
}

// 重新触发哨兵的可见性检测（排序/偏好切换后重置数据时使用）
const triggerSentinelCheck = () => {
  if (scrollObserver && sentinel.value) {
    scrollObserver.unobserve(sentinel.value)
    scrollObserver.observe(sentinel.value)
  }
}

// 点击番剧卡片
const handleAnimeClick = (anime: AnimeData) => {
  console.log('点击番剧:', anime.title)
}

onMounted(async () => {
  await loadRecommendations()
  await nextTick()
  initScrollObserver()
})

onUnmounted(() => {
  // 组件卸载时释放观察器，防止内存泄漏
  scrollObserver?.disconnect()
})
</script>

<style scoped>
.recommendation-view {
  padding: 20px;
}

.recommendation-content {
  max-width: 1400px;
  margin: 0 auto;
}

.recommendation-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
  padding: 20px;
  background: white;
  border-radius: 10px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  flex-wrap: wrap;
  gap: 20px;
}

.preference-status {
  position: relative;
}

.btn-pink {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  color: white;
  border: none;
  padding: 12px 24px;
  font-size: 16px;
  border-radius: 8px;
  transition: all 0.3s ease;
}

.btn-pink:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(245, 87, 108, 0.4);
}

.preference-tooltip {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 10px;
  padding: 10px 15px;
  background: #333;
  color: white;
  border-radius: 6px;
  font-size: 14px;
  white-space: nowrap;
  z-index: 10;
  animation: fadeIn 0.3s ease;
}

.preference-tooltip::before {
  content: '';
  position: absolute;
  bottom: 100%;
  left: 20px;
  border: 6px solid transparent;
  border-bottom-color: #333;
}

.sort-controls {
  display: flex;
  align-items: center;
  gap: 15px;
}

.sort-label {
  font-weight: 500;
  margin: 0;
  color: #666;
}

.btn-group .btn {
  padding: 8px 16px;
  font-size: 14px;
  border-radius: 6px;
  margin: 0 4px;
  transition: all 0.3s ease;
}

.btn-group .btn:hover {
  transform: translateY(-2px);
}

.recommendation-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 24px;
  min-height: 400px;
}

.anime-card {
  background: white;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  transition: all 0.3s ease;
  cursor: pointer;
}

.anime-card:hover {
  transform: translateY(-8px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
}

.anime-cover {
  position: relative;
  width: 100%;
  height: 320px;
  overflow: hidden;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.anime-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s ease;
}

.anime-card:hover .anime-cover img {
  transform: scale(1.1);
}

.anime-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.8), transparent);
  padding: 15px;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.anime-card:hover .anime-overlay {
  opacity: 1;
}

.anime-stats {
  display: flex;
  gap: 15px;
  color: white;
  font-size: 14px;
}

.anime-stats span {
  display: flex;
  align-items: center;
  gap: 5px;
}

.anime-info {
  padding: 16px;
}

.anime-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 10px 0;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.anime-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  font-size: 14px;
}

.anime-rating {
  color: #f5a623;
  font-weight: 500;
}

.anime-area {
  color: #999;
  font-size: 12px;
}

.anime-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag {
  display: inline-block;
  padding: 4px 10px;
  background: #f0f0f0;
  color: #666;
  border-radius: 12px;
  font-size: 12px;
}

.load-more-container {
  display: flex;
  justify-content: center;
  margin-top: 40px;
}

.load-more-container .btn {
  padding: 12px 32px;
  font-size: 16px;
  border-radius: 8px;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 空状态提示 */
.empty-tip {
  grid-column: 1 / -1;
  text-align: center;
  padding: 60px 0;
  color: #999;
  font-size: 16px;
}

/* 无限滚动哨兵元素（不可见占位符，供 IntersectionObserver 检测） */
.scroll-sentinel {
  height: 1px;
  width: 100%;
  margin-top: 20px;
}

@media (max-width: 768px) {
  .recommendation-header {
    flex-direction: column;
    align-items: stretch;
  }
  
  .sort-controls {
    flex-direction: column;
    align-items: stretch;
  }
  
  .btn-group {
    display: flex;
    width: 100%;
  }
  
  .btn-group .btn {
    flex: 1;
  }
  
  .recommendation-grid {
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 16px;
  }
}
</style>
