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

from .models import Anime, DailyStats, EpisodeStats, Ranking, TmdbAnimeInfo, RecommendationStrategyConfig


class AnalyticsService:
    """数据分析服务类"""
    
    def __init__(self, session: Session):
        self.session = session

    def _get_recommendation_strategy(self) -> Dict[str, Any]:
        """获取推荐策略配置；无配置时返回默认值。"""
        strategy = self.session.exec(
            select(RecommendationStrategyConfig).order_by(desc(RecommendationStrategyConfig.updated_at)).limit(1)
        ).first()
        if not strategy:
            return {
                "enabled": False,
                "views_weight": 0.35,
                "ai_weight": 0.35,
                "tmdb_weight": 0.2,
                "diversity_weight": 0.1,
            }
        return {
            "enabled": strategy.enabled,
            "views_weight": strategy.views_weight,
            "ai_weight": strategy.ai_weight,
            "tmdb_weight": strategy.tmdb_weight,
            "diversity_weight": strategy.diversity_weight,
        }

    def _build_recommendation_items(
        self,
        user_prefs_set: set[str],
        animes: List[Anime],
        target_season_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """构建推荐结果（未截断）。"""
        global_combo_counts: Dict[str, int] = {}
        strategy = self._get_recommendation_strategy()
        weight_sum = (
            strategy["views_weight"]
            + strategy["ai_weight"]
            + strategy["tmdb_weight"]
            + strategy["diversity_weight"]
        ) or 1.0

        for anime in animes:
            if not anime.styles:
                continue
            styles = json.loads(anime.styles)
            for s1, s2 in combinations(sorted(styles), 2):
                key = f"{s1}+{s2}"
                global_combo_counts[key] = global_combo_counts.get(key, 0) + 1

        max_combo_count = max(global_combo_counts.values(), default=1)
        recommendations: List[Dict[str, Any]] = []
        season_ids = list({anime.season_id for anime in animes if anime.season_id is not None})
        latest_stats_by_season: Dict[int, DailyStats] = {}
        if season_ids:
            latest_dates_subquery = (
                select(
                    DailyStats.season_id.label("season_id"),
                    func.max(DailyStats.date).label("max_date"),
                )
                .where(DailyStats.season_id.in_(season_ids))
                .group_by(DailyStats.season_id)
            ).subquery()
            latest_stats_rows = self.session.exec(
                select(DailyStats).join(
                    latest_dates_subquery,
                    and_(
                        DailyStats.season_id == latest_dates_subquery.c.season_id,
                        DailyStats.date == latest_dates_subquery.c.max_date,
                    ),
                )
            ).all()
            latest_stats_by_season = {
                stats.season_id: stats
                for stats in latest_stats_rows
                if stats.season_id is not None
            }

        for anime in animes:
            latest_stats = latest_stats_by_season.get(anime.season_id)
            views = latest_stats.views if latest_stats else 0
            favorites = latest_stats.favorites if latest_stats else 0
            anime_styles = set(json.loads(anime.styles)) if anime.styles else set()
            jaccard = 0.0
            combo_bonus = 0.0
            ai_signal = 0.0
            diversity_signal = 0.0

            popularity_signal = min(
                1.0,
                (favorites / 1_000_000 * 0.5) + (views / 10_000_000 * 0.5)
            )
            tmdb_signal = min(1.0, max(0.0, (anime.rating or 0.0) / 10.0))

            if not user_prefs_set:
                pass
            else:
                intersection = len(user_prefs_set & anime_styles)
                union = len(user_prefs_set | anime_styles)
                jaccard = intersection / union if union else 0.0

                raw_combo_bonus = 0.0
                user_style_list = sorted(user_prefs_set)
                for s1, s2 in combinations(user_style_list, 2):
                    key = f"{s1}+{s2}"
                    if key in global_combo_counts:
                        raw_combo_bonus += global_combo_counts[key] / max_combo_count
                combo_bonus = min(1.0, raw_combo_bonus)
                ai_signal = min(1.0, jaccard * 0.8 + combo_bonus * 0.2)
                diversity_signal = 1.0 - jaccard

            if strategy["enabled"]:
                score_0_1 = (
                    strategy["views_weight"] * popularity_signal
                    + strategy["ai_weight"] * ai_signal
                    + strategy["tmdb_weight"] * tmdb_signal
                    + strategy["diversity_weight"] * diversity_signal
                ) / weight_sum
                match_score = min(100.0, max(0.0, score_0_1 * 100.0))
                reasoning = (
                    f"策略加权(views/ai/tmdb/diversity)="
                    f"{strategy['views_weight']:.2f}/{strategy['ai_weight']:.2f}/"
                    f"{strategy['tmdb_weight']:.2f}/{strategy['diversity_weight']:.2f}"
                )
            else:
                if not user_prefs_set:
                    match_score = min(
                        100.0,
                        (favorites / 1_000_000 * 50) + (views / 10_000_000 * 50)
                    )
                    reasoning = "用户未设置偏好，按全站热度推荐"
                else:
                    match_score = min(100.0, jaccard * 80.0 + combo_bonus * 20.0)
                    reasoning = (
                        f"匹配风格 {len(user_prefs_set & anime_styles)} 个，"
                        f"Jaccard={jaccard:.2f}，组合奖励={combo_bonus:.2f}"
                    )

            explainability = {
                'jaccard_similarity': round(jaccard, 4),
                'combo_bonus_score': round(combo_bonus, 4),
                'reasoning': reasoning,
                'strategy_enabled': strategy["enabled"],
                'strategy_weights': {
                    'views_weight': strategy["views_weight"],
                    'ai_weight': strategy["ai_weight"],
                    'tmdb_weight': strategy["tmdb_weight"],
                    'diversity_weight': strategy["diversity_weight"],
                },
                'component_scores': {
                    'views_signal': round(popularity_signal, 4),
                    'ai_signal': round(ai_signal, 4),
                    'tmdb_signal': round(tmdb_signal, 4),
                    'diversity_signal': round(diversity_signal, 4),
                },
            }

            item = {
                'season_id': anime.season_id,
                'title': anime.title,
                'cover': anime.cover,
                'area': anime.area,
                'rating': anime.rating,
                'styles': sorted(anime_styles),
                'release_date': anime.release_date or '',
                'match_score': round(match_score, 2),
                'views': views,
                'favorites': favorites,
                'explainability': explainability,
            }
            if target_season_id is None or anime.season_id == target_season_id:
                recommendations.append(item)

        if target_season_id is None:
            recommendations.sort(key=lambda x: (x['match_score'], x['favorites']), reverse=True)
        return recommendations
    
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
        根据 season_id 获取番剧详情，同时携带 TMDB 补充信息。

        通过对 TmdbAnimeInfo 表执行左连接，若存在对应的 TMDB 记录，
        则在返回字典中嵌套 tmdb_info 字段；否则 tmdb_info 为 None。

        Args:
            season_id: 番剧 ID

        Returns:
            番剧详情字典，包含可选的 tmdb_info 嵌套字段
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

        # 查询关联的 TMDB 补充数据（左连接效果：未命中时为 None）
        tmdb_info = self.session.exec(
            select(TmdbAnimeInfo).where(TmdbAnimeInfo.season_id == season_id)
        ).first()

        result = {
            'season_id': anime.season_id,
            'title': anime.title,
            'cover': anime.cover,
            'area': anime.area,
            'rating': anime.rating,
            'styles': json.loads(anime.styles) if anime.styles else [],
            'release_date': anime.release_date,
            'views': latest_stats.views if latest_stats else 0,
            'favorites': latest_stats.favorites if latest_stats else 0,
            'tmdb_info': None,
        }

        # 若存在 TMDB 补充记录，则嵌套序列化后写入返回结果
        if tmdb_info:
            result['tmdb_info'] = {
                'tmdb_id': tmdb_info.tmdb_id,
                'original_name': tmdb_info.original_name,
                'overview': tmdb_info.overview,
                'tmdb_rating': tmdb_info.tmdb_rating,
                'backdrop_url': tmdb_info.backdrop_url,
                'logo_url': tmdb_info.logo_url,
                'poster_url': tmdb_info.poster_url,
                'genres': json.loads(tmdb_info.genres) if tmdb_info.genres else [],
                'first_air_date': tmdb_info.first_air_date,
            }

        return result
    
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
                    'cid': ep.cid,
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

    def get_watch_time_distribution(self, season_id: int) -> Dict[str, Any]:
        """
        获取番剧的 24 小时观看时间分布（真实数据）。

        从 EpisodeStats 表读取 hourly_online_history 列，
        将 JSON 字典格式化为长度为 24 的整数数组（缺失小时填 0）。

        Args:
            season_id: 番剧 ID

        Returns:
            包含 season_id 和 episodes_data 列表的字典；
            episodes_data 每项含 episode_title 和 distribution（长度24数组）
        """
        episodes = self.session.exec(
            select(EpisodeStats)
            .where(EpisodeStats.season_id == season_id)
            .order_by(EpisodeStats.id)
        ).all()

        result = []
        has_non_empty_history = False
        for ep in episodes:
            try:
                history_dict: Dict[str, int] = json.loads(ep.hourly_online_history) if ep.hourly_online_history else {}
            except (json.JSONDecodeError, TypeError):
                history_dict = {}

            if history_dict:
                has_non_empty_history = True

            # 将 {"14": 150, "15": 200} 转换为长度 24 的数组，缺失小时填 0
            distribution = [history_dict.get(f"{hour:02d}", 0) for hour in range(24)]
            result.append({
                "episode_title": ep.episode_title,
                "distribution": distribution,
            })

        if not has_non_empty_history:
            result = []

        return {
            "season_id": season_id,
            "episodes_data": result,
        }

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

        计算每部番剧的综合质量分，融入最新添加的互动指标与评分人数，增强区分度。

        Args:
            season: 季节筛选（spring/summer/autumn/winter）
            category: 风格/类型筛选

        Returns:
            前 15 名番剧列表
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

            # 获取新加入的互动与评分数据，容错处理
            rating_count = anime.rating_count or 1
            coins = anime.total_coins or 0
            likes = anime.total_likes or 0
            danmakus = anime.total_danmakus or 0
            reply = anime.total_reply or 0

            # 1. 基础热度 (Base Heat)
            # 使用加权对数和，避免单纯连乘导致的严重数值压缩
            base_heat = (math.log10(views) * 0.4) + (math.log10(favorites) * 0.6)

            # 2. 深度互动热度 (Interactive Heat) - 核心区分点
            # 引入投币、点赞、弹幕、评论，赋予硬通货（投币、点赞）更高权重
            interaction_heat = (
                    (math.log10(coins + 1) * 0.35) +
                    (math.log10(likes + 1) * 0.25) +
                    (math.log10(danmakus + 1) * 0.20) +
                    (math.log10(reply + 1) * 0.20)
            )

            # 3. 口碑质量与置信度 (Reputation & Confidence)
            # - 使用 rating 的平方来非线性放大高分番的优势 (例如 9.8的平方是96，8.0的平方是64)
            # - 引入 rating_count (评分人数) 作为置信度权重，过滤少数人打高分的偏差
            confidence = math.log10(rating_count + 1)
            reputation_score = (anime.rating ** 2) * confidence

            # 最终综合质量分：口碑置信度 驱动 整体综合热度
            quality_score = reputation_score * (base_heat + interaction_heat)

            result.append({
                'title': anime.title,
                'qualityScore': round(quality_score, 2),  # 分数区间将被拉大至数千至上万分
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

            # 保存完整番剧信息供下钻详情面板使用
            anime_info = {
                'title': anime.title,
                'cover': anime.cover or '',
                'season_id': anime.season_id,
                'score': anime.rating,
                'favorites': fav,
            }

            for s1, s2 in combinations(sorted(styles), 2):
                key = f"{s1} + {s2}"
                if key not in combo_data:
                    combo_data[key] = {'totalFavorites': 0, 'animes': []}
                combo_data[key]['totalFavorites'] += fav
                combo_data[key]['animes'].append(anime_info)

        result = []
        for combo, data in combo_data.items():
            anime_count = len(data['animes'])
            if anime_count < 5:
                continue
            avg_favorites = data['totalFavorites'] / anime_count
            # 代表番剧按追番数降序取前 8 部
            top_animes = sorted(data['animes'], key=lambda a: a['favorites'], reverse=True)
            result.append({
                'combination': combo,
                'totalFavorites': data['totalFavorites'],
                'animeCount': anime_count,
                'avgFavorites': round(avg_favorites, 2),
                'representativeAnimes': top_animes[:8],
            })

        result.sort(key=lambda x: x['avgFavorites'], reverse=True)
        return result[:20]

    # ─────────────────────────────────────────────────────────────
    # 1. 单集受众行为分析（Episode-Level Audience Behavior Analysis）
    # ─────────────────────────────────────────────────────────────

    def get_episode_behavior_analysis(self, season_id: int) -> Optional[Dict]:
        """
        单集受众行为分析：留存率、硬核指数与弹幕评论密度。

        留存率以第1集播放量为基准，比较第3集和最终集的播放量占比，
        用以衡量观众粘性。硬核指数（coin_rate / like_rate）反映内容质量，
        弹幕评论密度（danmaku_rate / reply_rate）衡量受众共鸣程度。

        Args:
            season_id: 番剧 season_id

        Returns:
            包含留存率、各集互动指数及全剧平均指标的字典；无数据时返回 None
        """
        episodes = self.session.exec(
            select(EpisodeStats)
            .where(EpisodeStats.season_id == season_id)
            .order_by(EpisodeStats.id)
        ).all()

        if not episodes:
            return None

        total = len(episodes)

        # 留存率计算
        ep1_views = episodes[0].views or 0
        ep3_views = episodes[2].views if total >= 3 and episodes[2].views is not None else None
        final_views = (
            episodes[-1].views
            if total > 1 and episodes[-1].views is not None
            else None
        )

        def _retention(base: int, target: Optional[int]) -> Optional[float]:
            """计算留存率百分比"""
            if target is None or base == 0:
                return None
            return round(target / base * 100, 2)

        # 各集指标
        engagement_list = []
        for ep in episodes:
            v = ep.views or 0
            engagement_list.append({
                'episode_title': ep.episode_title,
                'views': v,
                'coin_rate': round(ep.coin / v, 6) if v and ep.coin is not None else None,
                'like_rate': round(ep.like / v, 6) if v and ep.like is not None else None,
                'danmaku_rate': round(ep.danmaku / v, 6) if v and ep.danmaku is not None else None,
                'reply_rate': round(ep.reply / v, 6) if v and ep.reply is not None else None,
            })

        def _safe_avg(values: List[Optional[float]]) -> Optional[float]:
            """过滤 None 后求平均"""
            filtered = [x for x in values if x is not None]
            return round(sum(filtered) / len(filtered), 6) if filtered else None

        return {
            'season_id': season_id,
            'total_episodes': total,
            'retention': {
                'episode_1_views': ep1_views,
                'episode_3_views': ep3_views,
                'final_episode_views': final_views,
                'retention_ep1_to_ep3': _retention(ep1_views, ep3_views),
                'retention_ep1_to_final': _retention(ep1_views, final_views),
            },
            'engagement_by_episode': engagement_list,
            'avg_coin_rate': _safe_avg([e['coin_rate'] for e in engagement_list]),
            'avg_like_rate': _safe_avg([e['like_rate'] for e in engagement_list]),
            'avg_danmaku_rate': _safe_avg([e['danmaku_rate'] for e in engagement_list]),
            'avg_reply_rate': _safe_avg([e['reply_rate'] for e in engagement_list]),
        }

    # ─────────────────────────────────────────────────────────────
    # 2. 生命周期与增长分析（Lifecycle and Growth Analysis）
    # ─────────────────────────────────────────────────────────────

    def get_lifecycle_growth_analysis(
        self,
        season_id: int,
        window_days: int = 30,
    ) -> Optional[Dict]:
        """
        生命周期与增长分析：黑马指数（一/二阶导数）与长尾效应。

        一阶导数（日增量）反映短期爆发力，二阶导数（增速变化）刻画动量变化。
        长尾效应通过统计首播后 30/90 天的日均播放量来衡量持续影响力。

        Args:
            season_id: 番剧 season_id
            window_days: 用于计算黑马指数的滑动窗口天数（暂未使用，预留扩展）

        Returns:
            包含逐日增长数据、长尾效应和峰值信息的字典；番剧不存在时返回 None
        """
        anime = self.session.exec(
            select(Anime).where(Anime.season_id == season_id)
        ).first()

        if not anime:
            return None

        stats = self.session.exec(
            select(DailyStats)
            .where(DailyStats.season_id == season_id)
            .order_by(DailyStats.date)
        ).all()

        if not stats:
            return {
                'season_id': season_id,
                'growth_data': [],
                'long_tail': {'avg_daily_views_30d': None, 'avg_daily_views_90d': None},
                'peak_daily_growth': None,
                'peak_date': None,
            }

        views_list = [s.views for s in stats]
        favorites_list = [s.favorites for s in stats]

        growth_data = []
        for i, stat in enumerate(stats):
            # 一阶导数
            views_growth = views_list[i] - views_list[i - 1] if i > 0 else None
            favorites_growth = favorites_list[i] - favorites_list[i - 1] if i > 0 else None

            # 二阶导数
            if i > 1:
                views_accel = (
                    (views_list[i] - views_list[i - 1])
                    - (views_list[i - 1] - views_list[i - 2])
                )
                favorites_accel = (
                    (favorites_list[i] - favorites_list[i - 1])
                    - (favorites_list[i - 1] - favorites_list[i - 2])
                )
            else:
                views_accel = None
                favorites_accel = None

            growth_data.append({
                'date': stat.date.isoformat(),
                'views': stat.views,
                'favorites': stat.favorites,
                'views_growth': views_growth,
                'views_acceleration': views_accel,
                'favorites_growth': favorites_growth,
                'favorites_acceleration': favorites_accel,
            })

        # 峰值日增（黑马指数参考值）
        growths = [(g['views_growth'], g['date']) for g in growth_data if g['views_growth'] is not None]
        if growths:
            peak_daily_growth, peak_date = max(growths, key=lambda x: x[0])
        else:
            peak_daily_growth, peak_date = None, None

        # 长尾效应：以首条记录日期作为发布基准
        first_date = stats[0].date
        date_30d = first_date + timedelta(days=30)
        date_90d = first_date + timedelta(days=90)

        stats_after_30d = [s for s in stats if s.date >= date_30d]
        stats_after_90d = [s for s in stats if s.date >= date_90d]

        avg_30d = (
            round(sum(s.views for s in stats_after_30d) / len(stats_after_30d), 2)
            if stats_after_30d else None
        )
        avg_90d = (
            round(sum(s.views for s in stats_after_90d) / len(stats_after_90d), 2)
            if stats_after_90d else None
        )

        return {
            'season_id': season_id,
            'growth_data': growth_data,
            'long_tail': {
                'avg_daily_views_30d': avg_30d,
                'avg_daily_views_90d': avg_90d,
            },
            'peak_daily_growth': peak_daily_growth,
            'peak_date': peak_date,
        }

    # ─────────────────────────────────────────────────────────────
    # 3. 竞争态势分析（Competitive Landscape Analysis）
    # ─────────────────────────────────────────────────────────────

    def get_competitive_landscape_analysis(
        self,
        season_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict:
        """
        竞争态势分析：霸榜指数与排名波动率。

        霸榜指数（dominance_top3 / dominance_top10）统计番剧在指定时间窗口内
        进入前3名和前10名的天数占比；排名波动率（标准差）反映排名稳定性。

        Args:
            season_id: 番剧 season_id
            start_date: 统计开始日期（可选，默认不限）
            end_date: 统计结束日期（可选，默认不限）

        Returns:
            包含上榜天数、霸榜比例和波动率的字典
        """
        query = (
            select(Ranking)
            .where(Ranking.season_id == season_id)
            .where(Ranking.ranking_type == "views")
            .order_by(Ranking.date)
        )
        if start_date:
            query = query.where(Ranking.date >= start_date)
        if end_date:
            query = query.where(Ranking.date <= end_date)

        rankings = self.session.exec(query).all()

        if not rankings:
            return {
                'season_id': season_id,
                'total_ranking_days': 0,
                'top3_days': 0,
                'top10_days': 0,
                'dominance_top3': None,
                'dominance_top10': None,
                'avg_rank': None,
                'rank_volatility': None,
            }

        positions = [r.rank_position for r in rankings]
        total = len(positions)
        top3_days = sum(1 for p in positions if p <= 3)
        top10_days = sum(1 for p in positions if p <= 10)
        avg_rank = sum(positions) / total

        # 总体标准差（衡量排名波动率）
        variance = sum((p - avg_rank) ** 2 for p in positions) / total
        std_dev = math.sqrt(variance)

        return {
            'season_id': season_id,
            'total_ranking_days': total,
            'top3_days': top3_days,
            'top10_days': top10_days,
            'dominance_top3': round(top3_days / total * 100, 2),
            'dominance_top10': round(top10_days / total * 100, 2),
            'avg_rank': round(avg_rank, 2),
            'rank_volatility': round(std_dev, 2),
        }

    # ─────────────────────────────────────────────────────────────
    # 4. 题材季节性规律分析（Seasonal Genre Trends）
    # ─────────────────────────────────────────────────────────────

    def get_seasonal_genre_trends(self) -> Dict:
        """
        题材季节性规律分析：交叉分析番剧发布季节、题材风格与播放量。

        根据 release_date 月份映射季节（spring=04月, summer=07月,
        autumn=10月, winter=01月），统计各季节每种题材的番剧数量、
        总播放量及平均播放量，并给出每个季节表现最佳的题材。

        Returns:
            包含各季节题材数据列表和每季最佳题材映射的字典
        """
        MONTH_TO_SEASON = {
            '01': 'winter',
            '04': 'spring',
            '07': 'summer',
            '10': 'autumn',
        }

        animes = self.session.exec(select(Anime)).all()

        # season -> genre -> [views]
        trend_data: Dict[str, Dict[str, List[int]]] = {}

        for anime in animes:
            if not anime.release_date or anime.release_date in ('敬请期待', '更早'):
                continue

            parts = anime.release_date.split('-')
            if len(parts) != 2:
                continue

            season = MONTH_TO_SEASON.get(parts[1])
            if not season:
                continue

            if not anime.styles:
                continue
            styles = json.loads(anime.styles)

            latest_stats = self.session.exec(
                select(DailyStats)
                .where(DailyStats.season_id == anime.season_id)
                .order_by(desc(DailyStats.date))
                .limit(1)
            ).first()
            views = latest_stats.views if latest_stats else 0

            for style in styles:
                trend_data.setdefault(season, {}).setdefault(style, []).append(views)

        trends = []
        best_genre_by_season: Dict[str, str] = {}

        for season, genre_data in trend_data.items():
            best_genre = None
            best_avg_views = -1.0

            for genre, views_list in genre_data.items():
                anime_count = len(views_list)
                total_views = sum(views_list)
                avg_views = total_views / anime_count

                trends.append({
                    'season': season,
                    'genre': genre,
                    'anime_count': anime_count,
                    'avg_views': round(avg_views, 2),
                    'total_views': total_views,
                })

                if avg_views > best_avg_views:
                    best_avg_views = avg_views
                    best_genre = genre

            if best_genre:
                best_genre_by_season[season] = best_genre

        return {
            'trends': trends,
            'best_genre_by_season': best_genre_by_season,
        }

    # ─────────────────────────────────────────────────────────────
    # 5. 用户个性化推荐（User Personalization System）
    # ─────────────────────────────────────────────────────────────

    def get_personalized_recommendations(self, username: str) -> Optional[Dict]:
        """
        用户个性化推荐：基于双向匹配度算法为用户生成番剧推荐列表。

        匹配度算法说明：
        - 若用户有偏好风格：采用 Jaccard 相似度（交集/并集）作为基础分（权重80%），
          并叠加全局热门风格组合的奖励分（权重20%），最终映射到0~100分。
        - 若用户无偏好：基于播放量和追番数的归一化热度分排序。
        返回匹配度最高的前50部番剧。

        Args:
            username: 用户名

        Returns:
            包含用户偏好和推荐列表的字典；用户不存在时返回 None
        """
        from .models import User

        user = self.session.exec(
            select(User).where(User.username == username)
        ).first()

        if not user:
            return None

        user_prefs = json.loads(user.preferences) if user.preferences else []
        user_prefs_set = set(user_prefs)

        animes = self.session.exec(select(Anime)).all()
        recommendations = self._build_recommendation_items(user_prefs_set, animes)

        return {
            'username': username,
            'preferences': user_prefs,
            'recommendations': recommendations[:50],
        }

    def get_recommendation_explanation(self, username: str, season_id: int) -> Optional[Dict]:
        """
        获取用户对指定番剧的推荐解释（可解释推荐拆解）。

        Args:
            username: 用户名
            season_id: 番剧 ID

        Returns:
            推荐解释字典；用户或番剧不存在时返回 None
        """
        from .models import User

        user = self.session.exec(
            select(User).where(User.username == username)
        ).first()
        if not user:
            return None

        user_prefs = json.loads(user.preferences) if user.preferences else []
        user_prefs_set = set(user_prefs)
        animes = self.session.exec(select(Anime)).all()
        all_items = self._build_recommendation_items(user_prefs_set, animes)
        target = next((item for item in all_items if item["season_id"] == season_id), None)
        if not target:
            return None

        all_views = [item["views"] for item in all_items]
        lower_or_equal = sum(1 for v in all_views if v <= target["views"])
        views_percentile = (lower_or_equal / len(all_views)) if all_views else 0.0
        target_explainability = target.get("explainability")
        if target_explainability is None:
            target_explainability = {}
        strategy_defaults = self._get_recommendation_strategy()
        strategy_weights = target_explainability.get("strategy_weights") or {
            "views_weight": strategy_defaults["views_weight"],
            "ai_weight": strategy_defaults["ai_weight"],
            "tmdb_weight": strategy_defaults["tmdb_weight"],
            "diversity_weight": strategy_defaults["diversity_weight"],
        }
        component_scores = target_explainability.get("component_scores") or {
            "views_signal": 0.0,
            "ai_signal": 0.0,
            "tmdb_signal": 0.0,
            "diversity_signal": 0.0,
        }

        return {
            "username": username,
            "season_id": season_id,
            "title": target["title"],
            "match_score": target["match_score"],
            "explainability": {
                "jaccard_similarity": target_explainability.get("jaccard_similarity", 0.0),
                "combo_bonus_score": target_explainability.get("combo_bonus_score", 0.0),
                "views_percentile": round(views_percentile, 4),
                "matched_styles": sorted(list(user_prefs_set & set(target.get("styles") or []))),
                "reasoning": target_explainability.get("reasoning", "暂无解释信息"),
                "strategy_enabled": target_explainability.get("strategy_enabled", strategy_defaults["enabled"]),
                "strategy_weights": {
                    "views_weight": strategy_weights["views_weight"],
                    "ai_weight": strategy_weights["ai_weight"],
                    "tmdb_weight": strategy_weights["tmdb_weight"],
                    "diversity_weight": strategy_weights["diversity_weight"],
                },
                "component_scores": {
                    "views_signal": component_scores["views_signal"],
                    "ai_signal": component_scores["ai_signal"],
                    "tmdb_signal": component_scores["tmdb_signal"],
                    "diversity_signal": component_scores["diversity_signal"],
                },
            },
            "stats": {
                "views": target["views"],
                "favorites": target["favorites"],
            },
        }
