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
    
    # 关系：用户可以有多个追番记录
    favorites: List["UserFavorite"] = Relationship(back_populates="user")


class UserFavorite(SQLModel, table=True):
    """用户追番收藏记录表"""
    __tablename__ = "user_favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "season_id", name="uq_user_favorite_user_season"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    season_id: int = Field(foreign_key="anime.season_id", index=True)
    status: str = Field(default="watching", max_length=20)  # watching | plan | completed
    created_at: datetime = Field(default_factory=datetime.now)

    user: Optional["User"] = Relationship(back_populates="favorites")
    anime: Optional["Anime"] = Relationship(back_populates="favorited_by")


class Anime(SQLModel, table=True):
    """
    番剧表 - 存储番剧的基础信息
    替代原来 rank_cache.json 中的番剧数据
    """
    __tablename__ = "anime"
    
    season_id: int = Field(primary_key=True)  # B站番剧 season_id
    title: str = Field(index=True, max_length=255)  # 番剧标题
    cover: Optional[str] = Field(default=None, max_length=500)  # 封面图片 URL
    area: str = Field(default=AreaEnum.OTHER.value, max_length=20)  # 地区
    rating: Optional[float] = Field(default=None)  # 评分
    styles: Optional[str] = Field(default=None, sa_column=Column(JSON))  # JSON 数组存储风格标签
    release_date: Optional[str] = Field(default=None, max_length=50)  # 发布日期 (格式: "2023-01" 或 "敬请期待")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # ── 由番剧详情 API（/pgc/view/web/season）补充的字段 ──────────────────────
    # stat 对象
    total_coins: Optional[int] = Field(default=None)  # 全剧总投币数
    total_danmakus: Optional[int] = Field(default=None)  # 全剧总弹幕数
    total_likes: Optional[int] = Field(default=None)  # 全剧总点赞数
    total_reply: Optional[int] = Field(default=None)  # 全剧总评论数
    total_share: Optional[int] = Field(default=None)  # 全剧总分享数
    # rating 对象
    rating_count: Optional[int] = Field(default=None)  # 参与评分人数
    # publish 对象
    is_finish: Optional[int] = Field(default=None)  # 完结状态：0 连载中 / 1 已完结
    # rights 对象
    copyright: Optional[str] = Field(default=None, max_length=20)  # 版权类型：bilibili / dujia
    # areas 数组：存储完整地区列表 JSON，如 [{"id":2,"name":"日本"}]
    areas_raw: Optional[str] = Field(default=None, sa_column=Column(JSON))
    
    # 关系
    daily_stats: List["DailyStats"] = Relationship(back_populates="anime")
    tmdb_info: Optional["TmdbAnimeInfo"] = Relationship(back_populates="anime")
    favorited_by: List["UserFavorite"] = Relationship(back_populates="anime")


class DailyStats(SQLModel, table=True):
    """
    每日统计数据表 - 存储番剧的播放量、追番数等时序数据
    支持历史趋势分析
    """
    __tablename__ = "daily_stats"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    season_id: int = Field(foreign_key="anime.season_id", index=True)  # 关联番剧
    date: datetime = Field(default_factory=datetime.now, index=True)  # 统计日期
    views: int = Field(default=0)  # 播放量
    favorites: int = Field(default=0)  # 追番人数
    online_viewers: Optional[int] = Field(default=None)  # 在线观看人数（可选）
    
    # 关系
    anime: Optional[Anime] = Relationship(back_populates="daily_stats")
    
    class Config:
        # 创建复合唯一索引：同一番剧同一天只能有一条记录
        indexes = [
            {"fields": ["season_id", "date"], "unique": True}
        ]


