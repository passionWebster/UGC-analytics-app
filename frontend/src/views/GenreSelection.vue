<template>
  <div class="genre-container">
    <div class="genre-box">
      <h2>选择您感兴趣的番剧类型</h2>
      <p class="subtitle">请选择至少 3 个您喜欢的番剧风格</p>

      <div class="genre-grid">
        <div
          v-for="genre in allGenres"
          :key="genre"
          class="genre-item"
          :class="{ selected: selectedGenres.includes(genre) }"
          @click="toggleGenre(genre)"
        >
          {{ genre }}
        </div>
      </div>

      <div class="actions">
        <el-button
          type="primary"
          size="large"
          :disabled="selectedGenres.length < 3"
          :loading="loading"
          @click="handleSubmit"
        >
          确认并开始使用 ({{ selectedGenres.length }}/3)
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const loading = ref(false)
const selectedGenres = ref<string[]>([])

const allGenres = [
  '原创', '漫画改', '小说改', '游戏改', '热血', '穿越', '奇幻', '战斗',
  '搞笑', '日常', '科幻', '萌系', '治愈', '校园', '少儿', '泡面',
  '恋爱', '少女', '魔法', '冒险', '历史', '架空', '机战', '神魔',
  '声控', '运动', '励志', '音乐', '推理', '社团', '智斗', '催泪',
  '美食', '偶像', '乙女', '职场', '动态漫', '玄幻', '武侠', '悬疑', '古风'
]

const toggleGenre = (genre: string) => {
  const index = selectedGenres.value.indexOf(genre)
  if (index > -1) {
    selectedGenres.value.splice(index, 1)
  } else {
    selectedGenres.value.push(genre)
  }
}

const handleSubmit = async () => {
  if (selectedGenres.value.length < 3) {
    ElMessage.warning('请至少选择 3 个番剧类型')
    return
  }

  loading.value = true
  const result = await authStore.updatePreferences(selectedGenres.value)
  loading.value = false

  if (result.success) {
    ElMessage.success('偏好设置已保存')
    router.push('/home')
  } else {
    ElMessage.error('保存失败，请重试')
  }
}
</script>

<style scoped>
.genre-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.genre-box {
  background: white;
  border-radius: 12px;
  padding: 40px;
  width: 100%;
  max-width: 800px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
}

h2 {
  text-align: center;
  color: #333;
  margin-bottom: 10px;
}

.subtitle {
  text-align: center;
  color: #666;
  margin-bottom: 30px;
}

.genre-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: 15px;
  margin-bottom: 30px;
}

.genre-item {
  padding: 15px 20px;
  text-align: center;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
  font-size: 14px;
}

.genre-item:hover {
  border-color: #667eea;
  background: #f0f2ff;
}

.genre-item.selected {
  border-color: #667eea;
  background: #667eea;
  color: white;
}

.actions {
  text-align: center;
}
</style>
