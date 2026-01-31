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
    bilibili_request_timeout: int = 15
    bilibili_request_delay: float = 2.0  # 请求间隔（秒）
    
    # 爬虫配置
    crawler_pages_to_fetch: int = 5  # 每个分类抓取的页数
    crawler_page_size: int = 820  # 每页数据条数
    crawler_user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    
    # 缓存配置
    cache_dir: str = "./cache"
    
    # AI 服务配置
    doubao_api_url: str = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
    doubao_api_key: Optional[str] = None
    doubao_model: str = "doubao-seed-1-6-250615"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例（用于依赖注入）"""
    return settings