class EpisodeStats(SQLModel, table=True):
    """
    单集统计表 - 存储每一集的详细数据，包含完整互动指标
    """
    __tablename__ = "episode_stats"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    season_id: int = Field(foreign_key="anime.season_id", index=True)
    episode_title: str = Field(max_length=255)  # 集标题
    bvid: str = Field(max_length=20, index=True)  # B站视频 BV 号
    cid: str = Field(max_length=20)  # 弹幕 CID
    views: Optional[int] = Field(default=None)  # 播放量
    danmaku: Optional[int] = Field(default=None)  # 弹幕数
    reply: Optional[int] = Field(default=None)  # 评论数
    favorite: Optional[int] = Field(default=None)  # 收藏数
    coin: Optional[int] = Field(default=None)  # 投币数
    share: Optional[int] = Field(default=None)  # 分享数
    like: Optional[int] = Field(default=None)  # 点赞数
    online_viewers: Optional[int] = Field(default=None)  # 当前在线人数
    # 存储 24 小时在线人数分布，格式: {"00": 1500, "01": 1200, ..., "23": 1800}
    hourly_online_history: Optional[str] = Field(default=None, sa_column=Column(JSON))
    avg_sentiment_score: Optional[float] = Field(default=None)  # 单集弹幕平均情感分
    peak_danmaku_time: Optional[float] = Field(default=None)  # 单集弹幕峰值出现时间点（秒）
    nlp_status: Optional[str] = Field(default=None, max_length=20)  # NLP 状态: pending/running/success/failed
    nlp_sample_size: Optional[int] = Field(default=None)  # NLP 样本量（清洗后）
    nlp_sentiment_score: Optional[float] = Field(default=None)  # NLP 情感均分（-1~1）
    nlp_noise_ratio: Optional[float] = Field(default=None)  # 噪音占比（0~1）
    nlp_keywords: Optional[str] = Field(default=None, sa_column=Column(JSON))  # 关键词列表
    nlp_entities: Optional[str] = Field(default=None, sa_column=Column(JSON))  # 实体词频列表
    nlp_processed_at: Optional[datetime] = Field(default=None)  # NLP 最近处理时间
    updated_at: datetime = Field(default_factory=datetime.now)


class Ranking(SQLModel, table=True):
    """
    排行榜表 - 存储不同维度的排名快照
    支持按评分、播放量、追番数等多种排序
    """
    __tablename__ = "rankings"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    season_id: int = Field(foreign_key="anime.season_id", index=True)
    ranking_type: str = Field(max_length=50, index=True)  # 排名类型: "views", "favorites", "rating"
    rank_position: int  # 排名位置
    date: datetime = Field(default_factory=datetime.now, index=True)  # 排名日期
    
    class Config:
        indexes = [
            {"fields": ["ranking_type", "date", "rank_position"]}
        ]


class CrawlLog(SQLModel, table=True):
    """
    爬虫日志表 - 记录数据抓取历史
    """
    __tablename__ = "crawl_logs"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    task_type: str = Field(max_length=100)  # 任务类型: "full_update", "incremental_update"
    status: str = Field(max_length=20)  # 状态: "success", "failed", "running"
    items_count: int = Field(default=0)  # 抓取数据条数
    error_message: Optional[str] = Field(default=None, max_length=1000)  # 错误信息
    total_scraped: Optional[int] = Field(default=None)  # 原始抓取条数
    cleaned_filtered: Optional[int] = Field(default=None)  # 清洗过滤后条数
    final_inserted: Optional[int] = Field(default=None)  # 最终入库条数
    retry_count: Optional[int] = Field(default=0)  # 请求重试总次数
    failed_count: Optional[int] = Field(default=0)  # 失败条目数
    failed_reason: Optional[str] = Field(default=None, max_length=1000)  # 失败原因
    duration: Optional[float] = Field(default=None)  # 任务耗时（秒）
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = Field(default=None)


