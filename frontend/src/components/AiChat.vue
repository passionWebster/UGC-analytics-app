<template>
  <div class="ai-assistant">
    <!-- 浮动按钮 -->
    <div class="assistant-btn" @click="toggleChat">
      <i class="fas fa-robot"></i>
    </div>

    <!-- 聊天窗口 -->
    <div class="chat-container" :class="{ 'show': isOpen }">
      <div class="chat-header">
        <h3><i class="fas fa-robot"></i> 豆包AI助手</h3>
        <button class="close-btn" @click="toggleChat">
          <i class="fas fa-times"></i>
        </button>
      </div>

      <div class="messages" ref="messagesContainer">
        <!-- 欢迎消息 -->
        <div class="message bot-message">
          您好！我是豆包AI助手，专门为B站分析系统服务。
        </div>
        <div class="message bot-message">
          您可以问我关于番剧数据、用户行为分析、系统使用等问题。我会尽力为您提供帮助！
        </div>

        <!-- 服务状态 -->
        <div class="message status-message" v-if="!serviceAvailable">
          <div class="service-status">
            <span class="status-indicator status-offline"></span>
            <span>当前服务状态: <strong>未连接</strong></span>
          </div>
          <div class="connection-help">
            <h4><i class="fas fa-exclamation-triangle"></i> 服务未连接</h4>
            <p>AI助手服务当前不可用。这可能是因为后端服务未启动或网络连接问题。请联系系统管理员解决此问题。</p>
          </div>
        </div>

        <!-- 聊天消息 -->
        <div 
          v-for="(msg, index) in messages" 
          :key="index"
          class="message"
          :class="msg.role === 'user' ? 'user-message' : 'bot-message'"
        >
          {{ msg.content }}
        </div>

        <!-- 加载中 -->
        <div v-if="isLoading" class="message bot-message">
          <i class="fas fa-spinner fa-spin"></i> 思考中...
        </div>
      </div>

      <div class="input-area">
        <input 
          v-model="userInput" 
          @keyup.enter="sendMessage"
          :disabled="!serviceAvailable || isLoading"
          placeholder="输入您的问题..."
          type="text"
        />
        <button 
          class="send-btn" 
          @click="sendMessage"
          :disabled="!serviceAvailable || isLoading || !userInput.trim()"
        >
          <i class="fas fa-paper-plane"></i>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { chatWithAI, checkAIServiceStatus } from '@/api/ai'

// 状态
const isOpen = ref(false)
const serviceAvailable = ref(false)
const isLoading = ref(false)
const userInput = ref('')
const messages = ref<Array<{ role: string; content: string }>>([])
const messagesContainer = ref<HTMLElement>()

// 切换聊天窗口
const toggleChat = () => {
  isOpen.value = !isOpen.value
}

// 检查服务状态
const checkService = async () => {
  try {
    const status = await checkAIServiceStatus()
    serviceAvailable.value = status.status === 'online'
  } catch (error) {
    serviceAvailable.value = false
  }
}

// 发送消息
const sendMessage = async () => {
  if (!userInput.value.trim() || !serviceAvailable.value || isLoading.value) {
    return
  }

  const message = userInput.value.trim()
  userInput.value = ''

  // 添加用户消息
  messages.value.push({
    role: 'user',
    content: message
  })

  // 滚动到底部
  await nextTick()
  scrollToBottom()

  // 发送请求
  isLoading.value = true
  try {
    const response = await chatWithAI(message)
    messages.value.push({
      role: 'bot',
      content: response.reply
    })
  } catch (error) {
    messages.value.push({
      role: 'bot',
      content: '抱歉，我暂时无法回答您的问题。请稍后再试。'
    })
  } finally {
    isLoading.value = false
    await nextTick()
    scrollToBottom()
  }
}

// 滚动到底部
const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// 初始化
onMounted(() => {
  checkService()
})
</script>

<style scoped>
.ai-assistant {
  position: fixed;
  bottom: 20px;
  right: 20px;
  z-index: 1000;
}

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
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
  transition: all 0.3s;
}

.assistant-btn:hover {
  transform: scale(1.1);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
}

.chat-container {
  position: absolute;
  bottom: 80px;
  right: 0;
  width: 350px;
  height: 500px;
  background: white;
  border-radius: 10px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.2);
  display: none;
  flex-direction: column;
  overflow: hidden;
}

.chat-container.show {
  display: flex;
}

.chat-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
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

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  background: #f8f9fa;
}

.message {
  margin-bottom: 1rem;
  padding: 0.8rem;
  border-radius: 8px;
  max-width: 85%;
}

.user-message {
  background: #667eea;
  color: white;
  margin-left: auto;
  text-align: right;
}

.bot-message {
  background: white;
  color: #333;
  border: 1px solid #e0e0e0;
}

.status-message {
  background: #fff3cd;
  border: 1px solid #ffc107;
  max-width: 100%;
}

.service-status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.status-indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.status-offline {
  background: #dc3545;
}

.connection-help h4 {
  font-size: 0.9rem;
  margin: 0.5rem 0;
  color: #856404;
}

.connection-help p {
  font-size: 0.85rem;
  margin: 0;
  color: #856404;
}

.input-area {
  display: flex;
  padding: 1rem;
  background: white;
  border-top: 1px solid #e0e0e0;
}

.input-area input {
  flex: 1;
  border: 1px solid #ddd;
  border-radius: 20px;
  padding: 0.5rem 1rem;
  outline: none;
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
  transition: background 0.3s;
}

.send-btn:hover:not(:disabled) {
  background: #5568d3;
}

.send-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
}
</style>
