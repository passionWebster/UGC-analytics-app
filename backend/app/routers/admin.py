"""后台管理相关 API 路由

提供用户管理、爬虫监控与基础运营看板功能，全部接口均需管理员权限。
"""
from collections import Counter
import json
from typing import List
from datetime import datetime

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy import desc, func
from sqlmodel import Session, select

from ..auth import get_current_admin_user
from ..database import get_session, engine
from ..models import User, CrawlLog, Anime
from ..schemas import UserStatusUpdate, ResetPasswordRequest
from ..scraper import BilibiliBangumiCrawler
from ..config import settings


router = APIRouter(prefix="/api/admin", tags=["后台管理"])


@router.get("/users", response_model=dict)
def list_users(
    session: Session = Depends(get_session),
    _admin=Depends(get_current_admin_user),
):
    """获取所有用户列表"""
    users: List[User] = session.exec(
        select(User).order_by(desc(User.created_at))
    ).all()

    return {
        "success": True,
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "is_admin": u.is_admin,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat(),
            }
            for u in users
        ],
    }


@router.patch("/users/{user_id}/status", response_model=dict)
def update_user_status(
    user_id: int,
    payload: UserStatusUpdate,
    session: Session = Depends(get_session),
    admin=Depends(get_current_admin_user),
):
    """封禁/解封用户"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user.id == admin.id and not payload.is_active:
        raise HTTPException(status_code=400, detail="不能停用自己的账户")

    user.is_active = payload.is_active
    session.add(user)
    session.commit()
    session.refresh(user)

    return {"success": True, "message": "用户状态已更新", "is_active": user.is_active}


@router.post("/users/{user_id}/reset-password", response_model=dict)
def reset_user_password(
    user_id: int,
    payload: ResetPasswordRequest,
    session: Session = Depends(get_session),
    _admin=Depends(get_current_admin_user),
):
    """重置用户密码"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.password = payload.new_password
    session.add(user)
    session.commit()

    return {"success": True, "message": "密码已重置"}


@router.get("/crawler/logs", response_model=dict)
def get_crawler_logs(
    limit: int = 20,
    session: Session = Depends(get_session),
    _admin=Depends(get_current_admin_user),
):
    """获取最近的爬虫任务日志"""
    logs = session.exec(
        select(CrawlLog).order_by(desc(CrawlLog.started_at)).limit(limit)
    ).all()

    return {
        "success": True,
        "logs": [
            {
                "id": log.id,
                "task_type": log.task_type,
                "status": log.status,
                "items_count": log.items_count,
                "error_message": log.error_message,
                "started_at": log.started_at.isoformat(),
                "completed_at": log.completed_at.isoformat() if log.completed_at else None,
            }
            for log in logs
        ],
    }


def _run_update_task() -> None:
    """后台任务：更新番剧基础数据（使用独立 Session）"""
    with Session(engine) as background_session:
        crawler = BilibiliBangumiCrawler(background_session)
        crawler.update_anime_database()


@router.post("/crawler/trigger", response_model=dict)
def trigger_crawler_update(
    background_tasks: BackgroundTasks,
    _admin=Depends(get_current_admin_user),
):
    """手动触发爬虫更新任务"""
    background_tasks.add_task(_run_update_task)
    return {"success": True, "message": "数据更新任务已启动"}


@router.get("/overview", response_model=dict)
def admin_overview(
    session: Session = Depends(get_session),
    _admin=Depends(get_current_admin_user),
):
    """运营/监控大盘"""
    total_users = session.exec(select(func.count()).select_from(User)).one()
    active_users = session.exec(
        select(func.count()).select_from(User).where(User.is_active == True)  # noqa: E712
    ).one()
    admin_users = session.exec(
        select(func.count()).select_from(User).where(User.is_admin == True)  # noqa: E712
    ).one()
    total_anime = session.exec(select(func.count()).select_from(Anime)).one()

    latest_log = session.exec(
        select(CrawlLog).order_by(desc(CrawlLog.started_at)).limit(1)
    ).first()

    # 统计最常出现的风格（Genre）
    styles_counter: Counter[str] = Counter()
    style_rows = session.exec(
        select(Anime.styles).where(Anime.styles.is_not(None))
    ).all()
    for style_json in style_rows:
        if not style_json:
            continue
        try:
            styles = json.loads(style_json)
            for s in styles:
                if s:
                    styles_counter[s] += 1
        except Exception:
            continue
    top_genres = styles_counter.most_common(8)

    return {
        "success": True,
        "metrics": {
            "total_users": total_users[0] if isinstance(total_users, tuple) else total_users,
            "active_users": active_users[0] if isinstance(active_users, tuple) else active_users,
            "admin_users": admin_users[0] if isinstance(admin_users, tuple) else admin_users,
            "total_anime": total_anime[0] if isinstance(total_anime, tuple) else total_anime,
        },
        "latest_crawl": {
            "status": latest_log.status if latest_log else "never_run",
            "task_type": latest_log.task_type if latest_log else None,
            "items_count": latest_log.items_count if latest_log else 0,
            "started_at": latest_log.started_at.isoformat() if latest_log else None,
            "completed_at": latest_log.completed_at.isoformat() if latest_log and latest_log.completed_at else None,
            "error_message": latest_log.error_message if latest_log else None,
        },
        "top_genres": [{"name": name, "count": count} for name, count in top_genres],
    }


@router.get("/ai/stats", response_model=dict)
def ai_stats(
    _admin=Depends(get_current_admin_user),
):
    """
    AI 服务调用监控占位接口。
    目前未持久化调用量，可按需在 ai_service 中增加埋点。
    """
    return {
        "success": True,
        "ai_enabled": bool(settings.doubao_api_key),
        "message": (
            "AI 接口已启用" if settings.doubao_api_key else "未配置 AI API Key，已降级为本地规则"
        ),
        "call_stats": {
            "call_count": 0,
            "avg_latency_ms": None,
            "last_error": None,
        },
    }
