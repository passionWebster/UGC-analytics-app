# Bilibili 智能分析平台 v2.0

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 项目概述

Bilibili 智能分析平台是一个现代化的全栈 Web 应用，提供 B 站番剧数据的深度分析和可视化。

## 🎯 技术架构

- **后端**: **FastAPI** 统一后端
- **数据库**: **SQLite** 统一数据库
- **前端**: **Vue 3 + TypeScript + Vite + Pinia**

## 📁 项目结构

```
bilibili-analytics-app/
├── .github/                  # GitHub Actions CI/CD 工作流
│
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI 入口点
│   │   ├── config.py         # 配置管理
│   │   ├── database.py       # SQLite 数据库连接
│   │   ├── models.py         # SQLModel 数据模型
│   │   ├── schemas.py        # Pydantic 验证模型
│   │   ├── auth.py           # JWT 认证服务
│   │   ├── crud.py           # 数据库 CRUD 操作
│   │   ├── scraper.py        # B站数据爬虫
│   │   ├── ai_service.py     # AI 聊天服务
│   │   └── routers/          # API 路由
│   │       ├── auth.py       # 认证 API
│   │       ├── analytics.py  # 数据分析 API
│   │       ├── crawler.py    # 爬虫控制 API
│   │       └── ai.py         # AI 助手 API
│   └── requirements.txt      # Python 依赖
│
├── frontend/                 # Vue 3 前端
│   ├── src/
│   │   ├── components/       # 可复用组件
│   │   │   ├── AppHeader.vue # 全局导航栏
│   │   │   ├── AppFooter.vue # 全局页脚
│   │   │   └── AiChat.vue    # AI 聊天助手
│   │   ├── views/            # 页面视图
│   │   │   ├── Login.vue           # 登录页
│   │   │   ├── Home.vue            # 首页 (关键指标)
│   │   │   ├── Status.vue          # 番剧状态检测
│   │   │   ├── Overview.vue        # 数据概览 (ECharts)
│   │   │   ├── Recommendation.vue  # 番剧推荐
│   │   │   ├── GenreSelection.vue  # 偏好选择
│   │   │   ├── PersonalSpace.vue   # 个人空间
│   │   │   └── DataScreen.vue      # 数据大屏
│   │   ├── router/           # Vue Router 配置
│   │   ├── stores/           # Pinia 状态管理
│   │   ├── api/              # API 请求封装
│   │   ├── App.vue           # 根组件
│   │   └── main.ts           # 应用入口
│   ├── package.json
│   └── vite.config.ts
│
├── docs/
│   └── screenshots/          # 应用截图
├── scripts/
│   ├── start.sh              # 一键启动脚本
│   └── stop.sh               # 停止服务脚本
│
├── .env.example              # 环境变量模板
├── .gitignore
├── LICENSE                   # MIT 开源协议
└── README.md                 # 本文档
```

## 🚀 技术栈

### 后端
- **FastAPI** - 现代化 Python Web 框架
- **SQLModel** - 类型安全的 ORM (SQLAlchemy + Pydantic)
- **SQLite** - 轻量级嵌入式数据库
- **Uvicorn** - ASGI 服务器
- **python-jose** - JWT 认证
- **Requests** - HTTP 客户端

### 前端
- **Vue 3** - 渐进式 JavaScript 框架 (Composition API)
- **TypeScript** - 类型安全的 JavaScript 超集
- **Vite** - 下一代前端构建工具
- **Pinia** - Vue 3 官方状态管理
- **Vue Router** - 官方路由管理器
- **Axios** - HTTP 客户端
- **ECharts 5** - 强大的数据可视化库

## 📦 安装和运行

### 环境要求

- **Python**: 3.8+
- **Node.js**: 18+
- **npm**: 8+ 或 yarn

### 快速开始

#### 1. 克隆项目
```bash
git clone <repository-url>
cd bilibili-analytics-app
```

#### 2. 一键启动（推荐）
```bash
chmod +x scripts/start.sh scripts/stop.sh
./scripts/start.sh
```

