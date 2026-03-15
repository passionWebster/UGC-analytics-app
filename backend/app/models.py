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
    preferences: Optional[str] = Field(default=None, sa_column=Column(JSON))  # JSON 字符串存储偏好
    created_at: datetime = Field(default_factory=datetime.now)
    
    # 关系：用户可以有多个追番记录（未来扩展）
    # favorites: List["UserFavorite"] = Relationship(back_populates="user")


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
    
    # 关系
    daily_stats: List["DailyStats"] = Relationship(back_populates="anime")


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
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = Field(default=None)


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
