# analytics.py
"""
NLP 情感分析模块
使用 SnowNLP 对弹幕/评论文本进行中文情感打分，
并提供按番剧聚合情感数据的辅助函数。
"""
from typing import Optional, List, Dict, Any
from sqlmodel import Session, select
from sqlalchemy import func as sa_func

from .models import DanmuRecord, CommentRecord
from .logger import app_logger as logger

# ── SnowNLP 懒加载，避免在 import 阶段引发异常 ──────────────────────────────
try:
    from snownlp import SnowNLP
    _SNOWNLP_AVAILABLE = True
except ImportError:
    _SNOWNLP_AVAILABLE = False
    logger.warning("⚠️ snownlp 未安装，情感分析功能将不可用。请执行 pip install snownlp")


def score_sentiment(text: str) -> Optional[float]:
    """
    对单条中文文本打情感分（SnowNLP）。

    返回值范围 [0, 1]，越接近 1 表示越积极。
    若 SnowNLP 未安装，返回 None。

    Args:
        text: 待分析的中文文本

    Returns:
        情感得分（0~1），失败时返回 None
    """
    if not _SNOWNLP_AVAILABLE:
        return None
    try:
        return float(SnowNLP(text).sentiments)
    except Exception as exc:
        logger.debug("SnowNLP 打分失败: {}", exc)
        return None


def batch_score_danmaku(session: Session, season_id: int) -> int:
    """
    对指定番剧中所有尚未打分的弹幕记录进行情感分析，并将结果写入数据库。

    Args:
        session:   SQLModel 数据库会话
        season_id: 目标番剧 season_id

    Returns:
        成功打分的记录数
    """
    if not _SNOWNLP_AVAILABLE:
        logger.warning("⚠️ snownlp 未安装，跳过弹幕情感分析")
        return 0

    records = session.exec(
        select(DanmuRecord)
        .where(DanmuRecord.season_id == season_id)
        .where(DanmuRecord.sentiment_score == None)  # noqa: E711
    ).all()

    updated = 0
    for rec in records:
        score = score_sentiment(rec.content)
        if score is not None:
            rec.sentiment_score = score
            updated += 1

    if updated:
        session.commit()
    logger.info(f"✅ 弹幕情感分析完成：season_id={season_id} 共打分 {updated} 条")
    return updated


def batch_score_comments(session: Session, season_id: int) -> int:
    """
    对指定番剧中所有尚未打分的评论记录进行情感分析，并将结果写入数据库。

    Args:
        session:   SQLModel 数据库会话
        season_id: 目标番剧 season_id

    Returns:
        成功打分的记录数
    """
    if not _SNOWNLP_AVAILABLE:
        logger.warning("⚠️ snownlp 未安装，跳过评论情感分析")
        return 0

    records = session.exec(
        select(CommentRecord)
        .where(CommentRecord.season_id == season_id)
        .where(CommentRecord.sentiment_score == None)  # noqa: E711
    ).all()

    updated = 0
    for rec in records:
        score = score_sentiment(rec.content)
        if score is not None:
            rec.sentiment_score = score
            updated += 1

    if updated:
        session.commit()
    logger.info(f"✅ 评论情感分析完成：season_id={season_id} 共打分 {updated} 条")
    return updated


def get_sentiment_timeline(session: Session, season_id: int) -> List[Dict[str, Any]]:
    """
    按集数聚合弹幕情感均分，用于前端折线图（情感时间线）。

    Args:
        session:   SQLModel 数据库会话
        season_id: 目标番剧 season_id

    Returns:
        列表，每项为 {"episode_number": int, "avg_sentiment": float, "danmu_count": int}
    """
    rows = session.exec(
        select(
            DanmuRecord.episode_number,
            sa_func.avg(DanmuRecord.sentiment_score).label("avg_sentiment"),
            sa_func.count(DanmuRecord.id).label("danmu_count"),
        )
        .where(DanmuRecord.season_id == season_id)
        .where(DanmuRecord.sentiment_score != None)  # noqa: E711
        .group_by(DanmuRecord.episode_number)
        .order_by(DanmuRecord.episode_number)
    ).all()

    return [
        {
            "episode_number": row[0],
            "avg_sentiment": round(float(row[1]), 4) if row[1] is not None else None,
            "danmu_count": row[2],
        }
        for row in rows
    ]


def get_top_comments(session: Session, season_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """
    返回指定番剧点赞数最高的前 limit 条评论（含情感得分）。

    Args:
        session:   SQLModel 数据库会话
        season_id: 目标番剧 season_id
        limit:     最多返回条数

    Returns:
        评论列表，按 likes 降序排列
    """
    records = session.exec(
        select(CommentRecord)
        .where(CommentRecord.season_id == season_id)
        .order_by(CommentRecord.likes.desc())
        .limit(limit)
    ).all()

    return [
        {
            "id": r.id,
            "content": r.content,
            "likes": r.likes,
            "replies": r.replies,
            "sentiment_score": r.sentiment_score,
        }
        for r in records
    ]
