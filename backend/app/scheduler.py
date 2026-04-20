# scheduler.py
"""
定时任务调度器
使用 APScheduler AsyncIOScheduler 实现：
- 任务 B：每月 1 日凌晨 2:00 生成月度数据快照并存入 SQLite
- 任务 C：每天凌晨 3:00 执行 TMDB 数据批量富集
- 任务 D：每小时第 5 分钟记录剧集在线人数
"""
import asyncio
from datetime import datetime

from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger
from sqlmodel import Session, select

from .database import engine
from .models import Anime, DailyStats, MonthlySnapshot


def _task_b_monthly_snapshot():
    """
    任务 B：月度快照聚合。
    统计全量番剧的最新追番数和播放量，写入 MonthlySnapshot 表。
    同一番剧、同一月份若已存在记录则覆盖（upsert）。
    """
    logger.info("🔄 [任务 B] 开始生成月度数据快照...")
    month = datetime.now().strftime("%Y-%m")

    with Session(engine) as session:
        animes = session.exec(select(Anime)).all()

        upserted = 0
        for anime in animes:
            latest_stats = session.exec(
                select(DailyStats)
                .where(DailyStats.season_id == anime.season_id)
                .order_by(DailyStats.date.desc())
                .limit(1)
            ).first()

            favorites = latest_stats.favorites if latest_stats else 0
            views = latest_stats.views if latest_stats else 0

            # 查询是否已存在本月快照，有则更新，无则插入
            existing = session.exec(
                select(MonthlySnapshot)
                .where(
                    MonthlySnapshot.season_id == anime.season_id,
                    MonthlySnapshot.month == month,
                )
            ).first()

            if existing:
                existing.title = anime.title
                existing.favorites = favorites
                existing.views = views
                existing.updated_at = datetime.now()
                session.add(existing)
            else:
                session.add(
                    MonthlySnapshot(
                        season_id=anime.season_id,
                        month=month,
                        title=anime.title,
                        favorites=favorites,
                        views=views,
                    )
                )
            upserted += 1

        session.commit()

    logger.success(
        f"✅ 任务 B 完成：月度快照（{month}）已存入数据库，共 {upserted} 条记录"
    )


def _task_c_tmdb_enrichment():
    """
    任务 C：TMDB 数据后台批量富集。

    在 APScheduler 的线程池中运行，同步打开数据库会话，
    并通过 asyncio.run 驱动异步 TMDB 富集逻辑，避免阻塞主事件循环。
    若 TMDB_API_KEY 未配置则直接跳过，不产生错误。
    """
    from .tmdb_service import run_tmdb_enrichment

    logger.info("🔄 [任务 C] 开始执行 TMDB 数据批量富集...")
    with Session(engine) as session:
        # 在独立线程内使用 asyncio.run 执行异步 TMDB 富集任务
        result = asyncio.run(run_tmdb_enrichment(session))
    logger.success(
        f"  ✅ 任务 C 完成：{result.get('message', '')} "
        f"（成功 {result.get('success', 0)}，失败 {result.get('failed', 0)}）"
    )


def _task_d_hourly_online_viewers():
    """
    任务 D：每小时记录所有剧集的在线人数，写入 hourly_online_history 列。
    建议每小时第 5 分钟执行，避开整点网络拥堵。
    """
    from .scraper import BilibiliBangumiCrawler

    logger.info("🔄 [任务 D] 开始记录每小时在线人数...")
    with Session(engine) as session:
        crawler = BilibiliBangumiCrawler(session)
        crawler.episode_sync.record_hourly_online_viewers()
    logger.success("✅ 任务 D 完成")


def create_scheduler() -> AsyncIOScheduler:
    """
    创建并配置 AsyncIOScheduler 调度器。

    Returns:
        配置好任务的 AsyncIOScheduler 实例（尚未启动）
    """
    scheduler = AsyncIOScheduler(
        executors={
            "default": AsyncIOExecutor(),
            # 用于执行包含阻塞操作的任务（如网络请求、time.sleep 等）
            "blocking": ThreadPoolExecutor(max_workers=5),
        }
    )

    # 任务 B：每月 1 号凌晨 2:00 执行
    scheduler.add_job(
        _task_b_monthly_snapshot,
        trigger="cron",
        day=1,
        hour=2,
        minute=0,
        id="task_b_monthly_snapshot",
        replace_existing=True,
        executor="blocking",
    )

    # 任务 C：每天凌晨 3:00 执行 TMDB 富集，自动补全未处理的番剧
    scheduler.add_job(
        _task_c_tmdb_enrichment,
        trigger="cron",
        hour=3,
        minute=0,
        id="task_c_tmdb_enrichment",
        replace_existing=True,
        executor="blocking",
    )

    # 任务 D：每小时第 5 分钟记录剧集在线人数分布
    scheduler.add_job(
        _task_d_hourly_online_viewers,
        trigger="cron",
        minute=5,
        id="task_d_hourly_online_viewers",
        replace_existing=True,
        executor="blocking",
    )

    return scheduler
