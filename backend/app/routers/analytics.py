"""
数据分析相关的接口路由
"""
import hashlib
import json
import logging
import os
import re
import threading
from enum import Enum
from datetime import datetime, timedelta
from typing import Any, List, Optional
from urllib.parse import urlparse
import asyncio
import httpx
from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse
from sqlmodel import Session, select as sql_select
from sqlalchemy import func as sa_func

from ..analytics import (
    get_comment_insight_cards,
    get_episode_timeline_bins,
    get_season_character_trends,
    get_season_wordcloud,
)
from ..tasks import enqueue_episode_nlp_task
from ..auth import get_current_user
from ..database import get_session, engine
from ..crud import AnalyticsService
from ..models import Anime, EpisodeStats, TmdbAnimeInfo, User, EpisodeAnalysisCache, DanmuRecord
from ..mongodb import DanmakuMongoRepository
from ..schemas import (
    EpisodeTimelineResponse,
    SeasonWordcloudResponse,
    SeasonCharacterTrendsResponse,
    EpisodeBehaviorAnalysisResponse,
    LifecycleGrowthResponse,
    CompetitiveLandscapeResponse,
    SeasonalGenreTrendsResponse,
    PersonalizedRecommendationsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["数据分析"])
# 图片代理路由（与分析主路由独立挂载）
proxy_router = APIRouter(prefix="/api", tags=["图片代理"])

_STABLE_DATA_DAYS = 7
_ANALYTICS_CACHE: TTLCache = TTLCache(maxsize=512, ttl=3600)
_ANALYTICS_CACHE_LOCK = threading.RLock()
_MONGO_DANMAKU_REPO = DanmakuMongoRepository()
_MONGO_SENTIMENT_KEYS = ("nlp_sentiment_score", "sentiment_score", "sentiment")
_RECENT_EPISODE_DAYS = 30
_FROZEN_EPISODE_DAYS = 180

# 封面图片本地缓存目录
_COVER_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "cover_cache",
)

# 哔哩哔哩图片分发域名白名单（用于防止服务端请求伪造）
_ALLOWED_IMAGE_HOSTS = {
    "i0.hdslb.com",
    "i1.hdslb.com",
    "i2.hdslb.com",
    "s1.hdslb.com",
    "s2.hdslb.com",
    "pic.bilibili.com",
    "static.hdslb.com",
    # TMDB 图片服务器（背景图、标识图、海报均由此域名提供）
    "image.tmdb.org",
}

# 仅允许中文、字母数字与少量常见分隔符，长度限制为 1~30
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


def _validate_category_value(category: str | None) -> str | None:
    """校验分类参数合法性。

    参数:
        category: 原始分类参数。

    返回:
        str | None: 清洗后的分类值；空值返回 None。

    异常:
        HTTPException: 当分类参数包含非法字符或长度超限时抛出。
    """
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


def _parse_areas_param(areas: str | None) -> list[str] | None:
    """解析地区筛选参数。

    参数:
        areas: 逗号分隔的地区参数字符串。

    返回:
        list[str] | None: 解析后的地区列表；为空时返回 None。

    异常:
        HTTPException: 当地区值不在白名单中时抛出。
    """
    if not areas:
        return None
    items = [a.strip() for a in areas.split(',') if a.strip()]
    if not items:
        return None
    allowed_values = {item.value for item in AreaEnum}
    if any(item not in allowed_values for item in items):
        allowed_text = "、".join(sorted(allowed_values))
        raise HTTPException(status_code=400, detail=f"非法的 areas 参数，仅允许：{allowed_text}")
    return items


def _is_dataset_stable(
    session: Session,
    season_id: int | None = None,
    cid: str | None = None,
) -> bool:
    """判断目标数据是否进入稳定期。

    参数:
        session: 数据库会话。
        season_id: 可选 season_id。
        cid: 可选分集 CID。

    返回:
        bool: 数据超过稳定窗口返回 True，否则返回 False。
    """
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


def _read_cache(cache_key: str) -> dict[str, Any] | None:
    """读取内存缓存。

    参数:
        cache_key: 缓存键。

    返回:
        dict[str, Any] | None: 命中时返回缓存值，否则返回 None。
    """
    with _ANALYTICS_CACHE_LOCK:
        return _ANALYTICS_CACHE.get(cache_key)


def _write_cache(cache_key: str, payload: dict) -> None:
    """写入内存缓存。

    参数:
        cache_key: 缓存键。
        payload: 需要缓存的响应数据。
    """
    with _ANALYTICS_CACHE_LOCK:
        _ANALYTICS_CACHE[cache_key] = payload


