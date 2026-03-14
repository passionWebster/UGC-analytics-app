<template>
  <div class="ai-assistant">
    <!-- 全局浮动按钮：固定在右下角，点击展开/收起聊天窗口 -->
    <div class="assistant-btn" @click="toggleChat" :title="isOpen ? '收起助手' : '展开助手'">
      <i class="fas fa-robot"></i>
    </div>

    <!-- 聊天窗口：使用 visibility + opacity + transform 实现平滑动画 -->
    <div class="chat-container" :class="{ 'show': isOpen }">
      <div class="chat-header">
        <h3><i class="fas fa-robot"></i> 豆包AI助手</h3>
        <button class="close-btn" @click="toggleChat" title="关闭">
          <i class="fas fa-times"></i>
        </button>
      </div>

      <!-- 消息区域：flex 列布局，overflow-y scroll，新消息出现时自动滚动到底部 -->
      <div class="messages" ref="messagesContainer">
        <!-- 挂载时显示欢迎消息 -->
        <div class="message bot-message">
          您好！我是豆包AI助手，专门为B站分析系统服务。
        </div>
        <div class="message bot-message">
          您可以问我关于番剧数据、用户行为分析、系统使用等问题。我会尽力为您提供帮助！
        </div>

        <!-- 服务在线状态（首次检查完成后才显示，避免闪烁） -->
        <template v-if="serviceStatusChecked">
          <!-- 服务在线 -->
          <div v-if="serviceAvailable" class="message status-message status-online-msg">
            <div class="service-status">
              <span class="status-indicator status-online"></span>
              <span>当前服务状态: <strong>已连接</strong></span>
            </div>
          </div>
          <!-- 服务离线 -->
          <div v-else class="message status-message">
            <div class="service-status">
              <span class="status-indicator status-offline"></span>
              <span>当前服务状态: <strong>未连接</strong></span>
            </div>
            <div class="connection-help">
              <h4><i class="fas fa-exclamation-triangle"></i> 服务未连接</h4>
              <p>AI助手服务当前不可用，可能原因：后端服务未启动或网络连接问题。请联系系统管理员解决此问题。</p>
            </div>
          </div>
        </template>

        <!-- 示例问题：服务在线且尚未开始对话时展示 -->
        <div v-if="sampleQuestionsVisible" class="sample-questions-container">
          <p><i class="fas fa-lightbulb"></i> 试试问我：</p>
          <div class="samples-wrapper">
            <div
              v-for="q in sampleQuestions"
              :key="q"
              class="sample-question"
              @click="fillSampleQuestion(q)"
            >{{ q }}</div>
          </div>
        </div>

        <!-- 聊天消息列表 -->
        <div
          v-for="(msg, index) in messages"
          :key="index"
          class="message"
          :class="{
            'user-message': msg.role === 'user',
            'bot-message': msg.role === 'bot',
            'error-message': msg.role === 'error'
          }"
        >{{ msg.content }}</div>

        <!-- AI 打字指示器：三个跳动圆点，取代简单的"思考中..."文字 -->
        <div v-if="isTyping" class="message bot-message bot-typing">
          <span>豆包正在思考</span>
          <div class="typing-indicator">
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
          </div>
        </div>
      </div>

      <div class="input-area">
        <input
          v-model="userInput"
          @keyup.enter="sendMessage"
          :disabled="!serviceAvailable || isTyping"
          placeholder="输入您的问题..."
          type="text"
        />
        <button
          class="send-btn"
          @click="sendMessage"
          :disabled="!serviceAvailable || isTyping || !userInput.trim()"
        >
          <i class="fas fa-paper-plane"></i>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, watch } from 'vue'
import { chatWithAI, checkAIServiceStatus } from '@/api/ai'

// ——— 状态 ———
const isOpen = ref(false)                          // 聊天窗口是否展开
const serviceAvailable = ref(false)               // 后端 AI 服务是否在线
const serviceStatusChecked = ref(false)           // 是否已完成首次状态检查
const isTyping = ref(false)                       // AI 打字指示器（三个跳动点）
const userInput = ref('')
const messages = ref<Array<{ role: string; content: string }>>([])
const messagesContainer = ref<HTMLElement | null>(null)
const sampleQuestionsVisible = ref(false)         // 服务在线后是否显示示例问题

// 挂载后延迟检查服务的等待时间（给后端启动留出时间，单位毫秒）
const SERVICE_CHECK_DELAY = 1000

