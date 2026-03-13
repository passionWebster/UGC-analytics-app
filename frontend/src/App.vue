<template>
  <div id="app">
    <!-- 只在非登录页显示 Header -->
    <AppHeader v-if="showLayout" />
    
    <!-- 主内容区 -->
    <main :class="{ 'with-layout': showLayout }">
      <div class="container">
        <router-view />
      </div>
    </main>
    
    <!-- AI 聊天助手 (只在非登录页显示) -->
    <AiChat v-if="showLayout" />
    
    <!-- 只在非登录页显示 Footer -->
    <AppFooter v-if="showLayout" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AppHeader from '@/components/AppHeader.vue'
import AppFooter from '@/components/AppFooter.vue'
import AiChat from '@/components/AiChat.vue'

const route = useRoute()
const authStore = useAuthStore()

// 判断是否显示布局（Header/Footer/AiChat）
const showLayout = computed(() => {
  // 登录页和偏好选择页不显示布局
  return route.path !== '/login' && route.path !== '/genre-selection'
})

// 应用启动时初始化认证状态
onMounted(() => {
  authStore.initAuth()
})
</script>

<style>
/* 全局样式 */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
    'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background: #f5f7fa;
}

#app {
  width: 100%;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

main {
  flex: 1;
}

main.with-layout {
  padding-top: 2rem;
  padding-bottom: 2rem;
}

/* Bootstrap 兼容 */
.container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 1rem;
}

.row {
  display: flex;
  flex-wrap: wrap;
  margin: 0 -0.5rem;
}

.col,
.col-md-3,
.col-md-4,
.col-md-6,
.col-md-8,
.col-md-12 {
  padding: 0 0.5rem;
}

.col-md-3 { width: 25%; }
.col-md-4 { width: 33.333%; }
.col-md-6 { width: 50%; }
.col-md-8 { width: 66.666%; }
.col-md-12 { width: 100%; }

/* 响应式 */
@media (max-width: 768px) {
  .col-md-3,
  .col-md-4,
  .col-md-6,
  .col-md-8 {
    width: 100%;
  }
}

/* 通用卡片样式 */
.card {
  background: white;
  border-radius: 10px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
  transition: transform 0.3s, box-shadow 0.3s;
}

.card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
}

/* 按钮样式 */
.btn {
  padding: 0.5rem 1rem;
  border-radius: 5px;
  border: none;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.3s;
}

.btn-primary {
  background: #667eea;
  color: white;
}

.btn-primary:hover {
  background: #5568d3;
}

.btn-outline-primary {
  background: transparent;
  border: 1px solid #667eea;
  color: #667eea;
}

.btn-outline-primary:hover {
  background: #667eea;
  color: white;
}

/* 工具类 */
.mb-2 { margin-bottom: 0.5rem; }
.mb-3 { margin-bottom: 1rem; }
.mb-4 { margin-bottom: 1.5rem; }
.mt-2 { margin-top: 0.5rem; }
.mt-3 { margin-top: 1rem; }
.me-1 { margin-right: 0.25rem; }
.me-2 { margin-right: 0.5rem; }

.d-flex { display: flex; }
.justify-content-between { justify-content: space-between; }
.align-items-center { align-items: center; }
.text-center { text-align: center; }
.h-100 { height: 100%; }
</style>
