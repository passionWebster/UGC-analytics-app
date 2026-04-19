# routers/crawler.py
"""
爬虫控制相关的 API 路由
"""
from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Literal
from sqlmodel import Session

from ..database import get_session, engine
from ..scraper import BilibiliBangumiCrawler


router = APIRouter(prefix="/api/crawler", tags=["爬虫"])


@router.post("/update", response_model=dict)
def trigger_update(
    background_tasks: BackgroundTasks,
):
    """
    触发数据更新
    
    Args:
        background_tasks: 后台任务
        session: 数据库会话
        
    Returns:
        触发结果
    """
    # 在后台执行爬虫任务（任务内自行创建独立 Session）
    background_tasks.add_task(_run_update_task)
    
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
    mode: Literal["incremental", "full"] = "incremental"
    max_episodes: Optional[int] = 3      # 最多抓取前 N 集，默认 3
    comment_limit: Optional[int] = 50    # 每集最多评论条数，默认 50
    include_comment_replies: Optional[bool] = True
    nested_reply_limit: Optional[int] = 20
    retry_attempts: Optional[int] = None
    run_sentiment: Optional[bool] = True  # 是否在抓取后立即进行情感分析


def _scrape_and_score(
    season_id: int,
    mode: str,
    max_episodes: int,
    comment_limit: int,
    include_comment_replies: bool,
    nested_reply_limit: int,
    retry_attempts: Optional[int],
    run_sentiment: bool,
) -> None:
    """后台任务：抓取弹幕/评论，并触发异步 NLP 处理"""

    with Session(engine) as session:
        crawler = BilibiliBangumiCrawler(session)
        crawler.scrape_danmaku_and_comments(
            season_id=season_id,
            max_episodes=max_episodes,
            comment_limit=comment_limit,
            include_comment_replies=include_comment_replies,
            nested_reply_limit=nested_reply_limit,
            mode=mode,
            retry_attempts=retry_attempts,
            sentiment_fn=None,
            run_nlp_async=run_sentiment,
        )


def _run_update_task() -> None:
    """后台任务：更新番剧基础数据（使用独立 Session）"""
    with Session(engine) as session:
        crawler = BilibiliBangumiCrawler(session)
        crawler.update_anime_database()


@router.post("/scrape-danmaku", response_model=dict)
def trigger_danmaku_scrape(
    req: ScrapeDanmakuRequest,
    background_tasks: BackgroundTasks,
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
        mode=req.mode,
        max_episodes=req.max_episodes,
        comment_limit=req.comment_limit,
        include_comment_replies=req.include_comment_replies,
        nested_reply_limit=req.nested_reply_limit,
        retry_attempts=req.retry_attempts,
        run_sentiment=req.run_sentiment,
    )
    return {
        "success": True,
        "message": (
            f"弹幕/评论抓取任务已启动 (season_id={req.season_id}, "
            f"mode={req.mode}, 前 {req.max_episodes} 集, "
            f"楼中楼={'开启' if req.include_comment_replies else '关闭'}, "
            f"情感分析={'开启' if req.run_sentiment else '关闭'})"
        ),
    }
