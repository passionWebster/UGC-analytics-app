# Bilibili 智能分析平台 v2.0

## 项目概述

Bilibili 智能分析平台 是一个现代化的全栈 Web 应用，提供 B 站番剧数据的深度分析和可视化。

### 🎯 重大架构升级 (v2.0)

本版本进行了完全的架构重构，从混合架构迁移到统一的现代化技术栈：

**旧架构 (v1.x)**:
- 后端: Python Flask + Node.js Express (双服务器)
- 数据库: MySQL + JSON 文件 (rank_cache.json)
- 前端: Vanilla HTML/CSS/JavaScript
- 问题: 多服务器、文件存储、缺乏类型安全

**新架构 (v2.0)**:
- ✅ 后端: **FastAPI** 统一后端
- ✅ 数据库: **SQLite** (替代 MySQL + JSON)
- ✅ 前端: **Vue 3 + TypeScript + Vite + Pinia**
- ✅ 目录结构: 参考企业级最佳实践

## 技术栈

### 后端
- **FastAPI** - 现代化 Python Web 框架
- **SQLModel** - 类型安全的 ORM (SQLAlchemy + Pydantic)
- **SQLite** - 轻量级数据库
- **Uvicorn** - ASGI 服务器
- **Pydantic** - 数据验证
- **python-jose** - JWT 认证

### 前端
- **Vue 3** - 渐进式 JavaScript 框架
- **TypeScript** - 类型安全的 JavaScript
- **Vite** - 下一代前端构建工具
- **Pinia** - Vue 状态管理
- **Element Plus** - Vue 3 UI 组件库
- **Axios** - HTTP 客户端
- **ECharts** - 数据可视化

## 项目结构

```
bilibili-analytics-app/
├── data/                       # 数据存储目录
│   └── bilibili.db            # SQLite 数据库
├── src/
│   ├── backend/               # 后端应用 (FastAPI)
│   │   ├── routers/          # API 路由
│   │   │   ├── analytics.py  # 数据分析 API
│   │   │   ├── auth.py       # 用户认证 API
│   │   │   ├── ai.py         # AI 助手 API
│   │   │   └── crawler.py    # 爬虫控制 API
│   │   ├── services/         # 业务逻辑层
│   │   │   ├── analytics_service.py  # 数据分析服务
│   │   │   ├── auth_service.py       # 认证服务
│   │   │   └── crawler.py            # 爬虫服务
│   │   ├── main.py           # FastAPI 应用入口
│   │   ├── config.py         # 配置中心
│   │   ├── database.py       # 数据库连接
│   │   └── models.py         # 数据模型 (SQLModel)
│   └── frontend/             # 前端应用 (Vue 3)
│       ├── src/
│       │   ├── api/          # API 请求封装
│       │   │   ├── axios.ts
│       │   │   ├── auth.ts
│       │   │   ├── analytics.ts
│       │   │   └── ai.ts
│       │   ├── views/        # 页面组件
│       │   │   ├── Login.vue
│       │   │   ├── Dashboard.vue
│       │   │   ├── GenreSelection.vue
│       │   │   ├── PersonalSpace.vue
│       │   │   └── DataScreen.vue
│       │   ├── stores/       # Pinia 状态管理
│       │   │   ├── auth.ts
│       │   │   └── analytics.ts
│       │   ├── router/       # Vue Router
│       │   ├── App.vue
│       │   └── main.ts
│       ├── vite.config.ts
│       ├── tsconfig.json
│       └── package.json
├── logs/                      # 日志目录
├── requirements-new.txt       # Python 依赖
├── start_services.sh          # 一键启动脚本
├── stop_services.sh           # 停止服务脚本
└── README.md                  # 本文档
```

## 安装和运行

### 环境要求

- Python 3.8+
- Node.js 18+
- npm 或 yarn

### 快速开始

#### 1. 克隆项目

```bash
git clone https://github.com/passionWebster/bilibili-analytics-app.git
cd bilibili-analytics-app
```

#### 2. 一键启动 (推荐)

```bash
./start_services.sh
```

这将自动：
- 创建 Python 虚拟环境
- 安装所有依赖
- 启动后端服务 (端口 8000)
- 启动前端服务 (端口 5173)

#### 3. 访问应用

- 🌐 **前端应用**: http://localhost:5173
- 📖 **API 文档**: http://localhost:8000/api/docs
- 📖 **ReDoc 文档**: http://localhost:8000/api/redoc

#### 4. 停止服务

```bash
./stop_services.sh
```

### 手动启动 (高级)

#### 后端服务

```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements-new.txt

# 启动服务
cd src/backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### 前端服务

```bash
cd src/frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

## 功能特性

