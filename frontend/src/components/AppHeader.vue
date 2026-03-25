<template>
  <header class="app-header">
    <div class="container">
      <div class="d-flex justify-content-between align-items-center">
        <!-- Logo 和标题 -->
        <div class="d-flex align-items-center">
          <img 
            alt="B站Logo" 
            class="logo" 
            src="https://www.bilibili.com/favicon.ico"
          />
          <h3 class="mb-0">Bilibili 智能分析平台 · Intelligence Analytics Platform</h3>
        </div>

        <!-- 导航菜单 -->
        <nav class="navbar navbar-expand-lg">
          <ul class="navbar-nav">
            <li class="nav-item">
              <router-link 
                class="nav-link" 
                to="/home"
                active-class="active"
              >
                <i class="fas fa-home me-1"></i>首页
              </router-link>
            </li>
            <li class="nav-item">
              <router-link 
                class="nav-link" 
                to="/status"
                active-class="active"
              >
                <i class="fas fa-search me-1"></i>番剧状态检测
              </router-link>
            </li>
            <li class="nav-item">
              <router-link 
                class="nav-link" 
                to="/overview"
                active-class="active"
              >
                <i class="fas fa-chart-pie me-1"></i>番剧概览
              </router-link>
            </li>
            <li class="nav-item">
              <router-link 
                class="nav-link" 
                to="/recommendation"
                active-class="active"
              >
                <i class="fas fa-star me-1"></i>番剧推荐
              </router-link>
            </li>
            <li class="nav-item">
              <router-link
                class="nav-link"
                to="/report"
                active-class="active"
              >
                <i class="fas fa-file-chart-line me-1"></i>分析报告
              </router-link>
            </li>
          </ul>
        </nav>

        <!-- 用户信息和退出按钮 -->
        <div class="d-flex align-items-center">
          <div class="user-info" @click="goToProfile" style="cursor: pointer">
            <div class="avatar">{{ userInitial }}</div>
            <span class="username">{{ username }}</span>
          </div>
          <button class="btn btn-danger" @click="handleLogout">
            <i class="fas fa-sign-out-alt me-1"></i>退出
          </button>
        </div>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
// AppHeader.vue —— 全局顶部导航栏组件
// 包含：Logo、平台标题、导航菜单（首页/番剧状态检测/番剧概览/番剧推荐）、用户信息、退出登录按钮
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

// 计算用户名首字母（用于头像显示）
const userInitial = computed(() => {
  const name = authStore.user?.username || '用户'
  return name.charAt(0).toUpperCase()
})

// 当前登录用户名
const username = computed(() => {
  return authStore.user?.username || '用户'
})

// 跳转到个人资料页
const goToProfile = () => {
  router.push('/personal-space')
}

// 退出登录并跳转到登录页
const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.app-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 1rem 0;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

.logo {
  width: 40px;
  height: 40px;
  margin-right: 1rem;
}

.app-header h3 {
  color: white;
  font-size: 1.2rem;
}

.navbar-nav {
  display: flex;
  list-style: none;
  margin: 0;
  padding: 0;
  gap: 0.5rem;
}

.nav-link {
  color: rgba(255, 255, 255, 0.8);
  text-decoration: none;
  padding: 0.5rem 1rem;
  border-radius: 5px;
  transition: all 0.3s;
}

.nav-link:hover {
  color: white;
  background: rgba(255, 255, 255, 0.1);
}

.nav-link.active {
  color: white;
  background: rgba(255, 255, 255, 0.2);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-right: 1rem;
  padding: 0.5rem 1rem;
  border-radius: 5px;
  transition: background 0.3s;
}

.user-info:hover {
  background: rgba(255, 255, 255, 0.1);
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  color: white;
}

.username {
  color: white;
  font-weight: 500;
}

.btn-danger {
  background: rgba(220, 53, 69, 0.8);
  border: none;
  transition: background 0.3s;
}

.btn-danger:hover {
  background: rgba(220, 53, 69, 1);
}
</style>
