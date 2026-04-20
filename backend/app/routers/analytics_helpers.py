"""analytics 路由的共享常量与辅助函数。"""

import json
import logging
import os
import re
import threading
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional

from cachetools import TTLCache
from fastapi import HTTPException
from sqlalchemy import func as sa_func
from sqlmodel import Session, select as sql_select

from ..analytics import get_episode_timeline_bins, get_season_wordcloud
from ..database import engine
from ..models import Anime, DanmuRecord, EpisodeAnalysisCache, EpisodeStats
from ..mongodb import DanmakuMongoRepository

logger = logging.getLogger(__name__)

_STABLE_DATA_DAYS = 7
_ANALYTICS_CACHE: TTLCache = TTLCache(maxsize=512, ttl=3600)
_ANALYTICS_CACHE_LOCK = threading.RLock()
_MONGO_DANMAKU_REPO = DanmakuMongoRepository()
_MONGO_SENTIMENT_KEYS = ("nlp_sentiment_score", "sentiment_score", "sentiment")
_RECENT_EPISODE_DAYS = 30
_FROZEN_EPISODE_DAYS = 180

_COVER_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "cover_cache",
)

_ALLOWED_IMAGE_HOSTS = {
    "i0.hdslb.com",
    "i1.hdslb.com",
    "i2.hdslb.com",
    "s1.hdslb.com",
    "s2.hdslb.com",
    "pic.bilibili.com",
    "static.hdslb.com",
    "image.tmdb.org",
}

_VALID_CATEGORY_PATTERN = re.compile(r"^[\w\u4e00-\u9fff·、&+\-/]{1,30}$")


class AreaEnum(str, Enum):
    china = "国内"
    japan = "日本"
    us = "美国"


class SeasonEnum(str, Enum):
    spring = "spring"
    summer = "summer"
    autumn = "autumn"
    winter = "winter"


def _validate_category_value(category: Optional[str]) -> Optional[str]:
    if category is None:
        return None
    category = category.strip()
    if not category:
        return None
    if not _VALID_CATEGORY_PATTERN.fullmatch(category):
        raise HTTPException(
            status_code=400,
            detail="非法的 category 参数，仅允许中文/字母数字/下划线及 ·、&+-/，且长度为 1~30",
        )
    return category


def _parse_areas_param(areas: Optional[str]) -> Optional[List[str]]:
    if not areas:
        return None
    items = [a.strip() for a in areas.split(",") if a.strip()]
    if not items:
        return None
    allowed_values = {item.value for item in AreaEnum}
    if any(item not in allowed_values for item in items):
        allowed_text = "、".join(sorted(allowed_values))
        raise HTTPException(status_code=400, detail=f"非法的 areas 参数，仅允许：{allowed_text}")
    return items


def _is_dataset_stable(
    session: Session,
    season_id: Optional[int] = None,
    cid: Optional[str] = None,
) -> bool:
    if season_id is None and cid is None:
        return False

    query = sql_select(sa_func.max(EpisodeStats.updated_at))
    if season_id is not None:
        query = query.where(EpisodeStats.season_id == season_id)
    if cid:
        query = query.where(EpisodeStats.cid == cid)

    latest_updated = session.exec(query).first()
    if latest_updated is None:
        return False
    return latest_updated <= (datetime.now() - timedelta(days=_STABLE_DATA_DAYS))


def _read_cache(cache_key: str):
    with _ANALYTICS_CACHE_LOCK:
        return _ANALYTICS_CACHE.get(cache_key)


def _write_cache(cache_key: str, payload: dict) -> None:
    with _ANALYTICS_CACHE_LOCK:
        _ANALYTICS_CACHE[cache_key] = payload


def _parse_release_date_to_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _get_episode_publish_anchor(
    session: Session,
    target_ep: EpisodeStats,
) -> datetime:
    anime = session.exec(sql_select(Anime).where(Anime.season_id == target_ep.season_id)).first()
    release_dt = _parse_release_date_to_datetime(anime.release_date if anime else None)
    if release_dt:
        return release_dt
    return target_ep.updated_at or datetime.now()


def _has_source_danmaku_data(session: Session, cid: str, season_id: int) -> bool:
    mongo_doc = _MONGO_DANMAKU_REPO.get_danmaku_by_cid(cid)
    if mongo_doc and isinstance(mongo_doc.get("danmaku_items"), list) and mongo_doc.get("danmaku_items"):
        return True
    sqlite_count = session.exec(
        sql_select(sa_func.count(DanmuRecord.id)).where(
            DanmuRecord.season_id == season_id,
            DanmuRecord.cid == cid,
        )
    ).one()
    return bool(sqlite_count and int(sqlite_count) > 0)


