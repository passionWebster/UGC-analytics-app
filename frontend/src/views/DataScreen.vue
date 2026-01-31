<template>
  <div class="data-screen">
    <h1>数据大屏 - 开发中</h1>
    <el-button @click="goBack">返回首页</el-button>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

const goBack = () => {
  router.push('/dashboard')
}
</script>

<style scoped>
.data-screen {
  padding: 50px;
  text-align: center;
}
</style>
