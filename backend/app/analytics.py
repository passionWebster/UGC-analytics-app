"""Analytics and NLP aggregation helpers for danmaku/comment insights."""
import json
import re
from collections import Counter, defaultdict
from typing import Any
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


def score_sentiment(text: str) -> float | None:
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


def get_sentiment_timeline(session: Session, season_id: int) -> list[dict[str, Any]]:
    """
    按集数聚合弹幕情感均分，用于前端折线图（情感时间线）。

    Args:
        session:   SQLModel 数据库会话
        season_id: 目标番剧 season_id

    Returns:
        列表，每项为 {"episode_number": int, "avg_sentiment": float, "danmu_count": int}
    """
    episodes = sorted(
        session.exec(select(EpisodeStats).where(EpisodeStats.season_id == season_id)).all(),
        key=_episode_sort_key,
    )
    if not episodes:
        return []

    sentiment_expr = sa_func.coalesce(DanmuRecord.nlp_sentiment_score, DanmuRecord.sentiment_score)
    sqlite_rows = session.exec(
        select(
            DanmuRecord.cid,
            sa_func.avg(sentiment_expr).label("avg_sentiment"),
            sa_func.count(DanmuRecord.id).label("danmu_count"),
        )
        .where(DanmuRecord.season_id == season_id)
        .where(  # noqa: E711
            (DanmuRecord.nlp_sentiment_score != None) | (DanmuRecord.sentiment_score != None)
        )
        .group_by(DanmuRecord.cid)
        .order_by(DanmuRecord.cid)
    ).all()
    sqlite_map_by_cid = {
        str(row[0]): {
            "avg_sentiment": round(float(row[1]), 4) if row[1] is not None else None,
            "danmu_count": int(row[2] or 0),
        }
        for row in sqlite_rows
        if row[0]
    }

    timeline: list[dict[str, Any]] = []
    for idx, episode in enumerate(episodes, start=1):
        fallback = sqlite_map_by_cid.get(str(episode.cid))
        if fallback:
            timeline.append(
                {
                    "episode_number": idx,
                    "avg_sentiment": fallback["avg_sentiment"],
                    "danmu_count": fallback["danmu_count"],
                }
            )

    return timeline


def get_top_comments(session: Session, season_id: int, limit: int = 50) -> list[dict[str, Any]]:
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


def get_comment_insight_cards(
    session: Session,
    season_id: int,
    limit: int = 300,
    top_n: int = 6,
) -> list[dict[str, Any]]:
    """
    基于高赞评论提炼观点卡片（轻量聚类）。
    """
    records = session.exec(
        select(CommentRecord)
        .where(CommentRecord.season_id == season_id)
        .order_by(CommentRecord.likes.desc(), CommentRecord.id.desc())
        .limit(limit)
    ).all()
    if not records:
        return []

    clusters: dict[str, dict[str, Any]] = {}
    total_likes = 0

    for record in records:
        likes = int(record.likes or 0)
        total_likes += likes
        content = (record.content or "").strip()
        content_lower = content.lower()

        matched_topic = None
        max_hits = 0
        for topic, keywords in _COMMENT_TOPIC_KEYWORDS.items():
            hits = sum(1 for kw in keywords if kw and kw in content_lower)
            if hits > max_hits:
                max_hits = hits
                matched_topic = topic
        if not matched_topic:
            matched_topic = "综合观感"

        bucket = clusters.setdefault(
            matched_topic,
            {"topic": matched_topic, "likes": 0, "count": 0, "samples": [], "top_likes": 0},
        )
        bucket["likes"] += likes
        bucket["count"] += 1
        bucket["top_likes"] = max(bucket["top_likes"], likes)
        if content and len(bucket["samples"]) < 3:
            bucket["samples"].append(content[:_INSIGHT_SAMPLE_MAX_LEN])

    ranked = sorted(
        clusters.values(),
        key=lambda item: (item["likes"], item["count"], item["top_likes"]),
        reverse=True,
    )[:max(1, top_n)]

    denominator = max(total_likes, 1)
    return [
        {
            "topic": item["topic"],
            "support_rate": round(item["likes"] / denominator, 4),
            "total_likes": item["likes"],
            "comment_count": item["count"],
            "samples": item["samples"],
        }
        for item in ranked
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
    grouped: dict[int, list[DanmuRecord]] = {}
    for rec in danmu_records:
        grouped.setdefault(rec.episode_number, []).append(rec)

    updated = 0
    for ep_number, records in grouped.items():
        target = ep_by_number.get(ep_number)
        if not target:
            continue

        sentiment_values = [
            r.nlp_sentiment_score if r.nlp_sentiment_score is not None else r.sentiment_score
            for r in records
            if (r.nlp_sentiment_score is not None or r.sentiment_score is not None)
        ]
        target.avg_sentiment_score = (
            round(sum(sentiment_values) / len(sentiment_values), 4) if sentiment_values else None
        )

        bins: dict[int, int] = {}
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
_INSIGHT_SAMPLE_MAX_LEN = 180
_COMMENT_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "改编与原作": ["原作", "改编", "漫画", "小说", "还原", "删减", "魔改"],
    "剧情讨论": ["剧情", "节奏", "反转", "伏笔", "结局", "发展", "设定"],
    "角色塑造": ["角色", "人物", "主角", "配角", "人设", "成长", "演技"],
    "作画与制作": ["作画", "画面", "镜头", "特效", "制作", "分镜", "经费"],
    "音乐与配音": ["配乐", "音乐", "op", "ed", "配音", "声优", "音效"],
    "情绪共鸣": ["感动", "泪目", "刀", "治愈", "燃", "催泪", "共鸣"],
}


