"""
MongoDB 数据访问模块
用于存储原始弹幕文档，减轻关系型数据库压力。
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from .config import settings
from .logger import scraper_logger as logger

try:
    from pymongo import ASCENDING, MongoClient
    from pymongo.collection import Collection
    from pymongo.errors import PyMongoError
    _PYMONGO_AVAILABLE = True
except ImportError:  # pragma: no cover - 运行环境未安装 pymongo 时降级
    MongoClient = None
    Collection = None
    ASCENDING = 1
    PyMongoError = Exception
    _PYMONGO_AVAILABLE = False


class DanmakuMongoRepository:
    """原始弹幕文档仓储。"""

    def __init__(self):
        self._enabled = bool(settings.mongodb_uri and _PYMONGO_AVAILABLE)
        self._client = None
        self._collection = None
        self._initialized = False
        if not _PYMONGO_AVAILABLE:
            logger.warning("⚠️ pymongo 未安装，MongoDB 原始弹幕存储已禁用")
        elif not settings.mongodb_uri:
            logger.info("ℹ️ 未配置 MONGODB_URI，MongoDB 原始弹幕存储已禁用")

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _ensure_collection(self) -> Optional["Collection"]:
        if not self._enabled:
            return None
        if self._initialized:
            return self._collection
        try:
            self._client = MongoClient(
                settings.mongodb_uri,
                serverSelectionTimeoutMS=settings.mongodb_connect_timeout_ms,
                connectTimeoutMS=settings.mongodb_connect_timeout_ms,
            )
            db = self._client[settings.mongodb_db_name]
            self._collection = db[settings.mongodb_danmaku_collection]
            self._collection.create_index([("cid", ASCENDING)], unique=True, name="uq_cid")
            self._collection.create_index([("season_id", ASCENDING)], name="idx_season_id")
            self._collection.create_index([("bvid", ASCENDING)], name="idx_bvid")
            self._initialized = True
            logger.info(
                "✅ MongoDB 已连接 db={} collection={}",
                settings.mongodb_db_name,
                settings.mongodb_danmaku_collection,
            )
        except PyMongoError as exc:
            logger.warning("⚠️ MongoDB 初始化失败，降级仅写 SQLite: {}", exc)
            self._enabled = False
            self._collection = None
        return self._collection

    def upsert_episode_danmaku(
        self,
        *,
        cid: str,
        season_id: int,
        episode_number: int,
        bvid: Optional[str],
        danmaku_items: List[Dict[str, Any]],
    ) -> bool:
        """按 cid 维度写入/更新单集原始弹幕文档。"""
        if not cid:
            return False
        collection = self._ensure_collection()
        if collection is None:
            return False
        payload = {
            "cid": str(cid),
            "season_id": season_id,
            "episode_number": episode_number,
            "bvid": bvid,
            "danmaku_items": danmaku_items,
            "danmaku_count": len(danmaku_items),
            "updated_at": datetime.utcnow(),
        }
        try:
            collection.update_one({"cid": str(cid)}, {"$set": payload}, upsert=True)
            return True
        except PyMongoError as exc:
            logger.warning("⚠️ 写入 MongoDB 失败 cid={}: {}", cid, exc)
            return False