// 示例问题列表（服务连接成功后展示）
const sampleQuestions = [
  '当前最热门的番剧是哪些？',
  '如何查看用户留存率数据？',
  '解释一下弹幕情感分析的结果',
  '生成一份上周的数据简报'
]

// 切换聊天窗口；每次打开都重新检查服务状态
const toggleChat = () => {
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    checkService()
  }
}

// 检查后端 AI 服务健康状态
const checkService = async () => {
  try {
    const status = await checkAIServiceStatus()
    serviceAvailable.value = status.status === 'online'
    if (serviceAvailable.value && !sampleQuestionsVisible.value) {
      // 首次在线时显示示例问题
      sampleQuestionsVisible.value = true
    }
  } catch {
    serviceAvailable.value = false
  } finally {
    serviceStatusChecked.value = true
    await nextTick()
    scrollToBottom()
  }
}

// 将示例问题填入输入框
const fillSampleQuestion = (q: string) => {
  userInput.value = q
}

// 发送消息：校验 → 显示用户气泡 → 打字动画 → 请求 AI → 显示回复
const sendMessage = async () => {
  if (!userInput.value.trim() || !serviceAvailable.value || isTyping.value) return

  const message = userInput.value.trim()
  userInput.value = ''

  // 发送第一条消息后隐藏示例问题，保持界面整洁
  sampleQuestionsVisible.value = false

  // 添加用户消息气泡
  messages.value.push({ role: 'user', content: message })
  await nextTick()
  scrollToBottom()

  // 启动打字指示器
  isTyping.value = true
  await nextTick()
  scrollToBottom()

  try {
    const response = await chatWithAI(message)
    messages.value.push({ role: 'bot', content: response.reply })
  } catch {
    // 将错误作为 error 角色消息显示，样式独立于普通 bot 消息
    messages.value.push({ role: 'error', content: '抱歉，我暂时无法回答您的问题。请稍后再试。' })
  } finally {
    isTyping.value = false
    await nextTick()
    scrollToBottom()
  }
}

// 将消息区域滚动到最底部，确保新消息可见
const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// 聊天窗口打开时，也需要滚动到底部（确保最新消息可见）
watch(isOpen, async (newVal) => {
  if (newVal) {
    await nextTick()
    scrollToBottom()
  }
})

// 挂载后延迟 SERVICE_CHECK_DELAY 毫秒检查服务（给后端启动留出时间）
onMounted(() => {
  setTimeout(checkService, SERVICE_CHECK_DELAY)
})
</script>

<style scoped>
/* ——— 容器：固定在右下角，z-index 确保始终覆盖页面其他内容 ——— */
.ai-assistant {
  position: fixed;
  bottom: 20px;
  right: 20px;
  z-index: 1000;
}

/* ——— 浮动按钮：圆形，脉冲动画吸引注意 ——— */
.assistant-btn {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  cursor: pointer;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
  transition: transform 0.3s, box-shadow 0.3s;
  /* 脉冲动画：持续吸引用户注意 */
  animation: pulse 2s infinite;
}

.assistant-btn:hover {
  transform: scale(1.1);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
}

/* ——— 聊天窗口：absolute 定位于按钮上方，通过 visibility + opacity + transform 实现平滑动画 ——— */
.chat-container {
  position: absolute;
  bottom: 80px;
  right: 0;
  width: 350px;
  height: 500px;
  background: white;
  border-radius: 10px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.2);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  /* 默认隐藏状态：不可见、透明、向下偏移 */
  visibility: hidden;
  opacity: 0;
  transform: translateY(20px) scale(0.95);
  pointer-events: none;
  /* 隐藏时：先等 opacity/transform 动画完成，再隐藏 visibility */
  transition: opacity 0.3s ease, transform 0.3s ease, visibility 0s linear 0.3s;
}

/* 展开状态：立即可见，然后执行 opacity/transform 过渡 */
.chat-container.show {
  visibility: visible;
  opacity: 1;
  transform: translateY(0) scale(1);
  pointer-events: auto;
  transition: opacity 0.3s ease, transform 0.3s ease, visibility 0s linear 0s;
}

.chat-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.chat-header h3 {
  margin: 0;
  font-size: 1.1rem;
}

