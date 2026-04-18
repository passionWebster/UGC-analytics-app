<template>
  <el-card>
    <template #header>
      <div class="header">
        <span>内容偏好设置</span>
        <el-button type="primary" :loading="loading" @click="savePreferences">保存偏好</el-button>
      </div>
    </template>

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
    <p class="tip">已选择 {{ selectedGenres.length }} 个偏好（建议至少 3 个）</p>
  </el-card>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const loading = ref(false)
const selectedGenres = ref<string[]>([...authStore.preferences])

watch(
  () => authStore.preferences,
  (value) => {
    selectedGenres.value = [...value]
  },
)

const allGenres = [
  '原创', '漫画改', '小说改', '游戏改', '热血', '穿越', '奇幻', '战斗',
  '搞笑', '日常', '科幻', '萌系', '治愈', '校园', '少儿', '泡面',
  '恋爱', '少女', '魔法', '冒险', '历史', '架空', '机战', '神魔',
  '声控', '运动', '励志', '音乐', '推理', '社团', '智斗', '催泪',
  '美食', '偶像', '乙女', '职场', '动态漫', '玄幻', '武侠', '悬疑', '古风',
]

const toggleGenre = (genre: string) => {
  const index = selectedGenres.value.indexOf(genre)
  if (index > -1) {
    selectedGenres.value.splice(index, 1)
  } else {
    selectedGenres.value.push(genre)
  }
}

const savePreferences = async () => {
  loading.value = true
  const result = await authStore.updatePreferences(selectedGenres.value)
  loading.value = false

  if (result.success) {
    ElMessage.success('偏好保存成功')
  } else {
    ElMessage.error('偏好保存失败')
  }
}
</script>

<style scoped>
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.genre-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 12px;
}

.genre-item {
  padding: 10px 12px;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
}

.genre-item:hover {
  border-color: #409eff;
}

.genre-item.selected {
  color: #fff;
  border-color: #409eff;
  background: #409eff;
}

.tip {
  margin-top: 12px;
  color: #606266;
}
</style>