class RecommendationStrategyConfig(SQLModel, table=True):
    """
    推荐策略配置表
    用于管理可实时调整的多信号融合权重，并支持启停策略。
    """
    __tablename__ = "recommendation_strategy_configs"

    id: Optional[int] = Field(default=None, primary_key=True)
    views_weight: float = Field(default=0.35)
    ai_weight: float = Field(default=0.35)
    tmdb_weight: float = Field(default=0.2)
    diversity_weight: float = Field(default=0.1)
    enabled: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class AITelemetry(SQLModel, table=True):
    """
    AI 调用遥测表
    记录 AI 服务调用的稳定性、时延与资源消耗指标。
    """
    __tablename__ = "ai_telemetry_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.now, index=True)
    api_type: str = Field(max_length=50, index=True)
    latency_ms: Optional[int] = Field(default=None)
    is_success: bool = Field(default=True, index=True)
    token_usage: Optional[int] = Field(default=None)
    error_code: Optional[str] = Field(default=None, max_length=100, index=True)


class TmdbAnimeInfo(SQLModel, table=True):
    """
    TMDB 番剧扩展信息表 - 与 Anime 表 1:1 关联（从表）

    存储从 TMDB API 获取的补充元数据和高清图片资源，
    通过 season_id 外键与 Anime 表关联，保持两套数据系统的解耦。
    """
    __tablename__ = "tmdb_anime_info"

    # 主键同时为外键，实现 1:1 关联
    season_id: int = Field(primary_key=True, foreign_key="anime.season_id")
    # TMDB 剧集唯一标识，方便后续跳过搜索直接更新
    tmdb_id: Optional[int] = Field(default=None, index=True)
    # 原始名称（通常为日文）
    original_name: Optional[str] = Field(default=None, max_length=255)
    # 剧集简介（优先中文，降级为英文）
    overview: Optional[str] = Field(default=None)
    # TMDB 综合评分（可与 B站评分并列展示）
    tmdb_rating: Optional[float] = Field(default=None)
    # 横版背景剧照 URL（适合详情页头部大图，使用原始分辨率）
    backdrop_url: Optional[str] = Field(default=None, max_length=500)
    # 透明背景 Logo URL（适合悬浮于背景图上方展示）
    logo_url: Optional[str] = Field(default=None, max_length=500)
    # TMDB 版竖版海报 URL（可作为高清备选封面）
    poster_url: Optional[str] = Field(default=None, max_length=500)
    # TMDB 风格分类列表（JSON 序列化字符串，读取后需 json.loads 解析；
    # 与现有 Anime.styles 字段保持一致的存储约定）
    genres: Optional[str] = Field(default=None, sa_column=Column(JSON))
    # TMDB 首播日期（格式 "YYYY-MM-DD"）
    first_air_date: Optional[str] = Field(default=None, max_length=20)
    # 数据最近更新时间
    updated_at: datetime = Field(default_factory=datetime.now)

    # 反向关系：关联到 Anime 主表
    anime: Optional["Anime"] = Relationship(back_populates="tmdb_info")


