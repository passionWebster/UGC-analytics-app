# analytics.py
"""
NLP 情感分析模块
使用 SnowNLP 对弹幕/评论文本进行中文情感打分，
并提供按番剧聚合情感数据的辅助函数。
"""
import json
import re
from collections import Counter, defaultdict
from typing import Optional, List, Dict, Any
from sqlmodel import Session, select
from sqlalchemy import func as sa_func

from .models import DanmuRecord, CommentRecord, EpisodeStats
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


def update_episode_sentiment_aggregates(session: Session, season_id: int) -> int:
    """
    回填 EpisodeStats 聚合字段：
    - avg_sentiment_score
    - peak_danmaku_time
    """
    episodes = session.exec(
        select(EpisodeStats)
        .where(EpisodeStats.season_id == season_id)
        .order_by(EpisodeStats.id)
    ).all()
    if not episodes:
        return 0

    danmu_records = session.exec(
        select(DanmuRecord)
        .where(DanmuRecord.season_id == season_id)
        .order_by(DanmuRecord.episode_number)
    ).all()
    if not danmu_records:
        return 0

    ep_by_number = {idx + 1: ep for idx, ep in enumerate(episodes)}
    grouped: Dict[int, List[DanmuRecord]] = {}
    for rec in danmu_records:
        grouped.setdefault(rec.episode_number, []).append(rec)

    updated = 0
    for ep_number, records in grouped.items():
        target = ep_by_number.get(ep_number)
        if not target:
            continue

        sentiment_values = [r.sentiment_score for r in records if r.sentiment_score is not None]
        target.avg_sentiment_score = (
            round(sum(sentiment_values) / len(sentiment_values), 4) if sentiment_values else None
        )

        bins: Dict[int, int] = {}
        for r in records:
            if r.video_time is None:
                continue
            second = int(round(r.video_time))
            bins[second] = bins.get(second, 0) + 1
        if bins:
            max_count = max(bins.values())
            # 并列峰值时取最早时间点，便于时间轴可视化对齐
            peak_second = min(sec for sec, count in bins.items() if count == max_count)
            target.peak_danmaku_time = float(peak_second)
        else:
            target.peak_danmaku_time = None
        updated += 1

    if updated:
        session.commit()
    logger.info("✅ 单集聚合指标回填完成：season_id={} updated={}", season_id, updated)
    return updated


_CJK_UNIFIED_IDEOGRAPHS_RANGE = r"\u4e00-\u9fff"
_TOKEN_RE = re.compile(rf"[{_CJK_UNIFIED_IDEOGRAPHS_RANGE}]{{2,}}|[A-Za-z0-9]{{3,}}")
_TIMELINE_STOPWORDS = {"这个", "那个", "真的", "感觉", "就是", "你们", "我们", "他们", "一个", "不是", "没有"}
_EPISODE_NUM_RE = re.compile(r"\d+")
_MAX_EPISODE_SORT_KEY = 10**9
_WORDCLOUD_FALLBACK_BATCH_SIZE = 2000


