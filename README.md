# Bilibili 智能分析平台

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Vue 3](https://img.shields.io/badge/Vue-3.x-4FC08D?logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-5.x-646CFF?logo=vite&logoColor=white)](https://vitejs.dev/)

**一个现代化的 B 站番剧数据分析与可视化全栈 Web 应用。**

[快速开始](#-快速开始) · [核心特性](#-核心特性) · [技术栈](#-技术栈) · [提交 Issue](https://github.com/passionWebster/bilibili-analytics-app/issues)

</div>

---

## 📖 项目简介

**Bilibili 智能分析平台**通过爬取 B 站公开番剧数据，提供多维度的数据可视化分析。用户可以在精美的仪表盘中探索番剧排行、播放趋势、风格分布，并通过内置的 AI 助手获得个性化推荐与解读。

> 解决痛点：B 站官方页面信息分散、无法跨维度对比，本平台将所有数据汇聚一处，通过图表与 AI 一站式呈现洞察。

## ✨ 核心特性

- 📊 **多维数据可视化** — ECharts 驱动，涵盖趋势图、排行榜、树图、分布图等十余种图表类型
- 🤖 **AI 聊天助手** — 集成豆包大模型，支持与番剧数据交互式对话
- 🔍 **番剧状态检测** — 实时查看任意番剧的播放量趋势、剧集详情与观看时间分布
- 🎯 **个性化推荐** — 基于用户偏好标签，多维度排序筛选番剧
- 🔐 **JWT 用户系统** — 注册、登录、个人偏好管理
- 📡 **定时数据同步** — APScheduler 后台自动爬取最新番剧数据
- 🗂️ **数据大屏** — 全屏数据可视化展示模式

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| **前端框架** | Vue 3 (Composition API) + TypeScript |
| **前端构建** | Vite 5 |
| **状态管理** | Pinia |
| **路由** | Vue Router 4 |
| **图表** | Apache ECharts 5 |
| **HTTP 客户端** | Axios |
| **后端框架** | FastAPI |
| **ORM** | SQLModel (SQLAlchemy + Pydantic) |
| **数据库** | SQLite |
| **任务调度** | APScheduler |
| **认证** | JWT (python-jose) |
| **AI 服务** | 豆包大模型 (Ark API) |

## 🚀 快速开始

### 环境要求

- **Python** 3.8+
- **Node.js** 18+
- **npm** 8+

### 1. 克隆项目

```bash
git clone https://github.com/passionWebster/bilibili-analytics-app.git
cd bilibili-analytics-app
```

### 2. 配置环境变量

```bash
cp .env.example backend/.env
```

打开 `backend/.env`，至少修改以下字段：

```env
SECRET_KEY="your-strong-random-secret"   # 用于 JWT 签名，必须修改
DOUBAO_API_KEY="your-doubao-api-key"      # AI 助手功能所需（可选）
DOUBAO_MODEL="your-model-endpoint-id"    # AI 模型端点 ID（可选）
```

> ⚠️ `backend/.env` 已加入 `.gitignore`，切勿提交到版本控制。

### 3. 一键启动（推荐）

```bash
chmod +x scripts/start.sh scripts/stop.sh
./scripts/start.sh
```

脚本将自动完成：创建 Python 虚拟环境 → 安装后端依赖 → 安装前端依赖 → 启动双服务。

### 4. 访问应用

| 服务 | 地址 |
|------|------|
| 前端应用 | http://localhost:5173 |
| 后端 API | http://localhost:8000 |
| Swagger 文档 | http://localhost:8000/api/docs |
| ReDoc 文档 | http://localhost:8000/api/redoc |

### 5. 停止服务

```bash
./scripts/stop.sh
```

### 手动启动

<details>
<summary>点击展开手动启动步骤</summary>

**后端**
```bash
cd backend
python3 -m venv ../venv
source ../venv/bin/activate      # Windows: ..\venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**前端**
```bash
cd frontend
npm install
npm run dev          # 开发模式
npm run build        # 生产构建
```

</details>

## 📋 使用说明

首次访问 http://localhost:5173，通过注册页面创建账号，登录后即可访问完整功能。

**主要页面**

| 页面 | 路径 | 功能 |
|------|------|------|
| 登录 / 注册 | `/login` | 账号管理 |
| 首页 | `/home` | 关键指标卡片、排行榜、类型分布 |
| 状态检测 | `/status` | 搜索番剧，查看播放趋势与剧集详情 |
| 数据概览 | `/overview` | 历年趋势、偏好差异、风格组合树图 |
| 番剧推荐 | `/recommendation` | 基于偏好的个性化推荐列表 |

**触发数据爬取**（需要登录）：在首页或通过 API `POST /api/crawler/update` 手动触发。

**更新 AI 项目知识库**（推荐在代码变更后执行）：

```bash
python scripts/generate_kb.py
```

## 📁 项目结构

```text
bilibili-analytics-app/
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── main.py           # 应用入口 & 中间件
│   │   ├── config.py         # 统一配置管理
│   │   ├── database.py       # SQLite 连接 & 初始化
│   │   ├── models.py         # SQLModel 数据模型
│   │   ├── schemas.py        # Pydantic 请求/响应模型
│   │   ├── auth.py           # JWT 认证服务
│   │   ├── crud.py           # 数据库 CRUD 操作
│   │   ├── scraper.py        # B站数据爬虫
│   │   ├── scheduler.py      # APScheduler 定时任务
│   │   ├── ai_service.py     # 豆包 AI 聊天服务
│   │   └── routers/          # API 路由控制器
│   │       ├── auth.py
│   │       ├── analytics.py
│   │       ├── crawler.py
│   │       └── ai.py
│   └── requirements.txt
│
├── frontend/                 # Vue 3 前端
│   ├── src/
│   │   ├── api/              # Axios 请求封装
│   │   ├── components/       # 公共组件（Header / Footer / AiChat）
│   │   ├── views/            # 页面视图组件
│   │   ├── router/           # Vue Router 配置
│   │   ├── stores/           # Pinia 状态管理
│   │   ├── App.vue
│   │   └── main.ts
│   ├── package.json
│   └── vite.config.ts
│
├── docs/                     # 文档目录
├── scripts/
│   ├── start.sh              # 一键启动脚本
│   └── stop.sh               # 停止服务脚本
│
├── .env.example              # 环境变量模板
├── .gitignore
├── LICENSE
└── README.md
```

## 🗺️ 路线图

- [x] FastAPI + SQLite 统一后端
- [x] Vue 3 + TypeScript + Vite 前端重构
- [x] JWT 用户认证系统
- [x] ECharts 多维数据可视化
- [x] APScheduler 定时数据同步
- [x] 豆包 AI 聊天助手
- [ ] Docker Compose 一键容器化部署
- [ ] 数据导出（Excel / CSV）
- [ ] WebSocket 实时推送
- [ ] 移动端响应式适配
- [ ] 单元测试覆盖
- [ ] Redis 缓存层
- [ ] 国际化 (i18n)

## 🤝 贡献指南

欢迎所有形式的贡献！

1. Fork 本项目
2. 创建特性分支：`git checkout -b feature/your-feature`
3. 提交更改：`git commit -m 'feat: add your feature'`
4. 推送分支：`git push origin feature/your-feature`
5. 提交 Pull Request

请确保代码通过 `npm run build`（前端类型检查）且遵循现有代码风格。

## 📄 License

本项目基于 [MIT License](LICENSE) 开源。

## 📬 联系方式

- **GitHub Issues**: [提交问题或建议](https://github.com/passionWebster/bilibili-analytics-app/issues)
- **GitHub**: [@passionWebster](https://github.com/passionWebster)
