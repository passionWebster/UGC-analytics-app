// router/index.ts
/**
 * Vue Router 配置
 */
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/home'
    },
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/Login.vue')
    },
    {
      path: '/genre-selection',
      name: 'GenreSelection',
      component: () => import('@/views/GenreSelection.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/home',
      name: 'Home',
      component: () => import('@/views/Home.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/status',
      name: 'Status',
      component: () => import('@/views/Status.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/overview',
      name: 'Overview',
      component: () => import('@/views/Overview.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/recommendation',
      name: 'Recommendation',
      component: () => import('@/views/Recommendation.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/personal-space',
      name: 'PersonalSpace',
      component: () => import('@/views/PersonalSpace.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/report',
      name: 'Report',
      component: () => import('@/views/Report.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/admin',
      name: 'Admin',
      redirect: { path: '/personal-space', query: { tab: 'admin' } },
      meta: { requiresAuth: true, requiresAdmin: true }
    }
  ]
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  
  // 需要认证的路由
  if (to.meta.requiresAuth && !authStore.isLoggedIn) {
    next('/login')
  } else if (to.meta.requiresAdmin && !authStore.isAdmin) {
    ElMessage.warning('需要管理员权限')
    next('/home')
  } else if (to.path === '/login' && authStore.isLoggedIn) {
    next('/home')
  } else {
    next()
  }
})

export default router
