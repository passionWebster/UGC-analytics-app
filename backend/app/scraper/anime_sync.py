"""Anime domain synchronization service."""

from __future__ import annotations

import json
import random
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlmodel import select
from tqdm import tqdm

from ..config import settings
from ..logger import scraper_logger as logger
from ..models import Anime, CrawlLog, DailyStats, EpisodeStats
from .runtime import sqlite_write_lock

AnimePayload = dict[str, Any]

if TYPE_CHECKING:
    from .crawler import BilibiliBangumiCrawler


class AnimeSyncService:
    """Handle anime-level crawl and persistence workflows.

    This service owns season-level ingestion logic, while request/session/state are
    still shared through the crawler facade instance.
    """

    def __init__(self, crawler: BilibiliBangumiCrawler) -> None:
        """Bind the service to the shared crawler runtime context.

        参数:
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

    def update_anime_database(self) -> bool:
        """
        更新番剧数据库
        从 B站 API 抓取数据并存储到数据库

        返回:
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

        参数:
            keyword: 搜索关键词

        返回:
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
            full_data = self._crawler.episode_sync.get_episode_stat_details(bvid)
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
                    self._crawler.episode_sync._apply_stat_to_episode(new_ep, stat, ep_title)
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

        参数:
            title: 番剧标题

        返回:
            season_id 或 None
        """
        anime = self.session.exec(select(Anime).where(Anime.title == title)).first()

        return anime.season_id if anime else None

    def _fetch_api_data(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """
        执行单次 API 请求

        参数:
            params: API 请求参数

        返回:
            返回数据列表
        """
        all_items = []
        for page in range(1, settings.crawler_pages_to_fetch + 1):
            current_params = params.copy()
            current_params.update({"page": page, "pagesize": settings.crawler_page_size})

            try:
                response = self._request_get(
                    self.BASE_API_URL,
                    params=current_params,
                    timeout=settings.bilibili_request_timeout,
                )
                if response is None:
                    break
                data = response.json()

                if data.get("code") == 0 and "data" in data:
                    api_data = data["data"]
                    page_list = api_data.get("list", [])
                    all_items.extend(page_list)

                    if not api_data.get("has_next", 0):
                        break
                else:
                    logger.warning("  ❌ API 返回错误: {}", data.get("message", "未知错误"))
                    break
            except Exception as e:
                logger.exception("  ❌ 请求失败: {}", e)
                break

        return all_items

    def _fetch_domestic_animes(self) -> dict[int, AnimePayload]:
        """获取国产番剧数据"""
        animes = {}
        years = list(range(datetime.now().year, 2015, -1))

        for year in years:
            year_param = f"[{year},{year + 1})"
            params = {
                "season_version": -1,
                "is_finish": -1,
                "copyright": -1,
                "season_status": -1,
                "year": year_param,
                "style_id": -1,
                "order": 5,
                "st": 4,
                "sort": 0,
                "season_type": 4,
                "type": 1,
            }

            items = self._fetch_api_data(params)
            logger.info(f"  获取 {year} 年国产番剧: {len(items)} 部")

            for item in items:
                season_id = item.get("season_id")
                if not season_id or season_id in animes:
                    continue

                parsed_year, parsed_month = self._parse_release_date_from_order(
                    item.get("order", "")
                )
                release_date = "更早"
                if parsed_year in ["敬请期待", "更早"]:
                    release_date = parsed_year
                elif parsed_year and parsed_month:
                    release_date = f"{parsed_year}-{parsed_month:02d}"

                score_raw = (
                    item.get("score") if item.get("score") is not None else item.get("rating")
                )
                animes[season_id] = {
                    "season_id": season_id,
                    "title": item.get("title", ""),
                    "cover": item.get("cover", ""),
                    "area": "国内",
                    "rating": float(score_raw) if score_raw else None,
                    "styles": [],
                    "release_date": release_date,
                    "views": 0,
                    "favorites": 0,
                    # 以下字段由 _enrich_details 阶段填充
                    "total_coins": None,
                    "total_danmakus": None,
                    "total_likes": None,
                    "total_reply": None,
                    "total_share": None,
                    "rating_count": None,
                    "is_finish": None,
                    "copyright": None,
                    "areas_raw": [],
                }

        return animes

    def _fetch_regular_animes(self) -> dict[int, AnimePayload]:
        """获取常规番剧数据"""
        animes = {}
        years = list(range(datetime.now().year, 2015, -1))
        months = [1, 4, 7, 10]

        for year in years:
            for month in months:
                year_param = f"[{year},{year + 1})"
                params = {
                    "st": 1,
                    "order": 2,
                    "season_version": -1,
                    "spoken_language_type": -1,
                    "area": -1,
                    "is_finish": -1,
                    "copyright": -1,
                    "season_status": -1,
                    "season_month": month,
                    "year": year_param,
                    "style_id": -1,
                    "sort": 0,
                    "season_type": 1,
                    "type": 1,
                }

                items = self._fetch_api_data(params)
                logger.info(f"  获取 {year}-{month:02d} 常规番剧: {len(items)} 部")

                for item in items:
                    season_id = item.get("season_id")
                    if not season_id or season_id in animes:
                        continue

                    score_raw = (
                        item.get("score") if item.get("score") is not None else item.get("rating")
                    )
                    animes[season_id] = {
                        "season_id": season_id,
                        "title": item.get("title", ""),
                        "cover": item.get("cover", ""),
                        "area": "其他",
                        "rating": float(score_raw) if score_raw else None,
                        "styles": [],
                        "release_date": f"{year}-{month:02d}",
                        "views": self._convert_order_to_int(item.get("order", "0")),
                        "favorites": 0,
                        # 以下字段由 _enrich_details 阶段填充
                        "total_coins": None,
                        "total_danmakus": None,
                        "total_likes": None,
                        "total_reply": None,
                        "total_share": None,
                        "rating_count": None,
                        "is_finish": None,
                        "copyright": None,
                        "areas_raw": [],
                    }

        return animes

    def _fetch_regular_by_style(self, style_id: int) -> list[dict[str, Any]]:
        """获取指定风格的常规番剧列表"""
        params = {
            "st": 1,
            "order": 2,
            "season_version": -1,
            "spoken_language_type": -1,
            "area": -1,
            "is_finish": -1,
            "copyright": -1,
            "season_status": -1,
            "season_month": -1,
            "year": "-1",
            "style_id": style_id,
            "sort": 0,
            "season_type": 1,
            "type": 1,
        }
        return self._fetch_api_data(params)

    def _fetch_domestic_by_style(self, style_id: int) -> list[dict[str, Any]]:
        """获取指定风格的国产番剧列表"""
        params = {
            "season_version": -1,
            "is_finish": -1,
            "copyright": -1,
            "season_status": -1,
            "year": "-1",
            "style_id": style_id,
            "order": 2,
            "st": 4,
            "sort": 0,
            "season_type": 4,
            "type": 1,
        }
        return self._fetch_api_data(params)

    def _enrich_regular_styles(
        self, all_animes: dict[int, AnimePayload]
    ) -> dict[int, AnimePayload]:
        """
        补充常规番剧风格信息：遍历 REGULAR_API_STYLE_IDS，将返回的番剧追加对应风格
        """
        for style_id in self.REGULAR_API_STYLE_IDS:
            style_name = self.STYLE_MAP.get(style_id)
            if not style_name:
                continue
            style_items = self._fetch_regular_by_style(style_id)
            for item in style_items:
                season_id = item.get("season_id")
                if season_id in all_animes and style_name not in all_animes[season_id]["styles"]:
                    all_animes[season_id]["styles"].append(style_name)

        return all_animes

    def _enrich_domestic_styles(
        self, all_animes: dict[int, AnimePayload]
    ) -> dict[int, AnimePayload]:
        """
        补充国产番剧风格信息：遍历 DOMESTIC_API_STYLE_IDS，将返回的番剧追加对应风格
        """
        for style_id in self.DOMESTIC_API_STYLE_IDS:
            style_name = self.STYLE_MAP.get(style_id)
            if not style_name:
                continue
            style_items = self._fetch_domestic_by_style(style_id)
            for item in style_items:
                season_id = item.get("season_id")
                if season_id in all_animes and style_name not in all_animes[season_id]["styles"]:
                    all_animes[season_id]["styles"].append(style_name)

        return all_animes

    def _enrich_details(self, all_animes: dict[int, AnimePayload]) -> dict[int, AnimePayload]:
        """
        逐部请求番剧详情 API（/pgc/view/web/season），填充以下字段：
          - 播放量 / 追番量（覆盖底库中的估算值）
          - 评分及评分人数
          - 发布日期（更精确的 publish.pub_time 来源）
          - 地区（来自 areas 数组，替代旧的批量 area 接口）
          - 完结状态 / 版权类型 / 完整地区 JSON
          - 全剧互动统计：投币数、弹幕数、点赞数、评论数、分享数

        地区映射规则见类常量 AREA_ID_TO_ENUM。
        """
        total = len(all_animes)
        logger.info(f"  正在逐部请求番剧详情 API，共 {total} 部...")
        success_count = 0
        # 用于每 50 部批量落库的计数器与临时字典
        FLUSH_BATCH = 50
        batch: dict[int, AnimePayload] = {}

        for season_id, anime_data in tqdm(all_animes.items(), desc="详情补充", unit="部"):
            try:
                details = self.get_anime_details(season_id)
                if not details:
                    time.sleep(random.uniform(0.1, 2.0))
                    continue

                # ── 播放量 / 追番量（精确值，覆盖估算）──────────────────────────
                if details.get("views"):
                    anime_data["views"] = details["views"]
                if details.get("favorites"):
                    anime_data["favorites"] = details["favorites"]

                # ── 评分（detail API 精度更高）──────────────────────────────────
                if details.get("rating_score") is not None:
                    anime_data["rating"] = float(details["rating_score"])

                # ── 互动统计 ────────────────────────────────────────────────────
                anime_data["total_coins"] = details.get("total_coins")
                anime_data["total_danmakus"] = details.get("total_danmakus")
                anime_data["total_likes"] = details.get("total_likes")
                anime_data["total_reply"] = details.get("total_reply")
                anime_data["total_share"] = details.get("total_share")
                anime_data["rating_count"] = details.get("rating_count")

                # ── 完结状态 / 版权 ─────────────────────────────────────────────
                if details.get("is_finish") is not None:
                    anime_data["is_finish"] = details["is_finish"]
                if details.get("copyright"):
                    anime_data["copyright"] = details["copyright"]

                # ── 地区（areas 数组，替代旧的批量接口）────────────────────────
                areas = details.get("areas", [])
                if areas:
                    anime_data["areas_raw"] = areas
                    first_id = areas[0].get("id")
                    mapped = self.AREA_ID_TO_ENUM.get(first_id)
                    if mapped:
                        anime_data["area"] = mapped
                    # 若不在映射表内且当前仍是 '其他'，保持不变

                # ── 发布日期（使用 publish.pub_time 修正）──────────────────────
                pub_time: str = details.get("pub_time", "") or ""
                if pub_time:
                    try:
                        pub_dt = datetime.strptime(pub_time[:10], "%Y-%m-%d")
                        pub_year = pub_dt.year
                        quarter_month = self._get_quarter_month(pub_dt.month)
                        if pub_year >= 2015 and quarter_month:
                            anime_data["release_date"] = f"{pub_year}-{quarter_month:02d}"
                        elif pub_year < 2015:
                            anime_data["release_date"] = "更早"
                    except ValueError:
                        pass  # 日期格式异常时保留原值
                batch[season_id] = anime_data
                success_count += 1
            except Exception as exc:
                logger.warning(f"  ⚠️ season_id={season_id} 详情获取异常: {exc}")
            finally:
                # 随机延迟 0.1~2.0 秒，防止触发 B站反爬
                time.sleep(random.uniform(0.1, 2.0))
                # 每积累 FLUSH_BATCH 部就落库一次，防止进程意外终止导致数据丢失
            if len(batch) >= FLUSH_BATCH:
                logger.info(f"  💾 中间落库：保存已完成的 {len(batch)} 部...")
                self._save_animes_to_db(batch)
                batch.clear()
        # 落库剩余不足一批的数据
        if batch:
            logger.info(f"  💾 最终落库：保存剩余 {len(batch)} 部...")
            self._save_animes_to_db(batch)

        logger.info(f"  ✅ 番剧详情补充完成：成功 {success_count} / {total} 部")
        return all_animes

    def _save_animes_to_db(self, animes: dict[int, AnimePayload]) -> None:
        """
        将番剧数据保存到数据库
        """
        today = datetime.now().date()

        for season_id, anime_data in animes.items():
            # 检查番剧是否已存在
            existing_anime = self.session.exec(
                select(Anime).where(Anime.season_id == season_id)
            ).first()

            if existing_anime:
                # 更新现有记录
                existing_anime.title = anime_data["title"]
                existing_anime.cover = anime_data["cover"]
                existing_anime.area = anime_data["area"]
                existing_anime.rating = anime_data["rating"]
                existing_anime.styles = json.dumps(anime_data["styles"], ensure_ascii=False)
                existing_anime.release_date = anime_data["release_date"]
                # 新增互动统计字段
                existing_anime.total_coins = anime_data.get("total_coins")
                existing_anime.total_danmakus = anime_data.get("total_danmakus")
                existing_anime.total_likes = anime_data.get("total_likes")
                existing_anime.total_reply = anime_data.get("total_reply")
                existing_anime.total_share = anime_data.get("total_share")
                existing_anime.rating_count = anime_data.get("rating_count")
                existing_anime.is_finish = anime_data.get("is_finish")
                existing_anime.copyright = anime_data.get("copyright")
                areas_raw = anime_data.get("areas_raw", [])
                existing_anime.areas_raw = (
                    json.dumps(areas_raw, ensure_ascii=False) if areas_raw else None
                )
                existing_anime.updated_at = datetime.now()
            else:
                # 创建新记录
                areas_raw = anime_data.get("areas_raw", [])
                new_anime = Anime(
                    season_id=season_id,
                    title=anime_data["title"],
                    cover=anime_data["cover"],
                    area=anime_data["area"],
                    rating=anime_data["rating"],
                    styles=json.dumps(anime_data["styles"], ensure_ascii=False),
                    release_date=anime_data["release_date"],
                    total_coins=anime_data.get("total_coins"),
                    total_danmakus=anime_data.get("total_danmakus"),
                    total_likes=anime_data.get("total_likes"),
                    total_reply=anime_data.get("total_reply"),
                    total_share=anime_data.get("total_share"),
                    rating_count=anime_data.get("rating_count"),
                    is_finish=anime_data.get("is_finish"),
                    copyright=anime_data.get("copyright"),
                    areas_raw=json.dumps(areas_raw, ensure_ascii=False) if areas_raw else None,
                )
                self.session.add(new_anime)

            # 添加每日统计数据
            existing_stats = self.session.exec(
                select(DailyStats).where(
                    DailyStats.season_id == season_id,
                    DailyStats.date >= datetime.combine(today, datetime.min.time()),
                )
            ).first()

            if not existing_stats:
                daily_stat = DailyStats(
                    season_id=season_id,
                    date=datetime.now(),
                    views=anime_data["views"],
                    favorites=anime_data["favorites"],
                )
                self.session.add(daily_stat)

        self.session.commit()
        logger.info(f"✅ 已保存 {len(animes)} 部番剧到数据库")

    def get_anime_details(self, season_id: int) -> dict | None:
        """
        获取番剧详细信息（/pgc/view/web/season），返回包含完整元数据的字典。

        返回字段（均可能为 None）：
          title, cover              — 基础信息
          stat                      — 原始 stat 对象（向后兼容）
          episodes                  — 剧集列表（向后兼容）
          areas                     — 地区数组，如 [{"id":2,"name":"日本"}]
          views, favorites          — 播放量、追番量（来自 stat）
          total_coins               — 全剧总投币数（来自 stat.coins）
          total_danmakus            — 全剧总弹幕数（来自 stat.danmakus）
          total_likes               — 全剧总点赞数（来自 stat.likes）
          total_reply               — 全剧总评论数（来自 stat.reply）
          total_share               — 全剧总分享数（来自 stat.share）
          rating_score              — 评分（来自 rating.score）
          rating_count              — 评分人数（来自 rating.count）
          is_finish                 — 完结状态：0 连载 / 1 完结（来自 publish.is_finish）
          pub_time                  — 首播日期字符串（来自 publish.pub_time）
          copyright                 — 版权类型：bilibili / dujia（来自 rights.copyright）

        参数:
            season_id: 番剧 season_id

        返回:
            番剧详细信息字典，请求失败时返回 None
        """
        url = f"https://api.bilibili.com/pgc/view/web/season?season_id={season_id}"
        try:
            response = self._request_get(url, timeout=settings.bilibili_request_timeout)
            if response is None:
                return None
            data = response.json()

            if data.get("code") == 0 and "result" in data:
                result = data["result"]
                stat = result.get("stat", {})
                rating = result.get("rating", {})
                publish = result.get("publish", {})
                rights = result.get("rights", {})
                areas = result.get("areas", [])

                return {
                    # ── 向后兼容字段（fetch_and_save_episodes 等调用方使用）──
                    "title": result.get("title"),
                    "cover": result.get("cover"),
                    "stat": stat,
                    "episodes": result.get("episodes", []),
                    # ── 地区 ──────────────────────────────────────────────────
                    "areas": areas,
                    # ── stat 对象展开 ─────────────────────────────────────────
                    "views": stat.get("views"),
                    "favorites": stat.get("favorites"),
                    "total_coins": stat.get("coins"),
                    "total_danmakus": stat.get("danmakus"),
                    "total_likes": stat.get("likes"),
                    "total_reply": stat.get("reply"),
                    "total_share": stat.get("share"),
                    # ── rating 对象 ───────────────────────────────────────────
                    "rating_score": rating.get("score"),
                    "rating_count": rating.get("count"),
                    # ── publish 对象 ──────────────────────────────────────────
                    "is_finish": publish.get("is_finish"),
                    "pub_time": publish.get("pub_time"),
                    # ── rights 对象 ───────────────────────────────────────────
                    "copyright": rights.get("copyright"),
                }
        except Exception:
            logger.exception("❌ 获取番剧详情失败 season_id={}", season_id)

        return None

    def search_bangumi_on_bilibili(self, keyword: str) -> int | None:
        """
        通过关键词在 B站 搜索番剧，返回最匹配的 season_id

        参数:
            keyword: 搜索关键词

        返回:
            season_id 或 None
        """
        url = "https://api.bilibili.com/x/web-interface/search/type"
        params = {"keyword": keyword, "search_type": "media_bangumi"}
        try:
            response = self._request_get(
                url, params=params, timeout=settings.bilibili_request_timeout
            )
            if response is None:
                return None
            data = response.json()
            if data.get("code") == 0 and "data" in data:
                results = data["data"].get("result", [])
                if results:
                    # 取第一个结果的 season_id
                    season_id = results[0].get("season_id")
                    if season_id:
                        return int(season_id)
        except Exception as e:
            logger.exception("❌ B站搜索失败 keyword={}: {}", keyword, e)
        return None
