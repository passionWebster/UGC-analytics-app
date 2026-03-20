// main.ts
/**
 * Vue 应用入口
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

import App from './App.vue'
import router from './router'
import { useUIStore } from './stores/ui'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(ElementPlus)

// 初始化 UI store（恢复主题设置）
const uiStore = useUIStore(pinia)
uiStore.initUI()

app.mount('#app')
