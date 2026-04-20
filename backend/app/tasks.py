"""NLP task orchestration: run analysis and enqueue async worker tasks."""

from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from .config import settings
from .database import engine
from .logger import app_logger as logger
from .models import DanmuRecord, EpisodeStats
from .mongodb import DanmakuMongoRepository
from .nlp_pipeline import aggregate_episode_nlp, process_text_record
from .nlp_worker_pool import enqueue_nlp_task

_mongo_repo = DanmakuMongoRepository()


def _load_episode_doc_from_mongo(cid: str | None) -> dict[str, Any] | None:
    """Load episode danmaku document from MongoDB by cid.

    参数:
        cid: Episode cid.

    返回:
        MongoDB document dict when available, otherwise None.
    """
    if not cid:
        return None
    doc = _mongo_repo.get_danmaku_by_cid(cid)
    if not doc:
        return None
    return doc if isinstance(doc, dict) else None


def run_episode_nlp_analysis(
    season_id: int,
    episode_number: int,
    cid: str | None = None,
) -> dict[str, Any]:
    """Run NLP analysis for a season episode and persist analysis outputs.

    参数:
        season_id: Target season ID.
        episode_number: 1-based episode index in the season.
        cid: Optional episode cid for direct lookup.

    返回:
        Processing summary payload including source and processed sample size.

    异常:
        Exception: Re-raises any runtime error after updating episode NLP status.
    """
    with Session(engine) as session:
        ep: EpisodeStats | None = None
        if cid:
            ep = session.exec(
                select(EpisodeStats).where(
                    EpisodeStats.season_id == season_id,
                    EpisodeStats.cid == cid,
                )
            ).first()
        if ep is None:
            episodes = session.exec(
                select(EpisodeStats)
                .where(EpisodeStats.season_id == season_id)
                .order_by(EpisodeStats.id)
            ).all()
            if 0 < episode_number <= len(episodes):
                ep = episodes[episode_number - 1]
        if ep:
            ep.nlp_status = "running"
            session.add(ep)
            session.commit()

        try:
            sqlite_records = session.exec(
                select(DanmuRecord).where(
                    DanmuRecord.season_id == season_id,
                    DanmuRecord.episode_number == episode_number,
                )
            ).all()

            cid_candidate = None
            if ep and ep.cid:
                cid_candidate = str(ep.cid)
            elif cid is not None:
                cid_candidate = str(cid)
            mongo_doc = _load_episode_doc_from_mongo(cid_candidate)
            mongo_items = mongo_doc.get("danmaku_items") if isinstance(mongo_doc, dict) else None
            if not isinstance(mongo_items, list):
                mongo_items = None
            mongo_payload_items = [item for item in (mongo_items or []) if isinstance(item, dict)]
            mongo_texts = [
                str(item.get("content", "")).strip()
                for item in mongo_payload_items
                if str(item.get("content", "")).strip()
            ]
            source = "mongodb" if mongo_texts else "sqlite"

            if source == "mongodb":
                processed = [process_text_record(text) for text in mongo_texts]
                aggregate = aggregate_episode_nlp(processed)
            elif sqlite_records:
                processed = [process_text_record(r.content) for r in sqlite_records]
                aggregate = aggregate_episode_nlp(processed)
            else:
                if ep:
                    ep.nlp_status = "success"
                    ep.nlp_sample_size = 0
                    ep.nlp_noise_ratio = 0.0
                    ep.nlp_processed_at = datetime.now()
                    session.add(ep)
                    session.commit()
                return {"season_id": season_id, "episode_number": episode_number, "processed": 0}

            if source == "sqlite":
                for rec, item in zip(sqlite_records, processed):
                    rec.cleaned_content = item.get("cleaned_text")
                    rec.emotion_label = item.get("emotion_label")
                    rec.nlp_sentiment_score = item.get("sentiment_score")
                    rec.nlp_processed = True
                    session.add(rec)
            elif source == "mongodb" and mongo_payload_items:
                processed_idx = 0
                enriched_items = []
                for raw_item in mongo_payload_items:
                    content = str(raw_item.get("content", "")).strip()
                    item = dict(raw_item)
                    if content:
                        nlp_item = {}
                        if processed_idx < len(processed):
                            nlp_item = processed[processed_idx]
                            processed_idx += 1
                        item["cleaned_content"] = nlp_item.get("cleaned_text")
                        item["emotion_label"] = nlp_item.get("emotion_label")
                        item["nlp_sentiment_score"] = nlp_item.get("sentiment_score")
                    enriched_items.append(item)
                resolved_bvid = ep.bvid if ep else None
                if not resolved_bvid and isinstance(mongo_doc, dict):
                    resolved_bvid = mongo_doc.get("bvid")
                _mongo_repo.upsert_episode_danmaku(
                    cid=str(cid_candidate or ""),
                    season_id=season_id,
                    episode_number=episode_number,
                    bvid=resolved_bvid,
                    danmaku_items=enriched_items,
                )

            if ep:
                ep.nlp_status = "success"
                ep.nlp_sample_size = aggregate.get("sample_size")
                ep.nlp_sentiment_score = aggregate.get("sentiment_score")
                ep.nlp_noise_ratio = aggregate.get("noise_ratio")
                ep.nlp_keywords = aggregate.get("keywords") or []
                ep.nlp_entities = aggregate.get("entities") or []
                ep.nlp_processed_at = datetime.now()
                session.add(ep)

            session.commit()
            logger.info(
                "✅ NLP 分析完成 season_id={} episode={} source={} sample_size={}",
                season_id,
                episode_number,
                source,
                aggregate.get("sample_size"),
            )
            return {
                "season_id": season_id,
                "episode_number": episode_number,
                "processed": aggregate.get("sample_size", 0),
                "sample_size": aggregate.get("sample_size"),
                "source": source,
            }
        except Exception:
            logger.exception("❌ NLP 分析失败 season_id={} episode={}", season_id, episode_number)
            if ep:
                session.rollback()
                ep.nlp_status = "failed"
                ep.nlp_processed_at = datetime.now()
                session.add(ep)
                session.commit()
            raise


def enqueue_episode_nlp_task(
    season_id: int,
    episode_number: int,
    cid: str | None = None,
) -> str | None:
    """Enqueue NLP task to worker pool, with optional local fallback execution.

    参数:
        season_id: Target season ID.
        episode_number: 1-based episode index in the season.
        cid: Optional episode cid.

    返回:
        Task ID when enqueue succeeds, otherwise None.
    """
    task_id = enqueue_nlp_task(season_id=season_id, episode_number=episode_number, cid=cid)
    if task_id:
        return task_id
    if settings.nlp_async_fallback_local:
        logger.warning(
            "⚠️ NLP 任务入队失败，降级本地执行 season_id={} episode={}",
            season_id,
            episode_number,
        )
        run_episode_nlp_analysis(season_id=season_id, episode_number=episode_number, cid=cid)
    return None
