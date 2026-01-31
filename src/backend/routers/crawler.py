# routers/crawler.py
"""
爬虫控制相关的 API 路由
"""
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlmodel import Session

from ..database import get_session
from ..services.crawler import BilibiliBangumiCrawler


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
