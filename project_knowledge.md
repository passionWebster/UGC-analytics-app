# Bilibili Analytics Project Knowledge

本文件由 `scripts/generate_kb.py` 自动生成，用于 AI 助手系统提示词注入。

## 文件清单
- README.md
- backend/app/__init__.py
- backend/app/ai_service.py
- backend/app/analytics.py
- backend/app/auth.py
- backend/app/config.py
- backend/app/crud.py
- backend/app/database.py
- backend/app/logger.py
- backend/app/main.py
- backend/app/models.py
- backend/app/routers/__init__.py
- backend/app/routers/admin.py
- backend/app/routers/ai.py
- backend/app/routers/analytics.py
- backend/app/routers/auth.py
- backend/app/routers/crawler.py
- backend/app/routers/user_space.py
- backend/app/scheduler.py
- backend/app/schemas.py
- backend/app/scraper.py
- backend/app/tmdb_service.py
- backend/requirements.txt
- frontend/env.d.ts
- frontend/package-lock.json
- frontend/package.json
- frontend/src/App.vue
- frontend/src/api/admin.ts
- frontend/src/api/ai.ts
- frontend/src/api/analytics.ts
- frontend/src/api/auth.ts
- frontend/src/api/axios.ts
- frontend/src/api/userSpace.ts
- frontend/src/components/AiChat.vue
- frontend/src/components/AppFooter.vue
- frontend/src/components/AppHeader.vue
- frontend/src/components/PersonalSpace/AdminControlPanel.vue
- frontend/src/components/PersonalSpace/PersonalStatsBoard.vue
- frontend/src/components/PersonalSpace/PreferenceTags.vue
- frontend/src/components/PersonalSpace/ProfileSettings.vue
- frontend/src/components/PersonalSpace/UserWatchlist.vue
- frontend/src/composables/useEcharts.ts
- frontend/src/main.ts
- frontend/src/router/index.ts
- frontend/src/stores/analytics.ts
- frontend/src/stores/auth.ts
- frontend/src/stores/ui.ts
- frontend/src/utils/errorHandling.ts
- frontend/src/utils/imageProxy.ts
- frontend/src/views/GenreSelection.vue
- frontend/src/views/Home.vue
- frontend/src/views/Login.vue
- frontend/src/views/Overview.vue
- frontend/src/views/PersonalSpace.vue
- frontend/src/views/Recommendation.vue
- frontend/src/views/Report.vue
- frontend/src/views/Status.vue
- frontend/tsconfig.json
- frontend/vite.config.ts
- scripts/generate_kb.py

## 文件摘要

### README.md
- 行数: 229
- 字符数: 5451
- 片段:
```
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
-
...[截断]
```

### backend/app/__init__.py
- 行数: 1
- 字符数: 33
- 片段:
```
# Backend package initialization
```

### backend/app/ai_service.py
- 行数: 600
- 字符数: 21738
- 模块说明: AI 助手服务
处理与豆包 AI 的交互，并对相同消息进行 TTL 缓存以减少重复外部调用。

