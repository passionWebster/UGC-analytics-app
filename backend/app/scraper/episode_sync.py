"""EpisodeSyncService domain service for scraper facade."""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any

from sqlmodel import select

from ..config import settings
from ..logger import scraper_logger as logger
from ..models import EpisodeStats
from .runtime import sqlite_write_lock


class EpisodeSyncService:
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

    def fetch_and_save_episodes(self, season_id: int) -> bool:
        """
        通过 B站 API 抓取指定番剧的分集信息并存入数据库，包含完整互动统计数据

        Args:
            season_id: 番剧 season_id

        Returns:
            B站 API 成功返回分集数据则返回 True，否则返回 False
        """
        logger.info(f"🔍 正在从 B站 抓取 season_id={season_id} 的分集数据...")
        details = self.get_anime_details(season_id)
        if not details or not details.get("episodes"):
            logger.info(f"❌ 未能获取 season_id={season_id} 的分集数据")
            return False

        episodes = details["episodes"]
        logger.info(f"  -> 找到 {len(episodes)} 集，正在写入数据库...")
        saved_count = 0
        has_error = False
        for episode in episodes:
            bvid = episode.get("bvid", "")
            cid = str(episode.get("cid", ""))

            # 【防线 2】利用 API 的 badge / title 字段进行初步过滤
            if not self._is_valid_main_episode(episode):
                ep_title = episode.get("long_title") or episode.get("title")
                logger.info(f"  ⏭️ API字段过滤，跳过非正片: {ep_title}")
                continue

            if not bvid or not cid:
                continue

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
            # 查询也在锁内执行，防止并发线程在检查和插入之间写入相同的 bvid
            with sqlite_write_lock:
                try:
                    existing_ep = self.session.exec(
                        select(EpisodeStats).where(EpisodeStats.bvid == bvid)
                    ).first()

                    is_new = not existing_ep
                    if existing_ep:
                        self._apply_stat_to_episode(existing_ep, stat, ep_title)
                    else:
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
                    # commit 成功后才计入已保存数量
                    if is_new:
                        saved_count += 1
                except Exception as e:
                    self.session.rollback()
                    has_error = True
                    logger.exception(f"  ❌ 写入 {ep_title} 时发生错误: {e}")

        logger.info(f"  ✅ 已写入 {saved_count} 条分集记录 (season_id={season_id})")
        # 有任意一集写入失败时返回 False，让调用方感知并视情况重试
        return not has_error

    def record_hourly_online_viewers(self) -> None:
        """
        获取所有剧集的当前在线人数，并将结果按当前小时写入 hourly_online_history 列。
        建议由调度器每小时的第 5 分钟触发，避开整点网络拥堵。
        """
        logger.info("🔄 [定时任务] 开始记录剧集每小时在线人数...")
        episodes = self.session.exec(select(EpisodeStats)).all()
        current_hour = datetime.now().strftime("%H")
        updated = 0

        for ep in episodes:
            online_count = self.get_online_viewers(ep.bvid, ep.cid)
            if online_count is not None:
                # 解析现有历史记录（兼容 None 和空字符串）
                try:
                    history: dict[str, int] = (
                        json.loads(ep.hourly_online_history) if ep.hourly_online_history else {}
                    )
                except (json.JSONDecodeError, TypeError):
                    history = {}
                history[current_hour] = online_count
                ep.hourly_online_history = json.dumps(history, ensure_ascii=False)
                ep.updated_at = datetime.now()
                updated += 1
            self._throttle()  # 严格控制请求频率，防止触发 B站风控

        self.session.commit()
        logger.info(f"✅ 在线人数记录完成，成功更新 {updated}/{len(episodes)} 个剧集")

    def update_online_viewers_for_all_episodes(self) -> None:
        """
        遍历 EpisodeStats 表中所有记录，通过 B站 API 刷新在线观看人数
        """
        logger.info("🔄 [定时任务] 开始刷新所有剧集在线人数...")
        episodes = self.session.exec(select(EpisodeStats)).all()
        if not episodes:
            logger.info("  ℹ️  EpisodeStats 表为空，跳过更新")
            return

        updated = 0
        for ep in episodes:
            online = self.get_online_viewers(ep.bvid, ep.cid)
            if online is not None:
                ep.online_viewers = online
                ep.updated_at = datetime.now()
                updated += 1
            time.sleep(0.2)

        self.session.commit()
        logger.info(f"  ✅ 在线人数刷新完成，共更新 {updated}/{len(episodes)} 条记录")
