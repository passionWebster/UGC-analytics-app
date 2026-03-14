# routers/analytics.py
"""
数据分析相关的 API 路由
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from ..database import get_session
from ..crud import AnalyticsService


router = APIRouter(prefix="/api/analytics", tags=["数据分析"])


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
    搜索番剧
    
    Args:
        keyword: 搜索关键词
        session: 数据库会话
        
    Returns:
        搜索结果列表
    """
    analytics_service = AnalyticsService(session)
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
