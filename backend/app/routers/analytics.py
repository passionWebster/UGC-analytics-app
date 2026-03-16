# routers/analytics.py
"""
数据分析相关的 API 路由
"""
import json
import os
import re
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse
import asyncio
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlmodel import Session

from ..database import get_session
from ..crud import AnalyticsService
from ..models import Anime
from ..schemas import (
    EpisodeBehaviorAnalysisResponse,
    LifecycleGrowthResponse,
    CompetitiveLandscapeResponse,
    SeasonalGenreTrendsResponse,
    PersonalizedRecommendationsResponse,
)


router = APIRouter(prefix="/api/analytics", tags=["数据分析"])
# 图片代理路由（路径为 /api/image_proxy，与 analytics 路由独立）
proxy_router = APIRouter(prefix="/api", tags=["图片代理"])

# 封面图片本地缓存目录
_COVER_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "cover_cache",
)

# B站图片 CDN 允许域名白名单（防止 SSRF）
_ALLOWED_IMAGE_HOSTS = {
    "i0.hdslb.com",
    "i1.hdslb.com",
    "i2.hdslb.com",
    "s1.hdslb.com",
    "s2.hdslb.com",
    "pic.bilibili.com",
    "static.hdslb.com",
    # TMDB 图片服务器（背景图、Logo、海报均由此域名提供）
    "image.tmdb.org",
}


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

    Args:
        url: 原始图片链接（支持 B站 CDN 和 image.tmdb.org）
        title: 番剧名（用于生成缓存文件名）
        season_id: 番剧 season_id（用于生成缓存文件名）

    Returns:
        图片文件响应（FileResponse）
    """
    os.makedirs(_COVER_CACHE_DIR, exist_ok=True)

    # 校验 URL 只能指向白名单域名（防止 SSRF）
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in _ALLOWED_IMAGE_HOSTS:
        raise HTTPException(status_code=400, detail="不支持的图片域名，仅允许 B站图片 CDN 及 TMDB 图片域名")

    # 生成安全的文件名：清理特殊字符，保留字母、数字、中文、连字符
    safe_title = re.sub(r"[^\w\u4e00-\u9fff\-]", "_", title)
    safe_season_id = re.sub(r"[^\w]", "_", str(season_id))
    # 尝试从 URL 中推断扩展名，默认使用 .jpg
    url_path = url.split("?")[0]
    ext = os.path.splitext(url_path)[-1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"):
        ext = ".jpg"
    filename = f"{safe_title}_{safe_season_id}{ext}"
    filepath = os.path.join(_COVER_CACHE_DIR, filename)

    # 命中本地缓存则直接返回
    if os.path.exists(filepath):
        return FileResponse(filepath)

    # 按域名区分请求头策略：B站需要伪造 Referer，TMDB 无需
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
    
    Args:
        limit: 返回数量
        offset: 偏移量
        session: 数据库会话
        
    Returns:
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
def get_anime_detail(season_id: int, session: Session = Depends(get_session)):
    """
    获取番剧详情
    
    Args:
        season_id: 番剧 ID
        session: 数据库会话
        
    Returns:
        番剧详情
    """
    analytics_service = AnalyticsService(session)
    anime = analytics_service.get_anime_by_id(season_id)
    
    if not anime:
        raise HTTPException(status_code=404, detail="番剧不存在")
    
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

    Args:
        season_id: 需要富集的番剧 season_id
        session:   数据库会话

    Returns:
        富集结果，包含 tmdb_id 等关键字段
    """
    from ..tmdb_service import TmdbService
    from ..models import TmdbAnimeInfo
    from sqlmodel import select as sql_select

    # 校验番剧是否存在
    anime = session.exec(
        sql_select(Anime).where(Anime.season_id == season_id)
    ).first()
    if not anime:
        raise HTTPException(status_code=404, detail="番剧不存在")

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
    搜索番剧。若本地数据库中无匹配结果，则实时调用 B站 API 抓取并写入数据库。

    Args:
        keyword: 搜索关键词
        session: 数据库会话

    Returns:
        搜索结果列表
    """
    from ..scraper import BilibiliBangumiCrawler

    analytics_service = AnalyticsService(session)
    results = analytics_service.search_anime_by_title(keyword)

    if not results:
        # 本地未命中，触发实时抓取
        crawler = BilibiliBangumiCrawler(session)
        season_id = crawler.fetch_and_save_anime_with_episodes(keyword)
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
    area: Optional[str] = Query(None, description="地区筛选"),
    styles: Optional[str] = Query(None, description="风格筛选，逗号分隔"),
    season: Optional[str] = Query(None, description="季节筛选: spring, summer, autumn, winter"),
    session: Session = Depends(get_session)
):
    """
    获取排行榜

    Args:
        sort_by: 排序字段
        limit: 返回数量
        area: 地区筛选
        styles: 风格筛选
        season: 季节筛选（spring/summer/autumn/winter）
        session: 数据库会话

    Returns:
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
        area=area,
        styles=style_list,
        season=season,
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
    
    Args:
        session: 数据库会话
        
    Returns:
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
    
    Args:
        season_id: 番剧 ID
        days: 查询天数
        session: 数据库会话
        
    Returns:
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
    area: Optional[str] = Query(None, description="地区筛选（如 国内、日本、美国）"),
    session: Session = Depends(get_session)
):
    """
    获取风格分布统计

    Args:
        area: 地区筛选，None 表示全部
        session: 数据库会话

    Returns:
        风格分布数据
    """
    analytics_service = AnalyticsService(session)
    distribution = analytics_service.get_style_distribution(area=area)

    return {
        "success": True,
        "data": distribution
    }