def _safe_json_load(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return default
        return parsed
    return default


def _extract_tokens(text: str) -> List[str]:
    if not text:
        return []
    tokens = [token.lower() for token in _TOKEN_RE.findall(text)]
    return [token for token in tokens if token not in _TIMELINE_STOPWORDS]


def _normalize_term(text: str) -> str:
    return (text or "").strip().lower()


def _episode_sort_key(ep: EpisodeStats) -> tuple:
    title = ep.episode_title or ""
    match = _EPISODE_NUM_RE.search(title)
    if match:
        return int(match.group()), ep.id or 0
    return _MAX_EPISODE_SORT_KEY, ep.id or 0


def get_episode_timeline_bins(
    session: Session,
    cid: str,
    bin_size: int = 10,
    keyword_topk: int = 5,
) -> Dict[str, Any]:
    target_ep = session.exec(select(EpisodeStats).where(EpisodeStats.cid == cid)).first()
    if not target_ep:
        raise ValueError("episode_not_found")

    episodes = sorted(
        session.exec(select(EpisodeStats).where(EpisodeStats.season_id == target_ep.season_id)).all(),
        key=_episode_sort_key,
    )
    episode_index_map = {ep.id: idx + 1 for idx, ep in enumerate(episodes)}
    episode_number = episode_index_map.get(target_ep.id, 1)

    records = session.exec(
        select(DanmuRecord)
        .where(
            DanmuRecord.season_id == target_ep.season_id,
            DanmuRecord.cid == cid,
            DanmuRecord.video_time.is_not(None),
        )
        .order_by(DanmuRecord.video_time)
    ).all()

    bins: Dict[int, Dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "sent_sum": 0.0, "sent_count": 0, "token_counter": Counter()}
    )

    for record in records:
        if record.video_time is None:
            continue
        bin_start = int(record.video_time // bin_size) * bin_size
        bucket = bins[bin_start]
        bucket["count"] += 1
        score = record.nlp_sentiment_score
        if score is None:
            score = record.sentiment_score
        if score is not None:
            bucket["sent_sum"] += float(score)
            bucket["sent_count"] += 1
        text = record.cleaned_content or record.content
        for token in _extract_tokens(text):
            bucket["token_counter"][token] += 1

    timeline = []
    for time_start in sorted(bins.keys()):
        bucket = bins[time_start]
        avg_sentiment = (
            round(bucket["sent_sum"] / bucket["sent_count"], 4)
            if bucket["sent_count"] > 0
            else 0.0
        )
        top_keywords = [token for token, _ in bucket["token_counter"].most_common(keyword_topk)]
        timeline.append(
            {
                "time_start": time_start,
                "danmaku_count": bucket["count"],
                "avg_sentiment": avg_sentiment,
                "top_keywords": top_keywords,
            }
        )

    return {
        "season_id": target_ep.season_id,
        "cid": cid,
        "episode_number": episode_number,
        "bin_size": bin_size,
        "total_danmaku": len(records),
        "timeline": timeline,
    }


def get_season_wordcloud(
    session: Session,
    season_id: int,
    cid: Optional[str] = None,
    top_n: int = 120,
) -> Dict[str, Any]:
    query = select(EpisodeStats).where(EpisodeStats.season_id == season_id)
    if cid:
        query = query.where(EpisodeStats.cid == cid)
    episodes = sorted(session.exec(query).all(), key=_episode_sort_key)
    if not episodes:
        raise ValueError("episode_not_found")

    counter: Counter = Counter()

    for ep in episodes:
        entities = _safe_json_load(ep.nlp_entities, [])
        for item in entities:
            text = _normalize_term(str(item.get("text", "")))
            count = int(item.get("count", 0) or 0)
            if text and count > 0:
                counter[text] += count

        keywords = _safe_json_load(ep.nlp_keywords, [])
        for kw in keywords:
            text = _normalize_term(str(kw))
            if text:
                counter[text] += 1

    if not counter:
        record_query = select(DanmuRecord).where(DanmuRecord.season_id == season_id)
        if cid:
            record_query = record_query.where(DanmuRecord.cid == cid)
        offset = 0
        while True:
            batch = session.exec(
                record_query.order_by(DanmuRecord.id).offset(offset).limit(_WORDCLOUD_FALLBACK_BATCH_SIZE)
            ).all()
            if not batch:
                break
            for rec in batch:
                for token in _extract_tokens(rec.cleaned_content or rec.content):
                    counter[token] += 1
            offset += _WORDCLOUD_FALLBACK_BATCH_SIZE

    items = [{"text": text, "weight": weight} for text, weight in counter.most_common(top_n)]
    return {
        "season_id": season_id,
        "cid": cid,
        "total_terms": len(items),
        "items": items,
    }


def get_season_character_trends(
    session: Session,
    season_id: int,
    top_n: int = 8,
) -> Dict[str, Any]:
    episodes = sorted(
        session.exec(select(EpisodeStats).where(EpisodeStats.season_id == season_id)).all(),
        key=_episode_sort_key,
    )
    if not episodes:
        raise ValueError("season_not_found")

    per_episode_entity_counter: Dict[int, Counter] = {}
    global_counter: Counter = Counter()
    episode_labels: List[str] = []

    for idx, ep in enumerate(episodes, start=1):
        episode_labels.append(ep.episode_title or f"第{idx}集")
        counter = Counter()
        entities = _safe_json_load(ep.nlp_entities, [])
        for item in entities:
            text = _normalize_term(str(item.get("text", "")))
            count = int(item.get("count", 0) or 0)
            if text and count > 0:
                counter[text] += count
                global_counter[text] += count
        per_episode_entity_counter[idx] = counter

    top_characters = [name for name, _ in global_counter.most_common(top_n)]
    character_items = []
    for name in top_characters:
        trend = []
        total_count = 0
        for idx in range(1, len(episodes) + 1):
            count = int(per_episode_entity_counter.get(idx, Counter()).get(name, 0))
            total_count += count
            trend.append(
                {
                    "episode_number": idx,
                    "episode_title": episode_labels[idx - 1],
                    "count": count,
                }
            )
        character_items.append(
            {
                "character": name,
                "total_count": total_count,
                "trend": trend,
            }
        )

    return {
        "season_id": season_id,
        "total_episodes": len(episodes),
        "items": character_items,
    }
