// server.js
const express = require('express');
const bodyParser = require('body-parser');
const path = require('path');
const cors = require('cors');
const axios = require('axios');
const {
    authenticateUser,
    registerUser,
    updateUserPreferences,
    getUserInfo,
} = require('./db');
const {resolve} = require("node:path");
require('dotenv').config({path: resolve(__dirname, '..', '.env')});

const app = express();
const port = process.env.NODE_PORT || 3000;
const DOUBAO_API_URL = 'https://ark.cn-beijing.volces.com/api/v3/chat/completions';
const API_KEY = '14ff6bd4-93b1-4c48-b9f4-ba7db33089b2';

// 配置中间件
app.use(cors());
app.use(bodyParser.json());
app.use(express.static(path.join(__dirname, '..', 'public')));
app.use('/cover_cache', express.static(path.join(__dirname, '..', 'cover_cache')));


// 根路径重定向到 login.html
app.get('/', (req, res) => {
    res.redirect('/login.html');
});

// 获取用户信息的API
app.get('/api/user-info', async (req, res) => {
    const username = req.query.username;
    console.log('获取用户信息请求:', username);

    try {
        // 使用 getUserInfo 函数获取用户信息
        const user = await getUserInfo(username);
        if (!user) {
            return res.status(404).json({success: false, message: '用户不存在'});
        }

        // 格式化偏好设置
        let preferences = [];
        if (user.preferences) {
            try {
                preferences = JSON.parse(user.preferences);
            } catch (e) {
                console.error('偏好设置解析失败:', e);
            }
        }

        res.json({
            success: true,
            user: {
                id: user.id,
                username: user.username,
                email: user.email,
                preferences: preferences,
                created_at: user.created_at
            }
        });
    } catch (error) {
        console.error('获取用户信息错误:', error);
        res.status(500).json({success: false, message: '服务器错误'});
    }
});

// 登录API - 合并为一个路由
app.post('/api/login', async (req, res) => {
    console.log('登录请求:', req.body);
    try {
        const user = await authenticateUser(req.body.username, req.body.password);
        if (user) {
            console.log('登录成功:', user.username);

            // 添加日志验证 - 正确位置
            console.log('用户偏好设置:', user.preferences, typeof user.preferences);

            // 检查偏好设置是否为空
            const hasPreferences = user.preferences &&
                user.preferences.trim() !== '' &&
                user.preferences !== 'null' &&
                user.preferences !== '[]';

            res.json({
                success: true,
                message: '登录成功',
                hasPreferences, // 返回偏好设置状态
                preferences: user.preferences // 返回偏好设置数据
            });
        } else {
            console.log('登录失败: 用户名或密码错误');
            res.status(401).json({success: false, message: '用户名或密码错误'});
        }
    } catch (error) {
        console.error('登录错误:', error);
        res.status(500).json({success: false, message: '服务器错误'});
    }
});

// 更新用户偏好设置的API - 保持不变
app.post('/api/updatePreferences', async (req, res) => {
    const {username, preferences} = req.body;
    console.log('更新偏好设置:', username, preferences);

    try {
        await updateUserPreferences(username, preferences);
        console.log('偏好设置更新成功');
        res.json({success: true, message: '偏好设置已保存'});
    } catch (error) {
        console.error('更新偏好设置错误:', error);
        res.status(500).json({success: false, message: '保存偏好设置失败'});
    }
});

// 添加注册API
app.post('/api/register', async (req, res) => {
    const {username, email, password} = req.body;
    console.log('注册请求:', username, email);

    try {
        const userId = await registerUser(username, email, password);
        console.log('注册成功，用户ID:', userId);
        res.json({success: true, message: '注册成功'});
    } catch (error) {
        console.error('注册错误:', error);
        // 处理唯一约束错误
        if (error.message.includes('已存在')) {
            res.status(409).json({success: false, message: error.message});
        } else {
            res.status(500).json({success: false, message: '注册失败'});
        }
    }
});

// AI服务状态API
app.get('/api/aiservicestatus', (req, res) => {
    res.json({
        status: 'online', timestamp: new Date().toISOString(), version: '1.0.0'
    });
});

// 处理AI聊天请求
app.post('/api/chat', async (req, res) => {
    try {
        const {message} = req.body;
        const requestBody = {
            model: "doubao-seed-1-6-250615", messages: [{
                role: "system", content: "你是一个B站数据分析助手，帮助用户理解B站番剧数据、用户行为分析报告和系统使用。"
            }, {
                role: "user", content: message
            }], temperature: 0.7, max_tokens: 500
        };
        const response = await axios.post(DOUBAO_API_URL, requestBody, {
            headers: {
                'Content-Type': 'application/json', 'Authorization': `Bearer ${API_KEY}`
            }
        });
        const reply = response.data.choices[0].message.content;
        res.json({reply});
    } catch (error) {
        console.error('AI 助手服务错误:', error.response ? error.response.data : error.message);
        res.status(500).json({
            error: 'AI 服务暂时不可用，请稍后再试'
        });
    }
});

// 启动服务器
app.listen(port, () => {
    console.log(`服务器运行在 http://localhost:${port}`);
});