<template>
  <div class="personal-space-container">
    <el-card class="user-header">
      <h2>{{ authStore.user?.username || '用户' }} 的个人空间</h2>
      <p>注册时间：{{ formatDate(authStore.user?.created_at) }}</p>
    </el-card>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="基础设置" name="profile">
        <ProfileSettings />
      </el-tab-pane>
      <el-tab-pane label="内容偏好" name="preferences">
        <PreferenceTags />
      </el-tab-pane>
      <el-tab-pane label="我的追番" name="watchlist">
        <UserWatchlist />
      </el-tab-pane>
      <el-tab-pane label="个人看板" name="stats">
        <PersonalStatsBoard />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import ProfileSettings from '@/components/PersonalSpace/ProfileSettings.vue'
import PreferenceTags from '@/components/PersonalSpace/PreferenceTags.vue'
import UserWatchlist from '@/components/PersonalSpace/UserWatchlist.vue'
import PersonalStatsBoard from '@/components/PersonalSpace/PersonalStatsBoard.vue'

const authStore = useAuthStore()
const activeTab = ref('profile')

const formatDate = (value?: string) => {
  if (!value) return '-'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '-' : date.toLocaleString('zh-CN')
}
</script>

<style scoped>
.personal-space-container {
  display: grid;
  gap: 16px;
}

.user-header h2 {
  margin-bottom: 8px;
}

.user-header p {
  color: #606266;
}
</style>
