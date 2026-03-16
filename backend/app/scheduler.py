# scheduler.py
"""
定时任务调度器
使用 APScheduler AsyncIOScheduler 实现：
- 任务 A：每 4 小时刷新最新 50 部番剧的剧集在线人数
- 任务 B：每月 1 日凌晨 2:00 生成月度数据快照
"""
import json
import os
import time
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlmodel import Session, select

from .database import engine
from .models import Anime, DailyStats, EpisodeStats

# 项目根目录（backend/app/ 的上上级目录）
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _task_a_update_recent_episodes():
    """
    任务 A：从数据库中查出最新的 50 部番剧的 season_id，
    调用 scraper 获取在线观看人数，更新到 EpisodeStats 表中。
    """
    from .scraper import BilibiliBangumiCrawler

    print("🔄 [任务 A] 开始刷新最新 50 部番剧的剧集在线人数...")
    with Session(engine) as session:
        # 查出最新 50 部番剧（按 updated_at 倒序）
        recent_animes = session.exec(
            select(Anime).order_by(Anime.updated_at.desc()).limit(50)
        ).all()

        if not recent_animes:
            print("  ℹ️  数据库中暂无番剧记录，跳过任务 A")
            return

        season_ids = [a.season_id for a in recent_animes]

        # 取出这些番剧对应的所有剧集记录
        episodes = session.exec(
            select(EpisodeStats).where(EpisodeStats.season_id.in_(season_ids))
        ).all()

        if not episodes:
            print("  ℹ️  未找到对应的剧集记录，跳过任务 A")
            return

        crawler = BilibiliBangumiCrawler(session)
        updated = 0
        for ep in episodes:
            online = crawler.get_online_viewers(ep.bvid, ep.cid)
            if online is not None:
                ep.online_viewers = online
                ep.updated_at = datetime.now()
                updated += 1
            time.sleep(0.2)

        session.commit()
        print(f"  ✅ 任务 A 完成：共更新 {updated}/{len(episodes)} 条剧集在线人数记录")


def _task_b_monthly_snapshot():
    """
    任务 B：月度快照聚合。
    统计全量番剧的总追番数和总播放量，生成 JSON 文件保存到 cache 目录。
    文件命名格式：rank_fetcher_{月份}th.json
    """
    print("🔄 [任务 B] 开始生成月度数据快照...")
    with Session(engine) as session:
        animes = session.exec(select(Anime)).all()

        snapshot = {}
        for anime in animes:
            latest_stats = session.exec(
                select(DailyStats)
                .where(DailyStats.season_id == anime.season_id)
                .order_by(DailyStats.date.desc())
                .limit(1)
            ).first()

            snapshot[str(anime.season_id)] = {
                "title": anime.title,
                "favorites": latest_stats.favorites if latest_stats else 0,
                "views": latest_stats.views if latest_stats else 0,
            }

    cache_dir = os.path.join(_BASE_DIR, "cache")
    os.makedirs(cache_dir, exist_ok=True)

    month = datetime.now().month
    filename = f"rank_fetcher_{month}th.json"
    filepath = os.path.join(cache_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    print(f"  ✅ 任务 B 完成：月度快照已保存到 {filepath}，共 {len(snapshot)} 条记录")


async def _task_c_tmdb_enrichment():
    """
    任务 C：TMDB 数据后台批量富集（异步）。

    查询所有尚未建立 TmdbAnimeInfo 记录的番剧，
    使用受控并发异步调用 TMDB API 进行数据富集，并写入数据库。
    若 TMDB_API_KEY 未配置则直接跳过，不产生错误。
    """
    from .tmdb_service import run_tmdb_enrichment

    print("🔄 [任务 C] 开始执行 TMDB 数据批量富集...")
    with Session(engine) as session:
        result = await run_tmdb_enrichment(session)
    print(
        f"  ✅ 任务 C 完成：{result.get('message', '')} "
        f"（成功 {result.get('success', 0)}，失败 {result.get('failed', 0)}）"
    )


def create_scheduler() -> AsyncIOScheduler:
    """
    创建并配置 AsyncIOScheduler 调度器。

    Returns:
        配置好任务的 AsyncIOScheduler 实例（尚未启动）
    """
    scheduler = AsyncIOScheduler()

    # 任务 A：每 4 小时执行一次
    scheduler.add_job(
        _task_a_update_recent_episodes,
        trigger="interval",
        hours=4,
        id="task_a_update_recent_episodes",
        replace_existing=True,
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
    )

    # 任务 C：每天凌晨 3:00 执行 TMDB 富集，自动补全未处理的番剧
    scheduler.add_job(
        _task_c_tmdb_enrichment,
        trigger="cron",
        hour=3,
        minute=0,
        id="task_c_tmdb_enrichment",
        replace_existing=True,
    )

    return scheduler
