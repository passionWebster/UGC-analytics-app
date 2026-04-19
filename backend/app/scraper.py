# scraper.py
"""
B站数据爬虫服务 - 重构版
将原 scraper.py 和 data_manager.py 的功能整合，数据直接写入 SQLite 数据库
"""
import hashlib
import json
import random
import re
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from functools import reduce
from typing import Tuple, List, Dict, Any, Optional, Set
import requests
from requests import Response
from sqlmodel import Session, select
from tqdm import tqdm

from .models import Anime, DailyStats, EpisodeStats, CrawlLog, DanmuRecord, CommentRecord
from .config import settings
from .mongodb import DanmakuMongoRepository
from .logger import scraper_logger as logger

# SQLite 写入互斥锁：用于本模块内的爬虫写入操作，防止多线程并发写入时产生数据库锁冲突。
# 注意：此锁仅在当前进程内、且仅对实际获取它的代码路径生效，并不能保证全项目的所有写入都已串行化。
sqlite_write_lock = threading.Lock()


class BilibiliBangumiCrawler:
    """
    B站番剧爬虫类
    负责从 B站 API 抓取数据并存储到 SQLite 数据库
    """
    
    # B站番剧索引API的URL
    BASE_API_URL = "https://api.bilibili.com/pgc/season/index/result"
    
    # 风格映射
    STYLE_MAP = {
        10010: '原创', 10011: '漫画改', 10012: '小说改', 10013: '游戏改', 10102: '特摄',
        10015: '布袋戏', 10016: '热血', 10017: '穿越', 10018: '奇幻', 10020: '战斗',
        10021: '搞笑', 10022: '日常', 10023: '科幻', 10024: '萌系', 10025: '治愈',
        10026: '校园', 10027: '少儿', 10028: '泡面', 10029: '恋爱', 10030: '少女',
        10031: '魔法', 10032: '冒险', 10033: '历史', 10034: '架空', 10035: '机战',
        10036: '神魔', 10037: '声控', 10038: '运动', 10039: '励志', 10040: '音乐',
        10041: '推理', 10042: '社团', 10043: '智斗', 10044: '催泪', 10045: '美食',
        10046: '偶像', 10047: '乙女', 10048: '职场', 10014: '动态漫', 10019: '玄幻',
        10078: '武侠', 10057: '悬疑', 10049: '古风'
    }
    
    # 常规番剧API支持的风格ID
    REGULAR_API_STYLE_IDS = {
        10010, 10011, 10012, 10013, 10102, 10015, 10016, 10017, 10018, 10020,
        10021, 10022, 10023, 10024, 10025, 10026, 10027, 10028, 10029, 10030,
        10031, 10032, 10033, 10034, 10035, 10036, 10037, 10038, 10039, 10040,
        10041, 10042, 10043, 10044, 10045, 10046, 10047, 10048
    }
    
    # 国产番剧API支持的风格ID
    DOMESTIC_API_STYLE_IDS = {
        10010, 10011, 10012, 10013, 10014, 10015, 10016, 10018, 10019, 10020,
        10021, 10078, 10022, 10023, 10024, 10025, 10057, 10026, 10027, 10028,
        10029, 10030, 10031, 10033, 10035, 10036, 10037, 10038, 10039, 10040,
        10041, 10042, 10043, 10044, 10045, 10046, 10047, 10048, 10049
    }
    
    # B站地区 id → AreaEnum 映射表（来自 /pgc/view/web/season areas 数组）
    # id=1  中国大陆 / id=6 中国香港 / id=7 中国台湾 → 国内
    # id=2  日本                                    → 日本
    # id=3  美国                                    → 美国
    # 其余 id                                       → 其他（保持不变）
    AREA_ID_TO_ENUM: Dict[int, str] = {
        1: '国内', 6: '国内', 7: '国内',
        2: '日本',
        3: '美国',
    }
    # 历史弹幕索引接口错误码（命中后无需继续请求更多月份）
    DM_HISTORY_STOP_CODES = {
        -101,  # 未登录
        -111,  # csrf 校验失败
        -400,  # 参数错误
        -412,  # 风控拦截
    }

    def __init__(self, session: Session):
        """
        初始化爬虫
        
        Args:
            session: SQLModel 数据库会话
        """
        self.session = session
        self.http_session = requests.Session()
        self.http_session.headers.update({
            'User-Agent': settings.crawler_user_agent,
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://www.bilibili.com/'
        })
        sessdata = (settings.bilibili_sessdata or "").strip()
        if sessdata:
            self.http_session.cookies.set("SESSDATA", sessdata, domain=".bilibili.com")
            logger.info("🍪 已启用 SESSDATA Cookie（用于历史弹幕抓取）")
        self.mongo_repo = DanmakuMongoRepository()
        self.override_retry_attempts: Optional[int] = None
        self.request_counters: Dict[str, int] = {"requests": 0, "retries": 0, "failed": 0}
        logger.info('✅ 爬虫已初始化')

    def _build_proxy(self) -> Optional[Dict[str, str]]:
        """根据配置构建单次请求代理。"""
        if not settings.crawler_proxy_enabled:
            return None
        pool = (settings.crawler_proxy_pool or "").strip()
        if not pool:
            return None
        candidates = [p.strip() for p in pool.split(",") if p.strip()]
        if not candidates:
            return None
        proxy = random.choice(candidates)
        return {"http": proxy, "https": proxy}

    def _throttle(self, *, force_base_delay: bool = False):
        """统一节流，支持随机抖动。"""
        if not force_base_delay and settings.bilibili_request_delay <= 0:
            return
        base = max(settings.bilibili_request_delay, 0.0)
        jitter = max(settings.bilibili_request_jitter, 0.0)
        sleep_seconds = base + (random.uniform(0, jitter) if jitter > 0 else 0.0)
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    def _request_get(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        retry_attempts: Optional[int] = None,
        force_base_delay: bool = True,
    ) -> Optional[Response]:
        """
        带重试、退避、代理、节流的统一 GET 请求入口。
        """
        attempts = (
            retry_attempts
            if retry_attempts is not None
            else (self.override_retry_attempts or settings.bilibili_retry_attempts)
        )
        attempts = max(1, attempts)
        timeout = timeout or settings.bilibili_request_timeout
        last_exc: Optional[Exception] = None
        for attempt in range(1, attempts + 1):
            self._throttle(force_base_delay=force_base_delay)
            self.request_counters["requests"] += 1
            try:
                response = self.http_session.get(
                    url,
                    params=params,
                    timeout=timeout,
                    proxies=self._build_proxy(),
                )
                response.raise_for_status()
                return response
            except Exception as exc:
                last_exc = exc
                if attempt < attempts:
                    self.request_counters["retries"] += 1
                    backoff = min(
                        settings.bilibili_retry_backoff_base * (2 ** (attempt - 1)),
                        settings.bilibili_retry_backoff_max,
                    )
                    logger.warning(
                        "⚠️ 请求失败，准备重试 attempt={}/{} url={} error={}",
                        attempt,
                        attempts,
                        url,
                        exc,
                    )
                    time.sleep(backoff)
                else:
                    self.request_counters["failed"] += 1
        logger.warning("❌ 请求最终失败 url={} error={}", url, last_exc)
        return None
    
    @staticmethod
    def _convert_order_to_int(order_str: Any) -> int:
        """
        将B站API返回的带单位数字字符串转换为整数
        例如: "9.9亿" -> 990000000, "3.4万" -> 34000
        """
        if not isinstance(order_str, str):
            return 0
        num_match = re.search(r'(\d+(\.\d+)?)', order_str)
        if not num_match:
            return 0
        num = float(num_match.group(1))
        if '亿' in order_str:
            return int(num * 100_000_000)
        if '万' in order_str:
            return int(num * 10_000)
        return int(num)
    
    @staticmethod
    def _is_valid_main_episode(episode: dict) -> bool:
        """
        根据 API 返回的字段判断该集是否为正片。
        第二道防线：利用 badge（角标）和 title/long_title（标题）过滤预告、PV 等非正片内容。
        """
        # 检查角标 (badge)
        badge = episode.get('badge', '')
        if badge in ['预告', 'PV', 'CM', '特报', '花絮']:
            return False

        # 检查标题 (title 和 long_title)
        title = episode.get('title', '')
        long_title = episode.get('long_title', '')
        combined_title = f"{title} {long_title}"

        invalid_keywords = ['预告', 'PV', 'NCOP', 'NCED', '先行图', '总集篇']
        for keyword in invalid_keywords:
            if keyword in combined_title:
                return False

        return True

    @staticmethod
    def _get_quarter_month(month: int) -> Optional[int]:
        """根据月份获取季度首月"""
        if 1 <= month <= 3:
            return 1
        elif 4 <= month <= 6:
            return 4
        elif 7 <= month <= 9:
            return 7
        elif 10 <= month <= 12:
            return 10
        return None
    
    @staticmethod
    def _parse_release_date_from_order(order_str: Any) -> Tuple[Optional[Any], Optional[int]]:
        """
        从 order 字符串解析发布日期
        返回 (year, quarter_month)
        """
        if not isinstance(order_str, str) or not order_str.strip():
            return None, None
        
        if "敬请期待" in order_str:
            return "敬请期待", None
        
        if "昨日开播" in order_str:
            yesterday = datetime.now() - timedelta(days=1)
            return yesterday.year, BilibiliBangumiCrawler._get_quarter_month(yesterday.month)
        
        year_only_match = re.search(r'(\d{4})开播', order_str)
        if year_only_match:
            year = int(year_only_match.group(1))
            if year < 2015:
                return "更早", None
            return None, None
        
        match = re.search(r'(?:(\d{2,4})年)?(\d+)月', order_str)
        if not match:
            return None, None
        
        year_str, month_str = match.groups()
        month = int(month_str)
        quarter_month = BilibiliBangumiCrawler._get_quarter_month(month)
        
        if quarter_month is None:
            return None, None
        
        year = None
        if year_str:
            year = int(year_str)
            if year < 100:
                current_yy = datetime.now().year % 100
                year = (1900 + year) if year > current_yy else (2000 + year)
            if year < 2015:
                return "更早", None
        
        return year, quarter_month
    
    def _fetch_api_data(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        执行单次 API 请求
        
        Args:
            params: API 请求参数
            
        Returns:
            返回数据列表
        """
        all_items = []
        for page in range(1, settings.crawler_pages_to_fetch + 1):
            current_params = params.copy()
            current_params.update({'page': page, 'pagesize': settings.crawler_page_size})
            
            try:
                response = self._request_get(
                    self.BASE_API_URL,
                    params=current_params,
                    timeout=settings.bilibili_request_timeout,
                )
                if response is None:
                    break
                data = response.json()
                
                if data.get('code') == 0 and 'data' in data:
                    api_data = data['data']
                    page_list = api_data.get('list', [])
                    all_items.extend(page_list)
                    
                    if not api_data.get('has_next', 0):
                        break
                else:
                    logger.warning('  ❌ API 返回错误: {}', data.get('message', '未知错误'))
                    break
            except Exception as e:
                logger.exception('  ❌ 请求失败: {}', e)
                break
        
        return all_items
    
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
        crawl_log = CrawlLog(
            task_type="full_update",
            status="running",
            started_at=start_time
        )
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
    
    def _fetch_domestic_animes(self) -> Dict[int, Dict]:
        """获取国产番剧数据"""
        animes = {}
        years = list(range(datetime.now().year, 2015, -1))
        
        for year in years:
            year_param = f"[{year},{year + 1})"
            params = {
                'season_version': -1, 'is_finish': -1, 'copyright': -1,
                'season_status': -1, 'year': year_param, 'style_id': -1,
                'order': 5, 'st': 4, 'sort': 0, 'season_type': 4, 'type': 1
            }
            
            items = self._fetch_api_data(params)
            logger.info(f"  获取 {year} 年国产番剧: {len(items)} 部")
            
            for item in items:
                season_id = item.get('season_id')
                if not season_id or season_id in animes:
                    continue
                
                parsed_year, parsed_month = self._parse_release_date_from_order(item.get('order', ''))
                release_date = "更早"
                if parsed_year in ["敬请期待", "更早"]:
                    release_date = parsed_year
                elif parsed_year and parsed_month:
                    release_date = f"{parsed_year}-{parsed_month:02d}"
                
                score_raw = item.get('score') if item.get('score') is not None else item.get('rating')
                animes[season_id] = {
                    'season_id': season_id,
                    'title': item.get('title', ''),
                    'cover': item.get('cover', ''),
                    'area': '国内',
                    'rating': float(score_raw) if score_raw else None,
                    'styles': [],
                    'release_date': release_date,
                    'views': 0,
                    'favorites': 0,
                    # 以下字段由 _enrich_details 阶段填充
                    'total_coins': None,
                    'total_danmakus': None,
                    'total_likes': None,
                    'total_reply': None,
                    'total_share': None,
                    'rating_count': None,
                    'is_finish': None,
                    'copyright': None,
                    'areas_raw': [],
                }
        
        return animes
    
    def _fetch_regular_animes(self) -> Dict[int, Dict]:
        """获取常规番剧数据"""
        animes = {}
        years = list(range(datetime.now().year, 2015, -1))
        months = [1, 4, 7, 10]
        
        for year in years:
            for month in months:
                year_param = f"[{year},{year + 1})"
                params = {
                    'st': 1, 'order': 2, 'season_version': -1,
                    'spoken_language_type': -1, 'area': -1, 'is_finish': -1,
                    'copyright': -1, 'season_status': -1, 'season_month': month,
                    'year': year_param, 'style_id': -1, 'sort': 0,
                    'season_type': 1, 'type': 1
                }
                
                items = self._fetch_api_data(params)
                logger.info(f"  获取 {year}-{month:02d} 常规番剧: {len(items)} 部")
                
                for item in items:
                    season_id = item.get('season_id')
                    if not season_id or season_id in animes:
                        continue
                    
                    score_raw = item.get('score') if item.get('score') is not None else item.get('rating')
                    animes[season_id] = {
                        'season_id': season_id,
                        'title': item.get('title', ''),
                        'cover': item.get('cover', ''),
                        'area': '其他',
                        'rating': float(score_raw) if score_raw else None,
                        'styles': [],
                        'release_date': f"{year}-{month:02d}",
                        'views': self._convert_order_to_int(item.get('order', '0')),
                        'favorites': 0,
                        # 以下字段由 _enrich_details 阶段填充
                        'total_coins': None,
                        'total_danmakus': None,
                        'total_likes': None,
                        'total_reply': None,
                        'total_share': None,
                        'rating_count': None,
                        'is_finish': None,
                        'copyright': None,
                        'areas_raw': [],
                    }
        
        return animes

    def _fetch_regular_by_style(self, style_id: int) -> List[Dict[str, Any]]:
        """获取指定风格的常规番剧列表"""
        params = {
            'st': 1, 'order': 2, 'season_version': -1,
            'spoken_language_type': -1, 'area': -1, 'is_finish': -1,
            'copyright': -1, 'season_status': -1, 'season_month': -1,
            'year': '-1', 'style_id': style_id, 'sort': 0,
            'season_type': 1, 'type': 1
        }
        return self._fetch_api_data(params)

    def _fetch_domestic_by_style(self, style_id: int) -> List[Dict[str, Any]]:
        """获取指定风格的国产番剧列表"""
        params = {
            'season_version': -1, 'is_finish': -1, 'copyright': -1, 'season_status': -1,
            'year': '-1', 'style_id': style_id, 'order': 2, 'st': 4, 'sort': 0,
            'season_type': 4, 'type': 1
        }
        return self._fetch_api_data(params)

    def _enrich_regular_styles(self, all_animes: Dict[int, Dict]) -> Dict[int, Dict]:
        """
        补充常规番剧风格信息：遍历 REGULAR_API_STYLE_IDS，将返回的番剧追加对应风格
        """
        for style_id in self.REGULAR_API_STYLE_IDS:
            style_name = self.STYLE_MAP.get(style_id)
            if not style_name:
                continue
            style_items = self._fetch_regular_by_style(style_id)
            for item in style_items:
                season_id = item.get('season_id')
                if season_id in all_animes and style_name not in all_animes[season_id]['styles']:
                    all_animes[season_id]['styles'].append(style_name)

        return all_animes

    def _enrich_domestic_styles(self, all_animes: Dict[int, Dict]) -> Dict[int, Dict]:
        """
        补充国产番剧风格信息：遍历 DOMESTIC_API_STYLE_IDS，将返回的番剧追加对应风格
        """
        for style_id in self.DOMESTIC_API_STYLE_IDS:
            style_name = self.STYLE_MAP.get(style_id)
            if not style_name:
                continue
            style_items = self._fetch_domestic_by_style(style_id)
            for item in style_items:
                season_id = item.get('season_id')
                if season_id in all_animes and style_name not in all_animes[season_id]['styles']:
                    all_animes[season_id]['styles'].append(style_name)

        return all_animes

    def _enrich_details(self, all_animes: Dict[int, Dict]) -> Dict[int, Dict]:
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
        logger.info(
            f"  正在逐部请求番剧详情 API，共 {total} 部...")
        success_count = 0
        # 用于每 50 部批量落库的计数器与临时字典
        FLUSH_BATCH = 50
        batch: Dict[int, Dict] = {}

        for season_id, anime_data in tqdm(all_animes.items(), desc="详情补充", unit="部"):
            try:
                details = self.get_anime_details(season_id)
                if not details:
                    time.sleep(random.uniform(0.1, 2.0))
                    continue

                # ── 播放量 / 追番量（精确值，覆盖估算）──────────────────────────
                if details.get('views'):
                    anime_data['views'] = details['views']
                if details.get('favorites'):
                    anime_data['favorites'] = details['favorites']

                # ── 评分（detail API 精度更高）──────────────────────────────────
                if details.get('rating_score') is not None:
                    anime_data['rating'] = float(details['rating_score'])

                # ── 互动统计 ────────────────────────────────────────────────────
                anime_data['total_coins'] = details.get('total_coins')
                anime_data['total_danmakus'] = details.get('total_danmakus')
                anime_data['total_likes'] = details.get('total_likes')
                anime_data['total_reply'] = details.get('total_reply')
                anime_data['total_share'] = details.get('total_share')
                anime_data['rating_count'] = details.get('rating_count')

                # ── 完结状态 / 版权 ─────────────────────────────────────────────
                if details.get('is_finish') is not None:
                    anime_data['is_finish'] = details['is_finish']
                if details.get('copyright'):
                    anime_data['copyright'] = details['copyright']

                # ── 地区（areas 数组，替代旧的批量接口）────────────────────────
                areas = details.get('areas', [])
                if areas:
                    anime_data['areas_raw'] = areas
                    first_id = areas[0].get('id')
                    mapped = self.AREA_ID_TO_ENUM.get(first_id)
                    if mapped:
                        anime_data['area'] = mapped
                    # 若不在映射表内且当前仍是 '其他'，保持不变

                # ── 发布日期（使用 publish.pub_time 修正）──────────────────────
                pub_time: str = details.get('pub_time', '') or ''
                if pub_time:
                    try:
                        pub_dt = datetime.strptime(pub_time[:10], '%Y-%m-%d')
                        pub_year = pub_dt.year
                        quarter_month = self._get_quarter_month(pub_dt.month)
                        if pub_year >= 2015 and quarter_month:
                            anime_data['release_date'] = f"{pub_year}-{quarter_month:02d}"
                        elif pub_year < 2015:
                            anime_data['release_date'] = '更早'
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

    def _save_animes_to_db(self, animes: Dict[int, Dict]):
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
                existing_anime.title = anime_data['title']
                existing_anime.cover = anime_data['cover']
                existing_anime.area = anime_data['area']
                existing_anime.rating = anime_data['rating']
                existing_anime.styles = json.dumps(anime_data['styles'], ensure_ascii=False)
                existing_anime.release_date = anime_data['release_date']
                # 新增互动统计字段
                existing_anime.total_coins = anime_data.get('total_coins')
                existing_anime.total_danmakus = anime_data.get('total_danmakus')
                existing_anime.total_likes = anime_data.get('total_likes')
                existing_anime.total_reply = anime_data.get('total_reply')
                existing_anime.total_share = anime_data.get('total_share')
                existing_anime.rating_count = anime_data.get('rating_count')
                existing_anime.is_finish = anime_data.get('is_finish')
                existing_anime.copyright = anime_data.get('copyright')
                areas_raw = anime_data.get('areas_raw', [])
                existing_anime.areas_raw = json.dumps(areas_raw, ensure_ascii=False) if areas_raw else None
                existing_anime.updated_at = datetime.now()
            else:
                # 创建新记录
                areas_raw = anime_data.get('areas_raw', [])
                new_anime = Anime(
                    season_id=season_id,
                    title=anime_data['title'],
                    cover=anime_data['cover'],
                    area=anime_data['area'],
                    rating=anime_data['rating'],
                    styles=json.dumps(anime_data['styles'], ensure_ascii=False),
                    release_date=anime_data['release_date'],
                    total_coins=anime_data.get('total_coins'),
                    total_danmakus=anime_data.get('total_danmakus'),
                    total_likes=anime_data.get('total_likes'),
                    total_reply=anime_data.get('total_reply'),
                    total_share=anime_data.get('total_share'),
                    rating_count=anime_data.get('rating_count'),
                    is_finish=anime_data.get('is_finish'),
                    copyright=anime_data.get('copyright'),
                    areas_raw=json.dumps(areas_raw, ensure_ascii=False) if areas_raw else None,
                )
                self.session.add(new_anime)
            
            # 添加每日统计数据
            existing_stats = self.session.exec(
                select(DailyStats).where(
                    DailyStats.season_id == season_id,
                    DailyStats.date >= datetime.combine(today, datetime.min.time())
                )
            ).first()
            
            if not existing_stats:
                daily_stat = DailyStats(
                    season_id=season_id,
                    date=datetime.now(),
                    views=anime_data['views'],
                    favorites=anime_data['favorites']
                )
                self.session.add(daily_stat)
        
        self.session.commit()
        logger.info(f"✅ 已保存 {len(animes)} 部番剧到数据库")
    
    def get_anime_details(self, season_id: int) -> Optional[Dict]:
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
        
        Args:
            season_id: 番剧 season_id
            
        Returns:
            番剧详细信息字典，请求失败时返回 None
        """
        url = f"https://api.bilibili.com/pgc/view/web/season?season_id={season_id}"
        try:
            response = self._request_get(url, timeout=settings.bilibili_request_timeout)
            if response is None:
                return None
            data = response.json()
            
            if data.get('code') == 0 and 'result' in data:
                result = data['result']
                stat = result.get('stat', {})
                rating = result.get('rating', {})
                publish = result.get('publish', {})
                rights = result.get('rights', {})
                areas = result.get('areas', [])

                return {
                    # ── 向后兼容字段（fetch_and_save_episodes 等调用方使用）──
                    'title': result.get('title'),
                    'cover': result.get('cover'),
                    'stat': stat,
                    'episodes': result.get('episodes', []),
                    # ── 地区 ──────────────────────────────────────────────────
                    'areas': areas,
                    # ── stat 对象展开 ─────────────────────────────────────────
                    'views': stat.get('views'),
                    'favorites': stat.get('favorites'),
                    'total_coins': stat.get('coins'),
                    'total_danmakus': stat.get('danmakus'),
                    'total_likes': stat.get('likes'),
                    'total_reply': stat.get('reply'),
                    'total_share': stat.get('share'),
                    # ── rating 对象 ───────────────────────────────────────────
                    'rating_score': rating.get('score'),
                    'rating_count': rating.get('count'),
                    # ── publish 对象 ──────────────────────────────────────────
                    'is_finish': publish.get('is_finish'),
                    'pub_time': publish.get('pub_time'),
                    # ── rights 对象 ───────────────────────────────────────────
                    'copyright': rights.get('copyright'),
                }
        except Exception:
            logger.exception("❌ 获取番剧详情失败 season_id={}", season_id)
        
        return None

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
        if not details or not details.get('episodes'):
            logger.info(f"❌ 未能获取 season_id={season_id} 的分集数据")
            return False

        episodes = details['episodes']
        logger.info(f"  -> 找到 {len(episodes)} 集，正在写入数据库...")
        saved_count = 0
        has_error = False
        for episode in episodes:
            bvid = episode.get('bvid', '')
            cid = str(episode.get('cid', ''))

            # 【防线 2】利用 API 的 badge / title 字段进行初步过滤
            if not self._is_valid_main_episode(episode):
                ep_title = episode.get('long_title') or episode.get('title')
                logger.info(f"  ⏭️ API字段过滤，跳过非正片: {ep_title}")
                continue

            if not bvid or not cid:
                continue

            ep_title = (
                episode.get('long_title')
                or episode.get('title')
                or f'第{episode.get("index", "")}集'
            )

            # 【网络 I/O 阶段】：无锁，避免长事务持有写入锁
            full_data = self.get_episode_stat_details(bvid)
            stat = full_data.get('stat', {})
            duration = full_data.get('duration', 0)
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

    def get_episode_stat_details(self, bvid: str) -> dict:
        """
        通过 B站 视频详情 API 获取单集完整数据（含统计和时长）。

        Args:
            bvid: 视频 BV 号

        Returns:
            包含 stat（播放量等）和 duration（时长，秒）等字段的完整 data 字典；
            请求失败或数据结构异常时返回空字典
        """
        url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        try:
            response = self._request_get(url, timeout=settings.bilibili_request_timeout)
            if response is None:
                return {}
            data = response.json()
            if data.get('code') == 0:
                # 返回完整 data 字典，以便调用方同时获取 stat 和 duration
                payload = data.get('data')
                if isinstance(payload, dict):
                    return payload
                # 若 data 字段为空或不是字典，则按照约定返回空字典
                return {}
        except Exception as e:
            logger.exception('❌ 获取单集统计详情失败 bvid={}: {}', bvid, e)
        return {}

    @staticmethod
    def _apply_stat_to_episode(ep: "EpisodeStats", stat: dict, ep_title: str) -> None:
        """
        将 stat 字典中的互动指标写入 EpisodeStats 对象

        Args:
            ep: 目标 EpisodeStats 实例
            stat: get_episode_stat_details 返回的统计字典
            ep_title: 集标题
        """
        ep.episode_title = ep_title
        ep.views = stat.get('view')
        ep.danmaku = stat.get('danmaku')
        ep.reply = stat.get('reply')
        ep.favorite = stat.get('favorite')
        ep.coin = stat.get('coin')
        ep.share = stat.get('share')
        ep.like = stat.get('like')
        ep.updated_at = datetime.now()

    def get_online_viewers(self, bvid: str, cid: str) -> Optional[int]:
        """
        获取指定单集的当前在线观看人数

        Args:
            bvid: 视频 BV 号
            cid: 弹幕 CID

        Returns:
            当前在线人数，失败时返回 None
        """
        if not bvid or not cid:
            return None
        url = "https://api.bilibili.com/x/player/online/total"
        params = {'bvid': bvid, 'cid': str(cid)}
        try:
            response = self._request_get(url, params=params, timeout=settings.bilibili_request_timeout)
            if response is None:
                return None
            data = response.json()
            if data.get('code') == 0 and 'data' in data:
                return self._convert_order_to_int(str(data['data'].get('total', 0)))
        except Exception as e:
            logger.exception('❌ 获取在线人数失败 bvid={}: {}', bvid, e)
        return None

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
                    history: Dict[str, int] = json.loads(ep.hourly_online_history) if ep.hourly_online_history else {}
                except (json.JSONDecodeError, TypeError):
                    history = {}
                history[current_hour] = online_count
                ep.hourly_online_history = json.dumps(history, ensure_ascii=False)
                ep.updated_at = datetime.now()
                updated += 1
            self._throttle()  # 严格控制请求频率，防止触发 B站风控

        self.session.commit()
        logger.info(f"✅ 在线人数记录完成，成功更新 {updated}/{len(episodes)} 个剧集")

    def search_bangumi_on_bilibili(self, keyword: str) -> Optional[int]:
        """
        通过关键词在 B站 搜索番剧，返回最匹配的 season_id

        Args:
            keyword: 搜索关键词

        Returns:
            season_id 或 None
        """
        url = "https://api.bilibili.com/x/web-interface/search/type"
        params = {'keyword': keyword, 'search_type': 'media_bangumi'}
        try:
            response = self._request_get(url, params=params, timeout=settings.bilibili_request_timeout)
            if response is None:
                return None
            data = response.json()
            if data.get('code') == 0 and 'data' in data:
                results = data['data'].get('result', [])
                if results:
                    # 取第一个结果的 season_id
                    season_id = results[0].get('season_id')
                    if season_id:
                        return int(season_id)
        except Exception as e:
            logger.exception('❌ B站搜索失败 keyword={}: {}', keyword, e)
        return None

    def fetch_and_save_anime_with_episodes(self, keyword: str) -> Optional[int]:
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
                        title=details.get('title', keyword),
                        cover=details.get('cover'),
                        area='其他',
                        rating=None,
                        styles=json.dumps([], ensure_ascii=False),
                        release_date=None,
                    )
                    self.session.add(new_anime)
                    self.session.commit()  # 立即提交，释放写入锁

            # 添加每日统计快照（使用番剧级别的整体统计）
            anime_stat = details.get('stat', {})
            views = anime_stat.get('views', 0) or 0
            favorites = anime_stat.get('favorites', 0) or 0
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
        episodes = details.get('episodes', [])

        # 步骤 A：提纯 API 权威数据，过滤非正片
        api_valid_episodes = [
            ep for ep in episodes
            if self._is_valid_main_episode(ep) and ep.get('bvid') and ep.get('cid')
        ]

        # 步骤 B：获取本地数据库中该番剧已保存的 bvid 集合
        db_existing_bvids = set(
            self.session.exec(
                select(EpisodeStats.bvid).where(EpisodeStats.season_id == season_id)
            ).all()
        )

        # 步骤 C：计算差集，找出本地缺失的剧集
        missing_episodes = [
            ep for ep in api_valid_episodes if ep.get('bvid') not in db_existing_bvids
        ]

        # 步骤 D：无缺失则跳过，有缺失则补抓
        if not missing_episodes:
            logger.info(f"  ✅ 数据校验通过：本地已完整包含 {len(api_valid_episodes)} 集正片数据，无需修补。")
            return season_id

        logger.info(f"  ⚠️ 触发自动修复：发现本地缺失 {len(missing_episodes)} 集，正在补充抓取...")
        saved_count = 0

        for episode in missing_episodes:
            bvid = episode.get('bvid', '')
            cid = str(episode.get('cid', ''))
            ep_title = episode.get('long_title') or episode.get('title') or f'第{episode.get("index", "")}集'

            # 【网络 I/O 阶段】：无锁，避免长事务持有写入锁
            full_data = self.get_episode_stat_details(bvid)
            stat = full_data.get('stat', {})
            duration = full_data.get('duration', 0)
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

    def update_online_viewers_for_all_episodes(self):
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

    def search_anime_by_title(self, title: str) -> Optional[int]:
        """
        通过标题搜索番剧，返回 season_id
        
        Args:
            title: 番剧标题
            
        Returns:
            season_id 或 None
        """
        anime = self.session.exec(
            select(Anime).where(Anime.title == title)
        ).first()
        
        return anime.season_id if anime else None


    # ──────────────────────────────────────────────────────────────────────────
    # Wbi 签名 (B站新版 API 防爬机制)
    # 参考: https://github.com/SocialSisterYi/bilibili-API-collect/blob/master/docs/misc/sign/wbi.md
    # ──────────────────────────────────────────────────────────────────────────

    # Mixin 密钥混淆表（固定顺序）
    _MIXIN_KEY_ENC_TAB = [
        46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
        27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
        37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
        22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
    ]
    # Wbi 密钥缓存 (img_key, sub_key)
    _wbi_keys_cache: Optional[Tuple[str, str]] = None
    _wbi_keys_fetched_at: Optional[float] = None
    _WBI_CACHE_TTL = 3600  # 缓存 1 小时

    def _get_mixin_key(self, img_key: str, sub_key: str) -> str:
        """根据 img_key 和 sub_key 生成混淆后的 mixin key（取前 32 位）"""
        raw = img_key + sub_key
        return reduce(lambda s, i: s + raw[i], self._MIXIN_KEY_ENC_TAB, '')[:32]

    def _get_wbi_keys(self) -> Tuple[str, str]:
        """
        获取 Wbi 签名所需的 img_key 和 sub_key。
        每小时刷新一次，减少重复请求。
        """
        now = time.time()
        if (
            self._wbi_keys_cache is not None
            and self._wbi_keys_fetched_at is not None
            and now - self._wbi_keys_fetched_at < self._WBI_CACHE_TTL
        ):
            return self._wbi_keys_cache

        url = "https://api.bilibili.com/x/web-interface/nav"
        try:
            resp = self._request_get(url, timeout=settings.bilibili_request_timeout)
            if resp is None:
                return '', ''
            nav = resp.json().get('data', {})
            img_url: str = nav.get('wbi_img', {}).get('img_url', '')
            sub_url: str = nav.get('wbi_img', {}).get('sub_url', '')
            img_key = img_url.rsplit('/', 1)[-1].split('.')[0]
            sub_key = sub_url.rsplit('/', 1)[-1].split('.')[0]
            self.__class__._wbi_keys_cache = (img_key, sub_key)
            self.__class__._wbi_keys_fetched_at = now
            return img_key, sub_key
        except Exception as exc:
            logger.error(
                "❌ 获取 Wbi 密钥失败（后续 API 请求的签名将无效，建议检查网络连接与 Cookie）: {}", exc
            )
            # 降级：返回空字符串，后续签名会失败但不会崩溃
            return '', ''

    def _sign_wbi_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        对请求参数进行 Wbi 签名，自动附加 wts 和 w_rid 字段。

        Args:
            params: 原始请求参数字典

        Returns:
            含有 wts、w_rid 签名字段的新参数字典
        """
        img_key, sub_key = self._get_wbi_keys()
        # 如果获取 Wbi 密钥失败（降级返回空字符串），则跳过签名，避免后续崩溃
        if not img_key or not sub_key:
            logger.warning(
                "⚠️ Wbi 密钥为空，本次请求将不进行 Wbi 签名，直接使用原始参数。"
            )
            return dict(params)
        mixin_key = self._get_mixin_key(img_key, sub_key)
        wts = int(time.time())
        signed = dict(params)
        signed['wts'] = wts
        
        pattern = r'[!#$&+,/:;=?@\\[\\]]'
        
        query = '&'.join(
            f"{k}={re.sub(pattern, '', str(v))}"
            for k, v in sorted(signed.items())
        )
        
        w_rid = hashlib.md5((query + mixin_key).encode()).hexdigest()
        signed['w_rid'] = w_rid
        return signed

    # ──────────────────────────────────────────────────────────────────────────
    # 弹幕抓取（XML 格式，按 cid 拉取）
    # ──────────────────────────────────────────────────────────────────────────

    def _parse_danmaku_xml_payload(
        self,
        *,
        cid: str,
        xml_text: str,
        source: str,
    ) -> List[Dict[str, Any]]:
        """解析弹幕 XML 文本，统一返回标准字段。"""
        danmaku_list: List[Dict[str, Any]] = []
        try:
            root = ET.fromstring(xml_text)
            for d in root.findall('d'):
                attrs = d.get('p', '')
                text = (d.text or '').strip()
                if not text:
                    continue
                # p 属性格式: 时间,类型,大小,颜色,时间戳,弹幕池,用户ID,弹幕ID
                parts = attrs.split(',')
                try:
                    video_time = float(parts[0]) if parts and parts[0] else 0.0
                    ts_unix = int(parts[4]) if len(parts) > 4 and parts[4] else 0
                    sender_hash = parts[6] if len(parts) > 6 else None
                except (TypeError, ValueError):
                    logger.debug("跳过异常弹幕元数据 cid={} source={} attrs={}", cid, source, attrs)
                    continue
                ctime = datetime.fromtimestamp(ts_unix) if ts_unix else None
                danmaku_list.append({
                    'content': text,
                    'video_time': video_time,  # 保持兼容旧字段
                    'progress': video_time,
                    'timestamp': ctime,      # 保持兼容旧字段
                    'ctime': ctime,
                    'sender_hash': sender_hash,  # B站匿名用户哈希
                })
        except ET.ParseError as exc:
            logger.warning("⚠️ 解析弹幕 XML 失败 cid={} source={}: {}", cid, source, exc)
        except Exception as exc:
            logger.exception("❌ 解析弹幕 XML 异常 cid={} source={}: {}", cid, source, exc)
        return danmaku_list

    def _iter_history_months(self, publish_ts: Optional[int]) -> List[str]:
        """根据发布时间推导历史弹幕索引查询月份（倒序，YYYY-MM）。"""
        now = datetime.now()
        max_months = max(1, settings.crawler_history_months)
        cursor = datetime(now.year, now.month, 1)
        start_month: Optional[datetime] = None
        if publish_ts:
            try:
                start_month = datetime.fromtimestamp(int(publish_ts)).replace(day=1)
            except (ValueError, OSError, OverflowError, TypeError):
                logger.warning("⚠️ 非法发布时间戳，改用固定回溯窗口 publish_ts={}", publish_ts)
        months: List[str] = []
        while len(months) < max_months:
            if start_month and cursor < start_month:
                break
            months.append(cursor.strftime("%Y-%m"))
            if cursor.month == 1:
                cursor = datetime(cursor.year - 1, 12, 1)
            else:
                cursor = datetime(cursor.year, cursor.month - 1, 1)
        return months

    @staticmethod
    def _make_danmaku_dedup_key(item: Dict[str, Any]) -> Tuple[str, Any, Any, str]:
        """构造弹幕去重键：(content, video_time, timestamp, sender_hash)。"""
        return (
            str(item.get('content') or ''),
            item.get('video_time'),
            item.get('timestamp'),
            str(item.get('sender_hash') or ''),
        )

    def fetch_danmaku_xml(self, cid: str) -> List[Dict[str, Any]]:
        """
        通过 B站弹幕 XML 接口获取当前弹幕池。

        Args:
            cid: 分 P 的弹幕 ID

        Returns:
            弹幕记录列表。
            其中 progress/ctime/sender_hash 为新字段，video_time/timestamp 为兼容字段。
        """
        url = f"https://comment.bilibili.com/{cid}.xml"
        try:
            resp = self._request_get(url, timeout=settings.bilibili_request_timeout)
            if resp is None:
                return []
            resp.encoding = 'utf-8'
            return self._parse_danmaku_xml_payload(
                cid=cid,
                xml_text=resp.text,
                source="current_pool",
            )
        except Exception as exc:
            logger.exception("❌ 获取当前弹幕失败 cid={}: {}", cid, exc)
        return []

    def fetch_danmaku_history_xml(self, cid: str, *, publish_ts: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        抓取历史弹幕（需要 SESSDATA）。

        通过 history/index 获取可用日期，再逐日抓取 XML。
        """
        if not (settings.bilibili_sessdata or "").strip():
            return []

        index_url = "https://api.bilibili.com/x/v2/dm/history/index"
        history_url = "https://api.bilibili.com/x/v2/dm/history"
        all_dates: List[str] = []

        for month in self._iter_history_months(publish_ts):
            resp = self._request_get(
                index_url,
                params={"type": 1, "oid": str(cid), "month": month},
                timeout=settings.bilibili_request_timeout,
            )
            if resp is None:
                logger.warning("⚠️ 历史弹幕日期索引请求失败 cid={} month={}", cid, month)
                continue
            try:
                payload = resp.json()
            except Exception:
                logger.warning("⚠️ 历史弹幕日期索引解析失败 cid={} month={}", cid, month)
                continue
            code = payload.get("code")
            if code != 0:
                logger.warning(
                    "⚠️ 历史弹幕日期索引返回错误 cid={} month={} code={} message={}",
                    cid,
                    month,
                    code,
                    payload.get("message"),
                )
                # 未登录或权限不足时，无需继续请求更多月份
                if code in self.DM_HISTORY_STOP_CODES:
                    break
                continue
            day_list = payload.get("data") or []
            all_dates.extend([str(d) for d in day_list if d])

        if not all_dates:
            return []

        history_items: List[Dict[str, Any]] = []
        processed_dates: Set[str] = set()
        for date_str in all_dates:
            if date_str in processed_dates:
                continue
            processed_dates.add(date_str)
            resp = self._request_get(
                history_url,
                params={"type": 1, "oid": str(cid), "date": date_str},
                timeout=settings.bilibili_request_timeout,
            )
            if resp is None:
                logger.warning("⚠️ 历史弹幕抓取失败 cid={} date={}", cid, date_str)
                continue
            resp.encoding = "utf-8"
            text = (resp.text or "").strip()
            # 部分失败场景会返回 JSON 错误而不是 XML
            if text.startswith("{"):
                try:
                    err = resp.json()
                    logger.warning(
                        "⚠️ 历史弹幕接口返回错误 cid={} date={} code={} message={}",
                        cid,
                        date_str,
                        err.get("code"),
                        err.get("message"),
                    )
                except Exception:
                    logger.warning("⚠️ 历史弹幕接口返回非 XML 内容 cid={} date={}", cid, date_str)
                continue
            history_items.extend(
                self._parse_danmaku_xml_payload(
                    cid=cid,
                    xml_text=text,
                    source=f"history:{date_str}",
                )
            )
        logger.info("🕰️ 历史弹幕抓取完成 cid={} dates={} items={}", cid, len(processed_dates), len(history_items))
        return history_items

    def fetch_comment_replies(
        self,
        avid: int,
        root_rpid: str,
        *,
        limit: int,
        page_size: int,
    ) -> List[Dict[str, Any]]:
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
        nested: List[Dict[str, Any]] = []
        max_pages = max(1, settings.crawler_nested_reply_pages)
        root_rpid_str = str(root_rpid)
        for page in range(1, max_pages + 1):
            if len(nested) >= limit:
                break
            params = self._sign_wbi_params({
                "type": 1,
                "oid": avid,
                "root": root_rpid_str,
                "ps": page_size,
                "pn": page,
            })
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
                nested.append({
                    "content": content,
                    "likes": r.get("like", 0),
                    "replies": r.get("rcount", 0),
                    "root_rpid": root_rpid_str,
                    "parent_rpid": parent_rpid or root_rpid_str,
                    "level": 1,
                    "is_top_level": False,
                    "rpid": current_rpid,
                })
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
        bvid: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
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
        comment_list: List[Dict[str, Any]] = []
        page = 1
        while len(comment_list) < limit:
            params = self._sign_wbi_params({
                'type': 1,
                'oid': avid,
                'mode': 3,  # 3 = 热门模式（按点赞数排序）
                'ps': page_size,
                'pn': page,
            })
            resp = self._request_get(url, params=params, timeout=settings.bilibili_request_timeout)
            if resp is None:
                logger.warning("⚠️ 评论接口请求失败 bvid={} avid={} page={}", bvid, avid, page)
                break
            data = resp.json()
            if data.get('code') == 0:
                replies = (data.get('data') or {}).get('replies') or []
                if not replies:
                    break
                for r in replies:
                    content = r.get('content', {}).get('message', '').strip()
                    if not content:
                        continue
                    root_rpid = str(r.get("rpid") or "")
                    comment_list.append({
                        'content': content,
                        'likes': r.get('like', 0),
                        'replies': r.get('rcount', 0),
                        'root_rpid': root_rpid,
                        'parent_rpid': None,
                        'level': 0,
                        'is_top_level': True,
                    })
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
                    data.get('code'),
                    data.get('message'),
                )
                break
        return comment_list[:limit]

    @staticmethod
    def _make_comment_dedup_key(comment: Dict[str, Any]) -> Tuple[str, str, str]:
        """构造评论去重键：(root_rpid, parent_rpid, content)。"""
        return (
            str(comment.get("root_rpid") or ""),
            str(comment.get("parent_rpid") or ""),
            str(comment.get("content") or ""),
        )

    def scrape_danmaku_and_comments(
        self,
        season_id: int,
        max_episodes: int = 3,
        comment_limit: int = 50,
        include_comment_replies: bool = True,
        nested_reply_limit: int = 20,
        mode: str = "incremental",
        retry_attempts: Optional[int] = None,
        sentiment_fn: Optional[Any] = None,
    ) -> Dict[str, Any]:
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
            logger.warning(f"  ⚠️ season_id={season_id} 尚无剧集数据，请先执行 fetch_and_save_episodes")
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
                view_data: Dict[str, Any] = {}
                avid: Optional[int] = None
                pubdate_ts: Optional[int] = None
                if ep.bvid:
                    view_data = self.get_episode_stat_details(ep.bvid) or {}
                    avid = view_data.get('aid')
                    pubdate_ts = view_data.get('pubdate')

                # ── 弹幕 ───────────────────────────────────────────────────
                if ep.cid:
                    current_danmaku = self.fetch_danmaku_xml(ep.cid)
                    history_danmaku = self.fetch_danmaku_history_xml(ep.cid, publish_ts=pubdate_ts)
                    raw_danmaku = current_danmaku + history_danmaku

                    # 去重：同一集中仅移除完全重复的弹幕（文本+时间+发送者）
                    seen_keys: Set[Tuple[str, Any, Any, str]] = set()
                    dedup: List[Dict] = []
                    for d in raw_danmaku:
                        # video_time 表示视频内时间点；timestamp 表示发送时间，两者共同用于精确去重。
                        key = self._make_danmaku_dedup_key(d)
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        dedup.append(d)

                    records = []
                    existing_texts = set()
                    if mode != "full":
                        existing_texts = {
                            row[0]
                            for row in self.session.exec(
                                select(DanmuRecord.content).where(
                                    DanmuRecord.season_id == season_id,
                                    DanmuRecord.cid == ep.cid,
                                )
                            ).all()
                        }
                    for d in dedup:
                        if d['content'] in existing_texts:
                            continue
                        score = sentiment_fn(d['content']) if sentiment_fn else None
                        records.append(DanmuRecord(
                            season_id=season_id,
                            episode_number=ep_index,
                            cid=ep.cid,
                            content=d['content'],
                            video_time=d.get('video_time'),
                            timestamp=d.get('timestamp'),
                            sender_hash=d.get('sender_hash'),
                            sentiment_score=score,
                        ))

                    with sqlite_write_lock:
                        for r in records:
                            self.session.add(r)
                        self.session.commit()
                    danmu_saved += len(records)
                    if raw_danmaku and self.mongo_repo.upsert_episode_danmaku(
                        cid=str(ep.cid),
                        season_id=season_id,
                        episode_number=ep_index,
                        bvid=ep.bvid,
                        danmaku_items=raw_danmaku,
                    ):
                        mongo_saved += 1
                    logger.info(
                        "  ✅ 弹幕已写入 episode={} cid={} current={} history={} saved={}",
                        ep_index,
                        ep.cid,
                        len(current_danmaku),
                        len(history_danmaku),
                        len(records),
                    )
                    self._throttle()
                else:
                    logger.warning("  ⚠️ 跳过弹幕抓取：缺少 cid episode={} bvid={}", ep_index, ep.bvid)

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
                    key = self._make_comment_dedup_key(c)
                    if key in existing_comment_keys:
                        continue
                    score = sentiment_fn(c['content']) if sentiment_fn else None
                    c_records.append(CommentRecord(
                        season_id=season_id,
                        avid=avid,
                        root_rpid=c.get('root_rpid'),
                        parent_rpid=c.get('parent_rpid'),
                        level=c.get('level', 0),
                        is_top_level=c.get('is_top_level', True),
                        content=c['content'],
                        likes=c.get('likes', 0),
                        replies=c.get('replies', 0),
                        sentiment_score=score,
                    ))
                with sqlite_write_lock:
                    for r in c_records:
                        self.session.add(r)
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
            from .analytics import update_episode_sentiment_aggregates
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


def create_crawler(session: Session = None) -> BilibiliBangumiCrawler:
    """
    创建爬虫实例的工厂函数
    """
    if session is None:
        from .database import engine
        session = Session(engine)
    
    return BilibiliBangumiCrawler(session)