class MonthlySnapshot(SQLModel, table=True):
    """
    月度快照表 - 存储每月月初汇总的番剧追番数与播放量数据
    替代原 cache/rank_fetcher_{月份}th.json 文件存储方案
    """
    __tablename__ = "monthly_snapshots"
    __table_args__ = (
        UniqueConstraint("season_id", "month", name="uq_monthly_snapshot_season_month"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    season_id: int = Field(foreign_key="anime.season_id", index=True)  # 关联番剧
    month: str = Field(max_length=7, index=True)  # 快照月份，格式 "YYYY-MM"
    title: str = Field(max_length=255)  # 番剧标题（冗余存储，方便查询）
    favorites: int = Field(default=0)  # 当月最新追番数
    views: int = Field(default=0)  # 当月最新播放量
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)  # 最近更新时间


class DanmuRecord(SQLModel, table=True):
    """
    弹幕记录表 - 存储从 B站抓取的弹幕文本及情感分析结果
    """
    __tablename__ = "danmu_records"

    id: Optional[int] = Field(default=None, primary_key=True)
    season_id: int = Field(foreign_key="anime.season_id", index=True)  # 关联番剧
    episode_number: int = Field(default=1)  # 集数
    cid: Optional[str] = Field(default=None, max_length=20)  # 弹幕 CID
    content: str = Field(max_length=500)  # 弹幕文字内容
    video_time: Optional[float] = Field(default=None)  # 弹幕出现的视频时间点（秒）
    timestamp: Optional[datetime] = Field(default=None)  # 弹幕发送时间
    sender_hash: Optional[str] = Field(default=None, max_length=64)  # 匿名用户哈希
    sentiment_score: Optional[float] = Field(default=None)  # 情感得分（0=消极，1=积极）
    cleaned_content: Optional[str] = Field(default=None, max_length=500)  # 清洗后文本
    emotion_label: Optional[str] = Field(default=None, max_length=32)  # 特殊情绪标签（233/??? 等）
    nlp_sentiment_score: Optional[float] = Field(default=None)  # 细粒度情感得分（-1~1）
    nlp_processed: bool = Field(default=False)  # 是否已完成 NLP 处理
    created_at: datetime = Field(default_factory=datetime.now)


class CommentRecord(SQLModel, table=True):
    """
    评论记录表 - 存储从 B站抓取的热评及情感分析结果
    """
    __tablename__ = "comment_records"

    id: Optional[int] = Field(default=None, primary_key=True)
    season_id: int = Field(foreign_key="anime.season_id", index=True)  # 关联番剧
    avid: Optional[int] = Field(default=None, index=True)  # 视频 avid（oid）
    root_rpid: Optional[str] = Field(default=None, max_length=32, index=True)  # 主楼评论 ID
    parent_rpid: Optional[str] = Field(default=None, max_length=32, index=True)  # 父评论 ID
    level: int = Field(default=0)  # 层级：0=主楼，1=楼中楼
    is_top_level: bool = Field(default=True)  # 是否主楼评论
    content: str  # 评论文字内容
    likes: Optional[int] = Field(default=0)  # 点赞数
    replies: Optional[int] = Field(default=0)  # 回复数
    sentiment_score: Optional[float] = Field(default=None)  # 情感得分（0=消极，1=积极）
    created_at: datetime = Field(default_factory=datetime.now)


# Pydantic 模型用于 API 请求/响应
class UserCreate(SQLModel):
    """用户注册请求模型"""
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(max_length=100)
    password: str = Field(min_length=6, max_length=255)


class UserLogin(SQLModel):
    """用户登录请求模型"""
    username: str
    password: str


class UserResponse(SQLModel):
    """用户信息响应模型"""
    id: int
    username: str
    email: str
    preferences: Optional[str] = None
    created_at: datetime


class PreferenceUpdate(SQLModel):
    """偏好设置更新模型"""
    username: str
    preferences: List[str]  # 风格偏好列表


class AnimeResponse(SQLModel):
    """番剧信息响应模型"""
    season_id: int
    title: str
    cover: Optional[str]
    area: str
    rating: Optional[float]
    styles: Optional[List[str]]
    release_date: Optional[str]
    views: Optional[int] = None  # 最新播放量
    favorites: Optional[int] = None  # 最新追番数


class DailyStatsResponse(SQLModel):
    """每日统计响应模型"""
    season_id: int
    date: datetime
    views: int
    favorites: int
    online_viewers: Optional[int]


class TmdbInfoResponse(SQLModel):
    """
    TMDB 补充信息响应模型 - 嵌套在番剧详情响应的 tmdb_info 字段中
    """
    tmdb_id: Optional[int] = None
    original_name: Optional[str] = None
    overview: Optional[str] = None
    tmdb_rating: Optional[float] = None
    backdrop_url: Optional[str] = None
    logo_url: Optional[str] = None
    poster_url: Optional[str] = None
    genres: Optional[List[str]] = None
    first_air_date: Optional[str] = None
