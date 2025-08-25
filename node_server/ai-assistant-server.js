const express = require('express');
const axios = require('axios');
const cors = require('cors'); // 添加这行

const app = express();
const port = 3001;

// 添加CORS中间件
app.use(cors()); // 添加这行
app.use(express.json());

// 健康检查端点
app.get('/api/status', (req, res) => {
    res.json({
        status: 'online', timestamp: new Date().toISOString(), version: '1.0.0'
    });
});

// 豆包API配置
const DOUBAO_API_URL = 'https://ark.cn-beijing.volces.com/api/v3/chat/completions';
const API_KEY = '14ff6bd4-93b1-4c48-b9f4-ba7db33089b2';

// 处理AI聊天请求
app.post('/api/chat', async (req, res) => {
    try {
        const {message} = req.body;

        // 构建豆包API请求
        const requestBody = {
            model: "doubao-seed-1-6-250615", messages: [{
                role: "system", content: "你是一个B站数据分析助手，帮助用户理解B站番剧数据、用户行为分析报告和系统使用。"
            }, {
                role: "user", content: message
            }], temperature: 0.7, max_tokens: 500
        };

        // 调用豆包API
        const response = await axios.post(DOUBAO_API_URL, requestBody, {
            headers: {
                'Content-Type': 'application/json', 'Authorization': `Bearer ${API_KEY}`
            }
        });

        // 提取AI回复
        const reply = response.data.choices[0].message.content;

        // 返回响应
        res.json({reply});
    } catch (error) {
        console.error('后端服务错误:', error);
        res.status(500).json({
            error: '服务暂时不可用，请稍后再试'
        });
    }
});

// 启动服务
app.listen(port, () => {
    console.log(`后端服务运行在 http://localhost:${port}`);
});