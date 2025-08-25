// 使用 DOMContentLoaded 事件确保在HTML文档完全加载和解析后才执行脚本
document.addEventListener('DOMContentLoaded', () => {

    // --- DOM 元素获取 ---
    const assistantBtn = document.getElementById('assistantBtn');
    const chatContainer = document.getElementById('chatContainer');
    const closeChat = document.getElementById('closeChat');
    const messages = document.getElementById('messages');
    const userInput = document.getElementById('userInput');
    const sendBtn = document.getElementById('sendBtn');

    // --- 全局状态变量 ---
    let serviceOnline = false; // 用于跟踪后端服务的连接状态

    // --- 主要函数定义 ---

    /**
     * 异步检查后端服务的健康状态 (/api/status)。
     */
    async function checkServiceStatus() {
        try {
            // 向Node.js后端发送请求
            const response = await fetch('http://localhost:3000/api/status');
            if (response.ok) {
                const data = await response.json();
                serviceOnline = data.status === 'online';
                updateServiceStatus(serviceOnline);
            } else {
                serviceOnline = false;
                updateServiceStatus(false);
            }
        } catch (error) {
            console.error('服务状态检查失败:', error);
            serviceOnline = false;
            updateServiceStatus(false);
        }
    }

    /**
     * 根据服务是否在线，更新聊天窗口的UI状态和提示信息。
     * @param {boolean} isOnline - 服务是否在线。
     */
    function updateServiceStatus(isOnline) {
        // 移除旧的状态消息，防止重复显示
        const existingStatus = document.querySelector('.status-message');
        if (existingStatus) {
            existingStatus.remove();
        }

        const statusMessage = document.createElement('div');
        statusMessage.classList.add('message', 'status-message');

        if (isOnline) {
            // 服务在线时的显示
            statusMessage.innerHTML = `
        <div class="service-status">
          <span class="status-indicator status-online"></span>
          <span>当前服务状态: <strong>已连接</strong></span>
        </div>
      `;
            userInput.disabled = false;
            sendBtn.disabled = false;
            addSampleQuestions(); // 连接成功后显示示例问题
        } else {
            // 服务离线时的显示
            statusMessage.innerHTML = `
        <div class="service-status">
          <span class="status-indicator status-offline"></span>
          <span>当前服务状态: <strong>未连接</strong></span>
        </div>
        <div class="connection-help">
          <h4><i class="fas fa-exclamation-triangle"></i> 服务未连接</h4>
          <p>AI助手服务当前不可用。这可能是因为：</p>
          <ul>
            <li>后端服务未启动</li>
            <li>网络连接问题</li>
            <li>API密钥配置错误</li>
          </ul>
          <p>请联系系统管理员解决此问题。</p>
        </div>
      `;
            userInput.disabled = true;
            sendBtn.disabled = true;
        }

        messages.appendChild(statusMessage);
        scrollToBottom();
    }

    /**
     * 异步函数，将用户输入发送到后端 /api/chat 接口并获取AI的响应。
     * @param {string} prompt - 用户输入的消息。
     * @returns {Promise<string>} AI的回复文本。
     */
    async function getAIResponse(prompt) {
        try {
            const response = await fetch('http://localhost:3001/api/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: prompt})
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `请求失败，状态码：${response.status}`);
            }

            const data = await response.json();
            return data.reply;
        } catch (error) {
            console.error('请求后端服务错误:', error);
            // 抛出一个对用户更友好的错误信息
            throw new Error(`服务暂时不可用，请稍后再试`);
        }
    }

    /**
     * 在聊天窗口中添加一条用户发送的消息。
     * @param {string} message - 消息文本。
     */
    function addUserMessage(message) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', 'user-message');
        messageDiv.textContent = message;
        messages.appendChild(messageDiv);
        scrollToBottom();
    }

    /**
     * 在聊天窗口中添加一条AI回复的消息。
     * @param {string} message - 消息文本。
     */
    function addBotMessage(message) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', 'bot-message');
        messageDiv.textContent = message;
        messages.appendChild(messageDiv);
        scrollToBottom();
    }

    /**
     * 在聊天窗口中添加一条错误提示消息。
     * @param {string} message - 错误信息文本。
     */
    function addErrorMessage(message) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', 'error-message');
        messageDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;
        messages.appendChild(messageDiv);
        scrollToBottom();
    }

    /**
     * 显示“正在输入”的动画效果。
     * @returns {HTMLElement} 指示器DOM元素，方便后续移除。
     */
    function showTypingIndicator() {
        const typingDiv = document.createElement('div');
        typingDiv.classList.add('message', 'bot-message', 'bot-typing');
        typingDiv.innerHTML = `
      <span>豆包正在思考</span>
      <div class="typing-indicator">
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
      </div>
    `;
        messages.appendChild(typingDiv);
        scrollToBottom();
        return typingDiv;
    }

    /**
     * 核心函数：处理发送消息的整个流程。
     */
    async function sendMessage() {
        const message = userInput.value.trim();
        if (message === '') return;

        addUserMessage(message);
        userInput.value = '';
        sendBtn.disabled = true;

        const typingIndicator = showTypingIndicator();

        try {
            const aiResponse = await getAIResponse(message);
            typingIndicator.remove(); // 收到回复后，先移除"正在输入"
            addBotMessage(aiResponse);
        } catch (error) {
            typingIndicator.remove(); // 即使出错也要移除"正在输入"
            addErrorMessage(error.message);
        } finally {
            sendBtn.disabled = false; // 无论成功失败，最后都恢复发送按钮
            userInput.focus(); // 让用户可以继续输入
        }
    }

    /**
     * 在聊天窗口中动态添加可点击的示例问题。
     */
    function addSampleQuestions() {
        if (document.querySelector('.sample-questions-container')) return; // 如果已存在则不重复添加

        const sampleQuestions = [
            "当前最热门的番剧是哪些？",
            "如何查看用户留存率数据？",
            "解释一下弹幕情感分析的结果",
            "生成一份上周的数据简报"
        ];

        const sampleContainer = document.createElement('div');
        sampleContainer.classList.add('sample-questions-container');
        sampleContainer.innerHTML = `
      <p><i class="fas fa-lightbulb"></i> 试试问我：</p>
      <div class="samples-wrapper">
        ${sampleQuestions.map(q => `<div class="sample-question">${q}</div>`).join('')}
      </div>
    `;
        messages.appendChild(sampleContainer);

        // 为每个示例问题添加点击事件
        document.querySelectorAll('.sample-question').forEach(question => {
            question.addEventListener('click', () => {
                userInput.value = question.textContent;
                userInput.focus();
            });
        });
    }

    /**
     * 辅助函数：将聊天记录滚动到底部。
     */
    function scrollToBottom() {
        messages.scrollTop = messages.scrollHeight;
    }

    // --- 事件监听器绑定 ---

    // 打开聊天窗口
    assistantBtn.addEventListener('click', () => {
        chatContainer.classList.add('active');
        // 每次打开时都重新检查一下服务状态
        checkServiceStatus();
    });

    // 关闭聊天窗口
    closeChat.addEventListener('click', () => {
        chatContainer.classList.remove('active');
    });

    // 点击发送按钮
    sendBtn.addEventListener('click', sendMessage);

    // 在输入框按回车键
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });

    // 页面加载完成后，进行初始化
    function initialize() {
        updateServiceStatus(false); // 默认显示未连接
        setTimeout(checkServiceStatus, 1000); // 延迟1秒后开始检查，给后端启动留出时间
    }

    initialize();

});