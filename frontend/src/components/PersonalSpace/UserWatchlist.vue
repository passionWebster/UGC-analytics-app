<template>
  <el-card>
    <template #header>
      <div class="header">
        <span>我的追番库</span>
        <el-button @click="loadFavorites">刷新</el-button>
      </div>
    </template>

    <el-tabs v-model="activeStatus" @tab-change="loadFavorites">
      <el-tab-pane label="全部" name="all" />
      <el-tab-pane label="想看" name="plan" />
      <el-tab-pane label="在看" name="watching" />
      <el-tab-pane label="看过" name="completed" />
    </el-tabs>

    <el-table v-loading="loading" :data="favorites" empty-text="暂无追番记录">
      <el-table-column label="番剧" min-width="260">
        <template #default="{ row }">
          <div class="anime-cell">
            <img v-if="row.cover" :src="getProxiedUrl(row.cover, row.title, row.season_id)" :alt="row.title" />
            <div>
              <div class="title">{{ row.title }}</div>
              <div class="meta">评分：{{ row.rating ?? '-' }}</div>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="150">
        <template #default="{ row }">
          <el-select
            :model-value="row.status"
            size="small"
            @change="handleStatusChange(row.season_id, $event)"
          >
            <el-option label="想看" value="plan" />
            <el-option label="在看" value="watching" />
            <el-option label="看过" value="completed" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220">
        <template #default="{ row }">
          <el-button size="small" @click="goToStatus(row.title)">查看状态分析</el-button>
          <el-button size="small" type="danger" @click="removeFavorite(row.season_id)">取消收藏</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  getUserFavorites,
  type FavoriteStatus,
  type UserFavoriteItem,
  toggleFavorite,
  updateFavoriteStatus,
} from '@/api/userSpace'
import { getProxiedUrl } from '@/utils/imageProxy'

const router = useRouter()
const loading = ref(false)
const favorites = ref<UserFavoriteItem[]>([])
const activeStatus = ref<'all' | FavoriteStatus>('all')

const loadFavorites = async () => {
  loading.value = true
  try {
    const status = activeStatus.value === 'all' ? undefined : activeStatus.value
    const response = await getUserFavorites(status)
    favorites.value = response.data || []
  } finally {
    loading.value = false
  }
}

const changeStatus = async (seasonId: number, status: string) => {
  await updateFavoriteStatus(seasonId, status as FavoriteStatus)
  ElMessage.success('状态更新成功')
  await loadFavorites()
}

const handleStatusChange = (seasonId: number, value: string | number | boolean) => {
  changeStatus(seasonId, String(value))
}

const removeFavorite = async (seasonId: number) => {
  const response = await toggleFavorite(seasonId)
  if (response.success) {
    ElMessage.success('已取消收藏')
    await loadFavorites()
  }
}

const goToStatus = (title: string) => {
  router.push({ path: '/status', query: { keyword: title } })
}

onMounted(loadFavorites)
</script>

<style scoped>
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.anime-cell {
  display: flex;
  gap: 12px;
  align-items: center;
}

.anime-cell img {
  width: 64px;
  height: 86px;
  object-fit: cover;
  border-radius: 6px;
}

.title {
  font-weight: 600;
}

.meta {
  margin-top: 4px;
  color: #909399;
}
</style>
