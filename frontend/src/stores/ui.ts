// stores/ui.ts
/**
 * UI 全局状态管理
 * 管理应用的主题、全局加载状态和通知等 UI 相关状态，
 * 与业务逻辑状态（auth、analytics）严格隔离
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/** 支持的主题类型 */
export type ThemeMode = 'light' | 'dark'

export const useUIStore = defineStore('ui', () => {
  // ── 状态 ──────────────────────────────────────────────────────────────────

  /** 当前主题模式，默认跟随系统偏好 */
  const themeMode = ref<ThemeMode>(
    (localStorage.getItem('theme') as ThemeMode) || 'dark'
  )

  /** 全局加载状态（用于页面级骨架屏或全屏 Loading） */
  const globalLoading = ref<boolean>(false)

  /** 侧边栏折叠状态 */
  const sidebarCollapsed = ref<boolean>(false)

  // ── 计算属性 ──────────────────────────────────────────────────────────────

  /** 是否为暗色主题 */
  const isDark = computed(() => themeMode.value === 'dark')

  // ── 方法 ──────────────────────────────────────────────────────────────────

  /** 切换主题（亮色 ↔ 暗色） */
  const toggleTheme = () => {
    themeMode.value = themeMode.value === 'dark' ? 'light' : 'dark'
    localStorage.setItem('theme', themeMode.value)
    applyTheme()
  }

  /** 设置指定主题 */
  const setTheme = (mode: ThemeMode) => {
    themeMode.value = mode
    localStorage.setItem('theme', mode)
    applyTheme()
  }

  /** 将主题 class 应用到 document.documentElement */
  const applyTheme = () => {
    const html = document.documentElement
    if (themeMode.value === 'dark') {
      html.classList.add('dark')
      html.classList.remove('light')
    } else {
      html.classList.add('light')
      html.classList.remove('dark')
    }
  }

  /** 设置全局加载状态 */
  const setGlobalLoading = (loading: boolean) => {
    globalLoading.value = loading
  }

  /** 切换侧边栏折叠状态 */
  const toggleSidebar = () => {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  /** 初始化：在应用启动时恢复主题设置 */
  const initUI = () => {
    applyTheme()
  }

  return {
    // 状态
    themeMode,
    globalLoading,
    sidebarCollapsed,

    // 计算属性
    isDark,

    // 方法
    toggleTheme,
    setTheme,
    applyTheme,
    setGlobalLoading,
    toggleSidebar,
    initUI,
  }
})
