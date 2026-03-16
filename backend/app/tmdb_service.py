# tmdb_service.py
"""
TMDB API 集成服务

封装与 TMDB（The Movie Database）API 的所有交互逻辑，包括：
- 番剧搜索（标题清洗 + 年份辅助匹配）
- 剧集详情获取（支持多语言降级策略）
- 图片资源获取与优选（背景图、Logo、海报）
- 单部番剧完整富集流程
"""
import asyncio
import json
import re
from datetime import datetime
from typing import Optional, Dict, List

import httpx
from sqlmodel import Session, select

from .config import settings
from .database import engine
from .models import Anime, TmdbAnimeInfo

# 全局复用的 TMDB AsyncClient，避免每次调用重复建连与 TLS 握手
_tmdb_async_client: Optional[httpx.AsyncClient] = None
_tmdb_client_lock = asyncio.Lock()


async def get_shared_tmdb_client(timeout: float) -> httpx.AsyncClient:
    """
    获取全局复用的 httpx.AsyncClient 实例。

    若客户端尚未创建或已被关闭，则在加锁的情况下重新创建。
    """
    global _tmdb_async_client

    # 快路径：已存在且未关闭的客户端直接返回
    if _tmdb_async_client is not None and not _tmdb_async_client.is_closed:
        return _tmdb_async_client

    # 慢路径：需要在锁内检查并创建新客户端
    async with _tmdb_client_lock:
        if _tmdb_async_client is None or _tmdb_async_client.is_closed:
            _tmdb_async_client = httpx.AsyncClient(timeout=timeout)
        return _tmdb_async_client