def _episode_needs_nlp_refresh(session: Session, target_ep: EpisodeStats, cid: str, season_id: int) -> bool:
    if target_ep.nlp_status != "success" or target_ep.nlp_processed_at is None:
        return True
    mongo_doc = _MONGO_DANMAKU_REPO.get_danmaku_by_cid(cid)
    if mongo_doc and isinstance(mongo_doc.get("danmaku_items"), list):
        items = [item for item in mongo_doc.get("danmaku_items", []) if isinstance(item, dict)]
        if not items:
            return True
        has_sentiment = any(
            any(item.get(key) is not None for key in _MONGO_SENTIMENT_KEYS)
            for item in items
        )
        return not has_sentiment
    sqlite_sentiment_count = session.exec(
        sql_select(sa_func.count(DanmuRecord.id)).where(
            DanmuRecord.season_id == season_id,
            DanmuRecord.cid == cid,
            (DanmuRecord.nlp_sentiment_score.is_not(None)) | (DanmuRecord.sentiment_score.is_not(None)),
        )
    ).one()
    return not bool(sqlite_sentiment_count and int(sqlite_sentiment_count) > 0)


def _resolve_episode_number(session: Session, target_ep: EpisodeStats) -> int:
    count_value = session.exec(
        sql_select(sa_func.count(EpisodeStats.id)).where(
            EpisodeStats.season_id == target_ep.season_id,
            EpisodeStats.id <= target_ep.id,
        )
    ).one()
    return max(1, int(count_value))


def _upsert_episode_analysis_cache(
    session: Session,
    *,
    season_id: int,
    cid: str,
    episode_number: int,
    timeline_data: dict,
    wordcloud_data: dict,
) -> EpisodeAnalysisCache:
    row = session.exec(
        sql_select(EpisodeAnalysisCache).where(EpisodeAnalysisCache.cid == cid)
    ).first()
    now = datetime.now()
    if row is None:
        row = EpisodeAnalysisCache(
            season_id=season_id,
            cid=cid,
            episode_number=episode_number,
            timeline_payload=json.dumps(timeline_data, ensure_ascii=False),
            wordcloud_payload=json.dumps(wordcloud_data, ensure_ascii=False),
            created_at=now,
            updated_at=now,
        )
        session.add(row)
    else:
        row.season_id = season_id
        row.episode_number = episode_number
        row.timeline_payload = json.dumps(timeline_data, ensure_ascii=False)
        row.wordcloud_payload = json.dumps(wordcloud_data, ensure_ascii=False)
        row.updated_at = now
    session.commit()
    session.refresh(row)
    return row


def _load_episode_analysis_cache_payload(row: EpisodeAnalysisCache) -> dict:
    try:
        timeline_data = json.loads(row.timeline_payload or "{}")
    except Exception:
        timeline_data = {}
    try:
        wordcloud_data = json.loads(row.wordcloud_payload or "{}")
    except Exception:
        wordcloud_data = {}
    return {
        "timeline": timeline_data,
        "wordcloud": wordcloud_data,
    }


def _refresh_episode_analysis_cache(
    season_id: int,
    cid: str,
    bin_size: int,
    keyword_topk: int,
    top_n: int,
) -> None:
    with Session(engine) as bg_session:
        try:
            timeline_data = get_episode_timeline_bins(
                session=bg_session,
                cid=cid,
                bin_size=bin_size,
                keyword_topk=keyword_topk,
            )
            wordcloud_data = get_season_wordcloud(
                session=bg_session,
                season_id=season_id,
                cid=cid,
                top_n=top_n,
            )
            _upsert_episode_analysis_cache(
                bg_session,
                season_id=season_id,
                cid=cid,
                episode_number=int(timeline_data.get("episode_number", 1)),
                timeline_data=timeline_data,
                wordcloud_data=wordcloud_data,
            )
            logger.info("✅ episode analysis cache refreshed cid={} season_id={}", cid, season_id)
        except Exception as exc:
            logger.warning("⚠️ episode analysis cache refresh failed cid={} season_id={} err={}", cid, season_id, exc)


def _trigger_danmaku_scrape_for_episode(
    season_id: int,
    cid: str,
) -> None:
    from ..scraper import BilibiliBangumiCrawler

    with Session(engine) as bg_session:
        try:
            episodes = bg_session.exec(
                sql_select(EpisodeStats)
                .where(EpisodeStats.season_id == season_id)
                .order_by(EpisodeStats.id)
            ).all()
            if not episodes:
                return
            target_index = next((idx for idx, item in enumerate(episodes, start=1) if str(item.cid or "") == cid), None)
            if target_index is None:
                logger.warning("⚠️ skip background scrape: cid not found season_id={} cid={}", season_id, cid)
                return
            crawler = BilibiliBangumiCrawler(bg_session)
            crawler.scrape_danmaku_and_comments(
                season_id=season_id,
                max_episodes=target_index,
                comment_limit=50,
                include_comment_replies=True,
                nested_reply_limit=20,
                mode="incremental",
                sentiment_fn=None,
                run_nlp_async=True,
            )
            logger.info("✅ background danmaku scrape triggered season_id={} target_episode={}", season_id, target_index)
        except Exception as exc:
            logger.warning("⚠️ background danmaku scrape failed season_id={} cid={} err={}", season_id, cid, exc)
