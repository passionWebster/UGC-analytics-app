<template>
  <div class="personal-space-container">
    <div class="personal-space-header">
      <div class="personal-title-group">
        <h3 class="personal-title">{{ authStore.user?.username || '用户' }} 的个人空间</h3>
        <p class="personal-subtitle">
          注册时间：{{ formatDate(authStore.user?.created_at) }}
          <span v-if="authStore.isAdmin" class="admin-badge">管理员模式</span>
        </p>
      </div>
      <ul class="nav nav-pills personal-tabs" role="tablist">
        <li v-for="tab in visibleTabs" :key="tab.id" class="nav-item">
          <button
            class="nav-link"
            role="tab"
            :aria-selected="activeTab === tab.id"
            :class="{ active: activeTab === tab.id }"
            @click="switchTab(tab.id)"
          >
            {{ tab.label }}
          </button>
        </li>
      </ul>
    </div>

    <div class="tab-content">
      <section v-show="activeTab === 'profile'" class="tab-pane">
        <ProfileSettings />
      </section>
      <section v-show="activeTab === 'preferences'" class="tab-pane">
        <PreferenceTags />
      </section>
      <section v-show="activeTab === 'watchlist'" class="tab-pane">
        <UserWatchlist />
      </section>
      <section v-show="activeTab === 'stats'" class="tab-pane">
        <PersonalStatsBoard />
      </section>
      <section v-show="activeTab === 'admin'" class="tab-pane" v-if="authStore.isAdmin">
        <AdminControlPanel />
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import ProfileSettings from '@/components/PersonalSpace/ProfileSettings.vue'
import PreferenceTags from '@/components/PersonalSpace/PreferenceTags.vue'
import UserWatchlist from '@/components/PersonalSpace/UserWatchlist.vue'
import PersonalStatsBoard from '@/components/PersonalSpace/PersonalStatsBoard.vue'
import AdminControlPanel from '@/components/PersonalSpace/AdminControlPanel.vue'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

type PersonalTab = 'profile' | 'preferences' | 'watchlist' | 'stats' | 'admin'
const tabs: Array<{ id: PersonalTab; label: string; adminOnly?: boolean }> = [
  { id: 'profile', label: '基础设置' },
  { id: 'preferences', label: '内容偏好' },
  { id: 'watchlist', label: '我的追番' },
  { id: 'stats', label: '个人看板' },
  { id: 'admin', label: '后台管理', adminOnly: true },
]
const visibleTabs = computed(() => tabs.filter((tab) => !tab.adminOnly || authStore.isAdmin))

const normalizeTab = (queryTab: unknown): PersonalTab => {
  const normalized = Array.isArray(queryTab) ? queryTab[0] : queryTab
  const tab = typeof normalized === 'string' ? normalized : 'profile'
  if (tab === 'admin' && !authStore.isAdmin) return 'profile'
  return (tabs.find((item) => item.id === tab)?.id || 'profile') as PersonalTab
}

const activeTab = ref<PersonalTab>(normalizeTab(route.query.tab))

const switchTab = (tab: PersonalTab) => {
  if (tab === 'admin' && !authStore.isAdmin) return
  activeTab.value = tab
  const query = tab === 'profile' ? {} : { tab }
  router.replace({ path: '/personal-space', query })
}

watch(
  () => route.query.tab,
  (queryTab) => {
    const nextTab = normalizeTab(queryTab)
    if (nextTab !== activeTab.value) {
      activeTab.value = nextTab
    }
  },
)

const formatDate = (value?: string) => {
  if (!value) return '-'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '-' : date.toLocaleString('zh-CN')
}
</script>

<style scoped>
.personal-space-container {
  display: grid;
  gap: 14px;
}

.personal-space-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.9rem;
  padding: 0.95rem 1.1rem;
  border-radius: 12px;
  background: #ffffff;
  border: 1px solid rgba(0, 0, 0, 0.06);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
}

.personal-title-group {
  min-width: 0;
  flex: 1;
}

.personal-title {
  margin: 0 0 0.2rem;
  font-size: 1.15rem;
  font-weight: 700;
  color: #1f2937;
}

.personal-subtitle {
  margin: 0;
  color: #6b7280;
  font-size: 0.88rem;
  line-height: 1.35;
}

.admin-badge {
  display: inline-block;
  margin-left: 8px;
  padding: 2px 8px;
  border-radius: 999px;
  color: #0c4a6e;
  background: rgba(125, 211, 252, 0.4);
  font-size: 0.78rem;
}

.personal-tabs {
  margin: 0;
  padding: 0.25rem;
  gap: 0.45rem;
  border-radius: 12px;
  background: linear-gradient(180deg, #f8fbff 0%, #f1f6ff 100%);
  flex: 1 1 620px;
  max-width: 760px;
  margin-left: auto;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
  list-style: none;
}

.personal-tabs .nav-link {
  width: 100%;
  border-radius: 999px;
  border: none;
  padding: 0.45rem 0.7rem;
  font-size: 0.88rem;
  font-weight: 500;
  color: #334155;
  background: transparent;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.personal-tabs .nav-link.active {
  background: linear-gradient(135deg, #1d4ed8 0%, #0369a1 100%);
  color: #ffffff;
  box-shadow: 0 6px 16px rgba(29, 78, 216, 0.3);
}

.personal-tabs .nav-link:hover:not(.active),
.personal-tabs .nav-link:focus-visible:not(.active) {
  background: rgba(79, 172, 254, 0.14);
  color: #1d4ed8;
}

.personal-tabs .nav-link:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.25);
}

.tab-pane {
  display: block;
}

@media (max-width: 1200px) {
  .personal-space-header {
    flex-wrap: wrap;
  }

  .personal-tabs {
    width: 100%;
    max-width: none;
    margin-left: 0;
  }
}

@media (max-width: 768px) {
  .personal-tabs {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