### ✅ 已实现

- **用户系统**
  - 用户注册和登录
  - JWT token 认证
  - 用户偏好设置

- **数据管理**
  - 番剧数据爬取 (从 B 站 API)
  - 数据存储到 SQLite 数据库
  - 每日统计数据记录
  - 历史数据追踪

- **数据分析**
  - 数据总览仪表盘
  - 排行榜 (播放量、追番数、评分)
  - 番剧搜索
  - 风格分布统计
  - 发布趋势分析

- **API 接口**
  - RESTful API 设计
  - 自动生成 API 文档 (Swagger/ReDoc)
  - 请求验证和错误处理
  - CORS 跨域支持

- **前端界面**
  - 响应式设计
  - 现代化 UI (Element Plus)
  - 路由守卫和权限控制
  - 状态管理 (Pinia)

### 🚧 开发中

- 数据大屏展示
- 个人空间完整功能
- AI 助手集成 (需要配置 API Key)
- 更多图表和可视化
- 单集播放数据分析

## 数据库设计

### 核心表

1. **users** - 用户表
   - id, username, email, password, preferences, created_at

2. **anime** - 番剧表
   - season_id, title, cover, area, rating, styles, release_date

3. **daily_stats** - 每日统计表
   - id, season_id, date, views, favorites, online_viewers

4. **episode_stats** - 单集统计表
   - id, season_id, episode_title, bvid, cid, views, online_viewers

5. **rankings** - 排行榜表
   - id, season_id, ranking_type, rank_position, date

6. **crawl_logs** - 爬虫日志表
   - id, task_type, status, items_count, error_message, started_at, completed_at

## API 接口

### 认证相关

- `POST /api/register` - 用户注册
- `POST /api/login` - 用户登录
- `GET /api/user-info` - 获取用户信息
- `POST /api/updatePreferences` - 更新偏好设置

### 数据分析

- `GET /api/analytics/animes` - 获取番剧列表
- `GET /api/analytics/animes/{season_id}` - 获取番剧详情
- `GET /api/analytics/search` - 搜索番剧
- `GET /api/analytics/rankings` - 获取排行榜
- `GET /api/analytics/overview` - 获取数据总览
- `GET /api/analytics/animes/{season_id}/history` - 获取历史数据
- `GET /api/analytics/statistics/styles` - 获取风格分布
- `GET /api/analytics/statistics/trends` - 获取发布趋势

### 爬虫控制

- `POST /api/crawler/update` - 触发数据更新
- `GET /api/crawler/status` - 获取爬虫状态
- `GET /api/crawler/search/{title}` - 搜索番剧 ID

### AI 助手

- `GET /api/aiservicestatus` - 获取 AI 服务状态
- `POST /api/chat` - AI 对话

详细 API 文档请访问: http://localhost:8000/api/docs

## 配置说明

### 环境变量 (.env)

在项目根目录创建 `.env` 文件：

```env
# 数据库配置
DATABASE_URL=sqlite:///./data/bilibili.db

# JWT 配置
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# AI 服务配置 (可选)
DOUBAO_API_KEY=your-api-key-here
DOUBAO_API_URL=https://ark.cn-beijing.volces.com/api/v3/chat/completions
```

## 开发指南

### 添加新的 API 端点

1. 在 `src/backend/services/` 添加业务逻辑
2. 在 `src/backend/routers/` 创建新路由
3. 在 `src/backend/main.py` 注册路由
4. 在 `src/frontend/src/api/` 添加对应的 API 调用函数

### 添加新的页面

1. 在 `src/frontend/src/views/` 创建 Vue 组件
2. 在 `src/frontend/src/router/index.ts` 添加路由
3. 如需状态管理，在 `src/frontend/src/stores/` 添加 store

### 数据库迁移

当修改数据模型后，删除 `data/bilibili.db` 文件，重启后端服务会自动重新创建表结构。

## 常见问题

### Q: 启动失败，提示端口被占用？

A: 确保端口 8000 和 5173 没有被其他程序占用。可以修改配置文件中的端口。

### Q: 数据库中没有数据？

A: 首次启动后需要手动触发爬虫：
```bash
curl -X POST http://localhost:8000/api/crawler/update
```

### Q: AI 助手不可用？

A: 需要在 `.env` 文件中配置 `DOUBAO_API_KEY`。

## 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交改动 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

## 开源协议

本项目采用 MIT 协议 - 详见 LICENSE 文件

## 联系方式

- 项目主页: https://github.com/passionWebster/bilibili-analytics-app
- 问题反馈: https://github.com/passionWebster/bilibili-analytics-app/issues

---

⭐ 如果这个项目对你有帮助，请给个 Star 支持一下！
