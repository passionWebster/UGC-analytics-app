# services/crawler.py
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

from ..models import Anime, DailyStats, EpisodeStats, CrawlLog
from ..database import get_session
from ..config import settings


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
            # 1. 获取国产番剧
            print("\n📊 正在获取国产番剧数据...")
            domestic_animes = self._fetch_domestic_animes()
            
            # 2. 获取常规番剧
            print("\n📊 正在获取常规番剧数据...")
            regular_animes = self._fetch_regular_animes()
            
            # 3. 合并数据
            all_animes = {**domestic_animes, **regular_animes}
            print(f"\n✅ 共获取 {len(all_animes)} 部番剧")
            
            # 4. 存储到数据库
            print("\n💾 正在保存到数据库...")
            self._save_animes_to_db(all_animes)
            
            # 5. 更新爬虫日志
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
                
                animes[season_id] = {
                    'season_id': season_id,
                    'title': item.get('title', ''),
                    'cover': item.get('cover', ''),
                    'area': '国内',
                    'rating': item.get('rating', 0) / 2 if item.get('rating') else None,  # B站评分转为10分制
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
                    
                    animes[season_id] = {
                        'season_id': season_id,
                        'title': item.get('title', ''),
                        'cover': item.get('cover', ''),
                        'area': '其他',
                        'rating': item.get('rating', 0) / 2 if item.get('rating') else None,
                        'styles': [],
                        'release_date': f"{year}-{month:02d}",
                        'views': self._convert_order_to_int(item.get('order', '0')),
                        'favorites': 0
                    }
        
        return animes
    
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
        from ..database import engine
        session = Session(engine)
    
    return BilibiliBangumiCrawler(session)
