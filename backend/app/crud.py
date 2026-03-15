# crud.py
"""
数据分析服务
提供各种数据查询和分析功能
"""
import json
import math
import random
from itertools import combinations
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlmodel import Session, select, func, and_
from sqlalchemy import desc

from .models import Anime, DailyStats, EpisodeStats, Ranking


class AnalyticsService:
    """数据分析服务类"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_all_animes(self, limit: Optional[int] = None, offset: int = 0) -> List[Dict]:
        """
        获取所有番剧列表
        
        Args:
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            番剧列表
        """
        query = select(Anime).offset(offset)
        if limit:
            query = query.limit(limit)
        
        animes = self.session.exec(query).all()
        
        # 获取最新统计数据
        result = []
        for anime in animes:
            latest_stats = self.session.exec(
                select(DailyStats)
                .where(DailyStats.season_id == anime.season_id)
                .order_by(desc(DailyStats.date))
                .limit(1)
            ).first()
            
            result.append({
                'season_id': anime.season_id,
                'title': anime.title,
                'cover': anime.cover,
                'area': anime.area,
                'rating': anime.rating,
                'styles': json.loads(anime.styles) if anime.styles else [],
                'release_date': anime.release_date,
                'views': latest_stats.views if latest_stats else 0,
                'favorites': latest_stats.favorites if latest_stats else 0
            })
        
        return result
    
    def get_anime_by_id(self, season_id: int) -> Optional[Dict]:
        """
        根据 season_id 获取番剧详情
        
        Args:
            season_id: 番剧 ID
            
        Returns:
            番剧详情字典
        """
        anime = self.session.exec(
            select(Anime).where(Anime.season_id == season_id)
        ).first()
        
        if not anime:
            return None
        
        # 获取最新统计
        latest_stats = self.session.exec(
            select(DailyStats)
            .where(DailyStats.season_id == season_id)
            .order_by(desc(DailyStats.date))
            .limit(1)
        ).first()
        
        return {
            'season_id': anime.season_id,
            'title': anime.title,
            'cover': anime.cover,
            'area': anime.area,
            'rating': anime.rating,
            'styles': json.loads(anime.styles) if anime.styles else [],
            'release_date': anime.release_date,
            'views': latest_stats.views if latest_stats else 0,
            'favorites': latest_stats.favorites if latest_stats else 0
        }
    
    def search_anime_by_title(self, keyword: str) -> List[Dict]:
        """
        根据标题关键词搜索番剧
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            匹配的番剧列表
        """
        animes = self.session.exec(
            select(Anime).where(Anime.title.contains(keyword))
        ).all()
        
        result = []
        for anime in animes:
            latest_stats = self.session.exec(
                select(DailyStats)
                .where(DailyStats.season_id == anime.season_id)
                .order_by(desc(DailyStats.date))
                .limit(1)
            ).first()
            
            result.append({
                'season_id': anime.season_id,
                'title': anime.title,
                'cover': anime.cover,
                'area': anime.area,
                'rating': anime.rating,
                'styles': json.loads(anime.styles) if anime.styles else [],
                'release_date': anime.release_date,
                'views': latest_stats.views if latest_stats else 0,
                'favorites': latest_stats.favorites if latest_stats else 0
            })
        
        return result
    
    def get_top_animes(
        self,
        sort_by: str = "views",  # "views", "favorites", "rating"
        limit: int = 10,
        area: Optional[str] = None,
        styles: Optional[List[str]] = None,
        season: Optional[str] = None,  # "spring"(4月), "summer"(7月), "autumn"(10月), "winter"(1月)
    ) -> List[Dict]:
        """
        获取排行榜

        Args:
            sort_by: 排序字段
            limit: 返回数量
            area: 地区筛选
            styles: 风格筛选
            season: 季节筛选（spring/summer/autumn/winter），对应番剧 release_date 月份

        Returns:
            排行榜列表
        """
        # 季节 → 季度首月映射
        SEASON_MONTH_MAP = {
            'spring': '04',
            'summer': '07',
            'autumn': '10',
            'winter': '01',
        }

        # 构建基础查询
        query = select(Anime)

        # 地区筛选
        if area:
            query = query.where(Anime.area == area)

        # 获取所有符合条件的番剧
        animes = self.session.exec(query).all()
        
        # 获取最新统计并应用风格/季节筛选
        result = []
        for anime in animes:
            # 风格筛选
            if styles:
                anime_styles = json.loads(anime.styles) if anime.styles else []
                if not any(style in anime_styles for style in styles):
                    continue

            # 季节筛选：release_date 格式为 "YYYY-MM"，仅保留对应季度首月
            if season and season in SEASON_MONTH_MAP:
                month_suffix = SEASON_MONTH_MAP[season]
                if not (anime.release_date and anime.release_date.endswith(f'-{month_suffix}')):
                    continue
            
            latest_stats = self.session.exec(
                select(DailyStats)
                .where(DailyStats.season_id == anime.season_id)
                .order_by(desc(DailyStats.date))
                .limit(1)
            ).first()
            
            result.append({
                'season_id': anime.season_id,
                'title': anime.title,
                'cover': anime.cover,
                'area': anime.area,
                'rating': anime.rating,
                'styles': json.loads(anime.styles) if anime.styles else [],
                'release_date': anime.release_date,
                'views': latest_stats.views if latest_stats else 0,
                'favorites': latest_stats.favorites if latest_stats else 0
            })
        
        # 排序
        if sort_by == "views":
            result.sort(key=lambda x: x['views'], reverse=True)
        elif sort_by == "favorites":
            result.sort(key=lambda x: x['favorites'], reverse=True)
        elif sort_by == "rating":
            result.sort(key=lambda x: x['rating'] or 0, reverse=True)

        sorted_animes = result

        # 分层随机抽样算法（Tiered Random Sampling）
        if len(sorted_animes) <= limit:
            return sorted_animes

        total = len(sorted_animes)

        # 划分三个梯队
        tier1_size = max(5, math.ceil(total * 0.10))
        tier2_size = max(15, math.ceil(total * 0.20))

        tier1 = sorted_animes[:tier1_size]
        tier2 = sorted_animes[tier1_size:tier1_size + tier2_size]
        tier3 = sorted_animes[tier1_size + tier2_size:]

        # 各梯队抽取数量
        n1 = math.ceil(limit * 0.40)
        n2 = math.ceil(limit * 0.40)
        n3 = limit - n1 - n2

        # 从各梯队随机抽样（不超过各梯队大小）
        sample1 = random.sample(tier1, min(n1, len(tier1)))
        sample2 = random.sample(tier2, min(n2, len(tier2)))
        sample3 = random.sample(tier3, min(n3, len(tier3))) if tier3 else []

        selected = sample1 + sample2 + sample3

        # 若总数不足 limit，从未被选中的剩余数据中顺序补充
        if len(selected) < limit:
            selected_ids = {a['season_id'] for a in selected}
            for anime in sorted_animes:
                if len(selected) >= limit:
                    break
                if anime['season_id'] not in selected_ids:
                    selected.append(anime)
                    selected_ids.add(anime['season_id'])

        # 按 sort_by 字段再次降序排序后返回
        if sort_by == "views":
            selected.sort(key=lambda x: x['views'], reverse=True)
        elif sort_by == "favorites":
            selected.sort(key=lambda x: x['favorites'], reverse=True)
        elif sort_by == "rating":
            selected.sort(key=lambda x: x['rating'] or 0, reverse=True)

        return selected[:limit]
    
    def get_statistics_overview(self) -> Dict[str, Any]:
        """
        获取数据总览统计
        
        Returns:
            统计数据字典
        """
        # 番剧总数
        total_animes = self.session.exec(
            select(func.count(Anime.season_id))
        ).one()
        
        # 获取最新一天的统计数据
        latest_date = self.session.exec(
            select(func.max(DailyStats.date))
        ).one()
        
        if latest_date:
            latest_stats = self.session.exec(
                select(DailyStats).where(DailyStats.date >= latest_date - timedelta(days=1))
            ).all()
            
            total_views = sum(stat.views for stat in latest_stats)
            total_favorites = sum(stat.favorites for stat in latest_stats)
        else:
            total_views = 0
            total_favorites = 0
        
        # 按地区统计
        area_stats = {}
        for area in ['国内', '日本', '美国', '其他']:
            count = self.session.exec(
                select(func.count(Anime.season_id)).where(Anime.area == area)
            ).one()
            area_stats[area] = count
        
        return {
            'total_animes': total_animes,
            'total_views': total_views,
            'total_favorites': total_favorites,
            'area_distribution': area_stats,
            'last_update': latest_date.isoformat() if latest_date else None
        }
    
    def get_anime_history(
        self, 
        season_id: int, 
        days: int = 30
    ) -> List[Dict]:
        """
        获取番剧的历史数据
        
        Args:
            season_id: 番剧 ID
            days: 查询天数
            
        Returns:
            历史数据列表
        """
        start_date = datetime.now() - timedelta(days=days)
        
        stats = self.session.exec(
            select(DailyStats)
            .where(
                and_(
                    DailyStats.season_id == season_id,
                    DailyStats.date >= start_date
                )
            )
            .order_by(DailyStats.date)
        ).all()
        
        return [
            {
                'date': stat.date.isoformat(),
                'views': stat.views,
                'favorites': stat.favorites,
                'online_viewers': stat.online_viewers
            }
            for stat in stats
        ]
    
    def get_style_distribution(self, area: Optional[str] = None) -> Dict[str, int]:
        """
        获取风格分布统计

        Args:
            area: 地区筛选（如 "国内"、"日本"、"美国"），None 表示全部

        Returns:
            风格分布字典
        """
        query = select(Anime)
        if area:
            query = query.where(Anime.area == area)
        animes = self.session.exec(query).all()
        
        style_count = {}
        for anime in animes:
            if anime.styles:
                styles = json.loads(anime.styles)
                for style in styles:
                    style_count[style] = style_count.get(style, 0) + 1
        
        return style_count
    
    def get_release_trend(self, area: Optional[str] = None) -> Dict[str, int]:
        """
        获取发布趋势统计

        Args:
            area: 地区筛选（如 "国内"、"日本"、"美国"），None 表示全部

        Returns:
            按季度统计的发布数量
        """
        query = select(Anime)
        if area:
            query = query.where(Anime.area == area)
        animes = self.session.exec(query).all()
        
        release_count = {}
        for anime in animes:
            if anime.release_date and anime.release_date not in ['敬请期待', '更早']:
                release_count[anime.release_date] = release_count.get(anime.release_date, 0) + 1
        
        return dict(sorted(release_count.items()))

    def get_anime_episodes(self, season_id: int) -> List[Dict]:
        """
        获取番剧的剧集统计数据

        优先从 EpisodeStats 表中返回真实数据；若为空，先实时抓取并入库，
        再次查询后依然为空才以 DailyStats 历史记录作为代理数据返回。

        Args:
            season_id: 番剧 ID

        Returns:
            剧集数据列表，每项包含 title、views、peak_time、peak_online 字段
        """
        from .scraper import BilibiliBangumiCrawler

        # 优先返回真实剧集数据
        episodes = self.session.exec(
            select(EpisodeStats)
            .where(EpisodeStats.season_id == season_id)
            .order_by(EpisodeStats.id)
        ).all()

        if not episodes:
            # 数据库中无分集数据，尝试实时抓取并入库
            crawler = BilibiliBangumiCrawler(self.session)
            crawler.fetch_and_save_episodes(season_id)

            # 抓取完成后再次查询
            episodes = self.session.exec(
                select(EpisodeStats)
                .where(EpisodeStats.season_id == season_id)
                .order_by(EpisodeStats.id)
            ).all()

        if episodes:
            return [
                {
                    'title': ep.episode_title,
                    'views': ep.views or 0,
                    'peakTime': None,
                    'peakOnline': ep.online_viewers,
                }
                for ep in episodes
            ]

        # 回退：使用最近 90 天的每日统计作为剧集代理数据
        stats = self.session.exec(
            select(DailyStats)
            .where(DailyStats.season_id == season_id)
            .order_by(DailyStats.date)
        ).all()

        if not stats:
            return []

        return [
            {
                'title': f'第{i + 1}集',
                'views': stat.views,
                'peakTime': stat.date.strftime('%H:%M') if stat.date else None,
                'peakOnline': stat.online_viewers,
            }
            for i, stat in enumerate(stats)
        ]

    def get_reputation_popularity_chart(self, areas: List[str] = None) -> List[Dict]:
        """
        获取口碑与热度散点图数据

        获取番剧的评分、追番数、播放量和名称，用于绘制散点图。
        为防止数据点重叠，给评分加上微小的随机抖动值。

        Args:
            areas: 地区筛选列表（如 ["国内", "日本"]），None 表示全部

        Returns:
            散点图数据列表，每项包含 title、rating、favorites、views 字段
        """
        query = select(Anime)
        if areas:
            query = query.where(Anime.area.in_(areas))
        animes = self.session.exec(query).all()

        result = []
        for anime in animes:
            if not anime.rating:
                continue

            latest_stats = self.session.exec(
                select(DailyStats)
                .where(DailyStats.season_id == anime.season_id)
                .order_by(desc(DailyStats.date))
                .limit(1)
            ).first()

            favorites = latest_stats.favorites if latest_stats else 0
            views = latest_stats.views if latest_stats else 0

            if not favorites:
                continue

            jitter = random.uniform(-0.05, 0.05)
            result.append({
                'title': anime.title,
                'rating': anime.rating + jitter,
                'ratingRaw': anime.rating,
                'favorites': favorites,
                'views': views,
                'area': anime.area,
            })

        return result

    def get_preference_difference_chart(self, region: str = "国内") -> List[Dict]:
        """
        获取地区偏好差异图数据

        计算特定地区对各风格的偏好指数（地区平均追番数 / 全球平均追番数）。

        Args:
            region: 地区名称（如 "国内"、"日本"），默认 "国内"

        Returns:
            偏好指数列表，每项包含 style、preferenceIndex、regionCount、globalCount 字段
        """
        animes = self.session.exec(select(Anime)).all()

        # 为每部番剧预取最新追番数
        favorites_map: Dict[int, int] = {}
        for anime in animes:
            latest_stats = self.session.exec(
                select(DailyStats)
                .where(DailyStats.season_id == anime.season_id)
                .order_by(desc(DailyStats.date))
                .limit(1)
            ).first()
            favorites_map[anime.season_id] = latest_stats.favorites if latest_stats else 0

        # 统计全局及地区各风格的追番总数与番剧数
        global_style_data: Dict[str, List[int]] = {}
        region_style_data: Dict[str, List[int]] = {}

        for anime in animes:
            if not anime.styles:
                continue
            styles = json.loads(anime.styles)
            fav = favorites_map.get(anime.season_id, 0)
            for style in styles:
                global_style_data.setdefault(style, []).append(fav)
                if anime.area == region:
                    region_style_data.setdefault(style, []).append(fav)

        result = []
        for style, global_favs in global_style_data.items():
            region_favs = region_style_data.get(style, [])
            if len(region_favs) < 3:
                continue
            global_avg = sum(global_favs) / len(global_favs)
            if not global_avg:
                continue
            region_avg = sum(region_favs) / len(region_favs)
            preference_index = region_avg / global_avg
            result.append({
                'style': style,
                'preferenceIndex': round(preference_index, 4),
                'regionCount': len(region_favs),
                'globalCount': len(global_favs),
            })

        result.sort(key=lambda x: x['preferenceIndex'], reverse=True)
        return result

    def get_reputation_heat_index_chart(
        self,
        season: str = None,
        category: str = None,
    ) -> List[Dict]:
        """
        获取口碑热度指数图数据

        计算每部番剧的综合质量分：rating * log10(favorites) * log10(views)，
        返回前 15 名。

        Args:
            season: 季节筛选（spring/summer/autumn/winter）
            category: 风格/类型筛选

        Returns:
            前 15 名番剧列表，每项包含 title、qualityScore、rating、favorites、views 字段
        """
        SEASON_MONTH_MAP = {
            'spring': '04',
            'summer': '07',
            'autumn': '10',
            'winter': '01',
        }

        animes = self.session.exec(select(Anime)).all()

        result = []
        for anime in animes:
            if not anime.rating:
                continue

            # 季节筛选
            if season and season in SEASON_MONTH_MAP:
                month_suffix = SEASON_MONTH_MAP[season]
                if not (anime.release_date and anime.release_date.endswith(f'-{month_suffix}')):
                    continue

            # 风格（类型）筛选
            if category:
                anime_styles = json.loads(anime.styles) if anime.styles else []
                if category not in anime_styles:
                    continue

            latest_stats = self.session.exec(
                select(DailyStats)
                .where(DailyStats.season_id == anime.season_id)
                .order_by(desc(DailyStats.date))
                .limit(1)
            ).first()

            favorites = latest_stats.favorites if latest_stats else 0
            views = latest_stats.views if latest_stats else 0

            if not favorites or not views:
                continue

            quality_score = anime.rating * math.log10(favorites) * math.log10(views)
            result.append({
                'title': anime.title,
                'qualityScore': round(quality_score, 4),
                'rating': anime.rating,
                'favorites': favorites,
                'views': views,
                'area': anime.area,
                'cover': anime.cover,
            })

        result.sort(key=lambda x: x['qualityScore'], reverse=True)
        return result[:15]

    def get_popular_style_combination_chart(self) -> List[Dict]:
        """
        获取热门风格组合图数据

        遍历所有番剧的风格标签，统计所有两两组合的总追番数和包含番剧数，
        过滤掉番剧数 < 5 的组合，按平均追番数倒序，返回前 20 个组合及代表番剧。

        Returns:
            前 20 个风格组合列表，每项包含 combination、totalFavorites、animeCount、
            avgFavorites、representativeAnimes 字段
        """
        animes = self.session.exec(select(Anime)).all()

        combo_data: Dict[str, Dict] = {}

        for anime in animes:
            if not anime.styles:
                continue
            styles = json.loads(anime.styles)
            if len(styles) < 2:
                continue

            latest_stats = self.session.exec(
                select(DailyStats)
                .where(DailyStats.season_id == anime.season_id)
                .order_by(desc(DailyStats.date))
                .limit(1)
            ).first()
            fav = latest_stats.favorites if latest_stats else 0

            for s1, s2 in combinations(sorted(styles), 2):
                key = f"{s1} + {s2}"
                if key not in combo_data:
                    combo_data[key] = {'totalFavorites': 0, 'animes': []}
                combo_data[key]['totalFavorites'] += fav
                combo_data[key]['animes'].append(anime.title)

        result = []
        for combo, data in combo_data.items():
            anime_count = len(data['animes'])
            if anime_count < 5:
                continue
            avg_favorites = data['totalFavorites'] / anime_count
            result.append({
                'combination': combo,
                'totalFavorites': data['totalFavorites'],
                'animeCount': anime_count,
                'avgFavorites': round(avg_favorites, 2),
                'representativeAnimes': data['animes'][:5],
            })

        result.sort(key=lambda x: x['avgFavorites'], reverse=True)
        return result[:20]