.close-btn {
  background: none;
  border: none;
  color: white;
  font-size: 1.5rem;
  cursor: pointer;
  padding: 0;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 5px;
  transition: background 0.3s;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

/* ——— 消息区域：flex 列布局，overflow-y auto 确保滚动到底部有效 ——— */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  background: #f8f9fa;
  display: flex;
  flex-direction: column;
  gap: 10px;
  /* 平滑滚动体验 */
  scroll-behavior: smooth;
}

/* ——— 消息气泡通用样式 ——— */
.message {
  padding: 0.75rem 1rem;
  border-radius: 18px;
  max-width: 85%;
  font-size: 14px;
  line-height: 1.5;
  animation: fadeIn 0.3s ease;
}

/* 用户消息：右对齐，蓝色背景 */
.user-message {
  background: #667eea;
  color: white;
  margin-left: auto;
  border-bottom-right-radius: 4px;
}

/* AI 回复：左对齐，白色背景 */
.bot-message {
  background: white;
  color: #333;
  border: 1px solid #e0e0e0;
  margin-right: auto;
  border-bottom-left-radius: 4px;
}

/* 错误消息：红色警告样式 */
.error-message {
  background: #ffebee;
  border: 1px solid #ffcdd2;
  color: #c62828;
  margin-right: auto;
  border-bottom-left-radius: 4px;
}

/* 服务状态消息：黄色提示样式 */
.status-message {
  background: #fff3cd;
  border: 1px solid #ffc107;
  max-width: 100%;
  border-radius: 8px;
}

/* 服务在线消息：绿色成功样式 */
.status-online-msg {
  background: #e8f5e9;
  border-color: #c8e6c9;
}

.service-status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

/* 服务状态圆点指示器 */
.status-indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-online {
  background: #4caf50;
}

.status-offline {
  background: #dc3545;
}

.connection-help {
  margin-top: 0.5rem;
}

.connection-help h4 {
  font-size: 0.9rem;
  margin: 0.25rem 0;
  color: #856404;
}

.connection-help p {
  font-size: 0.85rem;
  margin: 0;
  color: #856404;
}

/* ——— 示例问题 ——— */
.sample-questions-container {
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 12px;
  padding: 0.75rem;
  max-width: 100%;
}

.sample-questions-container p {
  margin: 0 0 0.5rem 0;
  font-size: 13px;
  color: #666;
}

.samples-wrapper {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sample-question {
  background: #f5f5f5;
  border: 1px solid #ddd;
  border-radius: 16px;
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s;
}

.sample-question:hover {
  background: #e8eaf6;
  border-color: #667eea;
}

/* ——— AI 打字指示器：三个跳动圆点 ——— */
.bot-typing {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #888;
}

.typing-indicator {
  display: flex;
  gap: 4px;
  align-items: center;
}

.typing-dot {
  width: 8px;
  height: 8px;
  background: #667eea;
  border-radius: 50%;
  animation: bounce 1.5s infinite ease-in-out;
}

/* 错开各点的动画延迟，形成波浪效果 */
.typing-dot:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-dot:nth-child(3) {
  animation-delay: 0.4s;
}

/* ——— 输入区域 ——— */
.input-area {
  display: flex;
  align-items: center;
  padding: 1rem;
  background: white;
  border-top: 1px solid #e0e0e0;
  flex-shrink: 0;
}

.input-area input {
  flex: 1;
  border: 1px solid #ddd;
  border-radius: 20px;
  padding: 0.5rem 1rem;
  outline: none;
  font-size: 14px;
  transition: border-color 0.3s;
}

.input-area input:focus {
  border-color: #667eea;
}

.send-btn {
  background: #667eea;
  color: white;
  border: none;
  border-radius: 50%;
  width: 40px;
  height: 40px;
  margin-left: 0.5rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 0.3s;
}

.send-btn:hover:not(:disabled) {
  background: #5568d3;
}

.send-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
}

/* ——— 动画定义 ——— */

/* 浮动按钮脉冲（吸引用户点击） */
@keyframes pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(102, 126, 234, 0.6);
  }
  70% {
    box-shadow: 0 0 0 12px rgba(102, 126, 234, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(102, 126, 234, 0);
  }
}

/* 消息气泡淡入 */
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 打字圆点上下跳动 */
@keyframes bounce {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-5px);
  }
}

/* ——— 响应式：小屏幕适配 ——— */
@media (max-width: 768px) {
  .chat-container {
    width: 300px;
    height: 420px;
    right: 0;
  }

  .assistant-btn {
    width: 50px;
    height: 50px;
    font-size: 20px;
  }
}
</style>