这将自动：
- 创建 Python 虚拟环境
- 安装后端依赖
- 安装前端依赖
- 启动后端服务 (http://localhost:8000)
- 启动前端服务 (http://localhost:5173)

#### 3. 访问应用
- **前端应用**: http://localhost:5173
- **API 文档**: http://localhost:8000/api/docs
- **ReDoc 文档**: http://localhost:8000/api/redoc

#### 4. 停止服务
```bash
./scripts/stop.sh
```

### 手动启动

#### 后端
```bash
cd backend

# 创建虚拟环境（首次运行）
python3 -m venv ../venv
source ../venv/bin/activate  # Windows: ..\venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 启动服务
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 前端
```bash
cd frontend

# 安装依赖（首次运行）
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build
```

## 🎨 核心功能

### 页面视图

#### 1. Home - 首页
- 关键指标卡片（番剧总数、总播放量、追番人数、收藏占比）
- 热门番剧排行榜（可按评分、播放量、追番人数排序）
- 番剧类型分布图表
- 口碑热度分布图表

#### 2. Status - 番剧状态检测
- 番剧搜索功能
- 统计卡片（追番人数、播放数量、剧集数量、平均播放）
- 播放量趋势图表
- 观看时间分布图表
- 剧集详情表格

#### 3. Overview - 数据概览
- 历年番剧数量变化
- 偏好差异分析
- 口碑热度指数排行
- 热门风格组合分析（树图）

#### 4. Recommendation - 番剧推荐
- 个性化推荐（基于用户偏好）
- 多维度排序（评分、播放量、追番人数）
- 响应式网格布局
- 番剧卡片悬停效果

#### 5. 其他
- **Login** - 用户登录/注册
- **GenreSelection** - 偏好选择
- **PersonalSpace** - 个人空间
- **DataScreen** - 数据大屏

### 组件

#### AppHeader - 全局导航栏
- Logo 和标题
- 导航菜单（首页、状态检测、概览、推荐、数据大屏）
- 用户信息显示
- 退出登录按钮

#### AppFooter - 全局页脚
- 平台简介
- 快速链接
- 联系信息

#### AiChat - AI 聊天助手
- 浮动聊天按钮
- 折叠式聊天窗口
- 与豆包 AI 的实时对话
- 服务状态检测

## 🔧 API 端点

### 认证 API (`/api`)
- `POST /register` - 用户注册
- `POST /login` - 用户登录
- `GET /user/{username}` - 获取用户信息
- `POST /preferences` - 更新用户偏好

### 数据分析 API (`/api/analytics`)
- `GET /animes` - 获取所有番剧
- `GET /animes/{season_id}` - 获取单个番剧详情
- `GET /overview` - 获取概览数据
- `GET /rankings` - 获取排行榜
- `GET /stats/daily` - 获取每日统计
- `GET /trends` - 获取趋势数据
- `GET /distribution` - 获取分布数据
- `GET /recommendations` - 获取推荐

### 爬虫 API (`/api/crawler`)
- `POST /update` - 触发数据更新
- `GET /status` - 获取爬虫状态
- `GET /logs` - 获取爬虫日志

### AI 助手 API (`/api`)
- `GET /aiservicestatus` - 获取 AI 服务状态
- `POST /chat` - 与 AI 对话

## ⚙️ 配置

### 后端配置

复制根目录的 `.env.example` 为 `backend/.env` 并填写真实配置：

```bash
cp .env.example backend/.env
```

> ⚠️ **安全提示**: `backend/.env` 文件已加入 `.gitignore`，请勿将其提交到版本控制。

### 前端配置

`frontend/vite.config.ts` 已配置好代理：
```typescript
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true
    }
  }
}
```

## 📊 数据模型

### User - 用户表
- `id` - 用户 ID
- `username` - 用户名
- `email` - 邮箱
- `password` - 密码（哈希）
- `preferences` - 偏好设置（JSON）
- `created_at` - 创建时间

### Anime - 番剧表
- `season_id` - 番剧 ID
- `title` - 标题
- `cover` - 封面 URL
- `area` - 地区
- `rating` - 评分
- `styles` - 风格标签（JSON）
- `release_date` - 发布日期

### DailyStats - 每日统计表
- `id` - 统计 ID
- `season_id` - 番剧 ID
- `date` - 统计日期
- `views` - 播放量
- `favorites` - 追番人数
- `online_viewers` - 在线观看人数

## 🔒 安全特性

- ✅ JWT Token 认证
- ✅ CORS 跨域配置
- ✅ Pydantic 数据验证
- ✅ SQL 注入防护（ORM）
- ✅ 密码哈希（建议使用 bcrypt）

## 🐛 开发调试

### 查看日志
```bash
# 后端日志
tail -f logs/backend.log

# 前端日志
tail -f logs/frontend.log
```

### 数据库管理
```bash
# SQLite 命令行
sqlite3 data/bilibili.db

# 查看表
.tables

# 查看表结构
.schema anime

# 查询数据
SELECT * FROM anime LIMIT 10;
```

## 📝 待开发功能

- [ ] 用户头像上传
- [ ] 番剧收藏功能
- [ ] 评论系统
- [ ] 数据导出（Excel/CSV）
- [ ] WebSocket 实时更新
- [ ] 移动端适配
- [ ] 国际化 (i18n)
- [ ] Docker 容器化
- [ ] Redis 缓存
- [ ] 单元测试

## 🤝 贡献指南

欢迎贡献！请遵循以下步骤：

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 License

本项目采用 MIT License - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

- [Vue.js](https://vuejs.org/) - 渐进式 JavaScript 框架
- [FastAPI](https://fastapi.tiangolo.com/) - 现代 Python Web 框架
- [ECharts](https://echarts.apache.org/) - 强大的数据可视化库
- [Bilibili API](https://api.bilibili.com/) - B站数据接口

## 📧 联系方式

如有问题或建议，请通过以下方式联系：

- GitHub Issues: [提交问题](https://github.com/passionWebster/bilibili-analytics-app/issues)
- Email: support@bilibili-analytics.com

---

**版本**: v2.0.0  
**最后更新**: 2026-01-31
