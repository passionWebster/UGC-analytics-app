"""Crawler facade and shared HTTP/runtime utilities.

`BilibiliBangumiCrawler` is the composition root of scraper subservices:
`anime_sync`, `episode_sync`, `danmaku`, and `comments`.
"""

from __future__ import annotations

import random
import time
from typing import Any

import requests
from requests import Response
from sqlmodel import Session

from ..config import settings
from ..logger import scraper_logger as logger
from ..mongodb import DanmakuMongoRepository
from .anime_sync import AnimeSyncService
from .comments import CommentsService
from .constants import (
    AREA_ID_TO_ENUM as SCRAPER_AREA_ID_TO_ENUM,
)
from .constants import (
    DM_HISTORY_STOP_CODES as SCRAPER_DM_HISTORY_STOP_CODES,
)
from .constants import (
    DOMESTIC_API_STYLE_IDS as SCRAPER_DOMESTIC_API_STYLE_IDS,
)
from .constants import (
    REGULAR_API_STYLE_IDS as SCRAPER_REGULAR_API_STYLE_IDS,
)
from .constants import (
    STYLE_MAP as SCRAPER_STYLE_MAP,
)
from .danmaku import DanmakuService
from .episode_sync import EpisodeSyncService
from .helpers import (
    convert_order_to_int,
    get_quarter_month,
    is_valid_main_episode,
    parse_release_date_from_order,
)


class BilibiliBangumiCrawler:
    """Facade for scraper domain services plus shared request/session context.

    Attributes:
        session: Shared SQLModel session.
        http_session: Shared requests session with default headers/cookies.
        anime_sync: Anime-level sync service.
        episode_sync: Episode-level sync service.
        danmaku: Danmaku crawl/parse service.
        comments: Comment crawl/persistence service.
    """

    # B站番剧索引API的URL
    BASE_API_URL = "https://api.bilibili.com/pgc/season/index/result"

    # 风格映射
    STYLE_MAP = SCRAPER_STYLE_MAP

    # 常规番剧API支持的风格ID
    REGULAR_API_STYLE_IDS = SCRAPER_REGULAR_API_STYLE_IDS

    # 国产番剧API支持的风格ID
    DOMESTIC_API_STYLE_IDS = SCRAPER_DOMESTIC_API_STYLE_IDS

    # B站地区 id → AreaEnum 映射表（来自 /pgc/view/web/season areas 数组）
    # id=1  中国大陆 / id=6 中国香港 / id=7 中国台湾 → 国内
    # id=2  日本                                    → 日本
    # id=3  美国                                    → 美国
    # 其余 id                                       → 其他（保持不变）
    AREA_ID_TO_ENUM: dict[int, str] = SCRAPER_AREA_ID_TO_ENUM
    # 历史弹幕索引接口错误码（命中后无需继续请求更多月份）
    DM_HISTORY_STOP_CODES = SCRAPER_DM_HISTORY_STOP_CODES

    def __init__(self, session: Session) -> None:
        """Initialize shared runtime and compose domain subservices.

        Args:
            session: SQLModel database session used by all scraper subservices.
        """
        self.session = session
        self.http_session = requests.Session()
        self.http_session.headers.update(
            {
                "User-Agent": settings.crawler_user_agent,
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://www.bilibili.com/",
            }
        )
        sessdata = (settings.bilibili_sessdata or "").strip()
        if sessdata:
            self.http_session.cookies.set("SESSDATA", sessdata, domain=".bilibili.com")
            logger.info("🍪 已启用 SESSDATA Cookie（用于历史弹幕抓取）")
        self.mongo_repo = DanmakuMongoRepository()
        self.override_retry_attempts: int | None = None
        self.request_counters: dict[str, int] = {"requests": 0, "retries": 0, "failed": 0}
        # 组合子服务：所有业务能力通过显式子服务入口访问。
        self.anime_sync = AnimeSyncService(self)
        self.episode_sync = EpisodeSyncService(self)
        self.danmaku = DanmakuService(self)
        self.comments = CommentsService(self)

        logger.info("✅ 爬虫已初始化")

    def _build_proxy(self) -> dict[str, str] | None:
        """根据配置构建单次请求代理。"""
        if not settings.crawler_proxy_enabled:
            return None
        pool = (settings.crawler_proxy_pool or "").strip()
        if not pool:
            return None
        candidates = [p.strip() for p in pool.split(",") if p.strip()]
        if not candidates:
            return None
        proxy = random.choice(candidates)
        return {"http": proxy, "https": proxy}

    def _throttle(self, *, force_base_delay: bool = False) -> None:
        """统一节流，支持随机抖动。"""
        if not force_base_delay and settings.bilibili_request_delay <= 0:
            return
        base = max(settings.bilibili_request_delay, 0.0)
        jitter = max(settings.bilibili_request_jitter, 0.0)
        sleep_seconds = base + (random.uniform(0, jitter) if jitter > 0 else 0.0)
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    def _request_get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        timeout: int | None = None,
        retry_attempts: int | None = None,
        force_base_delay: bool = True,
    ) -> Response | None:
        """带重试、退避、代理、节流的统一 GET 请求入口。"""
        attempts = (
            retry_attempts
            if retry_attempts is not None
            else (self.override_retry_attempts or settings.bilibili_retry_attempts)
        )
        attempts = max(1, attempts)
        timeout = timeout or settings.bilibili_request_timeout
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            self._throttle(force_base_delay=force_base_delay)
            self.request_counters["requests"] += 1
            try:
                response = self.http_session.get(
                    url,
                    params=params,
                    timeout=timeout,
                    proxies=self._build_proxy(),
                )
                response.raise_for_status()
                return response
            except Exception as exc:
                last_exc = exc
                if attempt < attempts:
                    self.request_counters["retries"] += 1
                    backoff = min(
                        settings.bilibili_retry_backoff_base * (2 ** (attempt - 1)),
                        settings.bilibili_retry_backoff_max,
                    )
                    logger.warning(
                        "⚠️ 请求失败，准备重试 attempt={}/{} url={} error={}",
                        attempt,
                        attempts,
                        url,
                        exc,
                    )
                    time.sleep(backoff)
                else:
                    self.request_counters["failed"] += 1
        logger.warning("❌ 请求最终失败 url={} error={}", url, last_exc)
        return None

    @staticmethod
    def _convert_order_to_int(order_str: Any) -> int:
        """将B站API返回的带单位数字字符串转换为整数。"""
        return convert_order_to_int(order_str)

    @staticmethod
    def _is_valid_main_episode(episode: dict[str, Any]) -> bool:
        """根据 API 返回字段判断该集是否为正片。"""
        return is_valid_main_episode(episode)

    @staticmethod
    def _get_quarter_month(month: int) -> int | None:
        """根据月份获取季度首月。"""
        return get_quarter_month(month)

    @staticmethod
    def _parse_release_date_from_order(order_str: Any) -> tuple[Any | None, int | None]:
        """从 order 字符串解析发布日期，返回 (year, quarter_month)。"""
        return parse_release_date_from_order(order_str)


def create_crawler(session: Session | None = None) -> BilibiliBangumiCrawler:
    """创建爬虫实例的工厂函数。"""
    if session is None:
        from ..database import engine

        session = Session(engine)

    return BilibiliBangumiCrawler(session)
