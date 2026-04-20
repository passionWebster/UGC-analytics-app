"""AnimeSyncService domain service for scraper facade."""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any

from sqlmodel import select

from ..config import settings
from ..logger import scraper_logger as logger
from ..models import Anime, CrawlLog, DailyStats, EpisodeStats
from .runtime import sqlite_write_lock


class AnimeSyncService:
    """Domain service delegated by ``BilibiliBangumiCrawler`` facade."""

    def __init__(self, crawler: Any) -> None:
        self._crawler = crawler

    def __getattr__(self, name: str) -> Any:
        return getattr(self._crawler, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_crawler" or "_crawler" not in self.__dict__:
            object.__setattr__(self, name, value)
            return
        if hasattr(type(self), name):
            object.__setattr__(self, name, value)
            return
        setattr(self._crawler, name, value)

    def update_anime_database(self) -> bool:
        """
        更新番剧数据库
        从 B站 API 抓取数据并存储到数据库

        Returns:
            成功返回 True，失败返回 False
        """
        logger.info("🚀 [任务开始] 更新番剧数据库")

        # 创建爬虫日志
        start_time = datetime.now()
        crawl_log = CrawlLog(task_type="full_update", status="running", started_at=start_time)
        self.session.add(crawl_log)
        self.session.commit()

        try:
            # 1. 底库构建：获取国产番剧和常规番剧基础信息
            logger.info("📊 正在获取国产番剧数据...")
            domestic_animes = self._fetch_domestic_animes()

            logger.info("📊 正在获取常规番剧数据...")
            regular_animes = self._fetch_regular_animes()

            all_animes = {**domestic_animes, **regular_animes}
            logger.info(f"✅ 底库构建完成，共获取 {len(all_animes)} 部番剧")
            crawl_log.total_scraped = len(all_animes)

            # 2. 补充风格信息：遍历风格ID，将匹配的风格追加到底库
            logger.info("🎨 正在补充风格信息（常规番剧）...")
            all_animes = self._enrich_regular_styles(all_animes)

            logger.info("🎨 正在补充风格信息（国产番剧）...")
            all_animes = self._enrich_domestic_styles(all_animes)
            crawl_log.cleaned_filtered = len(all_animes)

            # 3. 逐部请求番剧详情 API：补充播放量/追番量/地区/完结状态/版权/互动统计等
            logger.info("🔍 正在通过详情 API 补充完整数据（每 50 部自动落库）...")
            all_animes = self._enrich_details(all_animes)
            crawl_log.final_inserted = len(all_animes)

            # 更新爬虫日志
            crawl_log.status = "success"
            crawl_log.items_count = len(all_animes)
            crawl_log.completed_at = datetime.now()
            crawl_log.duration = (crawl_log.completed_at - start_time).total_seconds()
            self.session.commit()

            logger.info(f"🎉 数据库更新成功！共保存 {len(all_animes)} 部番剧")
            return True

        except Exception as e:
            logger.exception("\n❌ 更新失败")
            crawl_log.status = "failed"
            crawl_log.error_message = str(e)
            crawl_log.failed_reason = str(e)
            crawl_log.completed_at = datetime.now()
            crawl_log.duration = (crawl_log.completed_at - start_time).total_seconds()
            self.session.commit()
            return False

    def fetch_and_save_anime_with_episodes(self, keyword: str) -> int | None:
        """
        通过关键词搜索番剧，抓取详情后将 Anime 信息和所有分集（含完整统计）写入数据库

        Args:
            keyword: 搜索关键词

        Returns:
            成功时返回 season_id，失败时返回 None
        """
        logger.info(f"🔍 正在搜索番剧: {keyword}")
        season_id = self.search_bangumi_on_bilibili(keyword)
        if not season_id:
            logger.info(f"❌ 未能通过 B站 API 找到番剧: {keyword}")
            return None

        logger.info(f"  -> 找到 season_id={season_id}，正在获取详情...")
        details = self.get_anime_details(season_id)
        if not details:
            logger.info(f"❌ 获取番剧详情失败: season_id={season_id}")
            return None

        # ==========================================
        # 1. 保存或更新 Anime 基础信息
        # ==========================================
        existing_anime = self.session.exec(
            select(Anime).where(Anime.season_id == season_id)
        ).first()

        if not existing_anime:
            # 在加锁后再次检查，避免并发线程在此期间已插入相同 season_id
            with sqlite_write_lock:
                existing_anime = self.session.exec(
                    select(Anime).where(Anime.season_id == season_id)
                ).first()
                if not existing_anime:
                    new_anime = Anime(
                        season_id=season_id,
                        title=details.get("title", keyword),
                        cover=details.get("cover"),
                        area="其他",
                        rating=None,
                        styles=json.dumps([], ensure_ascii=False),
                        release_date=None,
                    )
                    self.session.add(new_anime)
                    self.session.commit()  # 立即提交，释放写入锁

            # 添加每日统计快照（使用番剧级别的整体统计）
            anime_stat = details.get("stat", {})
            views = anime_stat.get("views", 0) or 0
            favorites = anime_stat.get("favorites", 0) or 0
            with sqlite_write_lock:
                daily_stat = DailyStats(
                    season_id=season_id,
                    date=datetime.now(),
                    views=views,
                    favorites=favorites,
                )
                self.session.add(daily_stat)
                self.session.commit()  # 立即提交，释放写入锁
            logger.info(f"  ✅ 已新增番剧: {details.get('title')} (season_id={season_id})")
        else:
            logger.info(f"  ℹ️  番剧已存在: {existing_anime.title} (season_id={season_id})")

        # ==========================================
        # 2. 【自愈校验】剧集差集比对与增量修补
        # ==========================================
        episodes = details.get("episodes", [])

        # 步骤 A：提纯 API 权威数据，过滤非正片
        api_valid_episodes = [
            ep
            for ep in episodes
            if self._is_valid_main_episode(ep) and ep.get("bvid") and ep.get("cid")
        ]

        # 步骤 B：获取本地数据库中该番剧已保存的 bvid 集合
        db_existing_bvids = set(
            self.session.exec(
                select(EpisodeStats.bvid).where(EpisodeStats.season_id == season_id)
            ).all()
        )

        # 步骤 C：计算差集，找出本地缺失的剧集
        missing_episodes = [
            ep for ep in api_valid_episodes if ep.get("bvid") not in db_existing_bvids
        ]

        # 步骤 D：无缺失则跳过，有缺失则补抓
        if not missing_episodes:
            logger.info(
                f"  ✅ 数据校验通过：本地已完整包含 {len(api_valid_episodes)} 集正片数据，无需修补。"
            )
            return season_id

        logger.info(f"  ⚠️ 触发自动修复：发现本地缺失 {len(missing_episodes)} 集，正在补充抓取...")
        saved_count = 0

        for episode in missing_episodes:
            bvid = episode.get("bvid", "")
            cid = str(episode.get("cid", ""))
            ep_title = (
                episode.get("long_title")
                or episode.get("title")
                or f"第{episode.get('index', '')}集"
            )

            # 【网络 I/O 阶段】：无锁，避免长事务持有写入锁
            full_data = self.get_episode_stat_details(bvid)
            stat = full_data.get("stat", {})
            duration = full_data.get("duration", 0)
            time.sleep(settings.bilibili_request_delay)

            # 【防线 3】时长兜底，过滤掉短于 3 分钟（180 秒）的视频
            if 0 < duration < 180:
                logger.info(f"  ⏭️ 时长兜底过滤，跳过极短视频: {ep_title} ({duration}秒)")
                continue

            # 【数据库写入阶段】：加锁，单条写入后立即提交，做到"快进快出"
            # 锁内再次查询，防止并发线程在差集计算后、本次写入前已插入相同 bvid
            with sqlite_write_lock:
                try:
                    already_exists = self.session.exec(
                        select(EpisodeStats).where(EpisodeStats.bvid == bvid)
                    ).first()
                    if already_exists:
                        # 差集计算完成后被其他线程抢先插入，跳过避免重复
                        continue
                    new_ep = EpisodeStats(
                        season_id=season_id,
                        episode_title=ep_title,
                        bvid=bvid,
                        cid=cid,
                        online_viewers=None,
                    )
                    self._apply_stat_to_episode(new_ep, stat, ep_title)
                    self.session.add(new_ep)
                    self.session.commit()
                    saved_count += 1
                except Exception as e:
                    self.session.rollback()
                    logger.exception(f"  ❌ 补充写入 {ep_title} 时发生错误: {e}")

        logger.info(f"  ✅ 修复完成：成功补充 {saved_count} 条剧集记录 (season_id={season_id})")
        return season_id

    def search_anime_by_title(self, title: str) -> int | None:
        """
        通过标题搜索番剧，返回 season_id

        Args:
            title: 番剧标题

        Returns:
            season_id 或 None
        """
        anime = self.session.exec(select(Anime).where(Anime.title == title)).first()

        return anime.season_id if anime else None
