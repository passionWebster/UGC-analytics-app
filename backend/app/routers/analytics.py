# routers/analytics.py
"""
数据分析相关的 API 路由
"""
import os
import re
from typing import List, Optional
from urllib.parse import urlparse
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlmodel import Session

from ..database import get_session
from ..crud import AnalyticsService


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
}


@proxy_router.get("/image_proxy")
def image_proxy(
    url: str = Query(..., description="原始图片链接"),
    title: str = Query(..., description="番剧名"),
    season_id: str = Query(..., description="番剧 season_id"),
):
    """
    图片反向代理接口，绕过 B站图片防盗链并提供本地缓存。

    首先检查本地 cover_cache 目录是否已缓存该图片；若命中则直接返回，
    否则伪造 Referer 请求原始 URL，将图片二进制保存后再返回。

    Args:
        url: 原始图片链接
        title: 番剧名（用于生成缓存文件名）
        season_id: 番剧 season_id（用于生成缓存文件名）

    Returns:
        图片文件响应（FileResponse）
    """
    os.makedirs(_COVER_CACHE_DIR, exist_ok=True)

    # 校验 URL 只能指向 B站图片 CDN（防止 SSRF）
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in _ALLOWED_IMAGE_HOSTS:
        raise HTTPException(status_code=400, detail="不支持的图片域名，仅允许 B站图片 CDN 域名")

    # 生成安全的文件名：清理特殊字符，保留字母、数字、中文、连字符
    safe_title = re.sub(r"[^\w\u4e00-\u9fff\-]", "_", title)
    safe_season_id = re.sub(r"[^\w]", "_", str(season_id))
    # 尝试从 URL 中推断扩展名，默认使用 .jpg
    url_path = url.split("?")[0]
    ext = os.path.splitext(url_path)[-1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        ext = ".jpg"
    filename = f"{safe_title}_{safe_season_id}{ext}"
    filepath = os.path.join(_COVER_CACHE_DIR, filename)

    # 命中本地缓存则直接返回
    if os.path.exists(filepath):
        return FileResponse(filepath)

    # 伪造 Referer 请求原始图片
    headers = {
        "Referer": "https://www.bilibili.com/",
        "User-Agent": "Mozilla/5.0",
    }
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
