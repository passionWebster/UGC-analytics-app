"""
个人空间相关 API 路由
"""
import json
import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlmodel import Session, select

from ..auth import AuthService, get_current_user
from ..database import get_session
from ..models import Anime, DailyStats, User, UserFavorite
from ..schemas import (
    FavoriteStatusUpdateRequest,
    FavoriteToggleRequest,
    UserPasswordUpdate,
)


router = APIRouter(prefix="/api/user", tags=["个人空间"])
logger = logging.getLogger(__name__)


@router.get("/favorites", response_model=dict)
def get_user_favorites(
    status: str | None = Query(default=None, description="追番状态筛选"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    获取当前登录用户追番列表。
    """
    query = (
        select(UserFavorite, Anime)
        .join(Anime, Anime.season_id == UserFavorite.season_id)
        .where(UserFavorite.user_id == current_user.id)
        .order_by(desc(UserFavorite.created_at))
    )
    if status:
        query = query.where(UserFavorite.status == status)

    rows = session.exec(query).all()
    data = []
    for favorite, anime in rows:
        data.append(
            {
                "id": favorite.id,
                "season_id": anime.season_id,
                "title": anime.title,
                "cover": anime.cover,
                "status": favorite.status,
                "rating": anime.rating,
                "created_at": favorite.created_at.isoformat(),
            }
        )

    return {"success": True, "total": len(data), "data": data}


@router.post("/favorites", response_model=dict)
def toggle_user_favorite(
    payload: FavoriteToggleRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    添加/取消当前登录用户追番收藏。
    """
    anime = session.exec(select(Anime).where(Anime.season_id == payload.season_id)).first()
    if not anime:
        raise HTTPException(status_code=404, detail="番剧不存在")

    existing = session.exec(
        select(UserFavorite).where(
            UserFavorite.user_id == current_user.id,
            UserFavorite.season_id == payload.season_id,
        )
    ).first()

    if existing:
        session.delete(existing)
        session.commit()
        return {
            "success": True,
            "action": "removed",
            "message": "已取消收藏",
            "season_id": payload.season_id,
        }

    favorite = UserFavorite(
        user_id=current_user.id,
        season_id=payload.season_id,
        status=payload.status,
    )
    session.add(favorite)
    session.commit()
    session.refresh(favorite)
    return {
        "success": True,
        "action": "added",
        "message": "已加入追番列表",
        "data": {
            "id": favorite.id,
            "season_id": favorite.season_id,
            "status": favorite.status,
            "created_at": favorite.created_at.isoformat(),
        },
    }


@router.put("/favorites/{season_id}/status", response_model=dict)
def update_favorite_status(
    season_id: int,
    payload: FavoriteStatusUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    更新当前用户追番状态。
    """
    favorite = session.exec(
        select(UserFavorite).where(
            UserFavorite.user_id == current_user.id,
            UserFavorite.season_id == season_id,
        )
    ).first()
    if not favorite:
        raise HTTPException(status_code=404, detail="追番记录不存在")

    favorite.status = payload.status
    session.add(favorite)
    session.commit()
    session.refresh(favorite)
    return {
        "success": True,
        "message": "追番状态已更新",
        "data": {
            "season_id": favorite.season_id,
            "status": favorite.status,
        },
    }


@router.put("/password", response_model=dict)
def update_user_password(
    payload: UserPasswordUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    当前用户修改密码（校验旧密码）。
    """
    auth_service = AuthService(session)
    auth_service.change_password(current_user, payload.old_password, payload.new_password)
    return {"success": True, "message": "密码修改成功"}


@router.get("/analytics", response_model=dict)
def get_user_space_analytics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    获取个人看板聚合数据。
    """
    favorites = session.exec(
        select(UserFavorite).where(UserFavorite.user_id == current_user.id)
    ).all()
    if not favorites:
        return {
            "success": True,
            "data": {
                "watchlist_count": 0,
                "status_distribution": {"plan": 0, "watching": 0, "completed": 0},
                "genre_distribution": [],
                "weekly_views_summary": {
                    "latest_views_total": 0,
                    "week_ago_views_total": 0,
                    "weekly_growth": 0,
                    "weekly_growth_rate": None,
                },
            },
        }

    status_distribution = {"plan": 0, "watching": 0, "completed": 0}
    genre_counter: dict[str, int] = {}
    latest_views_total = 0
    week_ago_views_total = 0

    for favorite in favorites:
        if favorite.status not in status_distribution:
            logger.warning(
                "Invalid favorite status found for user_id=%s season_id=%s status=%s",
                current_user.id,
                favorite.season_id,
                favorite.status,
            )
            continue
        status_distribution[favorite.status] += 1

        anime = session.exec(select(Anime).where(Anime.season_id == favorite.season_id)).first()
        if anime and anime.styles:
            try:
                styles = json.loads(anime.styles)
            except json.JSONDecodeError:
                logger.warning("Anime styles parse failed for season_id=%s", favorite.season_id)
                styles = []
            for genre in styles:
                genre_counter[genre] = genre_counter.get(genre, 0) + 1

        latest = session.exec(
            select(DailyStats)
            .where(DailyStats.season_id == favorite.season_id)
            .order_by(desc(DailyStats.date))
            .limit(1)
        ).first()
        if not latest:
            continue

        latest_views_total += latest.views
        week_ago = session.exec(
            select(DailyStats)
            .where(
                DailyStats.season_id == favorite.season_id,
                DailyStats.date <= latest.date - timedelta(days=7),
            )
            .order_by(desc(DailyStats.date))
            .limit(1)
        ).first()
        week_ago_views_total += week_ago.views if week_ago else 0

    weekly_growth = latest_views_total - week_ago_views_total
    weekly_growth_rate = (
        round(weekly_growth / week_ago_views_total * 100, 2)
        if week_ago_views_total > 0
        else None
    )

    genre_distribution = [
        {"genre": name, "count": count}
        for name, count in sorted(genre_counter.items(), key=lambda x: x[1], reverse=True)
    ]

    return {
        "success": True,
        "data": {
            "watchlist_count": len(favorites),
            "status_distribution": status_distribution,
            "genre_distribution": genre_distribution,
            "weekly_views_summary": {
                "latest_views_total": latest_views_total,
                "week_ago_views_total": week_ago_views_total,
                "weekly_growth": weekly_growth,
                "weekly_growth_rate": weekly_growth_rate,
            },
        },
    }
