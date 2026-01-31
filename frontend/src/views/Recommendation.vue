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

      <!-- 推荐网格 -->
      <div v-loading="loading" class="recommendation-grid">
        <div v-if="recommendations.length === 0 && !loading" class="text-center py-5">
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

      <!-- 加载更多按钮 -->
      <div v-if="hasMore && recommendations.length > 0" class="load-more-container">
        <button class="btn btn-outline-primary" @click="loadMore">
          <i class="fas fa-plus-circle me-1"></i>加载更多
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { getRankings, type AnimeData } from '@/api/analytics'
import { useRouter } from 'vue-router'

// 路由
const router = useRouter()

// 状态管理
const loading = ref(false)
const recommendations = ref<AnimeData[]>([])
const currentSort = ref('score')
const showPreferencesTooltip = ref(false)
const hasMore = ref(true)
const currentPage = ref<number>(1)
const pageSize: number = 12

// 排序选项
const sortOptions = [
  { value: 'score', label: '评分', icon: 'fas fa-star' },
  { value: 'views', label: '播放量', icon: 'fas fa-play-circle' },
  { value: 'followers', label: '追番人数', icon: 'fas fa-heart' }
]

// 偏好状态文本
const preferenceStatus = computed(() => {
  return showPreferencesTooltip.value ? '已启用偏好推荐' : '根据偏好推荐'
})

const preferencesText = computed(() => {
  return '根据您的观看历史和偏好，为您推荐相似的番剧'
})

// 格式化数字
const formatNumber = (num: number | undefined): string => {
  if (!num) return '0'
  if (num >= 100000000) return (num / 100000000).toFixed(1) + '亿'
  if (num >= 10000) return (num / 10000).toFixed(1) + '万'
  return num.toString()
}

// 切换偏好设置
const togglePreferences = () => {
  showPreferencesTooltip.value = !showPreferencesTooltip.value
  loadRecommendations()
}

// 处理排序变化
const handleSortChange = (sortValue: string) => {
  if (currentSort.value === sortValue) return
  currentSort.value = sortValue
  currentPage.value = 1
  recommendations.value = []
  loadRecommendations()
}

// 加载推荐数据
const loadRecommendations = async () => {
  try {
    loading.value = true
    
    // 转换排序字段
    let sortBy = currentSort.value
    if (sortBy === 'followers') sortBy = 'favorites'
    if (sortBy === 'score') sortBy = 'rating'
    
    const response = await getRankings(sortBy, pageSize * currentPage.value)
    
    if (response.list) {
      recommendations.value = response.list
      hasMore.value = response.list.length >= pageSize * currentPage.value
    }
  } catch (error) {
    console.error('加载推荐失败:', error)
  } finally {
    loading.value = false
  }
}

// 加载更多
const loadMore = () => {
  currentPage.value++
  loadRecommendations()
}

// 点击番剧卡片
const handleAnimeClick = (anime: AnimeData) => {
  // 可以跳转到详情页或触发其他操作
  console.log('点击番剧:', anime.title)
  // router.push(`/anime/${anime.season_id}`)
}

onMounted(() => {
  loadRecommendations()
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