@router.get("/statistics/trends", response_model=dict)
def get_release_trend(
    area: Optional[str] = Query(None, description="地区筛选（如 国内、日本、美国）"),
    session: Session = Depends(get_session)
):
    """
    获取发布趋势统计

    Args:
        area: 地区筛选，None 表示全部
        session: 数据库会话

    Returns:
        发布趋势数据
    """
    analytics_service = AnalyticsService(session)
    trend = analytics_service.get_release_trend(area=area)

    return {
        "success": True,
        "data": trend
    }


@router.get("/animes/{season_id}/episodes", response_model=dict)
def get_anime_episodes(season_id: int, session: Session = Depends(get_session)):
    """
    获取番剧剧集数据

    优先返回 EpisodeStats 表中的真实数据；若无数据，则以每日统计记录作为代理。

    Args:
        season_id: 番剧 ID
        session: 数据库会话

    Returns:
        剧集列表，每项包含 title、views、peakTime、peakOnline 字段
    """
    analytics_service = AnalyticsService(session)
    episodes = analytics_service.get_anime_episodes(season_id)

    return {
        "success": True,
        "total": len(episodes),
        "data": episodes
    }


@router.get("/charts/reputation-popularity", response_model=dict)
def get_reputation_popularity_chart(
    areas: Optional[str] = Query(None, description="地区筛选，逗号分隔（如 国内,日本）"),
    session: Session = Depends(get_session)
):
    """
    获取口碑与热度散点图数据

    Args:
        areas: 地区列表，逗号分隔，None 表示全部
        session: 数据库会话

    Returns:
        散点图数据列表，每项包含 title、rating、favorites、views、area 字段
    """
    analytics_service = AnalyticsService(session)
    area_list = [a.strip() for a in areas.split(',')] if areas else None
    data = analytics_service.get_reputation_popularity_chart(areas=area_list)

    return {
        "success": True,
        "total": len(data),
        "data": data
    }


@router.get("/charts/preference-difference", response_model=dict)
def get_preference_difference_chart(
    region: str = Query("国内", description="地区名称（如 国内、日本、美国）"),
    session: Session = Depends(get_session)
):
    """
    获取地区偏好差异图数据

    Args:
        region: 地区名称，默认 "国内"
        session: 数据库会话

    Returns:
        偏好指数列表，每项包含 style、preferenceIndex、regionCount、globalCount 字段
    """
    analytics_service = AnalyticsService(session)
    data = analytics_service.get_preference_difference_chart(region=region)

    return {
        "success": True,
        "total": len(data),
        "data": data
    }


@router.get("/charts/reputation-heat-index", response_model=dict)
def get_reputation_heat_index_chart(
    season: Optional[str] = Query(None, description="季节筛选: spring, summer, autumn, winter"),
    category: Optional[str] = Query(None, description="风格/类型筛选"),
    session: Session = Depends(get_session)
):
    """
    获取口碑热度指数图数据

    Args:
        season: 季节筛选（spring/summer/autumn/winter）
        category: 风格/类型筛选
        session: 数据库会话

    Returns:
        前 15 名番剧列表，每项包含 title、qualityScore、rating、favorites、views 字段
    """
    analytics_service = AnalyticsService(session)
    data = analytics_service.get_reputation_heat_index_chart(season=season, category=category)

    return {
        "success": True,
        "total": len(data),
        "data": data
    }


@router.get("/charts/popular-style-combination", response_model=dict)
def get_popular_style_combination_chart(session: Session = Depends(get_session)):
    """
    获取热门风格组合图数据

    Args:
        session: 数据库会话

    Returns:
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

    Args:
        season_id: 番剧 season_id
        session: 数据库会话

    Returns:
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

    Args:
        season_id: 番剧 season_id
        window_days: 滑动窗口天数（预留参数）
        session: 数据库会话

    Returns:
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

    Args:
        season_id: 番剧 season_id
        start_date: 统计开始日期（可选）
        end_date: 统计结束日期（可选）
        session: 数据库会话

    Returns:
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

    Args:
        session: 数据库会话

    Returns:
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

    Args:
        username: 用户名
        session: 数据库会话

    Returns:
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