def _safe_json_load(value: Any, default: Any) -> Any:
    """Safely parse JSON-compatible value, returning default on failure."""
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


def _extract_tokens(text: str) -> list[str]:
    """Extract normalized tokens for timeline/wordcloud aggregation."""
    if not text:
        return []
    tokens = [token.lower() for token in _TOKEN_RE.findall(text)]
    return [token for token in tokens if token not in _TIMELINE_STOPWORDS]


def _normalize_term(text: str) -> str:
    """Normalize lexical term for aggregate counting."""
    return (text or "").strip().lower()


def _episode_sort_key(ep: EpisodeStats) -> tuple:
    """Build sortable key from episode title number, fallback to record id."""
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
) -> dict[str, Any]:
    """Aggregate one episode timeline bins with sentiment and top keywords."""
    target_ep = session.exec(select(EpisodeStats).where(EpisodeStats.cid == cid)).first()
    if not target_ep:
        raise ValueError("episode_not_found")

    episodes = sorted(
        session.exec(select(EpisodeStats).where(EpisodeStats.season_id == target_ep.season_id)).all(),
        key=_episode_sort_key,
    )
    episode_index_map = {ep.id: idx + 1 for idx, ep in enumerate(episodes)}
    episode_number = episode_index_map.get(target_ep.id, 1)

    bins: dict[int, dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "sent_sum": 0.0, "sent_count": 0, "token_counter": Counter()}
    )
    total_danmaku = 0

    records = session.exec(
        select(DanmuRecord)
        .where(
            DanmuRecord.season_id == target_ep.season_id,
            DanmuRecord.cid == cid,
            DanmuRecord.video_time.is_not(None),
        )
        .order_by(DanmuRecord.video_time)
    ).all()
    total_danmaku = len(records)
    for record in records:
        if record.video_time is None:
            continue
        bin_start = int(record.video_time // bin_size) * bin_size
        bucket = bins[bin_start]
        bucket["count"] += 1
        score = (
            record.nlp_sentiment_score
            if record.nlp_sentiment_score is not None
            else record.sentiment_score
        )
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

    payload = {
        "season_id": target_ep.season_id,
        "cid": cid,
        "episode_number": episode_number,
        "bin_size": bin_size,
        "total_danmaku": total_danmaku,
        "timeline": timeline,
    }
    logger.info("📊 单集时间线聚合完成 cid={} source=sqlite bins={}", cid, len(timeline))
    return payload


def get_season_wordcloud(
    session: Session,
    season_id: int,
    cid: str | None = None,
    top_n: int = 120,
) -> dict[str, Any]:
    """Build season/episode wordcloud items from NLP fields with DB fallback."""
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
) -> dict[str, Any]:
    """Build per-episode character/entity trend series for one season."""
    episodes = sorted(
        session.exec(select(EpisodeStats).where(EpisodeStats.season_id == season_id)).all(),
        key=_episode_sort_key,
    )
    if not episodes:
        raise ValueError("season_not_found")

    per_episode_entity_counter: dict[int, Counter] = {}
    global_counter: Counter = Counter()
    episode_labels: list[str] = []

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
