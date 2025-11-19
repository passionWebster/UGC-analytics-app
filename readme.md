# Bilibili Insights Hub - 使用文档

## 1. 项目概述

Bilibili Insights
Hub是一个全栈Web应用，旨在提供对Bilibili番剧数据的深度分析和可视化。项目前端负责数据展示和用户交互，后端则分为三个部分：一个Python服务器用于数据抓取、处理和定时更新；一个Node.js服务器用于处理用户认证和偏好设置；以及一个独立的Node.js服务器为AI助手提供支持。

## 2. 项目架构

本项目由以下几个核心组件构成：

### Python后端 (`python_server`)

- **核心职责**: 负责所有与B站数据的交互，包括批量抓取番剧排名、获取特定番剧的详细信息、以及定时更新在线观看人数。
- **关键文件**:
  - `data_manager.py`: 数据管理器，用于从B站API批量抓取所有番剧的排名、播放量和追番数据，并生成核心数据文件 `rank_cache.json`。它还可以执行月度数据聚合。
  - `scraper.py`: B站数据抓取器，封装了所有与B站API直接交互的函数，例如根据关键词查找番剧ID、获取分集播放数据等。
  - `app.py`: Flask应用主程序。它提供了多个API接口供前端调用，例如搜索番剧、代理图片请求等。同时，它内置了一个定时任务，会周期性地更新被追踪番剧的在线人数。

### Node.js后端 (`node_server`)

- **核心职责**: 负责用户管理功能和AI助手服务。
- **关键文件**:
  - `server.js`: Express服务器主程序，定义了用户相关的API路由（如 `/api/login`, `/api/register`）。
  - `db.js`: 数据库模块，处理与MySQL数据库的连接和所有用户数据的增删改查操作。
  - `ai-assistant-server.js`: 一个独立的Express服务器，作为AI助手的后端，负责调用豆包AI模型的API并返回结果。

### 前端 (`public`)

- **核心职责**: 作为用户界面，通过图表、列表和卡片等形式将后端提供的数据进行可视化展示。
- **关键页面**:
  - `login.html`: 用户登录和注册的入口。
  - `genre_selection.html`: 新用户首次登录后选择个人番剧偏好的页面。
  - `index.html`: 系统的主仪表盘，包含了数据总览、番剧状态检测和番剧概览三大功能模块。
  - `personal-space.html`: 用户的个人空间，可以查看个人信息和修改番剧偏好。

## 3. 功能特性

- **用户系统**: 支持用户注册、登录、登出，并通过数据库持久化用户信息。
- **个性化偏好**: 新用户可以设置自己感兴趣的番剧类型，系统会根据偏好进行内容推荐。
- **数据总览仪表盘**:
  - 核心指标卡片：展示番剧总数、总播放量、总追番人数等关键数据，并与上月数据进行对比。
  - 可视化图表：包括番剧类型分布饼图和口碑热度分布散点图。
- **排行榜**: 提供按评分、播放量或追番人数排序的Top 10番剧推荐榜，并支持根据用户偏好进行筛选。
- **番剧状态检测**:
  - 用户可按名称搜索特定番剧。
  - 实时抓取或从缓存加载番剧的详细统计数据。
  - 图表化展示单集播放量趋势和用户观看时间段分布。
- **番剧概览分析**:
  - **历年数量变化**: 以折线图展示不同季度的新番数量，并可按类型筛选。
  - **偏好差异分析**: 通过矩形树图展示不同地区（国内、日本、美国）的用户对各类番剧的偏好指数。
  - **口碑热度指数**: 综合评分、播放量和追番数计算出一个指数，并以条形图展示Top 15番剧。
  - **热门风格组合**: 分析最受欢迎的番剧类型“黄金搭档”，并支持点击下钻查看包含该组合的具体番剧列表。
- **AI助手**: 集成了豆包AI模型，用户可以随时打开聊天窗口，询问关于数据解读、系统功能等问题。

## 4. 安装与运行指南

要成功运行此项目，请严格遵循以下步骤：

### 步骤一：环境准备

