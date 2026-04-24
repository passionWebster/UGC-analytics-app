# 配置管理模块实现文件
"""
应用配置中心
统一管理所有配置项，包括数据库、API、公开数据采集等设置
"""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """应用配置类"""
    
    # 应用基础配置
    app_name: str = "泛二次元流媒体数据智能分析与可视化平台"
    app_version: str = "2.0.0"
    debug: bool = True
    
    # 服务器配置
    host: str = "0.0.0.0"
    port: int = 8000
    
    # 数据库配置
    database_url: str = "sqlite:///./data/ugc_streaming_analytics.db"
    
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
    
    # 某头部弹幕视频网站 API 配置
    bilibili_api_base_url: str = "https://api.bilibili.com"
    bilibili_request_timeout: int = 15
    bilibili_request_delay: float = 2.0  # 请求间隔（秒）
    bilibili_retry_attempts: int = 3
    bilibili_retry_backoff_base: float = 0.8
    bilibili_retry_backoff_max: float = 8.0
    bilibili_request_jitter: float = 0.4
    bilibili_sessdata: Optional[str] = os.getenv("BILIBILI_SESSDATA")
    crawler_proxy_enabled: bool = False
    crawler_proxy_pool: Optional[str] = os.getenv("CRAWLER_PROXY_POOL")
    crawler_comment_page_size: int = 20
    crawler_nested_reply_limit: int = 20
    crawler_nested_reply_pages: int = 2
    crawler_history_months: int = 24

    # MongoDB 配置（原始弹幕文档存储）
    mongodb_uri: Optional[str] = os.getenv("MONGODB_URI")
    mongodb_db_name: str = os.getenv("MONGODB_DB_NAME", "ugc_streaming_analytics")
    mongodb_danmaku_collection: str = os.getenv("MONGODB_DANMAKU_COLLECTION", "danmaku_raw")
    mongodb_connect_timeout_ms: int = 3000
    
    # 公开数据采集配置
    crawler_pages_to_fetch: int = 5  # 每个分类同步页数
    crawler_page_size: int = 820  # 每页数据条数
    crawler_user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    
    # 缓存配置
    cache_dir: str = "./cache"
    
    # AI 服务配置
    doubao_api_url: str = "https://ark.cn-beijing.volces.com/api/v3/responses"
    doubao_api_key: Optional[str] = os.getenv("DOUBAO_API_KEY")
    doubao_model: str = "doubao-seed-1-6-250615"

    # TMDB API 配置
    tmdb_api_key: Optional[str] = os.getenv("TMDB_API_KEY")  # 从环境变量读取，未配置时 TMDB 功能自动降级
    tmdb_api_base_url: str = "https://api.themoviedb.org/3"
    tmdb_image_base_original: str = "https://image.tmdb.org/t/p/original"  # 背景图使用原始分辨率
    tmdb_image_base_w500: str = "https://image.tmdb.org/t/p/w500"  # Logo/海报使用 w500
    tmdb_request_timeout: int = 10  # 单次请求超时秒数
    tmdb_enrichment_concurrency: int = 5  # 后台富集任务并发上限

    # Multiprocessing（异步 NLP 任务）
    nlp_worker_pool_enabled: bool = True
    nlp_worker_start_method: str = os.getenv("NLP_WORKER_START_METHOD", "spawn")
    nlp_worker_processes: int = max(1, int(os.getenv("NLP_WORKER_PROCESSES", "2")))
    nlp_worker_queue_maxsize: int = max(1, int(os.getenv("NLP_WORKER_QUEUE_MAXSIZE", "1000")))
    nlp_worker_shutdown_timeout: int = max(1, int(os.getenv("NLP_WORKER_SHUTDOWN_TIMEOUT", "5")))
    nlp_async_fallback_local: bool = True

    # NLP 配置
    nlp_jieba_user_dict_path: str = os.getenv("NLP_JIEBA_USER_DICT_PATH", "")
    nlp_keyword_topk: int = 20
    nlp_entity_topk: int = 20
    nlp_entity_min_freq: int = 2
    nlp_spam_repeat_threshold: int = 3  # 连续重复字符达到该阈值时判定为刷屏噪音
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例（用于依赖注入）"""
    return settings