class TmdbService:
    """
    TMDB API 服务类

    所有对外方法均为异步，适合配合 FastAPI 的异步路由或
    APScheduler AsyncIOScheduler 调度任务使用。
    若 TMDB_API_KEY 未配置，所有方法安全地返回 None/空值，不抛出异常。
    """

    def __init__(self, api_key: Optional[str] = None):
        # 优先使用传入的 key，否则从全局配置读取
        self.api_key: Optional[str] = api_key or settings.tmdb_api_key
        self.base_url: str = settings.tmdb_api_base_url
        self.timeout: int = settings.tmdb_request_timeout
        self.image_base_original: str = settings.tmdb_image_base_original
        self.image_base_w500: str = settings.tmdb_image_base_w500

    def is_available(self) -> bool:
        """检查 TMDB API Key 是否已配置，未配置时 TMDB 功能全部降级"""
        return bool(self.api_key)

    # ─── 标题清洗 ───────────────────────────────────────────────────────────

    @staticmethod
    def clean_title(title: str) -> str:
        """
        清理 B站番剧标题，去除影响 TMDB 搜索精准度的附加信息。

        处理策略：
        1. 去除全角和半角括号及其括号内的全部内容（如"（中配版）"）
        2. 去除"第X季/第X部/第X期"等季度标识
        3. 去除常见中文版本标注（如"仅限港澳台"、"国语版"等）
        4. 去除首尾空白字符

        参数：
            title: 原始 B站番剧标题

        返回：
            清洗后的标题字符串
        """
        # 去除全角括号及其内容
        cleaned = re.sub(r'（[^）]*）', '', title)
        # 去除半角括号及其内容
        cleaned = re.sub(r'\([^)]*\)', '', cleaned)
        # 去除"第X季/第X部/第X期"格式的季度标识
        cleaned = re.sub(r'第[一二三四五六七八九十百\d]+[季部期]', '', cleaned)
        # 去除常见中文版本与地区标注
        cleaned = re.sub(
            r'(仅限港澳台|中配版|普通话版|国语版|粤语版|TV版|BD版|剧场版|完整版|修复版)',
            '',
            cleaned,
        )
        return cleaned.strip()

    # ─── TMDB API 调用 ───────────────────────────────────────────────────────

    async def search_tv(
        self,
        title: str,
        year: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        通过标题在 TMDB 搜索电视剧，返回最匹配的结果。

        匹配策略：
        - 若提供年份，优先返回 first_air_date 年份与之吻合的结果；
        - 年份未命中或未提供时，回退到搜索结果列表第一项。

        参数：
            title: 清洗后的番剧标题（建议先调用 clean_title）
            year:  B站发布年份（格式 "2023"），用于辅助匹配，可为 None

        返回：
            TMDB 搜索结果中最匹配的剧集字典；搜索失败或无结果时返回 None
        """
        if not self.is_available():
            return None

        params: Dict = {
            "api_key": self.api_key,
            "query": title,
            "language": "zh-CN",
        }

        try:
            client = await get_shared_tmdb_client(self.timeout)
            response = await client.get(
                f"{self.base_url}/search/tv", params=params
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError:
            return None

        results: List[Dict] = data.get("results", [])
        if not results:
            return None

        # 优先选择年份匹配的结果
        if year:
            for result in results:
                first_air = result.get("first_air_date") or ""
                if first_air.startswith(year):
                    return result

        # 年份未命中，退回第一个结果
        return results[0]

    async def get_tv_details(self, tmdb_id: int) -> Optional[Dict]:
        """
        获取 TMDB 电视剧详情。

        降级策略：若中文 overview 为空，自动以英文重新请求一次，
        确保简介字段不留白。

        参数：
            tmdb_id: TMDB 剧集唯一标识

        返回：
            剧集详情字典（语言为 zh-CN，overview 可能降级为英文）；失败返回 None
        """
        if not self.is_available():
            return None

        params: Dict = {"api_key": self.api_key, "language": "zh-CN"}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/tv/{tmdb_id}", params=params
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError:
            return None

        # overview 为空时降级请求英文简介
        if not data.get("overview"):
            try:
                params_en: Dict = {"api_key": self.api_key, "language": "en-US"}
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp_en = await client.get(
                        f"{self.base_url}/tv/{tmdb_id}", params=params_en
                    )
                    resp_en.raise_for_status()
                    data_en = resp_en.json()
                    data["overview"] = data_en.get("overview") or ""
            except httpx.HTTPError:
                pass  # 降级失败则 overview 保持空字符串

        return data

    async def get_tv_images(self, tmdb_id: int) -> Optional[Dict]:
        """
        获取 TMDB 电视剧图片资源（背景图、Logo、海报）。

        关键设计：使用 include_image_language=zh-CN,en,ja,null 参数
        一次性拉取多语言图片，避免仅请求 zh-CN 导致结果为空的问题。
        其中 null 表示无语言文字的纯净背景图，最适合作为详情页大图。

        参数：
            tmdb_id: TMDB 剧集唯一标识

        返回：
            包含 backdrops、logos、posters 列表的字典；失败返回 None
        """
        if not self.is_available():
            return None

        params: Dict = {
            "api_key": self.api_key,
            # 同时获取中文、英文、日文和无语言文字的纯净图片
            "include_image_language": "zh-CN,en,ja,null",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/tv/{tmdb_id}/images", params=params
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError:
            return None

    # ─── 图片优选逻辑 ────────────────────────────────────────────────────────

    def _select_best_backdrop(self, backdrops: List[Dict]) -> Optional[str]:
        """
        从背景图列表中筛选最佳图片。

        优选策略：
        1. 优先取 iso_639_1 为 null（无语言文字纯净背景）的图片
        2. 在候选池内按 vote_average（图片社区点赞分）降序取最高分
        3. 使用 original 分辨率前缀，保证最高清晰度

        参数：
            backdrops: TMDB /images 接口返回的 backdrops 列表

        返回：
            完整的背景图 URL；列表为空或无有效 file_path 时返回 None
        """
        if not backdrops:
            return None

        # 优先取无语言文字的纯净背景图
        clean_backdrops = [b for b in backdrops if b.get("iso_639_1") is None]
        pool = clean_backdrops if clean_backdrops else backdrops

        # 按社区点赞分降序排列，取最高分图片
        best = max(pool, key=lambda x: x.get("vote_average") or 0)
        file_path = best.get("file_path") or ""
        return f"{self.image_base_original}{file_path}" if file_path else None

    def _select_best_logo(self, logos: List[Dict]) -> Optional[str]:
        """
        从 Logo 列表中筛选最佳图片。

        优先顺序：zh（中文）> en（英文）> ja（日文）> 其他（兜底取第一张）。
        使用 w500 分辨率，平衡清晰度与加载性能。

        参数：
            logos: TMDB /images 接口返回的 logos 列表

        返回：
            完整的 Logo 图片 URL；列表为空时返回 None
        """
        if not logos:
            return None

        priority_langs = ["zh", "en", "ja"]
        for lang in priority_langs:
            matched = [lgo for lgo in logos if lgo.get("iso_639_1") == lang]
            if matched:
                file_path = matched[0].get("file_path") or ""
                return f"{self.image_base_w500}{file_path}" if file_path else None

        # 兜底：无语言偏好匹配时取列表第一张
        file_path = logos[0].get("file_path") or ""
        return f"{self.image_base_w500}{file_path}" if file_path else None

    def _select_best_poster(self, posters: List[Dict]) -> Optional[str]:
        """
        从海报列表中筛选最佳图片。

        优选策略：
        1. 优先取 iso_639_1 为 "zh" 的中文海报
        2. 在候选池内按 vote_average 降序取最高分
        3. 使用 w500 分辨率

        参数：
            posters: TMDB /images 接口返回的 posters 列表

        返回：
            完整的海报图片 URL；列表为空时返回 None
        """
        if not posters:
            return None

        zh_posters = [p for p in posters if p.get("iso_639_1") == "zh"]
        pool = zh_posters if zh_posters else posters

        best = max(pool, key=lambda x: x.get("vote_average") or 0)
        file_path = best.get("file_path") or ""
        return f"{self.image_base_w500}{file_path}" if file_path else None

    # ─── 完整富集流程 ────────────────────────────────────────────────────────

    async def enrich_anime(
        self,
        season_id: int,
        title: str,
        release_date: Optional[str] = None,
    ) -> Optional[TmdbAnimeInfo]:
        """
        对单部番剧执行完整的 TMDB 数据富集流程。

        流程：
        1. 清理 B站标题 → 搜索 TMDB → 年份辅助匹配
        2. 获取剧集详情（含 overview 降级策略）
        3. 获取多语言图片 → 优选背景图、Logo、海报
        4. 组装并返回 TmdbAnimeInfo 实例（未持久化到数据库）

        参数：
            season_id:    B站番剧 season_id
            title:        番剧标题（直接传入原始 B站标题，内部自动清洗）
            release_date: B站发布日期（格式 "YYYY-MM"），用于年份辅助匹配

        返回：
            填充完毕的 TmdbAnimeInfo 实例；搜索失败或 API 不可用时返回 None
        """
        if not self.is_available():
            return None

        # 清洗标题并提取年份
        cleaned_title = self.clean_title(title)
        year: Optional[str] = None
        if release_date and len(release_date) >= 4:
            year = release_date[:4]

        # 第一步：搜索
        search_result = await self.search_tv(cleaned_title, year)
        if not search_result:
            return None

        tmdb_id: Optional[int] = search_result.get("id")
        if not tmdb_id:
            return None

        # 第二步：并发获取详情和图片（两个请求无依赖，可同时发起）
        details, images = await asyncio.gather(
            self.get_tv_details(tmdb_id),
            self.get_tv_images(tmdb_id),
        )

        if not details:
            return None

        # 提取文本字段
        overview: str = details.get("overview") or ""
        tmdb_rating: Optional[float] = (
            float(details["vote_average"])
            if details.get("vote_average") is not None
            else None
        )
        genres: List[str] = [
            g["name"] for g in details.get("genres", []) if g.get("name")
        ]
        first_air_date: Optional[str] = (
            details.get("first_air_date")
            or search_result.get("first_air_date")
        )
        original_name: Optional[str] = (
            details.get("original_name") or details.get("name")
        )

        # 提取图片 URL
        backdrop_url: Optional[str] = None
        logo_url: Optional[str] = None
        poster_url: Optional[str] = None
        if images:
            backdrop_url = self._select_best_backdrop(images.get("backdrops") or [])
            logo_url = self._select_best_logo(images.get("logos") or [])
            poster_url = self._select_best_poster(images.get("posters") or [])

        return TmdbAnimeInfo(
            season_id=season_id,
            tmdb_id=tmdb_id,
            original_name=original_name,
            overview=overview,
            tmdb_rating=tmdb_rating,
            backdrop_url=backdrop_url,
            logo_url=logo_url,
            poster_url=poster_url,
            genres=json.dumps(genres, ensure_ascii=False),
            first_air_date=first_air_date,
            updated_at=datetime.now(),
        )


# ─── 批量富集任务 ─────────────────────────────────────────────────────────────

async def run_tmdb_enrichment(session: Session) -> Dict:
    """
    批量 TMDB 数据富集任务（异步）。

    执行逻辑：
    1. 通过传入的 session 查询所有尚未建立 TmdbAnimeInfo 记录的 Anime 条目
    2. 使用 asyncio.Semaphore 控制并发数（上限由配置项决定），
       避免触发 TMDB 的速率限制
    3. 每条富集任务在独立的数据库 Session 中提交，
       避免多协程共享同一 Session 导致的竞态条件
    4. 每次请求后等待 0.2 秒，进一步降低被限流的风险

    参数：
        session: SQLModel 数据库会话（仅用于查询待处理列表，不用于写入）

    返回：
        统计字典，包含 total（待处理数）、success（成功数）、failed（失败/跳过数）
    """
    service = TmdbService()
    if not service.is_available():
        return {"total": 0, "success": 0, "failed": 0, "message": "TMDB_API_KEY 未配置，任务跳过"}

    # 查询所有还没有 TMDB 记录的番剧（仅做读操作）
    enriched_ids = session.exec(
        select(TmdbAnimeInfo.season_id)
    ).all()
    enriched_set = set(enriched_ids)

    all_animes = session.exec(select(Anime)).all()
    pending = [a for a in all_animes if a.season_id not in enriched_set]

    if not pending:
        return {"total": 0, "success": 0, "failed": 0, "message": "所有番剧均已完成 TMDB 富集"}

    semaphore = asyncio.Semaphore(settings.tmdb_enrichment_concurrency)
    success_count = 0
    failed_count = 0

    async def _enrich_one(anime: Anime) -> None:
        nonlocal success_count, failed_count
        async with semaphore:
            try:
                info = await service.enrich_anime(
                    season_id=anime.season_id,
                    title=anime.title,
                    release_date=anime.release_date,
                )
                if info:
                    # 每个写操作使用独立 Session，避免多协程共享 Session 的竞态问题
                    with Session(engine) as write_session:
                        write_session.add(info)
                        write_session.commit()
                    success_count += 1
                else:
                    failed_count += 1
            except Exception:
                failed_count += 1
            # 每次请求后短暂等待，降低触发限流的概率
            await asyncio.sleep(0.2)

    # 并发执行所有富集任务
    await asyncio.gather(*[_enrich_one(anime) for anime in pending])

    return {
        "total": len(pending),
        "success": success_count,
        "failed": failed_count,
        "message": f"TMDB 富集完成：{success_count}/{len(pending)} 成功",
    }