架构说明：
  - _request_api(message, system_prompt)  ← 核心私有方法：鉴权、组包、HTTP 请求、错误处理、TTLCache
  - chat(message, context)                ← 通用问答，system_prompt = B站数据分析助手人设
  - generate_insight(data, cont
- 片段:
```
# ai_service.py
"""
AI 助手服务
处理与豆包 AI 的交互，并对相同消息进行 TTL 缓存以减少重复外部调用。

架构说明：
  - _request_api(message, system_prompt)  ← 核心私有方法：鉴权、组包、HTTP 请求、错误处理、TTLCache
  - chat(message, context)                ← 通用问答，system_prompt = B站数据分析助手人设
  - generate_insight(data, context_hint)  ← Auto-EDA，system_prompt = 资深二次元数据分析师人设
  - text_to_sql(natural_language)         ← Text-to-SQL，system_prompt = SQLite 专家 + Schema

缓存键 = SHA256(message + "||" + system_prompt)，不同人设下相同问题各自独立缓存。
"""
import hashlib
import json
import threading
import time
from pathlib import Path
import requests
from typing import Optional, Dict, Any, Iterator, Tuple
from fastapi import HTTPException
from cachetools import TTLCache

from .config import settings
from .logger import app_logger
from .database import engine
from .models import AITelemetry
from sqlmodel import Session

# ──────────────────────────────────────────────────────────────────────────────
# AI 响应缓存：最多缓存 128 条结果，每条 TTL 10 分钟
# 以 (message, system_prompt) 的 SHA256 摘要为键，确保不同人设下不冲突
# cachetools 不是线程安全的，使用 RLock 保护并发读写
# ──────────────────────────────────────────────────────────────────────────────
_ai_cache: TTLCache = TTLCache(maxsize=128, ttl=600)
_ai_cache_lock = t
...[截断]
```

### backend/app/analytics.py
- 行数: 174
- 字符数: 4356
- 模块说明: NLP 情感分析模块
使用 SnowNLP 对弹幕/评论文本进行中文情感打分，
并提供按番剧聚合情感数据的辅助函数。
- 片段:
```
# analytics.py
"""
NLP 情感分析模块
使用 SnowNLP 对弹幕/评论文本进行中文情感打分，
并提供按番剧聚合情感数据的辅助函数。
"""
from typing import Optional, List, Dict, Any
from sqlmodel import Session, select
from sqlalchemy import func as sa_func

from .models import DanmuRecord, CommentRecord
from .logger import app_logger as logger

# ── SnowNLP 懒加载，避免在 import 阶段引发异常 ──────────────────────────────
try:
    from snownlp import SnowNLP
    _SNOWNLP_AVAILABLE = True
except ImportError:
    _SNOWNLP_AVAILABLE = False
    logger.warning("⚠️ snownlp 未安装，情感分析功能将不可用。请执行 pip install snownlp")


def score_sentiment(text: str) -> Optional[float]:
    """
    对单条中文文本打情感分（SnowNLP）。

    返回值范围 [0, 1]，越接近 1 表示越积极。
    若 SnowNLP 未安装，返回 None。

    Args:
        text: 待分析的中文文本

    Returns:
        情感得分（0~1），失败时返回 None
    """
    if not _SNOWNLP_AVAILABLE:
        return None
    try:
        return float(SnowNLP(text).sentiments)
    except Exception as exc:
```

### backend/app/auth.py
- 行数: 351
- 字符数: 9700
- 模块说明: 用户认证服务
处理用户登录、注册、token 生成等认证相关逻辑
- 片段:
```
# auth.py
"""
用户认证服务
处理用户登录、注册、token 生成等认证相关逻辑
"""
from datetime import datetime, timedelta
from typing import Optional
import secrets
from jose import JWTError, jwt
from sqlmodel import Session, select
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

try:
    import bcrypt as _bcrypt

    if not hasattr(_bcrypt, "__about__") and hasattr(_bcrypt, "__version__"):
        class _BcryptAbout:
            __version__ = _bcrypt.__version__

        _bcrypt.__about__ = _BcryptAbout()  # type: ignore[attr-defined]
except (ImportError, AttributeError):
    pass

from passlib.context import CryptContext

from .models import User
from .schemas import UserCreate, UserLogin, UserResponse
from .config import settings
from .database import get_session

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """用户认证服务类"""
    
    def __init__(self, session: Session):
        self.session = session
```

### backend/app/config.py
- 行数: 76
- 字符数: 2078
- 模块说明: 应用配置中心
统一管理所有配置项，包括数据库、API、爬虫等设置
- 片段:
```
# config.py
"""
应用配置中心
统一管理所有配置项，包括数据库、API、爬虫等设置
"""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """应用配置类"""
    
    # 应用基础配置
    app_name: str = "Bilibili Analytics Platform"
    app_version: str = "2.0.0"
    debug: bool = True
    
    # 服务器配置
    host: str = "0.0.0.0"
    port: int = 8000
    
    # 数据库配置
    database_url: str = "sqlite:///./data/bilibili.db"
    
    # CORS 配置
    cors_origins: list = [
        "http://localhost:5173",  # Vite 默认开发服务器端口
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000"
    ]
    
    # JWT 配置（用于用户认证）
    secret_key: str = "your-secret-key-here-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 天
    
    # B站 API 配置
    bilibili_api_base_url: str = "https://api.bilibili.com"
```

### backend/app/crud.py
- 行数: 1438
- 字符数: 48903
- 模块说明: 数据分析服务
提供各种数据查询和分析功能
- 片段:
```
# crud.py
"""
数据分析服务
提供各种数据查询和分析功能
"""
import json
import math
import random
from itertools import combinations
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlmodel import Session, select, func, and_
from sqlalchemy import desc

from .models import Anime, DailyStats, EpisodeStats, Ranking, TmdbAnimeInfo, RecommendationStrategyConfig


class AnalyticsService:
    """数据分析服务类"""
    
    def __init__(self, session: Session):
        self.session = session

    def _get_recommendation_strategy(self) -> Dict[str, Any]:
        """获取推荐策略配置；无配置时返回默认值。"""
        strategy = self.session.exec(
            select(RecommendationStrategyConfig).order_by(desc(RecommendationStrategyConfig.updated_at)).limit(1)
        ).first()
        if not strategy:
            return {
                "enabled": False,
                "views_weight": 0.35,
                "ai_weight": 0.35,
                "tmdb_weight": 0.2,
                "diversity_weight": 0.1,
            }
        return {
            "enabled": strategy.enabled,
            "views_weight": strategy.views_weight,
            "ai_weight": strategy.ai_weight,
```

### backend/app/database.py
- 行数: 179
- 字符数: 5242
- 模块说明: 数据库连接和会话管理
使用 SQLite 作为数据存储，提供数据库引擎和会话工厂
- 片段:
```
# database.py
"""
数据库连接和会话管理
使用 SQLite 作为数据存储，提供数据库引擎和会话工厂
"""
import os
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import event, text as sa_text
from sqlalchemy.pool import StaticPool
from typing import Generator
from loguru import logger

# 数据库文件路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATABASE_DIR = os.path.join(BASE_DIR, "data")
DATABASE_PATH = os.path.join(DATABASE_DIR, "bilibili.db")

# 确保数据目录存在
os.makedirs(DATABASE_DIR, exist_ok=True)

# SQLite 连接字符串
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# 创建数据库引擎
# check_same_thread=False: 允许多线程访问（仅用于 SQLite）
# poolclass=StaticPool: 使用静态连接池（适合 SQLite）
engine = create_engine(
    DATABASE_URL,
    echo=False,  # 设置为 True 可以看到 SQL 日志
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, _connection_record):
    """
    开启 SQLite WAL 模式，支持读写并发，避免多线程下的数据库锁冲突。
    WAL 模式允许爬虫写入时，其他请求仍能正常读取，消除 'database is locked' 错误。
    """
```

### backend/app/logger.py
- 行数: 87
- 字符数: 2733
- 模块说明: 统一日志配置模块

基于 Loguru 提供全项目的日志管理，包括：
- 标准应用日志（输出到控制台 + 文件）
- 爬虫专属日志（独立绑定，隔离爬虫日志与 Web 服务日志）
- 片段:
```
# logger.py
"""
统一日志配置模块

基于 Loguru 提供全项目的日志管理，包括：
- 标准应用日志（输出到控制台 + 文件）
- 爬虫专属日志（独立绑定，隔离爬虫日志与 Web 服务日志）
"""
import sys
from pathlib import Path
from loguru import logger

# ──────────────────────────────────────────────────────────────────────────────
# 日志目录：固定在项目根目录下的 logs/，与进程工作目录无关
# __file__ = backend/app/logger.py  →  parents[2] = 项目根目录
# ──────────────────────────────────────────────────────────────────────────────
_LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
_LOG_DIR.mkdir(exist_ok=True)

# ──────────────────────────────────────────────────────────────────────────────
# 移除 Loguru 默认 Handler，统一重新配置
# ──────────────────────────────────────────────────────────────────────────────
logger.remove()

# ──────────────────────────────────────────────────────────────────────────────
# Handler 1：控制台输出（标准应用日志，级别 INFO 及以上）
# ──────────────────────────────────────────────────────────────────────────────
logger.add(
    sys.stdout,
    level="INFO",
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    ),
    c
...[截断]
```

### backend/app/main.py
- 行数: 176
- 字符数: 5022
- 模块说明: FastAPI 应用主入口
整合所有路由和中间件，启动应用服务
- 片段:
```
# main.py
"""
FastAPI 应用主入口
整合所有路由和中间件，启动应用服务
"""
import time
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .database import init_database
from .config import settings
from .logger import app_logger
from .routers import auth, analytics, ai, crawler, admin, user_space
from .scheduler import create_scheduler


# 创建 FastAPI 应用实例
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Bilibili 番剧数据分析平台 - 统一的 FastAPI 后端服务",
    docs_url="/api/docs",  # Swagger UI 文档地址
)

# 配置 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────────────────────────────────────
# HTTP 请求日志中间件：记录每条请求的时间、路径、方法、耗时与状态码
# ──────────────────────────────────────────────────────────────────────────────
```

### backend/app/models.py
- 行数: 374
- 字符数: 13277
- 模块说明: 数据模型定义
使用 SQLModel 定义数据库表结构，包括：
- User: 用户表 (替代 MySQL)
- Anime: 番剧基础信息表
- DailyStats: 每日统计数据表
- AnimeStyle: 番剧风格关联表
- 片段:
```
# models.py
"""
数据模型定义
使用 SQLModel 定义数据库表结构，包括：
- User: 用户表 (替代 MySQL)
- Anime: 番剧基础信息表
- DailyStats: 每日统计数据表
- AnimeStyle: 番剧风格关联表
"""
from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship, Column, JSON
from sqlalchemy import UniqueConstraint
from enum import Enum


class AreaEnum(str, Enum):
    """地区枚举"""
    DOMESTIC = "国内"
    JAPAN = "日本"
    USA = "美国"
    OTHER = "其他"


class User(SQLModel, table=True):
    """
    用户表 - 替代原 MySQL users 表
    存储用户认证信息和偏好设置
    """
    __tablename__ = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True, max_length=50)
    email: str = Field(unique=True, index=True, max_length=100)
    password: str = Field(max_length=255)  # 实际应用中应该使用哈希密码
    is_admin: bool = Field(default=False)  # 是否为管理员
    is_active: bool = Field(default=True)  # 账户是否启用/封禁
    preferences: Optional[str] = Field(default=None, sa_column=Column(JSON))  # JSON 字符串存储偏好
    created_at: datetime = Field(default_factory=datetime.now)
```

### backend/app/routers/__init__.py
- 行数: 1
- 字符数: 33
- 片段:
```
# Routers package initialization
```

### backend/app/routers/admin.py
- 行数: 356
- 字符数: 12099
- 模块说明: 后台管理相关 API 路由

提供用户管理、爬虫监控与基础运营看板功能，全部接口均需管理员权限。
- 片段:
```
"""后台管理相关 API 路由

提供用户管理、爬虫监控与基础运营看板功能，全部接口均需管理员权限。
"""
from collections import Counter
import json
from typing import List
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Query
from sqlalchemy import desc, func, case
from sqlmodel import Session, select

from ..auth import AuthService, get_current_admin_user
from ..database import get_session, engine
from ..models import User, CrawlLog, Anime, RecommendationStrategyConfig, AITelemetry
from ..schemas import UserStatusUpdate, ResetPasswordRequest, RecommendationStrategyUpdate
from ..scraper import BilibiliBangumiCrawler
from ..config import settings


router = APIRouter(prefix="/api/admin", tags=["后台管理"])


@router.get("/users", response_model=dict)
def list_users(
    session: Session = Depends(get_session),
    _admin=Depends(get_current_admin_user),
):
    """获取所有用户列表"""
    users: List[User] = session.exec(
        select(User).order_by(desc(User.created_at))
    ).all()

    return {
        "success": True,
        "users": [
            {
                "id": u.id,
                "username": u.username,
```

### backend/app/routers/ai.py
- 行数: 235
- 字符数: 6441
- 模块说明: AI 助手相关的 API 路由
- 片段:
```
# routers/ai.py
"""
AI 助手相关的 API 路由
"""
import re
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text as sa_text
from sqlmodel import Session

from ..ai_service import AIService
from ..database import get_session, engine
from ..analytics import get_sentiment_timeline, get_top_comments

router = APIRouter(prefix="/api", tags=["AI助手"])

# 实例化 AI 服务
ai_service = AIService()

# SQL 语句安全白名单：只允许 SELECT，禁止 DDL / DML
_SAFE_SQL_RE = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
# 检测多语句注入（分号分隔的多条 SQL）
_MULTI_STMT_RE = re.compile(r";(?!\s*$)", re.IGNORECASE)


class ChatMessage(BaseModel):
    """聊天消息模型"""
    message: str


class InsightRequest(BaseModel):
    """Auto-EDA 洞察请求模型"""
    data: Any                            # 图表数据（JSON 可序列化）
    context_hint: Optional[str] = ""    # 可选番剧名称等上下文
```

### backend/app/routers/analytics.py
- 行数: 910
- 字符数: 24727
- 模块说明: 数据分析相关的 API 路由
- 片段:
```
# routers/analytics.py
"""
数据分析相关的 API 路由
"""
import hashlib
import json
import logging
import os
import re
from enum import Enum
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse
import asyncio
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlmodel import Session, select as sql_select

from ..auth import get_current_user
from ..database import get_session
from ..crud import AnalyticsService
from ..models import Anime, TmdbAnimeInfo, User
from ..schemas import (
    EpisodeBehaviorAnalysisResponse,
    LifecycleGrowthResponse,
    CompetitiveLandscapeResponse,
    SeasonalGenreTrendsResponse,
    PersonalizedRecommendationsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["数据分析"])
# 图片代理路由（路径为 /api/image_proxy，与 analytics 路由独立）
proxy_router = APIRouter(prefix="/api", tags=["图片代理"])

# 封面图片本地缓存目录
_COVER_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
```

### backend/app/routers/auth.py
- 行数: 118
- 字符数: 2590
- 模块说明: 用户认证相关的 API 路由
- 片段:
```
# routers/auth.py
"""
用户认证相关的 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..database import get_session
from ..schemas import UserCreate, UserLogin, UserResponse, PreferenceUpdate
from ..auth import AuthService


router = APIRouter(prefix="/api", tags=["认证"])


@router.post("/register", response_model=dict)
def register(user_create: UserCreate, session: Session = Depends(get_session)):
    """
    用户注册
    
    Args:
        user_create: 用户注册信息
        session: 数据库会话
        
    Returns:
        注册成功信息
    """
    auth_service = AuthService(session)
    user = auth_service.register_user(user_create)
    
    return {
        "success": True,
        "message": "注册成功",
        "user": user
    }


@router.post("/login", response_model=dict)
def login(user_login: UserLogin, session: Session = Depends(get_session)):
    """
```

### backend/app/routers/crawler.py
- 行数: 172
- 字符数: 4306
- 模块说明: 爬虫控制相关的 API 路由
- 片段:
```
# routers/crawler.py
"""
爬虫控制相关的 API 路由
"""
from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from sqlmodel import Session

from ..database import get_session, engine
from ..scraper import BilibiliBangumiCrawler
from ..analytics import batch_score_danmaku, batch_score_comments


router = APIRouter(prefix="/api/crawler", tags=["爬虫"])


@router.post("/update", response_model=dict)
def trigger_update(
    background_tasks: BackgroundTasks,
):
    """
    触发数据更新
    
    Args:
        background_tasks: 后台任务
        session: 数据库会话
        
    Returns:
        触发结果
    """
    # 在后台执行爬虫任务（任务内自行创建独立 Session）
    background_tasks.add_task(_run_update_task)
    
    return {
        "success": True,
        "message": "数据更新任务已启动，请稍后查看结果"
    }
```

### backend/app/routers/user_space.py
- 行数: 272
- 字符数: 8375
- 模块说明: 个人空间相关 API 路由
- 片段:
```
"""
个人空间相关 API 路由
"""
import json
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlmodel import Session, select

from ..auth import AuthService, get_current_user
from ..database import get_session
from ..models import Anime, DailyStats, User, UserFavorite
from ..schemas import (
    FavoriteStatusUpdateRequest,
    FavoriteToggleRequest,
    UserPasswordUpdate,
)


router = APIRouter(prefix="/api/user", tags=["个人空间"])
logger = logging.getLogger(__name__)


@router.get("/favorites", response_model=dict)
def get_user_favorites(
    status: str | None = Query(default=None, description="追番状态筛选"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    获取当前登录用户追番列表。
    """
    query = (
        select(UserFavorite, Anime)
        .join(Anime, Anime.season_id == UserFavorite.season_id)
        .where(UserFavorite.user_id == current_user.id)
        .order_by(desc(UserFavorite.created_at))
    )
```

### backend/app/scheduler.py
- 行数: 163
- 字符数: 4428
- 模块说明: 定时任务调度器
使用 APScheduler AsyncIOScheduler 实现：
- 任务 B：每月 1 日凌晨 2:00 生成月度数据快照并存入 SQLite
- 任务 C：每天凌晨 3:00 执行 TMDB 数据批量富集
- 任务 D：每小时第 5 分钟记录剧集在线人数
- 片段:
```
# scheduler.py
"""
定时任务调度器
使用 APScheduler AsyncIOScheduler 实现：
- 任务 B：每月 1 日凌晨 2:00 生成月度数据快照并存入 SQLite
- 任务 C：每天凌晨 3:00 执行 TMDB 数据批量富集
- 任务 D：每小时第 5 分钟记录剧集在线人数
"""
import asyncio
from datetime import datetime

from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger
from sqlmodel import Session, select

from .database import engine
from .models import Anime, DailyStats, MonthlySnapshot


def _task_b_monthly_snapshot():
    """
    任务 B：月度快照聚合。
    统计全量番剧的最新追番数和播放量，写入 MonthlySnapshot 表。
    同一番剧、同一月份若已存在记录则覆盖（upsert）。
    """
    logger.info("🔄 [任务 B] 开始生成月度数据快照...")
    month = datetime.now().strftime("%Y-%m")

    with Session(engine) as session:
        animes = session.exec(select(Anime)).all()

        upserted = 0
        for anime in animes:
            latest_stats = session.exec(
                select(DailyStats)
                .where(DailyStats.season_id == anime.season_id)
                .order_by(DailyStats.date.desc())
                .limit(1)
```

### backend/app/schemas.py
- 行数: 273
- 字符数: 7322
- 模块说明: Pydantic 数据验证模型
定义 API 请求和响应的数据结构
- 片段:
```
# schemas.py
"""
Pydantic 数据验证模型
定义 API 请求和响应的数据结构
"""
import re
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, field_validator


class UserCreate(BaseModel):
    """用户注册请求模型"""
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(max_length=100)
    password: str = Field(min_length=6, max_length=255)


class UserLogin(BaseModel):
    """用户登录请求模型"""
    username: str
    password: str


class UserResponse(BaseModel):
    """用户信息响应模型"""
    id: int
    username: str
    email: str
    is_admin: bool = False
    is_active: bool = True
    preferences: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PreferenceUpdate(BaseModel):
    """偏好设置更新模型"""
```

### backend/app/scraper.py
- 行数: 1378
- 字符数: 53527
- 模块说明: B站数据爬虫服务 - 重构版
将原 scraper.py 和 data_manager.py 的功能整合，数据直接写入 SQLite 数据库
- 片段:
```
# scraper.py
"""
B站数据爬虫服务 - 重构版
将原 scraper.py 和 data_manager.py 的功能整合，数据直接写入 SQLite 数据库
"""
import hashlib
import json
import random
import re
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from functools import reduce
from typing import Tuple, List, Dict, Any, Optional
import requests
from sqlmodel import Session, select
from tqdm import tqdm

from .models import Anime, DailyStats, EpisodeStats, CrawlLog, DanmuRecord, CommentRecord
from .config import settings
from .logger import scraper_logger as logger

# SQLite 写入互斥锁：用于本模块内的爬虫写入操作，防止多线程并发写入时产生数据库锁冲突。
# 注意：此锁仅在当前进程内、且仅对实际获取它的代码路径生效，并不能保证全项目的所有写入都已串行化。
sqlite_write_lock = threading.Lock()


class BilibiliBangumiCrawler:
    """
    B站番剧爬虫类
    负责从 B站 API 抓取数据并存储到 SQLite 数据库
    """
    
    # B站番剧索引API的URL
    BASE_API_URL = "https://api.bilibili.com/pgc/season/index/result"
    
    # 风格映射
    STYLE_MAP = {
        10010: '原创', 10011: '漫画改', 10012: '小说改', 10013: '游戏改', 10102: '特摄',
```

### backend/app/tmdb_service.py
- 行数: 528
- 字符数: 16261
- 模块说明: TMDB API 集成服务

封装与 TMDB（The Movie Database）API 的所有交互逻辑，包括：
- 番剧搜索（标题清洗 + 年份辅助匹配）
- 剧集详情获取（支持多语言降级策略）
- 图片资源获取与优选（背景图、Logo、海报）
- 单部番剧完整富集流程
- 片段:
```
# tmdb_service.py
"""
TMDB API 集成服务

封装与 TMDB（The Movie Database）API 的所有交互逻辑，包括：
- 番剧搜索（标题清洗 + 年份辅助匹配）
- 剧集详情获取（支持多语言降级策略）
- 图片资源获取与优选（背景图、Logo、海报）
- 单部番剧完整富集流程
"""
import asyncio
import json
import re
import threading
from datetime import datetime
from typing import Optional, Dict, List

import httpx
from cachetools import TTLCache
from sqlmodel import Session, select

from .config import settings
from .database import engine
from .logger import app_logger
from .models import Anime, TmdbAnimeInfo

# 全局复用的 TMDB AsyncClient，避免每次调用重复建连与 TLS 握手
_tmdb_async_client: Optional[httpx.AsyncClient] = None
_tmdb_client_lock = asyncio.Lock()

# ──────────────────────────────────────────────────────────────────────────────
# TMDB 响应缓存
#   - search_cache:  搜索结果缓存，最多 256 条，TTL 1 小时
#   - details_cache: 剧集详情缓存，最多 512 条，TTL 6 小时
#   - images_cache:  图片资源缓存，最多 512 条，TTL 24 小时（图片 URL 极少变动）
# cachetools 不是线程安全的；此模块同时被异步 API handler 和 APScheduler
# 线程池任务（_task_c_tmdb_enrichment）访问，因此使用 RLock 保护全部缓存操作
# ──────────────────────────────────────────────────────────────────────────────
_search_cache: TTLCache = TTLCache(maxsize=256, ttl=3600)
_details_cache: TTLCache = TTLCache(maxsize=512, ttl=21600)
```

### backend/requirements.txt
- 行数: 16
- 字符数: 277
- 片段:
```
python-jose~=3.5.0
sqlmodel~=0.0.37
fastapi~=0.135.1
SQLAlchemy~=2.0.48
uvicorn~=0.42.0
pydantic~=2.12.5
httpx~=0.28.1
pydantic-settings~=2.13.1
loguru~=0.7.3
requests~=2.32.5
tqdm~=4.67.3
APScheduler~=3.11.2
cachetools~=7.0.5
snownlp~=0.12.3
passlib[bcrypt]~=1.7.4
bcrypt<4.1
```

### frontend/env.d.ts
- 行数: 7
- 字符数: 186
- 片段:
```
/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}
```

### frontend/package-lock.json
- 行数: 2387
- 字符数: 83611
- 片段:
```
{
  "name": "bilibili-analytics-frontend",
  "version": "2.0.0",
  "lockfileVersion": 3,
  "requires": true,
  "packages": {
    "": {
      "name": "bilibili-analytics-frontend",
      "version": "2.0.0",
      "dependencies": {
        "axios": "1.13.5",
        "dompurify": "^3.4.0",
        "echarts": "^5.5.0",
        "echarts-wordcloud": "^2.1.0",
        "element-plus": "^2.8.0",
        "highlight.js": "^11.11.1",
        "html2pdf.js": "^0.14.0",
        "markdown-it": "^14.1.1",
        "pinia": "^2.2.0",
        "vue": "^3.5.13",
        "vue-router": "^4.4.0"
      },
      "devDependencies": {
        "@vitejs/plugin-vue": "^5.2.1",
        "@vue/tsconfig": "^0.5.1",
        "typescript": "~5.6.2",
        "vite": "^6.0.5",
        "vue-tsc": "^2.1.10"
      }
    },
    "node_modules/@babel/helper-string-parser": {
      "version": "7.27.1",
      "resolved": "https://registry.npmjs.org/@babel/helper-string-parser/-/helper-string-parser-7.27.1.tgz",
      "integrity": "sha512-qMlSxKbpRlAridDExk92nSobyDdpPijUq2DW6oDnUqd0iOGxmQjyqhMIihI9+zv4LPyZdRje2cavWPbCbWm3eA==",
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@b
...[截断]
```

### frontend/package.json
- 行数: 33
- 字符数: 880
- 片段:
```
{
  "name": "bilibili-analytics-frontend",
  "version": "2.0.0",
  "type": "module",
  "private": true,
  "description": "Bilibili Analytics Platform - Vue 3 Frontend",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext .vue,.js,.jsx,.cjs,.mjs,.ts,.tsx,.cts,.mts --fix --ignore-path .gitignore"
  },
  "dependencies": {
    "axios": "1.13.5",
    "dompurify": "^3.4.0",
    "echarts": "^5.5.0",
    "echarts-wordcloud": "^2.1.0",
    "element-plus": "^2.8.0",
    "highlight.js": "^11.11.1",
    "html2pdf.js": "^0.14.0",
    "markdown-it": "^14.1.1",
    "pinia": "^2.2.0",
    "vue": "^3.5.13",
    "vue-router": "^4.4.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.2.1",
    "@vue/tsconfig": "^0.5.1",
    "typescript": "~5.6.2",
    "vite": "^6.0.5",
    "vue-tsc": "^2.1.10"
  }
}
```

### frontend/src/App.vue
- 行数: 174
- 字符数: 3214
- 片段:
```
<template>
  <div id="app">
    <!-- 只在非登录页显示 Header -->
    <AppHeader v-if="showLayout" />
    
    <!-- 主内容区 -->
    <main :class="{ 'with-layout': showLayout }">
      <div class="container">
        <KeepAlive include="StatusView">
          <router-view />
        </KeepAlive>
      </div>
    </main>
    
    <!-- AI 聊天助手 (只在非登录页显示) -->
    <AiChat v-if="showLayout" />
    
    <!-- 只在非登录页显示 Footer -->
    <AppFooter v-if="showLayout" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AppHeader from '@/components/AppHeader.vue'
import AppFooter from '@/components/AppFooter.vue'
import AiChat from '@/components/AiChat.vue'

const route = useRoute()
const authStore = useAuthStore()

// 判断是否显示布局（Header/Footer/AiChat）
const showLayout = computed(() => {
  // 登录页和偏好选择页不显示布局
  return route.path !== '/login' && route.path !== '/genre-selection'
})

// 应用启动时初始化认证状态
```

### frontend/src/api/admin.ts
- 行数: 71
- 字符数: 1880
- 片段:
```
// api/admin.ts
/**
 * 后台管理接口
 */
import apiClient from './axios'

export interface AdminUser {
  id: number
  username: string
  email: string
  is_admin: boolean
  is_active: boolean
  created_at: string
}

export const fetchUsers = async (): Promise<{ success: boolean; users: AdminUser[] }> => {
  return apiClient.get('/admin/users')
}

export const updateUserStatus = async (
  userId: number,
  isActive: boolean
): Promise<{ success: boolean; is_active: boolean }> => {
  return apiClient.patch(`/admin/users/${userId}/status`, { is_active: isActive })
}

export const resetUserPassword = async (
  userId: number,
  newPassword: string
): Promise<{ success: boolean }> => {
  return apiClient.post(`/admin/users/${userId}/reset-password`, { new_password: newPassword })
}

export const fetchOverview = async (): Promise<any> => {
  return apiClient.get('/admin/overview')
}

export const fetchCrawlerLogs = async (limit = 20): Promise<any> => {
  return apiClient.get('/admin/crawler/logs', { params: { limit } })
}
```

### frontend/src/api/ai.ts
- 行数: 207
- 字符数: 4741
- 片段:
```
// api/ai.ts
/**
 * AI 助手相关 API
 */
import apiClient from './axios'

export interface ChatMessage {
  message: string
}

export interface ChatResponse {
  success: boolean
  reply: string
}

export interface AIServiceStatus {
  status: string
  configured: boolean
  model: string
}

export interface InsightRequest {
  data: unknown
  context_hint?: string
}

export interface InsightResponse {
  success: boolean
  insight: string
}

export interface TextToSQLRequest {
  query: string
  schema_hint?: string
}

export interface TextToSQLResponse {
  success: boolean
  sql: string
  columns: string[]
```

### frontend/src/api/analytics.ts
- 行数: 526
- 字符数: 13495
- 片段:
```
// api/analytics.ts
/**
 * 数据分析相关 API
 */
import apiClient from './axios'

export const AREA_VALUES = ['国内', '日本', '美国'] as const
export type AreaValue = typeof AREA_VALUES[number]

/**
 * 季节枚举值（后端约定）：
 * spring=4-6月, summer=7-9月, autumn=10-12月, winter=1-3月
 */
export const SEASON_VALUES = ['spring', 'summer', 'autumn', 'winter'] as const
export type SeasonValue = typeof SEASON_VALUES[number]

export interface AnimeData {
  season_id: number
  title: string
  cover: string
  area: string
  rating: number | null
  styles: string[]
  release_date: string
  views: number
  favorites: number
  explainability?: {
    jaccard_similarity: number
    combo_bonus_score: number
    reasoning: string
  }
}

export interface AnimeListResponse {
  success: boolean
  total: number
  list: AnimeData[]
}

/** TMDB 扩展信息 */
```

### frontend/src/api/auth.ts
- 行数: 75
- 字符数: 1432
- 片段:
```
// api/auth.ts
/**
 * 用户认证相关 API
 */
import apiClient from './axios'

export interface UserLoginData {
  username: string
  password: string
}

export interface UserRegisterData {
  username: string
  email: string
  password: string
}

export interface LoginResponse {
  success: boolean
  message: string
  access_token: string
  token_type: string
  hasPreferences: boolean
  preferences: string | null
  user: {
    id: number
    username: string
    email: string
    is_admin: boolean
    is_active: boolean
    preferences: string | null
    created_at: string
  }
}

export interface UserInfoResponse {
  success: boolean
  user: {
    id: number
    username: string
```

### frontend/src/api/axios.ts
- 行数: 66
- 字符数: 1674
- 片段:
```
// api/axios.ts
/**
 * Axios 配置和拦截器
 * 统一管理 HTTP 请求，包含：
 * - 自动注入 JWT Token
 * - 全局错误处理（500 弹出错误消息，401 自动跳转登录页）
 */
import axios, { type AxiosInstance, type AxiosResponse, type AxiosError } from 'axios'
import { ElMessage } from 'element-plus'

// 创建 Axios 实例
const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器：自动注入 JWT Token
apiClient.interceptors.request.use(
  (config) => {
    // 从 localStorage 获取 token 并注入到 Authorization 请求头
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器：统一处理响应与错误
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    return response.data
  },
  (error: AxiosError) => {
```

### frontend/src/api/userSpace.ts
- 行数: 64
- 字符数: 1845
- 片段:
```
import apiClient from './axios'

export type FavoriteStatus = 'watching' | 'plan' | 'completed'

export interface UserFavoriteItem {
  id: number
  season_id: number
  title: string
  cover: string | null
  status: FavoriteStatus
  rating: number | null
  created_at: string
}

export interface UserFavoritesResponse {
  success: boolean
  total: number
  data: UserFavoriteItem[]
}

export interface UserSpaceAnalyticsResponse {
  success: boolean
  data: {
    watchlist_count: number
    status_distribution: Record<FavoriteStatus, number>
    genre_distribution: Array<{ genre: string; count: number }>
    weekly_views_summary: {
      latest_views_total: number
      week_ago_views_total: number
      weekly_growth: number
      weekly_growth_rate: number | null
    }
  }
}

export const getUserFavorites = async (status?: FavoriteStatus): Promise<UserFavoritesResponse> => {
  const params = status ? { status } : undefined
  return apiClient.get('/user/favorites', { params })
}
```

### frontend/src/components/AiChat.vue
- 行数: 935
- 字符数: 21038
- 片段:
```
<template>
  <div class="ai-assistant">
    <!-- 全局浮动按钮：固定在右下角，点击展开/收起聊天窗口 -->
    <div class="assistant-btn" @click="toggleChat" :title="isOpen ? '收起助手' : '展开助手'">
      <img :src="aiAvatar" class="assistant-btn-avatar" alt="AI助手" />
    </div>

    <!-- 聊天窗口：使用 visibility + opacity + transform 实现平滑动画 -->
    <div class="chat-container" :class="{ 'show': isOpen }">
      <div class="chat-header">
        <h3>
          <img :src="aiAvatar" class="header-ai-avatar" alt="AI助手" />
          AI助手
        </h3>
        <div class="header-tabs">
          <button
            class="tab-btn"
            :class="{ active: mode === 'chat' }"
            @click="mode = 'chat'"
            title="普通问答"
          >普通问答</button>
          <button
            class="tab-btn"
            :class="{ active: mode === 'sql' }"
            @click="mode = 'sql'"
            title="数据查询 Text-to-SQL"
          >数据查询</button>
        </div>
        <button class="close-btn" @click="toggleChat" title="关闭">
          <i class="fas fa-times"></i>
        </button>
      </div>

      <!-- 消息区域：flex 列布局，overflow-y scroll，新消息出现时自动滚动到底部 -->
      <div class="messages" ref="messagesContainer">
        <!-- 挂载时显
...[截断]
```

### frontend/src/components/AppFooter.vue
- 行数: 87
- 字符数: 1886
- 片段:
```
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
            <li><router-link to="/status">番剧状态检测</router-link></li>
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
// AppFooter.vue —— 全局底部组件
// 包含：平台简介、快速链接（首页/番剧状态检测/数据概览/番剧推荐）、联系方式
</script>

<style
...[截断]
```

### frontend/src/components/AppHeader.vue
- 行数: 199
- 字符数: 4542
- 片段:
```
<template>
  <header class="app-header">
    <div class="container">
      <div class="d-flex justify-content-between align-items-center">
        <!-- Logo 和标题 -->
        <div class="d-flex align-items-center">
          <img 
            alt="B站Logo" 
            class="logo" 
            src="https://www.bilibili.com/favicon.ico"
          />
          <h3 class="mb-0">Bilibili 智能分析平台 · Intelligence Analytics Platform</h3>
        </div>

        <!-- 导航菜单 -->
        <nav class="navbar navbar-expand-lg">
          <ul class="navbar-nav">
            <li class="nav-item">
              <router-link 
                class="nav-link" 
                to="/home"
                active-class="active"
              >
                <i class="fas fa-home me-1"></i>首页
              </router-link>
            </li>
            <li class="nav-item">
              <router-link 
                class="nav-link" 
                to="/status"
                active-class="active"
              >
                <i class="fas fa-search me-1"></i>番剧状态检测
              </router-link>
            </li>
            <li class="nav-item">
              <router-link 
                class="nav-link
...[截断]
```

### frontend/src/components/PersonalSpace/AdminControlPanel.vue
- 行数: 585
- 字符数: 16812
- 片段:
```
<template>
  <div class="admin-panel">
    <div class="admin-header">
      <div class="admin-title-group">
        <h3 class="admin-title">运营控制台</h3>
        <p class="admin-subtitle">面向管理员的数据治理与监控中心</p>
      </div>
      <ul class="nav nav-pills admin-tabs" role="tablist">
        <li v-for="tab in tabs" :key="tab.id" class="nav-item">
          <button
            class="nav-link"
            :class="{ active: activeMenu === tab.id }"
            role="tab"
            :aria-selected="activeMenu === tab.id"
            @click="switchTab(tab.id)"
          >
            {{ tab.label }}
          </button>
        </li>
      </ul>
    </div>

    <div class="style-unified">
      <div class="card-header-unified">
        <h5>{{ currentTabTitle }}</h5>
        <div class="section-actions" v-if="activeMenu === 'users'">
          <el-button :loading="loadingUsers" type="primary" @click="loadUsers">刷新列表</el-button>
        </div>
        <div class="section-actions" v-else-if="activeMenu === 'crawler'">
          <el-button type="primary" :loading="triggeringUpdate" @click="triggerUpdate">
            手动更新热门番剧
          </el-button>
          <el-button :loading="loadingCrawler" @c
...[截断]
```

### frontend/src/components/PersonalSpace/PersonalStatsBoard.vue
- 行数: 173
- 字符数: 4291
- 片段:
```
<template>
  <div class="stats-board" v-loading="loading">
    <el-alert
      v-if="errorMessage"
      :title="errorMessage"
      type="error"
      show-icon
      :closable="false"
    />
    <template v-else-if="data">
      <el-card>
        <template #header>
          <span>本周追番播放量增长</span>
        </template>
        <div class="summary">
          <div class="item">
            <label>当前总播放量</label>
            <strong>{{ formatNumber(data.weekly_views_summary.latest_views_total) }}</strong>
          </div>
          <div class="item">
            <label>7天前总播放量</label>
            <strong>{{ formatNumber(data.weekly_views_summary.week_ago_views_total) }}</strong>
          </div>
          <div class="item">
            <label>本周增长</label>
            <strong>
              {{ formatNumber(data.weekly_views_summary.weekly_growth) }}
              <span v-if="data.weekly_views_summary.weekly_growth_rate !== null">
                ({{ data.weekly_views_summary.weekly_growth_rate }}%)
              </span>
            </strong>
          </div>
        </div>
      </el-card>

      <div class="charts">
        <el-card>
          <template #header><span>追番状态占比</span></te
...[截断]
```

### frontend/src/components/PersonalSpace/PreferenceTags.vue
- 行数: 107
- 字符数: 2291
- 片段:
```
<template>
  <el-card>
    <template #header>
      <div class="header">
        <span>内容偏好设置</span>
        <el-button type="primary" :loading="loading" @click="savePreferences">保存偏好</el-button>
      </div>
    </template>

    <div class="genre-grid">
      <div
        v-for="genre in allGenres"
        :key="genre"
        class="genre-item"
        :class="{ selected: selectedGenres.includes(genre) }"
        @click="toggleGenre(genre)"
      >
        {{ genre }}
      </div>
    </div>
    <p class="tip">已选择 {{ selectedGenres.length }} 个偏好（建议至少 3 个）</p>
  </el-card>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const loading = ref(false)
const selectedGenres = ref<string[]>([...authStore.preferences])

watch(
  () => authStore.preferences,
  (value) => {
    selectedGenres.value = [...value]
  },
)
```

### frontend/src/components/PersonalSpace/ProfileSettings.vue
- 行数: 119
- 字符数: 3614
- 片段:
```
<template>
  <div class="profile-settings">
    <el-card class="info-card">
      <template #header>
        <span>基础信息</span>
      </template>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="用户名">{{ authStore.user.username }}</el-descriptions-item>
        <el-descriptions-item label="邮箱">{{ authStore.user.email || '-' }}</el-descriptions-item>
        <el-descriptions-item label="注册时间">{{ formatDate(authStore.user.created_at) }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card class="password-card">
      <template #header>
        <span>修改密码</span>
      </template>
      <el-form ref="passwordFormRef" :model="passwordForm" :rules="rules" label-width="90px">
        <el-form-item label="旧密码" prop="oldPassword">
          <el-input v-model="passwordForm.oldPassword" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码" prop="newPassword">
          <el-input v-model="passwordForm.newPassword" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input v-model="passwordForm.confirmPassword" type="password" sho
...[截断]
```

### frontend/src/components/PersonalSpace/UserWatchlist.vue
- 行数: 144
- 字符数: 3767
- 片段:
```
<template>
  <el-card>
    <template #header>
      <div class="header">
        <span>我的追番库</span>
        <el-button @click="loadFavorites">刷新</el-button>
      </div>
    </template>

    <el-tabs v-model="activeStatus" @tab-change="loadFavorites">
      <el-tab-pane label="全部" name="all" />
      <el-tab-pane label="想看" name="plan" />
      <el-tab-pane label="在看" name="watching" />
      <el-tab-pane label="看过" name="completed" />
    </el-tabs>

    <el-table v-loading="loading" :data="favorites" empty-text="暂无追番记录">
      <el-table-column label="番剧" min-width="260">
        <template #default="{ row }">
          <div class="anime-cell">
            <img v-if="row.cover" :src="getProxiedUrl(row.cover, row.title, row.season_id)" :alt="row.title" />
            <div>
              <div class="title">{{ row.title }}</div>
              <div class="meta">评分：{{ row.rating ?? '-' }}</div>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="150">
        <template #default="{ row }">
          <el-select
            :model-value="row.status"
            size="small"
            @change="handleStatusChange(row.sea
...[截断]
```

### frontend/src/composables/useEcharts.ts
- 行数: 91
- 字符数: 2269
- 片段:
```
// composables/useEcharts.ts
/**
 * 通用 ECharts 组合式函数
 *
 * 封装图表初始化、配置更新、加载状态及自动自适应逻辑：
 * - 使用 ResizeObserver 监听容器尺寸变化，自动调用 chart.resize()
 * - 在组件卸载时自动断开观察器并销毁图表实例，防止内存泄漏
 *
 * 使用方式：
 * ```ts
 * const { chartRef, initChart, setOption } = useEcharts()
 * // 模板中：<div ref="chartRef" style="height:400px"></div>
 * // 挂载后：initChart(option)
 * ```
 */
import { ref, onUnmounted, shallowRef } from 'vue'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'

export function useEcharts() {
  /** 绑定到图表容器 DOM 元素的模板 ref */
  const chartRef = ref<HTMLElement | null>(null)
  /** ECharts 实例（使用 shallowRef 避免深度响应式代理影响性能） */
  const chartInstance = shallowRef<echarts.ECharts | null>(null)
  /** 用于自适应容器尺寸的 ResizeObserver */
  let resizeObserver: ResizeObserver | null = null

  /**
   * 初始化图表并应用初始配置项。
   * 若容器元素已有旧实例，先销毁再重新初始化。
   *
   * @param option - 初始 ECharts 配置项
   */
  const initChart = (option: EChartsOption) => {
    if (!chartRef.value) return

    // 先断开并清理旧的 ResizeObserver，防止多次调用 initChart 时累积监听器
    if (resizeObserver) {
      resizeObserver.disconnect()
      resizeObserver = null
```

### frontend/src/main.ts
- 行数: 25
- 字符数: 479
- 片段:
```
// main.ts
/**
 * Vue 应用入口
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

import App from './App.vue'
import router from './router'
import { useUIStore } from './stores/ui'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(ElementPlus)

// 初始化 UI store（恢复主题设置）
const uiStore = useUIStore(pinia)
uiStore.initUI()

app.mount('#app')
```

### frontend/src/router/index.ts
- 行数: 89
- 字符数: 2173
- 片段:
```
// router/index.ts
/**
 * Vue Router 配置
 */
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/home'
    },
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/Login.vue')
    },
    {
      path: '/genre-selection',
      name: 'GenreSelection',
      component: () => import('@/views/GenreSelection.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/home',
      name: 'Home',
      component: () => import('@/views/Home.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/status',
      name: 'Status',
      component: () => import('@/views/Status.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/overview',
```

### frontend/src/stores/analytics.ts
- 行数: 160
- 字符数: 3635
- 片段:
```
// stores/analytics.ts
/**
 * 数据分析状态管理
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as analyticsAPI from '@/api/analytics'
import type { AnimeData, StatisticsOverview } from '@/api/analytics'

export const useAnalyticsStore = defineStore('analytics', () => {
  // 状态
  const animeList = ref<AnimeData[]>([])
  const currentAnime = ref<AnimeData | null>(null)
  const overview = ref<StatisticsOverview | null>(null)
  const loading = ref<boolean>(false)

  // 获取番剧列表
  const fetchAnimes = async (limit?: number, offset?: number) => {
    loading.value = true
    try {
      const response = await analyticsAPI.getAnimes(limit, offset)
      if (response.success) {
        animeList.value = response.list
      }
    } catch (error) {
      console.error('获取番剧列表失败:', error)
    } finally {
      loading.value = false
    }
  }

  // 获取番剧详情
  const fetchAnimeDetail = async (seasonId: number) => {
    loading.value = true
    try {
      const response = await analyticsAPI.getAnimeDetail(seasonId)
      if (response.success) {
        currentAnime.value = response.data
      }
    } catch (error) {
```

### frontend/src/stores/auth.ts
- 行数: 185
- 字符数: 4868
- 片段:
```
// stores/auth.ts
/**
 * 用户认证状态管理
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as authAPI from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  // 状态
  const username = ref<string>('')
  const email = ref<string>('')
  const userId = ref<number | null>(null)
  const createdAt = ref<string>('')
  const isLoggedIn = ref<boolean>(false)
  const isAdmin = ref<boolean>(false)
  const isActive = ref<boolean>(true)
  const preferences = ref<string[]>([])
  const accessToken = ref<string>('')

  // 计算属性
  const hasPreferences = computed(() => preferences.value.length > 0)
  const user = computed(() => ({
    id: userId.value,
    username: username.value,
    email: email.value,
    created_at: createdAt.value,
    isAdmin: isAdmin.value,
    isActive: isActive.value
  }))

  // 初始化：从 localStorage 恢复状态
  const initAuth = () => {
    const savedToken = localStorage.getItem('access_token')
    const savedUsername = localStorage.getItem('username')
    const savedIsAdmin = localStorage.getItem('is_admin')
    
    if (savedToken && savedUsername) {
      accessToken.value = savedToken
      username.value = savedUsername
```

### frontend/src/stores/ui.ts
- 行数: 104
- 字符数: 2413
- 片段:
```
// stores/ui.ts
/**
 * UI 全局状态管理
 * 管理应用的主题、全局加载状态和通知等 UI 相关状态，
 * 与业务逻辑状态（auth、analytics）严格隔离
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/** 支持的主题类型 */
export type ThemeMode = 'light' | 'dark'

const getInitialThemeMode = (): ThemeMode => {
  const stored = localStorage.getItem('theme') as ThemeMode | null
  if (stored === 'light' || stored === 'dark') {
    return stored
  }

  if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    return prefersDark ? 'dark' : 'light'
  }

  return 'dark'
}

export const useUIStore = defineStore('ui', () => {
  // ── 状态 ──────────────────────────────────────────────────────────────────

  /** 当前主题模式，默认跟随系统偏好 */
  const themeMode = ref<ThemeMode>(getInitialThemeMode())

  /** 全局加载状态（用于页面级骨架屏或全屏 Loading） */
  const globalLoading = ref<boolean>(false)

  /** 侧边栏折叠状态 */
  const sidebarCollapsed = ref<boolean>(false)

  // ── 计算属性 ──────────────────────────────────────────────────────────────
```

### frontend/src/utils/errorHandling.ts
- 行数: 12
- 字符数: 544
- 片段:
```
import type { AxiosError } from 'axios'

export const getApiErrorMessage = (error: unknown, fallback: string): string => {
  const axiosError = error as AxiosError<{ detail?: string; msg?: string }>
  const detail = axiosError?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  const msg = axiosError?.response?.data?.msg
  if (typeof msg === 'string' && msg.trim()) return msg
  const message = axiosError?.message
  if (typeof message === 'string' && message.trim()) return message
  return fallback
}
```

### frontend/src/utils/imageProxy.ts
- 行数: 27
- 字符数: 886
- 片段:
```
import type { AnimeData } from '@/api/analytics'

/**
 * 获取代理图片 URL，通过后端 /api/image_proxy 接口绕过防盗链限制并缓存图片。
 * 若番剧封面地址为空，则返回空字符串。
 *
 * @param anime - 番剧数据对象
 * @returns 代理后的图片 URL，或空字符串
 */
export const getProxiedImageUrl = (anime: AnimeData): string => {
  if (!anime.cover) return ''
  return `/api/image_proxy?url=${encodeURIComponent(anime.cover)}&title=${encodeURIComponent(anime.title)}&season_id=${anime.season_id}`
}

/**
 * 获取任意 URL 的代理图片地址（用于 TMDB 图片等非番剧封面的场景）。
 * 若 url 为空，则返回空字符串。
 *
 * @param url - 原始图片链接（支持 B站 CDN 和 image.tmdb.org）
 * @param title - 番剧名（用于生成缓存文件名）
 * @param seasonId - 番剧 season_id（用于生成缓存文件名）
 * @returns 代理后的图片 URL，或空字符串
 */
export const getProxiedUrl = (url: string, title: string, seasonId: number): string => {
  if (!url) return ''
  return `/api/image_proxy?url=${encodeURIComponent(url)}&title=${encodeURIComponent(title)}&season_id=${seasonId}`
}
```

### frontend/src/views/GenreSelection.vue
- 行数: 144
- 字符数: 2988
- 片段:
```
<template>
  <div class="genre-container">
    <div class="genre-box">
      <h2>选择您感兴趣的番剧类型</h2>
      <p class="subtitle">请选择至少 3 个您喜欢的番剧风格</p>

      <div class="genre-grid">
        <div
          v-for="genre in allGenres"
          :key="genre"
          class="genre-item"
          :class="{ selected: selectedGenres.includes(genre) }"
          @click="toggleGenre(genre)"
        >
          {{ genre }}
        </div>
      </div>

      <div class="actions">
        <el-button
          type="primary"
          size="large"
          :disabled="selectedGenres.length < 3"
          :loading="loading"
          @click="handleSubmit"
        >
          确认并开始使用 ({{ selectedGenres.length }}/3)
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
```

### frontend/src/views/Home.vue
- 行数: 1518
- 字符数: 42566
- 片段:
```
<template>
  <div class="home-view">

    <!-- ── 页面标题 ── -->
    <div class="page-header mb-4">
      <h2 class="page-title">📊 数据总览</h2>
      <p class="page-subtitle">
        {{
          overview?.last_update
            ? '最后更新：' + new Date(overview.last_update).toLocaleDateString('zh-CN')
            : isLoading ? '数据加载中…' : '暂无更新记录'
        }}
      </p>
    </div>

    <!-- ── Row 1：指标卡片 ── -->
    <div class="row mb-4">
      <div class="col-md-3 mb-3">
        <div class="metric-card pink">
          <div class="metric-icon"><i class="fas fa-film"></i></div>
          <div class="metric-content">
            <h5>番剧总数</h5>
            <p class="metric-value">{{ isLoading ? '…' : (overview?.total_animes ?? 0) }}</p>
            <p class="metric-sub">Total Animes</p>
          </div>
        </div>
      </div>
      <div class="col-md-3 mb-3">
        <div class="metric-card blue">
          <div class="metric-icon"><i class="fas fa-play-circle"></i></div>
          <div class="metric-content">
            <h5>总播放量</h5>
            <p class="metric-value">{{ isLoading ? '…' : formatNumber(overview?.total_views) }}</p>
            <p class="metric-sub">Total Views</p>
      
...[截断]
```

### frontend/src/views/Login.vue
- 行数: 264
- 字符数: 6694
- 片段:
```
<template>
  <div class="login-container">
    <div class="login-box">
      <div class="logo-section">
        <img src="https://www.bilibili.com/favicon.ico" alt="Bilibili" class="logo" />
        <h2>Bilibili 智能分析平台</h2>
      </div>

      <el-tabs v-model="activeTab" class="login-tabs">
        <!-- 登录标签页 -->
        <el-tab-pane label="登录" name="login">
          <el-form :model="loginForm" :rules="loginRules" ref="loginFormRef" label-width="0">
            <el-form-item prop="username">
              <el-input
                v-model="loginForm.username"
                placeholder="请输入用户名"
                prefix-icon="User"
                size="large"
              />
            </el-form-item>
            <el-form-item prop="password">
              <el-input
                v-model="loginForm.password"
                type="password"
                placeholder="请输入密码"
                prefix-icon="Lock"
                size="large"
                @keyup.enter="handleLogin"
              />
            </el-form-item>
            <el-form-item>
              <el-button
                type="primary"
                size="large"
                style="width: 100%"
      
...[截断]
```

### frontend/src/views/Overview.vue
- 行数: 1195
- 字符数: 33263
- 片段:
```
<template>
  <div class="overview-view">
    <div class="overview-header mb-3">
      <div class="overview-title-group">
        <h3 class="overview-title">深度市场洞察</h3>
        <p class="overview-subtitle">聚焦趋势演进、受众差异与题材组合的结构化分析</p>
      </div>
      <ul class="nav nav-pills overview-tabs" role="tablist">
        <li v-for="tab in tabs" :key="tab.id" class="nav-item">
          <button
            class="nav-link"
            :id="`overview-tab-${tab.id}`"
            role="tab"
            :aria-selected="activeTab === tab.id"
            :aria-controls="`overview-panel-${tab.id}`"
            :class="{ active: activeTab === tab.id }"
            @click="switchTab(tab.id)"
          >
            {{ tab.label }}
          </button>
        </li>
      </ul>
    </div>

    <div class="tab-content">
      <div
        v-show="activeTab === 'yearly'"
        class="tab-pane"
        role="tabpanel"
        id="overview-panel-yearly"
        aria-labelledby="overview-tab-yearly"
      >
        <div class="style-unified h-100">
          <div class="card-header-unified">
            <h5>历年上新趋势（季度对比）</h5>
            <div class="area-btn-group">
              <button
                v
...[截断]
```

### frontend/src/views/PersonalSpace.vue
- 行数: 215
- 字符数: 5714
- 片段:
```
<template>
  <div class="personal-space-container">
    <div class="personal-space-header">
      <div class="personal-title-group">
        <h3 class="personal-title">{{ authStore.user?.username || '用户' }} 的个人空间</h3>
        <p class="personal-subtitle">
          注册时间：{{ formatDate(authStore.user?.created_at) }}
          <span v-if="authStore.isAdmin" class="admin-badge">管理员模式</span>
        </p>
      </div>
      <ul class="nav nav-pills personal-tabs" role="tablist">
        <li v-for="tab in visibleTabs" :key="tab.id" class="nav-item">
          <button
            class="nav-link"
            role="tab"
            :aria-selected="activeTab === tab.id"
            :class="{ active: activeTab === tab.id }"
            @click="switchTab(tab.id)"
          >
            {{ tab.label }}
          </button>
        </li>
      </ul>
    </div>

    <div class="tab-content">
      <section v-show="activeTab === 'profile'" class="tab-pane">
        <ProfileSettings />
      </section>
      <section v-show="activeTab === 'preferences'" class="tab-pane">
        <PreferenceTags />
      </section>
      <section v-show="activeTab === 'watchlist'" class="tab-pane">
        <UserWatc
...[截断]
```

### frontend/src/views/Recommendation.vue
- 行数: 1091
- 字符数: 32804
- 片段:
```
<template>
  <div class="recommendation-view">
    <div class="recommendation-content">
      <!-- 头部控制区 -->
      <div class="recommendation-header">
        <div class="preference-status">
          <button class="btn btn-lg btn-pink" @click="togglePreferences">
            <i class="fas fa-heart me-2"></i>
            <span>{{ preferenceStatus }}</span>
          </button>
          <div v-if="showPreferencesTooltip" class="preference-tooltip">
            {{ preferencesText }}
          </div>
        </div>

        <!-- 排序控制 -->
        <div class="sort-controls">
          <label class="sort-label">排序方式：</label>
          <div class="btn-group" role="group">
            <button
              v-for="sort in sortOptions"
              :key="sort.value"
              class="btn"
              :class="currentSort === sort.value ? 'btn-primary active' : 'btn-outline-primary'"
              @click="handleSortChange(sort.value)"
            >
              <i :class="sort.icon + ' me-1'"></i>{{ sort.label }}
            </button>
          </div>
        </div>
      </div>

      <!-- 主从联动布局 -->
      <div class="master-detail-layout" v-loading="loading && allAnimes.length === 0">
...[截断]
```

### frontend/src/views/Report.vue
- 行数: 869
- 字符数: 23846
- 片段:
```
<template>
  <div class="report-view">
    <!-- 页面标题 -->
    <div class="report-hero mb-4">
      <h2><i class="fas fa-file-chart-line me-2"></i>番剧数据分析报告生成器</h2>
      <p class="text-muted">选择一部番剧，由 AI 自动生成多维度 EDA 分析报告</p>
    </div>

    <!-- 搜索与控制区 -->
    <div class="row mb-4">
      <div class="col-md-8 mx-auto">
        <div class="report-search-group">
          <div class="report-search-wrap">
            <span class="report-search-icon"><i class="fas fa-search"></i></span>
            <input
              ref="searchInputRef"
              v-model="keyword"
              class="report-search-input"
              placeholder="输入番剧名称搜索..."
              type="text"
              autocomplete="off"
              @keyup.enter="handleSearch"
            />
          </div>
          <button class="report-search-btn" @click="handleSearch" :disabled="searching">
            <i class="fas fa-search me-1"></i>{{ searching ? '搜索中…' : '搜索' }}
          </button>
          <button
            v-if="animeData && !generating"
            class="report-gen-btn"
            @click="generateReport"
          >
            <i class="fas fa-magic me-1"></i>生成报告
          </button>
          <
...[截断]
```

### frontend/src/views/Status.vue
- 行数: 1429
- 字符数: 40316
- 片段:
```
<template>
  <div class="status-view">
    <!-- 搜索区域 -->
    <div class="row mb-4">
      <div class="col-md-8 mx-auto">
        <div class="status-search-group">
          <div class="status-search-wrap">
            <span class="status-search-icon"><i class="fas fa-search"></i></span>
            <input
              ref="statusSearchInputRef"
              v-model="keyword"
              class="status-search-input"
              placeholder="输入番剧名搜索..."
              type="text"
              autocomplete="off"
              @keyup.enter="handleSearch"
              @focus="onStatusSearchFocus"
              @blur="hideStatusSuggestions"
              @input="onStatusSearchInput"
            />
          </div>
          <button class="status-search-btn" @click="handleSearch">
            <i class="fas fa-search me-1"></i>搜索
          </button>
          <button
            v-if="animeData"
            class="status-detail-btn"
            @click="toggleEpisodeDetails"
          >
            <i class="fas fa-list me-1"></i>剧集详情
          </button>
        </div>

        <Teleport to="body">
          <ul
            v-if="showStatusSuggestions && statusSuggestions.length > 0"

...[截断]
```

### frontend/tsconfig.json
- 行数: 13
- 字符数: 290
- 片段:
```
{
  "extends": "@vue/tsconfig/tsconfig.dom.json",
  "include": ["env.d.ts", "src/**/*", "src/**/*.vue"],
  "exclude": ["src/**/__tests__/*"],
  "compilerOptions": {
    "composite": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    },
    "types": ["vite/client"]
  }
}
```

### frontend/vite.config.ts
- 行数: 23
- 字符数: 466
- 片段:
```
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 5173,
    proxy: {
      // 代理所有 /api 请求到后端
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
```

### scripts/generate_kb.py
- 行数: 134
- 字符数: 3240
- 模块说明: 生成项目知识库文件（project_knowledge.md）。
- 片段:
```
#!/usr/bin/env python3
"""
生成项目知识库文件（project_knowledge.md）。
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "project_knowledge.md"

INCLUDE_EXTENSIONS = {".py", ".vue", ".ts", ".tsx", ".js", ".md", ".json"}
INCLUDE_FILENAMES = {"README.md", "requirements.txt", "package.json"}
EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "dist",
    "build",
    "__pycache__",
    ".idea",
    ".vscode",
    ".pytest_cache",
}
MAX_FILE_CHARS = 1200
MAX_TOTAL_CHARS = 180000


def should_include(path: Path) -> bool:
    if path.name in INCLUDE_FILENAMES:
        return True
    return path.suffix.lower() in INCLUDE_EXTENSIONS


def iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
```
