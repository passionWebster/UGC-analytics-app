# schemas.py
"""
Pydantic 数据验证模型
定义 API 请求和响应的数据结构
"""
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field


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
    preferences: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PreferenceUpdate(BaseModel):
    """偏好设置更新模型"""
    username: str
    preferences: List[str]  # 风格偏好列表


class AnimeResponse(BaseModel):
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

    class Config:
        from_attributes = True


class DailyStatsResponse(BaseModel):
    """每日统计响应模型"""
    season_id: int
    date: datetime
    views: int
    favorites: int
    online_viewers: Optional[int]

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """JWT Token 响应模型"""
    access_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    """通用消息响应模型"""
    message: str
    success: bool = True


# ─────────────────────────────────────────────
# 1. 单集受众行为分析相关模型
# ─────────────────────────────────────────────

class EpisodeRetentionData(BaseModel):
    """单集留存率数据"""
    episode_1_views: int        # 第1集播放量
    episode_3_views: Optional[int]    # 第3集播放量（不足3集时为空）
    final_episode_views: Optional[int]  # 最终集播放量（仅1集时为空）
    retention_ep1_to_ep3: Optional[float]   # 第1→第3集留存率（%）
    retention_ep1_to_final: Optional[float]  # 第1→最终集留存率（%）


class EpisodeEngagementIndex(BaseModel):
    """单集硬核指数与互动密度"""
    episode_title: str
    views: int
    coin_rate: Optional[float]    # 硬核指数：投币率 = coin / views
    like_rate: Optional[float]    # 硬核指数：点赞率 = like / views
    danmaku_rate: Optional[float] # 共鸣密度：弹幕率 = danmaku / views
    reply_rate: Optional[float]   # 共鸣密度：评论率 = reply / views


class EpisodeBehaviorAnalysisResponse(BaseModel):
    """单集受众行为分析完整响应"""
    season_id: int
    total_episodes: int
    retention: EpisodeRetentionData
    engagement_by_episode: List[EpisodeEngagementIndex]
    avg_coin_rate: Optional[float]    # 全剧平均投币率
    avg_like_rate: Optional[float]    # 全剧平均点赞率
    avg_danmaku_rate: Optional[float] # 全剧平均弹幕率
    avg_reply_rate: Optional[float]   # 全剧平均评论率


# ─────────────────────────────────────────────
# 2. 生命周期与增长分析相关模型
# ─────────────────────────────────────────────

class GrowthDataPoint(BaseModel):
    """单日增长数据点"""
    date: str
    views: int
    favorites: int
    views_growth: Optional[float]         # 播放量一阶导数（日增量）
    views_acceleration: Optional[float]   # 播放量二阶导数（增速变化量）
    favorites_growth: Optional[float]     # 追番数一阶导数（日增量）
    favorites_acceleration: Optional[float]  # 追番数二阶导数


class LongTailEffect(BaseModel):
    """长尾效应数据"""
    avg_daily_views_30d: Optional[float]  # 首播30天后的日均播放量
    avg_daily_views_90d: Optional[float]  # 首播90天后的日均播放量


class LifecycleGrowthResponse(BaseModel):
    """生命周期与增长分析完整响应"""
    season_id: int
    growth_data: List[GrowthDataPoint]
    long_tail: LongTailEffect
    peak_daily_growth: Optional[float]  # 峰值日增播放量（黑马指数参考）
    peak_date: Optional[str]            # 峰值增长日期


# ─────────────────────────────────────────────
# 3. 竞争态势分析相关模型
# ─────────────────────────────────────────────

class CompetitiveLandscapeResponse(BaseModel):
    """竞争态势分析完整响应"""
    season_id: int
    total_ranking_days: int         # 上榜总天数
    top3_days: int                  # 排名前3天数
    top10_days: int                 # 排名前10天数
    dominance_top3: Optional[float]  # 霸榜Top3比例（%）
    dominance_top10: Optional[float] # 霸榜Top10比例（%）
    avg_rank: Optional[float]        # 平均排名
    rank_volatility: Optional[float] # 排名波动率（标准差）


# ─────────────────────────────────────────────
# 4. 题材季节性规律分析相关模型
# ─────────────────────────────────────────────

class SeasonGenreTrendItem(BaseModel):
    """单条季节题材趋势数据"""
    season: str      # spring / summer / autumn / winter
    genre: str       # 题材/风格名称
    anime_count: int
    avg_views: float
    total_views: int


class SeasonalGenreTrendsResponse(BaseModel):
    """题材季节性规律分析完整响应"""
    trends: List[SeasonGenreTrendItem]
    best_genre_by_season: Dict[str, str]  # 每个季节表现最佳的题材


# ─────────────────────────────────────────────
# 5. 用户个性化推荐相关模型
# ─────────────────────────────────────────────

class PersonalizedRecommendationItem(BaseModel):
    """单条个性化推荐番剧"""
    season_id: int
    title: str
    cover: Optional[str]
    area: str
    rating: Optional[float]
    styles: List[str]
    match_score: float  # 双向匹配度（0-100）
    views: int
    favorites: int


class PersonalizedRecommendationsResponse(BaseModel):
    """用户个性化推荐完整响应"""
    username: str
    preferences: List[str]
    recommendations: List[PersonalizedRecommendationItem]
