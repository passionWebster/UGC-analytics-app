# crud.py
"""
数据分析服务
提供各种数据查询和分析功能
"""
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
            
            import json
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
        
        import json
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
            
            import json
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
                import json
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
            
            import json
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
        
        return result[:limit]
    
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
        import json
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

        优先从 EpisodeStats 表中返回真实数据；若为空，则以 DailyStats 历史记录
        作为代理，模拟剧集数据供图表展示。

        Args:
            season_id: 番剧 ID

        Returns:
            剧集数据列表，每项包含 title、views、peak_time、peak_online 字段
        """
        # 优先返回真实剧集数据
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