def _parse_release_date_to_datetime(value: str | None) -> datetime | None:
    """将发布日期字符串解析为 datetime。

    参数:
        value: 发布日期字符串，支持 YYYY / YYYY-MM / YYYY-MM-DD。

    返回:
        datetime | None: 解析成功返回 datetime，失败返回 None。
    """
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
    """获取分集发布时间锚点。

    优先使用番剧发布日期；缺失时回退到分集更新时间或当前时间。

    参数:
        session: 数据库会话。
        target_ep: 目标分集记录。

    返回:
        datetime: 计算后的发布时间锚点。
    """
    anime = session.exec(sql_select(Anime).where(Anime.season_id == target_ep.season_id)).first()
    release_dt = _parse_release_date_to_datetime(anime.release_date if anime else None)
    if release_dt:
        return release_dt
    return target_ep.updated_at or datetime.now()


def _has_source_danmaku_data(session: Session, cid: str, season_id: int) -> bool:
    """判断分集是否存在可用弹幕源数据。

    参数:
        session: 数据库会话。
        cid: 分集 CID。
        season_id: 番剧季 ID。

    返回:
        bool: Mongo 或 SQLite 任一来源存在弹幕数据即返回 True。
    """
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
    """判断单集是否需要补跑 NLP。

    触发条件包括：
    1) 分集状态未成功或缺少处理时间；
    2) Mongo 弹幕存在但无可用情感字段；
    3) Mongo 不可用且 SQLite 也无可用情感字段。

    参数:
        session: 数据库会话。
        target_ep: 目标分集记录。
        cid: 分集 CID。
        season_id: 番剧季 ID。

    返回:
        bool: 需要补跑返回 True，否则返回 False。
    """
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
    """
    通过统计同 season 中 id 小于等于当前集的记录数，得到该集顺序号（从 1 开始）。
    """
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
            crawler.comments.scrape_danmaku_and_comments(
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

@router.get("/episode/{cid}/timeline", response_model=dict)
def get_episode_timeline(
    cid: str,
    bin_size: int = Query(10, ge=1, le=300, description="时间窗大小（秒）"),
    keyword_topk: int = Query(5, ge=1, le=20, description="每个切片返回关键词数量"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """获取单集时间窗弹幕聚合数据。

    参数:
        cid: 分集 CID。
        bin_size: 时间窗大小（秒）。
        keyword_topk: 每个切片返回关键词数量。
        session: 数据库会话。

    返回:
        dict[str, Any]: 时间线聚合响应。

    异常:
        HTTPException: 未找到对应分集数据时抛出 404。
    """
    cache_key = f"episode_timeline:{cid}:bin={bin_size}:topk={keyword_topk}"
    cache_enabled = _is_dataset_stable(session=session, cid=cid)
    if cache_enabled:
        cached = _read_cache(cache_key)
        if cached is not None:
            return cached

    try:
        data = get_episode_timeline_bins(
            session=session,
            cid=cid,
            bin_size=bin_size,
            keyword_topk=keyword_topk,
        )
    except ValueError as exc:
        if str(exc) == "episode_not_found":
            raise HTTPException(status_code=404, detail="未找到对应 CID 的剧集数据")
        raise
    payload = {"success": True, "data": EpisodeTimelineResponse.model_validate(data)}
    if cache_enabled:
        _write_cache(cache_key, payload)
    return payload


@router.get("/season/{season_id}/episode/{cid}/analysis", response_model=dict)
def get_episode_analysis_with_cache(
    season_id: int,
    cid: str,
    background_tasks: BackgroundTasks,
    bin_size: int = Query(10, ge=1, le=300, description="时间窗大小（秒）"),
    keyword_topk: int = Query(5, ge=1, le=20, description="每个切片返回关键词数量"),
    top_n: int = Query(120, ge=10, le=500, description="词云词条数量上限"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """获取单集分析结果并管理缓存刷新。

    策略为优先返回 SQLite 缓存，并根据分集状态决定是否调度 NLP 刷新
    或触发弹幕抓取任务。

    参数:
        season_id: 番剧季 ID。
        cid: 分集 CID。
        background_tasks: 后台任务调度器。
        bin_size: 时间窗大小（秒）。
        keyword_topk: 每个切片返回关键词数量。
        top_n: 词云词条数量上限。
        session: 数据库会话。

    返回:
        dict[str, Any]: 单集分析响应，可能为缓存结果、待处理状态或实时计算结果。

    异常:
        HTTPException: 当分集不存在时抛出 404。
    """
    target_ep = session.exec(
        sql_select(EpisodeStats).where(
            EpisodeStats.season_id == season_id,
            EpisodeStats.cid == cid,
        )
    ).first()
    if not target_ep:
        raise HTTPException(status_code=404, detail="未找到对应剧集")

    cache_row = session.exec(
        sql_select(EpisodeAnalysisCache).where(EpisodeAnalysisCache.cid == cid)
    ).first()
    publish_anchor = _get_episode_publish_anchor(session, target_ep)
    age_days = max(0, (datetime.now() - publish_anchor).days)
    is_recent = age_days <= _RECENT_EPISODE_DAYS
    is_frozen = age_days >= _FROZEN_EPISODE_DAYS
    needs_nlp_refresh = _episode_needs_nlp_refresh(session, target_ep, cid, season_id)

    if needs_nlp_refresh:
        episode_number = _resolve_episode_number(session, target_ep)
        background_tasks.add_task(
            enqueue_episode_nlp_task,
            season_id,
            episode_number,
            cid,
        )
        if cache_row is not None:
            return {
                "success": True,
                "cached": True,
                "stale": True,
                "refresh_scheduled": True,
                "age_days": age_days,
                "message": "检测到该集情感数据待刷新，已触发后台 NLP，当前先返回缓存结果",
                "data": _load_episode_analysis_cache_payload(cache_row),
            }
        return {
            "success": False,
            "pending": True,
            "refresh_scheduled": True,
            "age_days": age_days,
            "message": "已触发后台 NLP 分析，请稍后重试",
        }

    if cache_row is not None:
        refresh_scheduled = False
        if is_recent:
            background_tasks.add_task(
                _refresh_episode_analysis_cache,
                season_id,
                cid,
                bin_size,
                keyword_topk,
                top_n,
            )
            refresh_scheduled = True
        elif not is_frozen and (datetime.now() - cache_row.updated_at) > timedelta(hours=24):
            background_tasks.add_task(
                _refresh_episode_analysis_cache,
                season_id,
                cid,
                bin_size,
                keyword_topk,
                top_n,
            )
            refresh_scheduled = True
        return {
            "success": True,
            "cached": True,
            "refresh_scheduled": refresh_scheduled,
            "age_days": age_days,
            "data": _load_episode_analysis_cache_payload(cache_row),
        }

    if not _has_source_danmaku_data(session, cid, season_id):
        background_tasks.add_task(_trigger_danmaku_scrape_for_episode, season_id, cid)
        return {
            "success": False,
            "pending": True,
            "message": "暂无可用弹幕数据，已触发后台抓取，请稍后重试",
            "data": {"timeline": {}, "wordcloud": {}},
        }

    timeline_data = get_episode_timeline_bins(
        session=session,
        cid=cid,
        bin_size=bin_size,
        keyword_topk=keyword_topk,
    )
    wordcloud_data = get_season_wordcloud(
        session=session,
        season_id=season_id,
        cid=cid,
        top_n=top_n,
    )
    _upsert_episode_analysis_cache(
        session,
        season_id=season_id,
        cid=cid,
        episode_number=int(timeline_data.get("episode_number", 1)),
        timeline_data=timeline_data,
        wordcloud_data=wordcloud_data,
    )
    return {
        "success": True,
        "cached": False,
        "refresh_scheduled": False,
        "age_days": age_days,
        "data": {
            "timeline": timeline_data,
            "wordcloud": wordcloud_data,
        },
    }


@router.get("/season/{season_id}/wordcloud", response_model=dict)
def get_season_wordcloud_api(
    season_id: int,
    cid: str | None = Query(None, description="可选：按单集 CID 聚合词云"),
    top_n: int = Query(120, ge=10, le=500, description="返回词条数量上限"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """获取整季或单集词云数据。

    参数:
        season_id: 番剧季 ID。
        cid: 可选分集 CID。
        top_n: 返回词条数量上限。
        session: 数据库会话。

    返回:
        dict[str, Any]: 词云聚合响应。

    异常:
        HTTPException: 当目标分集不存在可聚合数据时抛出 404。
    """
    cache_key = f"season_wordcloud:{season_id}:cid={cid or ''}:top={top_n}"
    cache_enabled = _is_dataset_stable(session=session, season_id=season_id, cid=cid)
    if cache_enabled:
        cached = _read_cache(cache_key)
        if cached is not None:
            return cached

    try:
        data = get_season_wordcloud(
            session=session,
            season_id=season_id,
            cid=cid,
            top_n=top_n,
        )
    except ValueError as exc:
        if str(exc) == "episode_not_found":
            raise HTTPException(status_code=404, detail="未找到可用于词云聚合的剧集数据")
        raise
    payload = {"success": True, "data": SeasonWordcloudResponse.model_validate(data)}
    if cache_enabled:
        _write_cache(cache_key, payload)
    return payload


@router.get("/season/{season_id}/characters", response_model=dict)
def get_season_characters_api(
    season_id: int,
    top_n: int = Query(8, ge=1, le=30, description="返回角色数量上限"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """获取整季核心角色讨论趋势。

    参数:
        season_id: 番剧季 ID。
        top_n: 返回角色数量上限。
        session: 数据库会话。

    返回:
        dict[str, Any]: 角色趋势分析响应。

    异常:
        HTTPException: 当 season_id 无对应数据时抛出 404。
    """
    cache_key = f"season_characters:{season_id}:top={top_n}"
    cache_enabled = _is_dataset_stable(session=session, season_id=season_id)
    if cache_enabled:
        cached = _read_cache(cache_key)
        if cached is not None:
            return cached

    try:
        data = get_season_character_trends(
            session=session,
            season_id=season_id,
            top_n=top_n,
        )
    except ValueError as exc:
        if str(exc) == "season_not_found":
            raise HTTPException(status_code=404, detail="未找到该 season_id 的剧集数据")
        raise
    payload = {"success": True, "data": SeasonCharacterTrendsResponse.model_validate(data)}
    if cache_enabled:
        _write_cache(cache_key, payload)
    return payload


@router.get("/season/{season_id}/insight-cards", response_model=dict)
def get_season_insight_cards_api(
    season_id: int,
    limit: int = Query(300, ge=30, le=1000, description="用于聚类的评论采样数"),
    top_n: int = Query(6, ge=1, le=20, description="返回观点卡片数量"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """获取整季评论观点卡片。

    参数:
        season_id: 番剧季 ID。
        limit: 聚类前的评论采样数。
        top_n: 返回观点卡片数量。
        session: 数据库会话。

    返回:
        dict[str, Any]: 评论观点卡片响应。
    """
    cache_key = f"season_insight_cards:{season_id}:limit={limit}:top={top_n}"
    cache_enabled = _is_dataset_stable(session=session, season_id=season_id)
    if cache_enabled:
        cached = _read_cache(cache_key)
        if cached is not None:
            return cached

    items = get_comment_insight_cards(
        session=session,
        season_id=season_id,
        limit=limit,
        top_n=top_n,
    )
    payload = {"success": True, "total": len(items), "data": items}
    if cache_enabled:
        _write_cache(cache_key, payload)
    return payload


@proxy_router.get("/image_proxy")
def image_proxy(
    url: str = Query(..., description="原始图片链接"),
    title: str = Query(..., description="番剧名"),
    season_id: str = Query(..., description="番剧 season_id"),
):
    """
    图片反向代理接口，同时支持 B站图片防盗链绕过和 TMDB 图片缓存。

    处理流程：
    1. 校验 URL 域名是否在白名单内（防止 SSRF）
    2. 命中本地缓存则直接返回 FileResponse
    3. 未命中则向源站发起请求，按域名区分请求头策略：
       - B站域名：附加 Referer 绕过防盗链
       - TMDB 域名：使用标准 User-Agent，无需 Referer
    4. 将图片二进制写入本地缓存后返回

    参数:
        url: 原始图片链接（支持 B站 CDN 和 image.tmdb.org）
        title: 番剧名（用于生成缓存文件名）
        season_id: 番剧 season_id（用于生成缓存文件名）

    返回:
        图片文件响应（FileResponse）
    """
    os.makedirs(_COVER_CACHE_DIR, exist_ok=True)

    # 校验图片地址仅指向白名单域名（防止服务端请求伪造）
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in _ALLOWED_IMAGE_HOSTS:
        raise HTTPException(status_code=400, detail="不支持的图片域名，仅允许 B站图片 CDN 及 TMDB 图片域名")

    # 生成安全的文件名：清理特殊字符，保留字母、数字、中文、连字符
    safe_title = re.sub(r"[^\w\u4e00-\u9fff\-]", "_", title)
    safe_season_id = re.sub(r"[^\w]", "_", str(season_id))
    # 尝试从图片地址推断扩展名，默认使用常见图片后缀
    url_path = url.split("?")[0]
    ext = os.path.splitext(url_path)[-1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        ext = ".jpg"
    url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()[:8]
    filename = f"{safe_title}_{safe_season_id}_{url_hash}{ext}"
    filepath = os.path.join(_COVER_CACHE_DIR, filename)

    # 命中本地缓存则直接返回
    if os.path.exists(filepath):
        return FileResponse(filepath)

    # 按域名区分请求头策略：哔哩哔哩需要伪造来源页，TMDB 无需
    is_bilibili = parsed.hostname != "image.tmdb.org"
    headers = {"User-Agent": "Mozilla/5.0"}
    if is_bilibili:
        headers["Referer"] = "https://www.bilibili.com/"

    try:
        with httpx.Client(follow_redirects=True, timeout=15) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"图片请求失败: {exc}") from exc

    # 将图片二进制写入缓存
    with open(filepath, "wb") as f:
        f.write(response.content)

    return FileResponse(filepath)


@router.get("/animes", response_model=dict)
def get_animes(
    limit: Optional[int] = Query(None, description="返回数量限制"),
    offset: int = Query(0, description="偏移量"),
    session: Session = Depends(get_session)
):
    """
    获取番剧列表
    
    参数:
        limit: 返回数量
        offset: 偏移量
        session: 数据库会话
        
    返回:
        番剧列表
    """
    analytics_service = AnalyticsService(session)
    animes = analytics_service.get_all_animes(limit=limit, offset=offset)
    
    return {
        "success": True,
        "total": len(animes),
        "list": animes
    }


@router.get("/animes/{season_id}", response_model=dict)
async def get_anime_detail(season_id: int, session: Session = Depends(get_session)):
    """
    获取番剧详情，若尚未绑定 TMDB 数据则自动触发富集（超时或失败时降级返回基础数据）。

    参数:
        season_id: 番剧 ID
        session: 数据库会话

    返回:
        番剧详情（含可选的 tmdb_info 嵌套字段）
    """
    from ..tmdb_service import TmdbService
    from ..models import TmdbAnimeInfo
    from sqlmodel import select as sql_select

    analytics_service = AnalyticsService(session)
    anime = analytics_service.get_anime_by_id(season_id)

    if not anime:
        raise HTTPException(status_code=404, detail="番剧不存在")

    # 若尚未绑定 TMDB 数据，则自动触发富集（失败时降级，不阻断主流程）
    if anime.get("tmdb_info") is None:
        try:
            from ..tmdb_service import TmdbService  # 延迟导入，避免模块加载期语法错误影响路由注册
            service = TmdbService()
            if service.is_available():
                info = await asyncio.wait_for(
                    service.enrich_anime(
                        season_id=season_id,
                        title=anime["title"],
                        release_date=anime.get("release_date"),
                    ),
                    timeout=5.0,
                )
                if info:
                    existing = session.exec(
                        sql_select(TmdbAnimeInfo).where(TmdbAnimeInfo.season_id == season_id)
                    ).first()
                    if existing:
                        existing.tmdb_id = info.tmdb_id
                        existing.original_name = info.original_name
                        existing.overview = info.overview
                        existing.tmdb_rating = info.tmdb_rating
                        existing.backdrop_url = info.backdrop_url
                        existing.logo_url = info.logo_url
                        existing.poster_url = info.poster_url
                        existing.genres = info.genres
                        existing.first_air_date = info.first_air_date
                        existing.updated_at = info.updated_at
                        session.add(existing)
                    else:
                        session.add(info)
                    session.commit()

                    # 写入成功后重新读取，以返回完整数据
                    anime = analytics_service.get_anime_by_id(season_id) or anime
        except asyncio.TimeoutError:
            logger.warning("自动 TMDB 富集超时（season_id=%s），降级返回基础数据", season_id)
        except Exception:
            logger.warning("自动 TMDB 富集失败（season_id=%s），降级返回基础数据", season_id, exc_info=True)

    return {
        "success": True,
        "data": anime
    }

@router.post("/tmdb/enrich/{season_id}", response_model=dict)
async def trigger_tmdb_enrich(season_id: int, session: Session = Depends(get_session)):
    """
    手动触发单部番剧的 TMDB 数据富集。

    若该番剧已有 TMDB 记录，则更新现有记录；否则新建记录。
    适用于首次导入或需要强制刷新 TMDB 数据的场景。

    参数:
        season_id: 需要富集的番剧 season_id
        session:   数据库会话

    返回:
        富集结果，包含 tmdb_id 等关键字段
    """
    # 校验番剧是否存在
    anime = session.exec(
        sql_select(Anime).where(Anime.season_id == season_id)
    ).first()
    if not anime:
        raise HTTPException(status_code=404, detail="番剧不存在")

    from ..tmdb_service import TmdbService  # 延迟导入，避免模块加载期语法错误影响路由注册
    service = TmdbService()
    if not service.is_available():
        raise HTTPException(status_code=503, detail="TMDB_API_KEY 未配置，服务不可用")

    # 执行富集
    info = await service.enrich_anime(
        season_id=anime.season_id,
        title=anime.title,
        release_date=anime.release_date,
    )
    if not info:
        raise HTTPException(status_code=404, detail="未在 TMDB 找到匹配的番剧记录")

    # 若已有记录则更新，否则新建
    def _upsert_tmdb_info() -> None:
        existing = session.exec(
            sql_select(TmdbAnimeInfo).where(TmdbAnimeInfo.season_id == season_id)
        ).first()
        if existing:
            existing.tmdb_id = info.tmdb_id
            existing.original_name = info.original_name
            existing.overview = info.overview
            existing.tmdb_rating = info.tmdb_rating
            existing.backdrop_url = info.backdrop_url
            existing.logo_url = info.logo_url
            existing.poster_url = info.poster_url
            existing.genres = info.genres
            existing.first_air_date = info.first_air_date
            existing.updated_at = info.updated_at
            session.add(existing)
        else:
            session.add(info)
        session.commit()

    # 将同步数据库操作放入线程池，避免阻塞事件循环
    await asyncio.to_thread(_upsert_tmdb_info)

    return {
        "success": True,
        "message": f"番剧 {anime.title} 的 TMDB 数据富集成功",
        "data": {
            "season_id": info.season_id,
            "tmdb_id": info.tmdb_id,
            "original_name": info.original_name,
            "overview": info.overview,
            "tmdb_rating": info.tmdb_rating,
            "backdrop_url": info.backdrop_url,
            "logo_url": info.logo_url,
            "poster_url": info.poster_url,
            "genres": json.loads(info.genres) if info.genres else [],
            "first_air_date": info.first_air_date,
        },
    }


@router.get("/search", response_model=dict)
def search_animes(
    keyword: str = Query(..., description="搜索关键词"),
    session: Session = Depends(get_session)
):
    """
    搜索番剧。若本地数据库中无匹配结果，则实时调用 B 站开放接口抓取并写入数据库。

    参数:
        keyword: 搜索关键词
        session: 数据库会话

    返回:
        搜索结果列表
    """
    from ..scraper import BilibiliBangumiCrawler

    analytics_service = AnalyticsService(session)
    results = analytics_service.search_anime_by_title(keyword)

    if not results:
        # 本地未命中，触发实时抓取
        crawler = BilibiliBangumiCrawler(session)
        season_id = crawler.anime_sync.fetch_and_save_anime_with_episodes(keyword)
        if season_id:
            # 抓取成功后重新查询数据库
            results = analytics_service.search_anime_by_title(keyword)

    return {
        "success": True,
        "total": len(results),
        "list": results
    }


@router.get("/rankings", response_model=dict)
def get_rankings(
    sort_by: str = Query("views", description="排序字段: views, favorites, rating"),
    limit: int = Query(10, description="返回数量"),
    area: Optional[AreaEnum] = Query(None, description="地区筛选"),
    styles: Optional[str] = Query(None, description="风格筛选，逗号分隔"),
    season: Optional[SeasonEnum] = Query(None, description="季节筛选: spring, summer, autumn, winter"),
    session: Session = Depends(get_session)
):
    """
    获取排行榜

    参数:
        sort_by: 排序字段
        limit: 返回数量
        area: 地区筛选
        styles: 风格筛选
        season: 季节筛选（spring/summer/autumn/winter）
        session: 数据库会话

    返回:
        排行榜数据
    """
    analytics_service = AnalyticsService(session)

    # 解析风格列表
    style_list = None
    if styles:
        style_list = [s.strip() for s in styles.split(',')]

    rankings = analytics_service.get_top_animes(
        sort_by=sort_by,
        limit=limit,
        area=area.value if area else None,
        styles=style_list,
        season=season.value if season else None,
    )

    return {
        "success": True,
        "total": len(rankings),
        "list": rankings
    }


@router.get("/overview", response_model=dict)
def get_overview(session: Session = Depends(get_session)):
    """
    获取数据总览统计
    
    参数:
        session: 数据库会话
        
    返回:
        统计数据
    """
    analytics_service = AnalyticsService(session)
    stats = analytics_service.get_statistics_overview()
    
    return {
        "success": True,
        "data": stats
    }


@router.get("/animes/{season_id}/history", response_model=dict)
def get_anime_history(
    season_id: int,
    days: int = Query(30, description="查询天数"),
    session: Session = Depends(get_session)
):
    """
    获取番剧历史数据
    
    参数:
        season_id: 番剧 ID
        days: 查询天数
        session: 数据库会话
        
    返回:
        历史数据
    """
    analytics_service = AnalyticsService(session)
    history = analytics_service.get_anime_history(season_id, days)
    
    return {
        "success": True,
        "data": history
    }


@router.get("/statistics/styles", response_model=dict)
def get_style_distribution(
    area: Optional[AreaEnum] = Query(None, description="地区筛选（如 国内、日本、美国）"),
    session: Session = Depends(get_session)
):
    """
    获取风格分布统计

    参数:
        area: 地区筛选，None 表示全部
        session: 数据库会话

    返回:
        风格分布数据
    """
    analytics_service = AnalyticsService(session)
    distribution = analytics_service.get_style_distribution(area=area.value if area else None)

    return {
        "success": True,
        "data": distribution
    }


@router.get("/statistics/trends", response_model=dict)
def get_release_trend(
    area: Optional[AreaEnum] = Query(None, description="地区筛选（如 国内、日本、美国）"),
    session: Session = Depends(get_session)
):
    """
    获取发布趋势统计

    参数:
        area: 地区筛选，None 表示全部
        session: 数据库会话

    返回:
        发布趋势数据
    """
    analytics_service = AnalyticsService(session)
    trend = analytics_service.get_release_trend(area=area.value if area else None)

    return {
        "success": True,
        "data": trend
    }


@router.get("/animes/{season_id}/episodes", response_model=dict)
def get_anime_episodes(season_id: int, session: Session = Depends(get_session)):
    """
    获取番剧剧集数据

    优先返回 EpisodeStats 表中的真实数据；若无数据，则以每日统计记录作为代理。

    参数:
        season_id: 番剧 ID
        session: 数据库会话

    返回:
        剧集列表，每项包含 title、views、peakTime、peakOnline 字段
    """
    analytics_service = AnalyticsService(session)
    episodes = analytics_service.get_anime_episodes(season_id)

    return {
        "success": True,
        "total": len(episodes),
        "data": episodes
    }


@router.get("/animes/{season_id}/watch-time", response_model=dict)
def get_watch_time(season_id: int, session: Session = Depends(get_session)):
    """
    获取番剧各集的 24 小时观看时间分布（真实数据）。

    从 EpisodeStats.hourly_online_history 列读取每小时在线人数快照，
    格式化为长度 24 的整数数组供前端 ECharts 渲染。

    参数:
        season_id: 番剧 ID
        session: 数据库会话

    返回:
        各集 24 小时分布数据，episodes_data 为空时返回 404
    """
    analytics_service = AnalyticsService(session)
    data = analytics_service.get_watch_time_distribution(season_id)

    if not data["episodes_data"]:
        raise HTTPException(status_code=404, detail="暂无分集在线人数数据")

    return {
        "success": True,
        "data": data,
    }


@router.get("/charts/reputation-popularity", response_model=dict)
def get_reputation_popularity_chart(
    areas: Optional[str] = Query(None, description="地区筛选，逗号分隔（如 国内,日本）"),
    session: Session = Depends(get_session)
):
    """
    获取口碑与热度散点图数据

    参数:
        areas: 地区列表，逗号分隔，None 表示全部
        session: 数据库会话

    返回:
        散点图数据列表，每项包含 title、rating、favorites、views、area 字段
    """
    analytics_service = AnalyticsService(session)
    area_list = _parse_areas_param(areas)
    data = analytics_service.get_reputation_popularity_chart(areas=area_list)

    return {
        "success": True,
        "total": len(data),
        "data": data
    }


@router.get("/charts/preference-difference", response_model=dict)
def get_preference_difference_chart(
    region: AreaEnum = Query(AreaEnum.china, description="地区名称（如 国内、日本、美国）"),
    session: Session = Depends(get_session)
):
    """
    获取地区偏好差异图数据

    参数:
        region: 地区名称，默认 "国内"
        session: 数据库会话

    返回:
        偏好指数列表，每项包含 style、preferenceIndex、regionCount、globalCount 字段
    """
    analytics_service = AnalyticsService(session)
    data = analytics_service.get_preference_difference_chart(region=region.value)

    return {
        "success": True,
        "total": len(data),
        "data": data
    }


@router.get("/charts/reputation-heat-index", response_model=dict)
def get_reputation_heat_index_chart(
    season: Optional[SeasonEnum] = Query(None, description="季节筛选: spring, summer, autumn, winter"),
    category: Optional[str] = Query(None, description="风格/类型筛选"),
    session: Session = Depends(get_session)
):
    """
    获取口碑热度指数图数据

    参数:
        season: 季节筛选（spring/summer/autumn/winter）
        category: 风格/类型筛选
        session: 数据库会话

    返回:
        前 15 名番剧列表，每项包含 title、qualityScore、rating、favorites、views 字段
    """
    analytics_service = AnalyticsService(session)
    data = analytics_service.get_reputation_heat_index_chart(
        season=season.value if season else None,
        category=_validate_category_value(category),
    )

    return {
        "success": True,
        "total": len(data),
        "data": data
    }


@router.get("/charts/popular-style-combination", response_model=dict)
def get_popular_style_combination_chart(session: Session = Depends(get_session)):
    """
    获取热门风格组合图数据

    参数:
        session: 数据库会话

    返回:
        前 20 个风格组合列表，每项包含 combination、totalFavorites、animeCount、
        avgFavorites、representativeAnimes 字段
    """
    analytics_service = AnalyticsService(session)
    data = analytics_service.get_popular_style_combination_chart()

    return {
        "success": True,
        "total": len(data),
        "data": data
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1. 单集受众行为分析端点
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/animes/{season_id}/episode-behavior",
    response_model=dict,
    summary="单集受众行为分析",
)
def get_episode_behavior_analysis(
    season_id: int,
    session: Session = Depends(get_session),
):
    """
    单集受众行为分析：留存率、硬核指数与弹幕评论密度。

    - **留存率**：以第1集播放量为基准，计算第3集及最终集的观众留存百分比。
    - **硬核指数**：逐集计算投币率（coin/views）和点赞率（like/views），
      高投币率表明内容质量高，低值则可能为标题党。
    - **共鸣密度**：逐集计算弹幕率（danmaku/views）和评论率（reply/views），
      反映观众互动活跃程度。

    参数:
        season_id: 番剧 season_id
        session: 数据库会话

    返回:
        留存率、各集互动指标及全剧平均指标
    """
    analytics_service = AnalyticsService(session)
    data = analytics_service.get_episode_behavior_analysis(season_id)

    if data is None:
        raise HTTPException(status_code=404, detail="该番剧暂无分集数据")

    return {
        "success": True,
        "data": data,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. 生命周期与增长分析端点
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/animes/{season_id}/lifecycle",
    response_model=dict,
    summary="生命周期与增长分析",
)
def get_lifecycle_growth_analysis(
    season_id: int,
    window_days: int = Query(30, description="滑动窗口天数（预留扩展参数）"),
    session: Session = Depends(get_session),
):
    """
    生命周期与增长分析：黑马指数（一/二阶导数）与长尾效应。

    - **黑马指数**：计算每日播放量和追番数的一阶导数（日增量）与
      二阶导数（增速加速度），峰值日增可作为黑马爆发力参考。
    - **长尾效应**：统计首播后 30 天和 90 天的日均播放量，
      评估番剧的持续影响力与生命周期。

    参数:
        season_id: 番剧 season_id
        window_days: 滑动窗口天数（预留参数）
        session: 数据库会话

    返回:
        逐日增长数据、长尾效应及峰值增长信息
    """
    analytics_service = AnalyticsService(session)
    data = analytics_service.get_lifecycle_growth_analysis(season_id, window_days)

    if data is None:
        raise HTTPException(status_code=404, detail="番剧不存在")

    return {
        "success": True,
        "data": data,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. 竞争态势分析端点
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/animes/{season_id}/competitive",
    response_model=dict,
    summary="竞争态势分析",
)
def get_competitive_landscape_analysis(
    season_id: int,
    start_date: Optional[str] = Query(None, description="统计开始日期，格式 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="统计结束日期，格式 YYYY-MM-DD"),
    session: Session = Depends(get_session),
):
    """
    竞争态势分析：霸榜指数与排名波动率。

    - **霸榜指数**：统计指定时间范围内番剧进入排行榜前3名和前10名的天数占比，
      反映该番剧在竞争环境中的统治力。
    - **排名波动率**：计算排名位置的标准差，数值越小说明排名越稳定。

    参数:
        season_id: 番剧 season_id
        start_date: 统计开始日期（可选）
        end_date: 统计结束日期（可选）
        session: 数据库会话

    返回:
        上榜天数、霸榜比例、平均排名及波动率
    """
    parsed_start = None
    parsed_end = None
    try:
        if start_date:
            parsed_start = datetime.strptime(start_date, "%Y-%m-%d")
        if end_date:
            parsed_end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD")

    analytics_service = AnalyticsService(session)
    data = analytics_service.get_competitive_landscape_analysis(
        season_id, parsed_start, parsed_end
    )

    return {
        "success": True,
        "data": data,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. 题材季节性规律分析端点
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/seasonal-genre-trends",
    response_model=dict,
    summary="题材季节性规律分析",
)
def get_seasonal_genre_trends(session: Session = Depends(get_session)):
    """
    题材季节性规律分析：跨维度分析发布季节、题材风格与播放量的关联。

    将番剧 release_date 的月份映射为四季（spring=04月, summer=07月,
    autumn=10月, winter=01月），结合 styles 和最新播放量，计算各季节
    每种题材的平均播放量，识别不同季节表现最佳的题材类型。

    参数:
        session: 数据库会话

    返回:
        各季节题材数据列表及每季最佳题材映射
    """
    analytics_service = AnalyticsService(session)
    data = analytics_service.get_seasonal_genre_trends()

    return {
        "success": True,
        "total": len(data.get("trends", [])),
        "data": data,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. 用户个性化推荐端点
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/users/{username}/recommendations",
    response_model=dict,
    summary="用户个性化番剧推荐",
)
def get_personalized_recommendations(
    username: str,
    session: Session = Depends(get_session),
):
    """
    用户个性化推荐：基于双向匹配度算法为用户生成番剧推荐列表。

    算法说明：
    - **有偏好**：以用户偏好风格与番剧风格的 Jaccard 相似度为基础（权重80%），
      叠加全局热门风格组合奖励分（权重20%），计算0~100的匹配度。
    - **无偏好**：按播放量和追番数的归一化热度排序。
    返回匹配度最高的前50部番剧。

    参数:
        username: 用户名
        session: 数据库会话

    返回:
        用户偏好风格及排序后的推荐番剧列表（含匹配度分数）
    """
    analytics_service = AnalyticsService(session)
    data = analytics_service.get_personalized_recommendations(username)

    if data is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    return {
        "success": True,
        "total": len(data.get("recommendations", [])),
        "data": data,
    }


@router.get(
    "/users/{username}/recommendations/{season_id}/explanation",
    response_model=dict,
    summary="推荐解释详情",
)
def get_recommendation_explanation(
    username: str,
    season_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """获取用户对指定番剧的可解释推荐明细。"""
    if not current_user.is_admin and username != current_user.username:
        raise HTTPException(status_code=403, detail="无权查看其他用户的推荐解释")

    analytics_service = AnalyticsService(session)
    data = analytics_service.get_recommendation_explanation(username, season_id)

    if data is None:
        raise HTTPException(status_code=404, detail="用户或番剧不存在")

    return {
        "success": True,
        "data": data,
    }
