# routers/crawler.py
"""
爬虫控制相关的 API 路由
"""
from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from sqlmodel import Session

from ..database import get_session
from ..scraper import BilibiliBangumiCrawler
from ..analytics import batch_score_danmaku, batch_score_comments


router = APIRouter(prefix="/api/crawler", tags=["爬虫"])


@router.post("/update", response_model=dict)
def trigger_update(
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    """
    触发数据更新
    
    Args:
        background_tasks: 后台任务
        session: 数据库会话
        
    Returns:
        触发结果
    """
    # 在后台执行爬虫任务
    crawler = BilibiliBangumiCrawler(session)
    background_tasks.add_task(crawler.update_anime_database)
    
    return {
        "success": True,
        "message": "数据更新任务已启动，请稍后查看结果"
    }


@router.get("/status", response_model=dict)
def get_crawler_status(session: Session = Depends(get_session)):
    """
    获取爬虫状态
    
    Args:
        session: 数据库会话
        
    Returns:
        爬虫状态信息
    """
    from ..models import CrawlLog
    from sqlmodel import select, desc
    
    # 获取最近的爬虫日志
    latest_log = session.exec(
        select(CrawlLog).order_by(desc(CrawlLog.started_at)).limit(1)
    ).first()
    
    if not latest_log:
        return {
            "success": True,
            "status": "never_run",
            "message": "尚未执行过爬虫任务"
        }
    
    return {
        "success": True,
        "status": latest_log.status,
        "task_type": latest_log.task_type,
        "items_count": latest_log.items_count,
        "started_at": latest_log.started_at.isoformat(),
        "completed_at": latest_log.completed_at.isoformat() if latest_log.completed_at else None,
        "error_message": latest_log.error_message
    }


@router.get("/search/{title}", response_model=dict)
def search_anime_id(title: str, session: Session = Depends(get_session)):
    """
    根据标题搜索番剧 ID
    
    Args:
        title: 番剧标题
        session: 数据库会话
        
    Returns:
        番剧 ID
    """
    crawler = BilibiliBangumiCrawler(session)
    season_id = crawler.search_anime_by_title(title)
    
    if not season_id:
        return {
            "success": False,
            "message": f"未找到标题为 '{title}' 的番剧"
        }
    
    return {
        "success": True,
        "season_id": season_id,
        "title": title
    }


class ScrapeDanmakuRequest(BaseModel):
    """弹幕/评论抓取请求模型"""
    season_id: int
    max_episodes: Optional[int] = 3      # 最多抓取前 N 集，默认 3
    comment_limit: Optional[int] = 50    # 每集最多评论条数，默认 50
    run_sentiment: Optional[bool] = True  # 是否在抓取后立即进行情感分析


def _scrape_and_score(
    season_id: int,
    max_episodes: int,
    comment_limit: int,
    run_sentiment: bool,
    session: Session,
) -> None:
    """后台任务：抓取弹幕/评论，并可选地进行情感分析打分"""
    from ..analytics import score_sentiment

    crawler = BilibiliBangumiCrawler(session)
    sentiment_fn = score_sentiment if run_sentiment else None
    crawler.scrape_danmaku_and_comments(
        season_id=season_id,
        max_episodes=max_episodes,
        comment_limit=comment_limit,
        sentiment_fn=sentiment_fn,
    )
    # 对已有但未打分的历史记录补分
    if run_sentiment:
        batch_score_danmaku(session, season_id)
        batch_score_comments(session, season_id)


@router.post("/scrape-danmaku", response_model=dict)
def trigger_danmaku_scrape(
    req: ScrapeDanmakuRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """
    触发指定番剧的弹幕与评论抓取（后台异步执行）。

    Args:
        req: 包含 season_id、max_episodes、comment_limit、run_sentiment

    Returns:
        {"success": True, "message": "..."}
    """
    background_tasks.add_task(
        _scrape_and_score,
        season_id=req.season_id,
        max_episodes=req.max_episodes,
        comment_limit=req.comment_limit,
        run_sentiment=req.run_sentiment,
        session=session,
    )
    return {
        "success": True,
        "message": (
            f"弹幕/评论抓取任务已启动 (season_id={req.season_id}, "
            f"前 {req.max_episodes} 集, 情感分析={'开启' if req.run_sentiment else '关闭'})"
        ),
    }
