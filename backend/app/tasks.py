"""NLP task orchestration: run analysis and enqueue async worker tasks."""

from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from .config import settings
from .database import engine
from .logger import app_logger as logger
from .models import DanmuRecord, EpisodeStats
from .nlp_pipeline import aggregate_episode_nlp, process_text_record
from .nlp_worker_pool import enqueue_nlp_task

def run_episode_nlp_analysis(
    season_id: int,
    episode_number: int,
    cid: str | None = None,
) -> dict[str, Any]:
    """Run NLP analysis for a season episode and persist analysis outputs.

    Args:
        season_id: Target season ID.
        episode_number: 1-based episode index in the season.
        cid: Optional episode cid for direct lookup.

    Returns:
        Processing summary payload including source and processed sample size.

    Raises:
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
            source = "sqlite"

            if sqlite_records:
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

            for rec, item in zip(sqlite_records, processed):
                rec.cleaned_content = item.get("cleaned_text")
                rec.emotion_label = item.get("emotion_label")
                rec.nlp_sentiment_score = item.get("sentiment_score")
                rec.nlp_processed = True
                session.add(rec)

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

    Args:
        season_id: Target season ID.
        episode_number: 1-based episode index in the season.
        cid: Optional episode cid.

    Returns:
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
