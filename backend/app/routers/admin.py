"""后台管理相关 API 路由

提供用户管理、爬虫监控与基础运营看板功能，全部接口均需管理员权限。
"""
from collections import Counter
import json
from typing import List
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Query
from sqlalchemy import desc, func, case
from sqlmodel import Session, select

from ..auth import AuthService, get_current_admin_user
from ..database import get_session, engine
from ..models import User, CrawlLog, Anime, RecommendationStrategyConfig, AITelemetry
from ..schemas import UserStatusUpdate, ResetPasswordRequest, RecommendationStrategyUpdate
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

    user.password = AuthService.hash_password(payload.new_password)
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
                "total_scraped": log.total_scraped,
                "cleaned_filtered": log.cleaned_filtered,
                "final_inserted": log.final_inserted,
                "failed_reason": log.failed_reason,
                "duration": log.duration,
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
        select(func.count()).select_from(User).where(User.is_active.is_(True))
    ).one()
    admin_users = session.exec(
        select(func.count()).select_from(User).where(User.is_admin.is_(True))
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
    days: int = Query(default=7, ge=1, le=90),
    session: Session = Depends(get_session),
    _admin=Depends(get_current_admin_user),
):
    """AI 服务调用监控接口（基于 ai_telemetry_logs 聚合）。"""
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    logs = session.exec(
        select(AITelemetry).where(
            AITelemetry.timestamp >= start_time,
            AITelemetry.timestamp <= end_time,
        )
    ).all()

    call_count = len(logs)
    latency_values = [item.latency_ms for item in logs if item.latency_ms is not None]
    avg_latency = round(sum(latency_values) / len(latency_values), 2) if latency_values else None
    last_error_log = next((item for item in reversed(logs) if not item.is_success and item.error_code), None)

    success_count = sum(1 for item in logs if item.is_success)
    success_rate = round(success_count / call_count * 100, 2) if call_count else None
    token_values = [item.token_usage for item in logs if item.token_usage is not None]
    total_tokens = sum(token_values) if token_values else 0

    by_api_type_rows = session.exec(
        select(
            AITelemetry.api_type,
            func.count(AITelemetry.id).label("count"),
            func.avg(AITelemetry.latency_ms).label("avg_latency"),
            func.sum(case((AITelemetry.is_success.is_(True), 1), else_=0)).label("success_count"),
        )
        .where(
            AITelemetry.timestamp >= start_time,
            AITelemetry.timestamp <= end_time,
        )
        .group_by(AITelemetry.api_type)
    ).all()

    by_api_type = []
    for api_type, count, avg_latency, success_count in by_api_type_rows:
        success_rate_item = round(success_count / count * 100, 2) if count else None
        by_api_type.append({
            "api_type": api_type,
            "call_count": count,
            "avg_latency_ms": round(float(avg_latency), 2) if avg_latency is not None else None,
            "success_rate": success_rate_item,
        })

    error_distribution_rows = session.exec(
        select(AITelemetry.error_code, func.count(AITelemetry.id))
        .where(
            AITelemetry.timestamp >= start_time,
            AITelemetry.timestamp <= end_time,
            AITelemetry.error_code.is_not(None),
        )
        .group_by(AITelemetry.error_code)
        .order_by(desc(func.count(AITelemetry.id)))
        .limit(5)
    ).all()
    error_distribution = [
        {"error_code": error_code, "count": count}
        for error_code, count in error_distribution_rows
    ]

    return {
        "success": True,
        "ai_enabled": bool(settings.doubao_api_key),
        "message": (
            "AI 接口已启用" if settings.doubao_api_key else "未配置 AI API Key，已降级为本地规则"
        ),
        "call_stats": {
            "call_count": call_count,
            "avg_latency_ms": avg_latency,
            "last_error": last_error_log.error_code if last_error_log else None,
            "success_rate": success_rate,
            "total_tokens": total_tokens,
            "period_days": days,
        },
        "by_api_type": by_api_type,
        "top_errors": error_distribution,
    }


@router.get("/recommendation-strategy", response_model=dict)
def get_recommendation_strategy(
    session: Session = Depends(get_session),
    _admin=Depends(get_current_admin_user),
):
    """获取当前推荐策略配置。"""
    strategy = session.exec(
        select(RecommendationStrategyConfig).order_by(desc(RecommendationStrategyConfig.updated_at)).limit(1)
    ).first()

    if not strategy:
        strategy = RecommendationStrategyConfig()
        session.add(strategy)
        session.commit()
        session.refresh(strategy)

    return {
        "success": True,
        "data": {
            "id": strategy.id,
            "views_weight": strategy.views_weight,
            "ai_weight": strategy.ai_weight,
            "tmdb_weight": strategy.tmdb_weight,
            "diversity_weight": strategy.diversity_weight,
            "enabled": strategy.enabled,
            "updated_at": strategy.updated_at.isoformat(),
        },
    }


@router.put("/recommendation-strategy", response_model=dict)
def update_recommendation_strategy(
    payload: RecommendationStrategyUpdate,
    session: Session = Depends(get_session),
    _admin=Depends(get_current_admin_user),
):
    """更新推荐策略配置。"""
    total_weight = payload.views_weight + payload.ai_weight + payload.tmdb_weight + payload.diversity_weight
    if total_weight <= 0:
        raise HTTPException(status_code=400, detail="权重总和必须大于 0")

    strategy = session.exec(
        select(RecommendationStrategyConfig).order_by(desc(RecommendationStrategyConfig.updated_at)).limit(1)
    ).first()
    if not strategy:
        strategy = RecommendationStrategyConfig()
        session.add(strategy)
        session.flush()

    strategy.views_weight = payload.views_weight
    strategy.ai_weight = payload.ai_weight
    strategy.tmdb_weight = payload.tmdb_weight
    strategy.diversity_weight = payload.diversity_weight
    strategy.enabled = payload.enabled
    strategy.updated_at = datetime.now()

    session.add(strategy)
    session.commit()
    session.refresh(strategy)

    return {
        "success": True,
        "message": "推荐策略已更新",
        "data": {
            "id": strategy.id,
            "views_weight": strategy.views_weight,
            "ai_weight": strategy.ai_weight,
            "tmdb_weight": strategy.tmdb_weight,
            "diversity_weight": strategy.diversity_weight,
            "enabled": strategy.enabled,
            "updated_at": strategy.updated_at.isoformat(),
        },
    }
