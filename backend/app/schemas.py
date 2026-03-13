# schemas.py
"""
Pydantic 数据验证模型
定义 API 请求和响应的数据结构
"""
from datetime import datetime
from typing import Optional, List
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
