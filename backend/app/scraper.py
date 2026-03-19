# scraper.py
"""
B站数据爬虫服务 - 重构版
将原 scraper.py 和 data_manager.py 的功能整合，数据直接写入 SQLite 数据库
"""
import json
import re
import time
from datetime import datetime, timedelta
from typing import Tuple, List, Dict, Any, Optional
import requests
from sqlmodel import Session, select
from tqdm import tqdm

from .models import Anime, DailyStats, EpisodeStats, CrawlLog
from .database import get_session
from .config import settings


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
        print(f"✅ 爬虫已初始化")
    
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
                response = self.http_session.get(
                    self.BASE_API_URL,
                    params=current_params,
                    timeout=settings.bilibili_request_timeout
                )
                response.raise_for_status()
                data = response.json()
                
                if data.get('code') == 0 and 'data' in data:
                    api_data = data['data']
                    page_list = api_data.get('list', [])
                    all_items.extend(page_list)
                    
                    if not api_data.get('has_next', 0):
                        break
                    
                    time.sleep(settings.bilibili_request_delay)
                else:
                    print(f"  ❌ API 返回错误: {data.get('message', '未知错误')}")
                    break
            except Exception as e:
                print(f"  ❌ 请求失败: {e}")
                break
        
        return all_items
    
    def update_anime_database(self) -> bool:
        """
        更新番剧数据库
        从 B站 API 抓取数据并存储到数据库
        
        Returns:
            成功返回 True，失败返回 False
        """
        print("🚀 [任务开始] 更新番剧数据库")
        
        # 创建爬虫日志
        crawl_log = CrawlLog(
            task_type="full_update",
            status="running",
            started_at=datetime.now()
        )
        self.session.add(crawl_log)
        self.session.commit()
        
        try:
            # 1. 底库构建：获取国产番剧和常规番剧基础信息
            print("\n📊 正在获取国产番剧数据...")
            domestic_animes = self._fetch_domestic_animes()
            
            print("\n📊 正在获取常规番剧数据...")
            regular_animes = self._fetch_regular_animes()
            
            all_animes = {**domestic_animes, **regular_animes}
            print(f"\n✅ 底库构建完成，共获取 {len(all_animes)} 部番剧")
            
            # 2. 补充地区信息：按地区再次请求，更新底库中非国产番剧的地区字段
            print("\n🌍 正在补充地区信息...")
            all_animes = self._enrich_area(all_animes)
            
            # 3. 补充风格信息：遍历风格ID，将匹配的风格追加到底库
            print("\n🎨 正在补充风格信息（常规番剧）...")
            all_animes = self._enrich_regular_styles(all_animes)
            
            print("\n🎨 正在补充风格信息（国产番剧）...")
            all_animes = self._enrich_domestic_styles(all_animes)
            
            # 4. 补充播放量和追番量：使用 order=2/3 重新请求，覆盖底库数据
            print("\n📈 正在补充播放量和追番量数据...")
            all_animes = self._enrich_views_and_favorites(all_animes)
            
            # 5. 入库存储
            print("\n💾 正在保存到数据库...")
            self._save_animes_to_db(all_animes)
            
            # 更新爬虫日志
            crawl_log.status = "success"
            crawl_log.items_count = len(all_animes)
            crawl_log.completed_at = datetime.now()
            self.session.commit()
            
            print(f"\n🎉 数据库更新成功！共保存 {len(all_animes)} 部番剧")
            return True
            
        except Exception as e:
            print(f"\n❌ 更新失败: {e}")
            crawl_log.status = "failed"
            crawl_log.error_message = str(e)
            crawl_log.completed_at = datetime.now()
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
            print(f"  获取 {year} 年国产番剧: {len(items)} 部")
            
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
                    'favorites': 0
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
                print(f"  获取 {year}-{month:02d} 常规番剧: {len(items)} 部")
                
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
                        'favorites': 0
                    }
        
        return animes
    
    def _fetch_regular_by_area(self, area: int) -> List[Dict[str, Any]]:
        """获取指定地区的常规番剧列表 (area=2 日本, area=3 美国)"""
        print(f"  获取地区 {area} 常规番剧...")
        params = {
            'st': 1, 'order': 2, 'season_version': -1,
            'spoken_language_type': -1, 'area': area, 'is_finish': -1,
            'copyright': -1, 'season_status': -1, 'season_month': -1,
            'year': '-1', 'style_id': -1, 'sort': 0,
            'season_type': 1, 'type': 1
        }
        return self._fetch_api_data(params)

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

    def _fetch_regular_ranking(self, order: int) -> List[Dict[str, Any]]:
        """获取常规番剧全量排名数据 (order=2 播放量, order=3 追番量)"""
        params = {
            'st': 1, 'order': order, 'season_version': -1,
            'spoken_language_type': -1, 'area': -1, 'is_finish': -1,
            'copyright': -1, 'season_status': -1, 'season_month': -1,
            'year': '-1', 'style_id': -1, 'sort': 0,
            'season_type': 1, 'type': 1
        }
        return self._fetch_api_data(params)

    def _fetch_domestic_ranking(self, order: int) -> List[Dict[str, Any]]:
        """获取国产番剧全量排名数据 (order=2 播放量, order=3 追番量)"""
        params = {
            'season_version': -1, 'is_finish': -1, 'copyright': -1, 'season_status': -1,
            'year': '-1', 'style_id': -1, 'order': order, 'st': 4, 'sort': 0,
            'season_type': 4, 'type': 1
        }
        return self._fetch_api_data(params)

    def _enrich_area(self, all_animes: Dict[int, Dict]) -> Dict[int, Dict]:
        """
        补充地区信息：对非国产番剧，通过 area=2(日本) 和 area=3(美国) 的 API 请求更新地区字段
        """
        japan_items = self._fetch_regular_by_area(area=2)
        usa_items = self._fetch_regular_by_area(area=3)

        japan_ids = {item.get('season_id') for item in japan_items if item.get('season_id')}
        usa_ids = {item.get('season_id') for item in usa_items if item.get('season_id')}

        for season_id, item in all_animes.items():
            if item['area'] == '国内':
                continue
            if season_id in japan_ids:
                item['area'] = '日本'
            elif season_id in usa_ids:
                item['area'] = '美国'

        print(f"  ✅ 地区标记完成：日本 {len(japan_ids)} 部，美国 {len(usa_ids)} 部")
        return all_animes

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

    def _enrich_views_and_favorites(self, all_animes: Dict[int, Dict]) -> Dict[int, Dict]:
        """
        补充播放量和追番量：使用 order=2(播放量) 和 order=3(追番量) 重新请求，覆盖底库数据
        """
        print("  获取播放量数据 (order=2)...")
        views_items = self._fetch_regular_ranking(2) + self._fetch_domestic_ranking(2)

        print("  获取追番量数据 (order=3)...")
        favorites_items = self._fetch_regular_ranking(3) + self._fetch_domestic_ranking(3)

        views_map = {
            item['season_id']: self._convert_order_to_int(item.get('order', '0'))
            for item in views_items if item.get('season_id')
        }
        favorites_map = {
            item['season_id']: self._convert_order_to_int(item.get('order', '0'))
            for item in favorites_items if item.get('season_id')
        }

        for season_id, item in all_animes.items():
            item['views'] = views_map.get(season_id, item.get('views', 0))
            item['favorites'] = favorites_map.get(season_id, 0)

        print(f"  ✅ 播放量/追番量补充完成")
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
                existing_anime.updated_at = datetime.now()
            else:
                # 创建新记录
                new_anime = Anime(
                    season_id=season_id,
                    title=anime_data['title'],
                    cover=anime_data['cover'],
                    area=anime_data['area'],
                    rating=anime_data['rating'],
                    styles=json.dumps(anime_data['styles'], ensure_ascii=False),
                    release_date=anime_data['release_date']
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
        print(f"✅ 已保存 {len(animes)} 部番剧到数据库")
    
    def get_anime_details(self, season_id: int) -> Optional[Dict]:
        """
        获取番剧详细信息
        
        Args:
            season_id: 番剧 season_id
            
        Returns:
            番剧详细信息字典
        """
        url = f"https://api.bilibili.com/pgc/view/web/season?season_id={season_id}"
        try:
            response = self.http_session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') == 0 and 'result' in data:
                result = data['result']
                return {
                    'title': result.get('title'),
                    'cover': result.get('cover'),
                    'stat': result.get('stat', {}),
                    'episodes': result.get('episodes', [])
                }
        except Exception as e:
            print(f"❌ 获取番剧详情失败: {e}")
        
        return None

    def fetch_and_save_episodes(self, season_id: int) -> bool:
        """
        通过 B站 API 抓取指定番剧的分集信息并存入数据库，包含完整互动统计数据

        Args:
            season_id: 番剧 season_id

        Returns:
            B站 API 成功返回分集数据则返回 True，否则返回 False
        """
        print(f"🔍 正在从 B站 抓取 season_id={season_id} 的分集数据...")
        details = self.get_anime_details(season_id)
        if not details or not details.get('episodes'):
            print(f"❌ 未能获取 season_id={season_id} 的分集数据")
            return False

        episodes = details['episodes']
        print(f"  -> 找到 {len(episodes)} 集，正在写入数据库...")
        try:
            saved_count = 0
            for episode in episodes:
                bvid = episode.get('bvid', '')
                cid = str(episode.get('cid', ''))
                if not bvid or not cid:
                    continue

                ep_title = (
                    episode.get('long_title')
                    or episode.get('title')
                    or f'第{episode.get("index", "")}集'
                )

                # 获取完整统计数据（播放量、弹幕、评论、收藏、投币、分享、点赞）
                stat = self.get_episode_stat_details(bvid)
                time.sleep(settings.bilibili_request_delay)

                existing_ep = self.session.exec(
                    select(EpisodeStats).where(EpisodeStats.bvid == bvid)
                ).first()

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
                    saved_count += 1

            self.session.commit()
            print(f"  ✅ 已写入 {saved_count} 条分集记录 (season_id={season_id})")
            return True
        except Exception as e:
            print(f"❌ 写入分集数据失败: {e}")
            self.session.rollback()
            return False

    def get_episode_stat_details(self, bvid: str) -> dict:
        """
        通过 B站 视频详情 API 获取单集完整统计数据

        Args:
            bvid: 视频 BV 号

        Returns:
            包含 view/danmaku/reply/favorite/coin/share/like 等字段的 stat 字典；
            请求失败或数据结构异常时返回空字典
        """
        url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        try:
            response = self.http_session.get(url, timeout=settings.bilibili_request_timeout)
            response.raise_for_status()
            data = response.json()
            if data.get('code') == 0:
                return data.get('data', {}).get('stat', {})
        except Exception as e:
            print(f"❌ 获取单集统计详情失败 bvid={bvid}: {e}")
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
            response = self.http_session.get(url, params=params, timeout=settings.bilibili_request_timeout)
            response.raise_for_status()
            data = response.json()
            if data.get('code') == 0 and 'data' in data:
                return self._convert_order_to_int(str(data['data'].get('total', 0)))
        except Exception as e:
            print(f"❌ 获取在线人数失败 bvid={bvid}: {e}")
        return None

    def record_hourly_online_viewers(self) -> None:
        """
        获取所有剧集的当前在线人数，并将结果按当前小时写入 hourly_online_history 列。
        建议由调度器每小时的第 5 分钟触发，避开整点网络拥堵。
        """
        print("🔄 [定时任务] 开始记录剧集每小时在线人数...")
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
            time.sleep(0.5)  # 严格控制请求频率，防止触发 B站风控

        self.session.commit()
        print(f"✅ 在线人数记录完成，成功更新 {updated}/{len(episodes)} 个剧集")

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
            response = self.http_session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data.get('code') == 0 and 'data' in data:
                results = data['data'].get('result', [])
                if results:
                    # 取第一个结果的 season_id
                    season_id = results[0].get('season_id')
                    if season_id:
                        return int(season_id)
        except Exception as e:
            print(f"❌ B站搜索失败 keyword={keyword}: {e}")
        return None

    def fetch_and_save_anime_with_episodes(self, keyword: str) -> Optional[int]:
        """
        通过关键词搜索番剧，抓取详情后将 Anime 信息和所有分集（含完整统计）写入数据库

        Args:
            keyword: 搜索关键词

        Returns:
            成功时返回 season_id，失败时返回 None
        """
        print(f"🔍 正在搜索番剧: {keyword}")
        season_id = self.search_bangumi_on_bilibili(keyword)
        if not season_id:
            print(f"❌ 未能通过 B站 API 找到番剧: {keyword}")
            return None

        print(f"  -> 找到 season_id={season_id}，正在获取详情...")
        details = self.get_anime_details(season_id)
        if not details:
            print(f"❌ 获取番剧详情失败: season_id={season_id}")
            return None

        # 保存或更新 Anime 基础信息
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
            self.session.flush()

            # 添加每日统计快照（使用番剧级别的整体统计）
            anime_stat = details.get('stat', {})
            views = anime_stat.get('views', 0) or 0
            favorites = anime_stat.get('favorites', 0) or 0
            daily_stat = DailyStats(
                season_id=season_id,
                date=datetime.now(),
                views=views,
                favorites=favorites,
            )
            self.session.add(daily_stat)
            print(f"  ✅ 已新增番剧: {details.get('title')} (season_id={season_id})")
        else:
            print(f"  ℹ️  番剧已存在: {existing_anime.title} (season_id={season_id})")

        # 写入/更新 EpisodeStats（含完整互动统计）
        episodes = details.get('episodes', [])
        print(f"  -> 正在写入 {len(episodes)} 集数据到 EpisodeStats...")
        saved_count = 0
        for episode in episodes:
            bvid = episode.get('bvid', '')
            cid = str(episode.get('cid', ''))
            if not bvid or not cid:
                continue

            ep_title = episode.get('long_title') or episode.get('title') or f'第{episode.get("index", "")}集'

            # 使用统一辅助方法获取完整单集统计
            stat = self.get_episode_stat_details(bvid)
            time.sleep(settings.bilibili_request_delay)

            existing_ep = self.session.exec(
                select(EpisodeStats).where(EpisodeStats.bvid == bvid)
            ).first()

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
                saved_count += 1

        self.session.commit()
        print(f"  ✅ 已写入 {saved_count} 条新剧集记录 (season_id={season_id})")
        return season_id

    def update_online_viewers_for_all_episodes(self):
        """
        遍历 EpisodeStats 表中所有记录，通过 B站 API 刷新在线观看人数
        """
        print("🔄 [定时任务] 开始刷新所有剧集在线人数...")
        episodes = self.session.exec(select(EpisodeStats)).all()
        if not episodes:
            print("  ℹ️  EpisodeStats 表为空，跳过更新")
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
        print(f"  ✅ 在线人数刷新完成，共更新 {updated}/{len(episodes)} 条记录")

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


def create_crawler(session: Session = None) -> BilibiliBangumiCrawler:
    """
    创建爬虫实例的工厂函数
    """
    if session is None:
        from .database import engine
        session = Session(engine)
    
    return BilibiliBangumiCrawler(session)
