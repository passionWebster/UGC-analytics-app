"""Comment crawl and persistence service."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlmodel import select

from ..config import settings
from ..logger import scraper_logger as logger
from ..models import CommentRecord, CrawlLog, DanmuRecord, EpisodeStats
from .runtime import sqlite_write_lock

if TYPE_CHECKING:
    from .crawler import BilibiliBangumiCrawler


class CommentsService:
    """Handle comment crawling, danmaku/comment persistence and task orchestration."""

    def __init__(self, crawler: BilibiliBangumiCrawler) -> None:
        """Bind the service to the shared crawler runtime context.

        Args:
            crawler: Shared scraper facade providing session, request helpers and config.
        """
        self._crawler = crawler

    def __getattr__(self, name: str) -> Any:
        """Fallback unknown attributes to the shared crawler facade."""
        return getattr(self._crawler, name)

    def __setattr__(self, name: str, value: Any) -> None:
        """Route unknown attribute writes to the shared crawler facade."""
        if name == "_crawler" or "_crawler" not in self.__dict__:
            object.__setattr__(self, name, value)
            return
        if hasattr(type(self), name):
            object.__setattr__(self, name, value)
            return
        setattr(self._crawler, name, value)

    def fetch_comment_replies(
        self,
        avid: int,
        root_rpid: str,
        *,
        limit: int,
        page_size: int,
    ) -> list[dict[str, Any]]:
        """
        抓取指定主楼下的楼中楼评论。

        Args:
            avid: 视频 avid（oid）
            root_rpid: 主楼评论 ID
            limit: 楼中楼最多抓取条数
            page_size: 每页抓取条数

        Returns:
            楼中楼评论列表（含层级和父子关系字段）
        """
        url = "https://api.bilibili.com/x/v2/reply/reply"
        nested: list[dict[str, Any]] = []
        max_pages = max(1, settings.crawler_nested_reply_pages)
        root_rpid_str = str(root_rpid)
        for page in range(1, max_pages + 1):
            if len(nested) >= limit:
                break
            params = self._crawler.danmaku._sign_wbi_params(
                {
                    "type": 1,
                    "oid": avid,
                    "root": root_rpid_str,
                    "ps": page_size,
                    "pn": page,
                }
            )
            resp = self._request_get(url, params=params, timeout=settings.bilibili_request_timeout)
            if resp is None:
                break
            data = resp.json()
            if data.get("code") != 0:
                break
            replies = (data.get("data") or {}).get("replies") or []
            if not replies:
                break
            for r in replies:
                content = (r.get("content") or {}).get("message", "").strip()
                if not content:
                    continue
                current_rpid = str(r.get("rpid") or "")
                parent_info = r.get("parent_info") or {}
                parent_rpid = str(parent_info.get("rpid") or "")
                nested.append(
                    {
                        "content": content,
                        "likes": r.get("like", 0),
                        "replies": r.get("rcount", 0),
                        "root_rpid": root_rpid_str,
                        "parent_rpid": parent_rpid or root_rpid_str,
                        "level": 1,
                        "is_top_level": False,
                        "rpid": current_rpid,
                    }
                )
                if len(nested) >= limit:
                    break
        return nested

    def fetch_comments(
        self,
        avid: int,
        *,
        limit: int = 50,
        include_replies: bool = True,
        nested_reply_limit: int = 20,
        bvid: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        通过 B站评论接口抓取主楼评论，并可选抓取楼中楼回复。

        Args:
            avid:  视频 avid（即 oid）
            limit: 最多返回评论条数（按热门排序）

        Returns:
            评论列表，包含层级和父子关系字段
        """
        url = "https://api.bilibili.com/x/v2/reply/main"
        page_size = min(max(1, settings.crawler_comment_page_size), 20)
        comment_list: list[dict[str, Any]] = []
        page = 1
        while len(comment_list) < limit:
            params = self._crawler.danmaku._sign_wbi_params(
                {
                    "type": 1,
                    "oid": avid,
                    "mode": 3,  # 3 = 热门模式（按点赞数排序）
                    "ps": page_size,
                    "pn": page,
                }
            )
            resp = self._request_get(url, params=params, timeout=settings.bilibili_request_timeout)
            if resp is None:
                logger.warning("⚠️ 评论接口请求失败 bvid={} avid={} page={}", bvid, avid, page)
                break
            data = resp.json()
            if data.get("code") == 0:
                replies = (data.get("data") or {}).get("replies") or []
                if not replies:
                    break
                for r in replies:
                    content = r.get("content", {}).get("message", "").strip()
                    if not content:
                        continue
                    root_rpid = str(r.get("rpid") or "")
                    comment_list.append(
                        {
                            "content": content,
                            "likes": r.get("like", 0),
                            "replies": r.get("rcount", 0),
                            "root_rpid": root_rpid,
                            "parent_rpid": None,
                            "level": 0,
                            "is_top_level": True,
                        }
                    )
                    if include_replies and root_rpid and nested_reply_limit > 0:
                        comment_list.extend(
                            self.fetch_comment_replies(
                                avid,
                                root_rpid,
                                limit=nested_reply_limit,
                                page_size=page_size,
                            )
                        )
                    if len(comment_list) >= limit:
                        break
                page += 1
                if len(replies) < page_size:
                    break
            else:
                logger.warning(
                    "⚠️ 评论 API 返回错误 bvid={} avid={} code={} message={}",
                    bvid,
                    avid,
                    data.get("code"),
                    data.get("message"),
                )
                break
        return comment_list[:limit]

    def scrape_danmaku_and_comments(
        self,
        season_id: int,
        max_episodes: int = 3,
        comment_limit: int = 50,
        include_comment_replies: bool = True,
        nested_reply_limit: int = 20,
        mode: str = "incremental",
        retry_attempts: int | None = None,
        sentiment_fn: Any | None = None,
        run_nlp_async: bool = True,
    ) -> dict[str, Any]:
        """
        对指定番剧抓取弹幕和评论，进行初步清洗后写入数据库。

        流程：
          1. 从 EpisodeStats 表查出该番剧前 max_episodes 集的 cid / bvid
          2. 使用 fetch_danmaku_xml 获取弹幕，去除重复刷屏内容
          3. 使用 fetch_comments 获取高赞评论
          4. 若提供 sentiment_fn，对每条文本打分后写入 sentiment_score
          5. 批量写入 DanmuRecord / CommentRecord

        Args:
            season_id:     目标番剧 season_id
            max_episodes:  最多抓取前 N 集弹幕，默认 3
            comment_limit: 每集最多抓取评论数，默认 50
            sentiment_fn:  可选的情感打分函数，签名为 (text: str) -> float

        Returns:
            统计字典，包含写入数量与请求重试指标
        """
        self.override_retry_attempts = max(1, retry_attempts) if retry_attempts else None
        logger.info(f"🎯 开始抓取弹幕/评论 season_id={season_id}（最多 {max_episodes} 集）")
        self.request_counters = {"requests": 0, "retries": 0, "failed": 0}

        crawl_log = CrawlLog(
            task_type=f"scrape_danmaku_comments:{mode}",
            status="running",
            started_at=datetime.now(),
        )
        self.session.add(crawl_log)
        self.session.commit()

        episodes = self.session.exec(
            select(EpisodeStats)
            .where(EpisodeStats.season_id == season_id)
            .order_by(EpisodeStats.id)
        ).all()
        if max_episodes:
            episodes = episodes[:max_episodes]

        if not episodes:
            logger.warning(
                f"  ⚠️ season_id={season_id} 尚无剧集数据，请先执行 fetch_and_save_episodes"
            )
            crawl_log.status = "failed"
            crawl_log.failed_reason = "EpisodeStats records not found"
            crawl_log.completed_at = datetime.now()
            self.session.commit()
            self.override_retry_attempts = None
            return {"danmu_saved": 0, "comment_saved": 0}

        if mode == "full":
            old_danmu = self.session.exec(
                select(DanmuRecord).where(DanmuRecord.season_id == season_id)
            ).all()
            old_comments = self.session.exec(
                select(CommentRecord).where(CommentRecord.season_id == season_id)
            ).all()
            with sqlite_write_lock:
                for record in old_danmu:
                    self.session.delete(record)
                for record in old_comments:
                    self.session.delete(record)
                self.session.commit()

        danmu_saved = 0
        comment_saved = 0
        mongo_saved = 0

        for ep_index, ep in enumerate(episodes, start=1):
            logger.info("▶️ 开始处理剧集 episode={} bvid={} cid={}", ep_index, ep.bvid, ep.cid)
            try:
                view_data: dict[str, Any] = {}
                avid: int | None = None
                pubdate_ts: int | None = None
                if ep.bvid:
                    view_data = self._crawler.episode_sync.get_episode_stat_details(ep.bvid) or {}
                    avid = view_data.get("aid")
                    pubdate_ts = view_data.get("pubdate")

                # ── 弹幕 ───────────────────────────────────────────────────
                if ep.cid:
                    current_danmaku = self._crawler.danmaku.fetch_danmaku_xml(ep.cid)
                    history_danmaku = self._crawler.danmaku.fetch_danmaku_history(
                        ep.cid, publish_ts=pubdate_ts
                    )

                    # 去重：同一集中仅移除完全重复的弹幕（文本+时间+发送者）
                    seen_keys: set[tuple[str, Any, Any, str]] = set()
                    dedup: list[dict] = []
                    for d in current_danmaku:
                        # video_time 表示视频内时间点；timestamp 表示发送时间，两者共同用于精确去重。
                        key = self._crawler.danmaku._make_danmaku_dedup_key(d)
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        dedup.append(d)

                    records = []
                    existing_keys: set[tuple[str, Any, Any, str]] = set()
                    if mode != "full":
                        existing_keys = {
                            (
                                str(row[0] or ""),
                                row[1],
                                row[2],
                                str(row[3] or ""),
                            )
                            for row in self.session.exec(
                                select(
                                    DanmuRecord.content,
                                    DanmuRecord.video_time,
                                    DanmuRecord.timestamp,
                                    DanmuRecord.sender_hash,
                                ).where(
                                    DanmuRecord.season_id == season_id,
                                    DanmuRecord.cid == ep.cid,
                                )
                            ).all()
                        }
                    for d in dedup:
                        key = self._crawler.danmaku._make_danmaku_dedup_key(d)
                        if key in existing_keys:
                            continue
                        existing_keys.add(key)
                        score = None
                        if callable(sentiment_fn):
                            try:
                                score = sentiment_fn(d["content"])
                            except Exception as exc:
                                logger.warning("⚠️ 弹幕情感函数执行失败 content_len={} error={}", len(d["content"]), exc)
                        records.append(
                            DanmuRecord(
                                season_id=season_id,
                                episode_number=ep_index,
                                cid=ep.cid,
                                content=d["content"],
                                video_time=d.get("video_time"),
                                timestamp=d.get("timestamp"),
                                sender_hash=d.get("sender_hash"),
                                sentiment_score=score,
                            )
                        )

                    with sqlite_write_lock:
                        self.session.add_all(records)
                        self.session.commit()
                    danmu_saved += len(records)
                    logger.info(
                        "  ✅ 弹幕已写入 episode={} cid={} current={} history={} sqlite_saved={}",
                        ep_index,
                        ep.cid,
                        len(current_danmaku),
                        len(history_danmaku),
                        len(records),
                    )
                    self._throttle()
                else:
                    logger.warning(
                        "  ⚠️ 跳过弹幕抓取：缺少 cid episode={} bvid={}", ep_index, ep.bvid
                    )

                # ── 评论 ───────────────────────────────────────────────────
                if not ep.bvid:
                    logger.warning("  ⚠️ 跳过评论抓取：缺少 bvid episode={}", ep_index)
                    continue
                if not avid:
                    logger.warning(
                        "  ⚠️ 跳过评论抓取：无法解析 aid episode={} bvid={} aid={} view_keys={}",
                        ep_index,
                        ep.bvid,
                        avid,
                        list(view_data.keys())[:8],
                    )
                    continue

                raw_comments = self.fetch_comments(
                    avid,
                    limit=comment_limit,
                    include_replies=include_comment_replies,
                    nested_reply_limit=nested_reply_limit,
                    bvid=ep.bvid,
                )
                c_records = []
                existing_comment_keys = set()
                if mode != "full":
                    existing_comment_keys = {
                        (str(row[0] or ""), str(row[1] or ""), row[2])
                        for row in self.session.exec(
                            select(
                                CommentRecord.root_rpid,
                                CommentRecord.parent_rpid,
                                CommentRecord.content,
                            ).where(
                                CommentRecord.season_id == season_id,
                                CommentRecord.avid == avid,
                            )
                        ).all()
                    }
                for c in raw_comments:
                    comment_key = self._make_comment_dedup_key(c)
                    if comment_key in existing_comment_keys:
                        continue
                    existing_comment_keys.add(comment_key)
                    score = None
                    if callable(sentiment_fn):
                        try:
                            score = sentiment_fn(c["content"])
                        except Exception as exc:
                            logger.warning("⚠️ 评论情感函数执行失败 content_len={} error={}", len(c["content"]), exc)
                    c_records.append(
                        CommentRecord(
                            season_id=season_id,
                            avid=avid,
                            root_rpid=c.get("root_rpid"),
                            parent_rpid=c.get("parent_rpid"),
                            level=c.get("level", 0),
                            is_top_level=c.get("is_top_level", True),
                            content=c["content"],
                            likes=c.get("likes", 0),
                            replies=c.get("replies", 0),
                            sentiment_score=score,
                        )
                    )
                with sqlite_write_lock:
                    self.session.add_all(c_records)
                    self.session.commit()
                comment_saved += len(c_records)
                logger.info(
                    "  ✅ 评论已写入 episode={} bvid={} avid={} fetched={} saved={}",
                    ep_index,
                    ep.bvid,
                    avid,
                    len(raw_comments),
                    len(c_records),
                )
                if run_nlp_async:
                    try:
                        from ..tasks import enqueue_episode_nlp_task

                        task_id = enqueue_episode_nlp_task(
                            season_id=season_id,
                            episode_number=ep_index,
                            cid=str(ep.cid) if ep.cid else None,
                        )
                        if task_id:
                            logger.info(
                                "  🧠 NLP 任务已派发 episode={} season_id={} task_id={}",
                                ep_index,
                                season_id,
                                task_id,
                            )
                        else:
                            logger.info(
                                "  🧠 NLP 本地执行完成 episode={} season_id={}", ep_index, season_id
                            )
                    except Exception as exc:
                        logger.warning(
                            "⚠️ NLP 任务触发失败 episode={} season_id={} error={}",
                            ep_index,
                            season_id,
                            exc,
                        )
                self._throttle()
            except Exception as exc:
                logger.exception(
                    "❌ 剧集抓取失败 episode={} bvid={} cid={} error={}",
                    ep_index,
                    ep.bvid,
                    ep.cid,
                    exc,
                )
                continue

        try:
            from ..analytics import update_episode_sentiment_aggregates

            update_episode_sentiment_aggregates(self.session, season_id)
        except Exception as exc:
            logger.warning("⚠️ 回填 EpisodeStats 聚合字段失败 season_id={}: {}", season_id, exc)

        crawl_log.status = "success"
        crawl_log.items_count = danmu_saved + comment_saved
        crawl_log.total_scraped = danmu_saved + comment_saved
        crawl_log.final_inserted = danmu_saved + comment_saved
        crawl_log.retry_count = self.request_counters["retries"]
        crawl_log.failed_count = self.request_counters["failed"]
        crawl_log.completed_at = datetime.now()
        crawl_log.duration = (crawl_log.completed_at - crawl_log.started_at).total_seconds()
        self.session.commit()
        self.override_retry_attempts = None
        logger.info(
            f"🎉 弹幕/评论抓取完成 season_id={season_id} danmu={danmu_saved} comments={comment_saved}"
        )
        return {
            "danmu_saved": danmu_saved,
            "comment_saved": comment_saved,
            "mongo_saved": mongo_saved,
            "retry_count": self.request_counters["retries"],
            "failed_requests": self.request_counters["failed"],
        }

    @staticmethod
    def _make_comment_dedup_key(comment: dict[str, Any]) -> tuple[str, str, str]:
        """构造评论去重键：(root_rpid, parent_rpid, content)。"""
        return (
            str(comment.get("root_rpid") or ""),
            str(comment.get("parent_rpid") or ""),
            str(comment.get("content") or ""),
        )
