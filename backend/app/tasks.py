from datetime import datetime
from typing import Any, Dict, Optional

from sqlmodel import Session, select

from .config import settings
from .database import engine
from .logger import app_logger as logger
from .models import DanmuRecord, EpisodeStats
from .mongodb import DanmakuMongoRepository
from .nlp_pipeline import aggregate_episode_nlp, process_text_record
from .nlp_worker_pool import enqueue_nlp_task

_mongo_repo = DanmakuMongoRepository()


def _load_episode_doc_from_mongo(cid: Optional[str]) -> Optional[Dict[str, Any]]:
    if not cid:
        return None
    doc = _mongo_repo.get_danmaku_by_cid(cid)
    if not doc:
        return None
    return doc if isinstance(doc, dict) else None


def run_episode_nlp_analysis(season_id: int, episode_number: int, cid: Optional[str] = None) -> Dict[str, Any]:
    with Session(engine) as session:
        ep: Optional[EpisodeStats] = None
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
                        nlp_item = processed[processed_idx] if processed_idx < len(processed) else {}
                        processed_idx += 1
                        item["cleaned_content"] = nlp_item.get("cleaned_text")
                        item["emotion_label"] = nlp_item.get("emotion_label")
                        item["nlp_sentiment_score"] = nlp_item.get("sentiment_score")
                    enriched_items.append(item)
                _mongo_repo.upsert_episode_danmaku(
                    cid=str(cid_candidate or ""),
                    season_id=season_id,
                    episode_number=episode_number,
                    bvid=(ep.bvid if ep else None) or (mongo_doc.get("bvid") if isinstance(mongo_doc, dict) else None),
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


def enqueue_episode_nlp_task(season_id: int, episode_number: int, cid: Optional[str] = None) -> Optional[str]:
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