- 安装 [Node.js](https://nodejs.org/) (推荐LTS版本)
- 安装 [Python](https://www.python.org/) (推荐3.8或更高版本)
- 安装并启动一个 [MySQL](https://www.mysql.com/) 数据库服务。

### 步骤二：数据库设置

1. 连接到您的MySQL服务。

2. 创建一个新的数据库（例如，`blibl`）。

3. 在该数据库中执行以下SQL语句来创建`users`表：

   ```sql
   CREATE TABLE `users` (
     `id` int NOT NULL AUTO_INCREMENT,
     `username` varchar(50) NOT NULL,
     `email` varchar(100) NOT NULL,
     `password` varchar(255) NOT NULL,
     `preferences` json DEFAULT NULL,
     `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
     PRIMARY KEY (`id`),
     UNIQUE KEY `username` (`username`),
     UNIQUE KEY `email` (`email`)
   ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
   ```

4. 修改 `node_server/db.js` 文件，更新数据库连接配置（`host`, `user`, `password`, `database`）。

### 步骤三：后端设置

1. **Python后端**:

   - 进入 `python_server` 目录。

   - 建议创建一个Python虚拟环境。

   - 安装依赖：

     ```bash
     pip install -r requirements.txt
     ```

2. **Node.js后端**:

   - 进入项目根目录。

   - 安装依赖：

     ```bash
     npm install
     ```

### 步骤四：初始化核心数据

这是项目运行的 **前提**。由于大部分前端展示的数据都来源于 `rank_cache.json`，因此必须先生成这个文件。

1. 打开终端，进入 `python_server` 目录。

2. 运行以下命令以抓取B站全站番剧的排名、播放和追番数据：

   ```powershell
   python data_manager.py fetch
   ```

3. 该命令会创建一个名为 `rank_cache.json` 的文件，其中包含了后续分析所需的基础数据。

4. （可选）您可以运行月度聚合命令来生成当月的统计文件：

   ```powershell
   python data_manager.py aggregate
   ```

   这会根据 `rank_cache.json` 的内容计算总播放和总追番，并生成一个如 `rank_fetcher_8th.json` 的文件。

### 步骤五：启动所有服务

项目需要同时运行三个后端服务。为方便起见，项目提供了一个 `run.bat` 批处理文件来一键启动所有服务（仅限Windows）。

- **Windows用户**:

  - 双击根目录下的 `run.bat` 文件。它会自动在新的命令行窗口中分别启动三个服务器。

- **macOS / Linux 用户**:

  - 需要手动打开三个终端窗口。

  - **终端1 (Node.js主服务)**:

    ```bash
    node node_server/server.js
    ```

  - **终端2 (Node.js AI服务)**:

    ```bash
    node node_server/ai-assistant-server.js
    ```

  - **终端3 (Python数据服务)**:

    ```bash
    python python_server/app.py
    ```

### 步骤六：访问前端页面

当所有后端服务都成功运行后，即可访问应用。

1. 打开您的网络浏览器。

2. 访问Node.js主服务器的地址：

   ```http
   http://localhost:3000
   ```

3. 浏览器会自动重定向到 `login.html` 页面。您可以注册一个新账号或使用已有账号登录。

## 5. 技术栈

- **前端**: HTML, CSS, JavaScript, Bootstrap, ECharts
- **后端**:
  - Node.js, Express.js (用户系统 & AI服务)
  - Python, Flask (数据处理 & API)
  - MySQL (数据库)
- **AI模型**: 豆包 (Doubao)

## 6. 文件结构概览

```
.
├── node_server/                # Node.js后端
│   ├── ai-assistant-server.js  # AI助手服务器
│   ├── db.js                   # 数据库连接与操作
│   └── server.js               # 用户系统主服务器
├── public/                     # 前端静态文件
│   ├── *.html                  # HTML页面
│   ├── *.css                   # 样式文件
│   └── *.js                    # 逻辑脚本
├── python_server/              # Python后端
│   ├── app.py                  # Flask主应用和API
│   ├── data_manager.py         # 批量数据抓取与处理
│   ├── scraper.py              # B站API抓取工具
│   ├── rank_cache.json         # (生成) 核心番剧数据缓存
│   └── cache.json              # (生成) 单个番剧详情缓存
├── package.json                # Node.js项目配置
├── requirements.txt            # Python项目依赖
└── run.bat                     # 一键启动脚本 (Windows)
```
