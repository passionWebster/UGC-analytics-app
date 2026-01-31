<template>
  <footer class="app-footer">
    <div class="container">
      <div class="row">
        <div class="col-md-4">
          <h5>关于平台</h5>
          <p>Bilibili 智能分析平台提供专业的番剧数据分析和可视化服务</p>
        </div>
        <div class="col-md-4">
          <h5>快速链接</h5>
          <ul class="footer-links">
            <li><router-link to="/home">首页</router-link></li>
            <li><router-link to="/overview">数据概览</router-link></li>
            <li><router-link to="/recommendation">番剧推荐</router-link></li>
          </ul>
        </div>
        <div class="col-md-4">
          <h5>联系我们</h5>
          <p>
            <i class="fas fa-envelope me-2"></i>support@bilibili-analytics.com<br>
            <i class="fas fa-github me-2"></i>GitHub Repository
          </p>
        </div>
      </div>
      <div class="row mt-3">
        <div class="col text-center">
          <p class="mb-0">&copy; 2026 Bilibili Analytics Platform. All rights reserved.</p>
        </div>
      </div>
    </div>
  </footer>
</template>

<script setup lang="ts">
// Footer 组件不需要额外的逻辑
</script>

<style scoped>
.app-footer {
  background: #2c3e50;
  color: #ecf0f1;
  padding: 3rem 0 1rem;
  margin-top: 4rem;
}

.app-footer h5 {
  color: white;
  font-size: 1.1rem;
  margin-bottom: 1rem;
  font-weight: 600;
}

.app-footer p {
  color: #bdc3c7;
  font-size: 0.9rem;
  line-height: 1.8;
}

.footer-links {
  list-style: none;
  padding: 0;
  margin: 0;
}

.footer-links li {
  margin-bottom: 0.5rem;
}

.footer-links a {
  color: #bdc3c7;
  text-decoration: none;
  transition: color 0.3s;
}

.footer-links a:hover {
  color: white;
}

.app-footer .text-center p {
  color: #95a5a6;
  font-size: 0.85rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}
</style>
