# app.py
import json
import os
import random
import re
import threading
import time
from datetime import datetime
from math import log10

import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_apscheduler import APScheduler
from flask_cors import CORS

from data_manager import BangumiDataManager
from scraper import BilibiliBangumiScraper

# 确定脚本所在的目录
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(CURRENT_DIR, 'cache.json')
COVER_CACHE_DIR = os.path.join(os.path.dirname(CURRENT_DIR), "cover_cache")


def _get_animes_from_rank_cache():
    """
    一个辅助函数，用于安全地从 rank_cache.json 文件中读取番剧列表。
    如果文件不存在，它将自动触发数据获取和处理流程来创建该文件。

    Returns:
        list: 包含番剧数据的列表。如果文件不存在、自动创建失败或解析失败，则返回一个空列表。
    """
    rank_cache_path = os.path.join(CURRENT_DIR, 'rank_cache.json')

    # 1. 检查缓存文件是否存在，如果不存在则自动生成
    if not os.path.exists(rank_cache_path):
        print("排名缓存文件 'rank_cache.json' 未找到。")
        print("正在启动自动数据获取流程，这可能需要几分钟时间...")
        try:
            data_manager = BangumiDataManager(pages_to_fetch=5)
            result = data_manager.update_rank_cache()
            if not result:
                print("自动数据获取流程未能成功生成缓存文件。")
                return []
        except Exception as e:
            print(f"自动数据获取流程因异常而失败: {e}")
            return []

    try:
        with open(rank_cache_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('list', [])
    except Exception as e:
        print(f"读取缓存文件 '{rank_cache_path}' 时发生未知错误: {e}")
        return []


def get_type_distribution_chart():
    """
    计算并返回番剧的类型（风格）分布数据。

    该函数统计 `rank_cache.json` 中所有番剧的每种风格出现的次数，
    并按出现次数从高到低排序。

    Returns:
        Response: 一个 JSON 响应，其数据格式为 [[style_name, count], ...]。
    """
    animes = _get_animes_from_rank_cache()
    style_counts = {}
    for anime in animes:
        if anime.get('styles') and isinstance(anime['styles'], list):
            for style in anime['styles']:
                style_counts[style] = style_counts.get(style, 0) + 1

    sorted_styles = sorted(style_counts.items(), key=lambda item: item[1], reverse=True)
    return jsonify(sorted_styles)


def get_reputation_popularity_chart():
    """
    生成用于展示番剧口碑与热度关系的散点图数据。

    支持通过 'areas' 查询参数按地区筛选数据（例如 '国内,日本'）。
    为了解决数据点在同一评分上重叠的问题，我们为评分添加了微小的随机“抖动”(jitter)。

    Query Parameters:
        areas (str): 可选参数，一个用逗号分隔的地区字符串列表。

    Returns:
        Response: 一个 JSON 响应，其数据格式为 [[jittered_score, favorites, title, views, original_score, area], ...]。
    """
    animes = _get_animes_from_rank_cache()
    chart_data = []

    # 1. 获取并解析地区筛选参数
    selected_areas_str = request.args.get('areas', '')
    selected_areas = [area.strip() for area in selected_areas_str.split(',') if
                      area.strip()] if selected_areas_str else []

    for anime in animes:
        # 2. 如果设置了地区筛选，则跳过不匹配的番剧
        if selected_areas and anime.get('area') not in selected_areas:
            continue

        score_str = anime.get('score')
        if not score_str:
            continue
        try:
            score = float(score_str)
        except (ValueError, TypeError):
            continue

        favorites = int(anime.get('favorites', 0))
        views = int(anime.get('views', 0))

        if score > 0 and favorites > 0:
            jitter = random.uniform(-0.05, 0.05)
            jittered_score = round(score + jitter, 2)
            chart_data.append([jittered_score, favorites, anime.get('title'), views, score, anime.get('area')])

    return jsonify(chart_data)


def get_yearly_quantity_chart():
    """
    按年份和季度统计番剧的发布数量。

    该函数可以根据查询参数 `category` 对番剧类型进行过滤。
    然后，它将统计每年每个季度（1-3月、4-6月等）发布的番剧数量。

    Query Parameters:
        category (str): 可选参数，用于筛选特定类型的番剧。如果为 'all' 或未提供，则统计所有番剧。

    Returns:
        Response: 一个 JSON 响应，其数据格式为 { "year": [q1_count, q2_count, q3_count, q4_count], ... }。
    """
    animes = _get_animes_from_rank_cache()
    category = request.args.get('category', 'all')

    filtered_animes = []
    if category == 'all':
        filtered_animes = animes
    else:
        for anime in animes:
            if anime.get('styles') and isinstance(anime['styles'], list) and category in anime['styles']:
                filtered_animes.append(anime)

    yearly_data = {}
    for anime in filtered_animes:
        if anime.get('release_date') and isinstance(anime['release_date'], str):
            date_parts = anime['release_date'].split('-')
            if len(date_parts) >= 2:
                year = date_parts[0]
                month = int(date_parts[1])

                if year not in yearly_data:
                    yearly_data[year] = [0, 0, 0, 0]

                if 1 <= month <= 3:
                    yearly_data[year][0] += 1
                elif 4 <= month <= 6:
                    yearly_data[year][1] += 1
                elif 7 <= month <= 9:
                    yearly_data[year][2] += 1
                elif 10 <= month <= 12:
                    yearly_data[year][3] += 1

    return jsonify(yearly_data)


def get_preference_difference_chart():
    """
    计算特定地区与全球平均对不同番剧类型的偏好差异指数。

    该函数首先计算每种类型的全球平均收藏数。然后，根据查询参数 `region` 筛选出
    特定地区的番剧，并计算该地区每种类型的平均收藏数。最后，通过将地区平均值
    除以全球平均值，得到偏好指数。

    Query Parameters:
        region (str): 必选参数，用于指定地区（例如 '国内', '日本'）。默认为 '国内'。

    Returns:
        Response: 一个 JSON 响应，其数据格式为 [{'name': style, 'value': preference_index, ...}, ...]。
    """
    animes = _get_animes_from_rank_cache()

    # 计算全球各类别的平均收藏数
    global_genre_stats = {}
    for anime in animes:
        if anime.get('styles') and isinstance(anime['styles'], list):
            for style in anime['styles']:
                if style not in global_genre_stats:
                    global_genre_stats[style] = {'totalFavorites': 0, 'count': 0}
                global_genre_stats[style]['totalFavorites'] += anime.get('favorites', 0)
                global_genre_stats[style]['count'] += 1

    for style in global_genre_stats:
        stats = global_genre_stats[style]
        stats['avgFavorites'] = stats['totalFavorites'] / stats['count'] if stats['count'] > 0 else 0

    # 筛选特定地区的番剧
    selected_region = request.args.get('region', '国内')
    regional_animes = [anime for anime in animes if selected_region == 'all' or anime.get('area') == selected_region]

    # 计算地区内各类别的平均收藏数
    regional_genre_stats = {}
    for anime in regional_animes:
        if anime.get('styles') and isinstance(anime['styles'], list):
            for style in anime['styles']:
                if style not in regional_genre_stats:
                    regional_genre_stats[style] = {'totalFavorites': 0, 'count': 0}
                regional_genre_stats[style]['totalFavorites'] += anime.get('favorites', 0)
                regional_genre_stats[style]['count'] += 1

    for style in regional_genre_stats:
        stats = regional_genre_stats[style]
        stats['avgFavorites'] = stats['totalFavorites'] / stats['count'] if stats['count'] > 0 else 0

    # 计算偏好指数
    chart_data = []
    for style, regional_stats in regional_genre_stats.items():
        global_stats = global_genre_stats.get(style)
        if global_stats and global_stats['avgFavorites'] > 0 and regional_stats['count'] >= 3:
            preference_index = regional_stats['avgFavorites'] / global_stats['avgFavorites']
            chart_data.append({
                'name': style,
                'value': round(preference_index, 2),
                'regionalAvg': round(regional_stats['avgFavorites']),
                'globalAvg': round(global_stats['avgFavorites'])
            })

    return jsonify(chart_data)


def get_reputation_heat_index_chart():
    """
    计算并返回番剧的“口碑热度指数”排名前15的作品。

    该指数通过公式 `score * log10(favorites) * log10(views)` 计算得出。
    支持通过查询参数 `season` 和 `category` 进行筛选。

    Query Parameters:
        season (str): 可选参数，筛选特定季节 ('winter', 'spring', 'summer', 'autumn')。
        category (str): 可选参数，筛选特定类型。

    Returns:
        Response: 一个 JSON 响应，包含排名前15的番剧完整信息的列表。
    """
    animes = _get_animes_from_rank_cache()
    season = request.args.get('season', 'all')
    category = request.args.get('category', 'all')

    season_map = {
        'winter': [1, 2, 3], 'spring': [4, 5, 6],
        'summer': [7, 8, 9], 'autumn': [10, 11, 12]
    }

    processed_data = []
    for anime in animes:
        score = anime.get('score')
        views = anime.get('views')
        favorites = anime.get('favorites')

        if not all([score, views, favorites]) or float(score) <= 0 or int(views) <= 0 or int(favorites) <= 0:
            continue

        if season != 'all':
            release_date_parts = anime.get('release_date', '').split('-')
            if len(release_date_parts) < 2 or int(release_date_parts[1]) not in season_map.get(season, []):
                continue

        if category != 'all':
            if not (anime.get('styles') and category in anime.get('styles', [])):
                continue

        anime['qualityScore'] = float(score) * log10(int(favorites)) * log10(int(views))
        processed_data.append(anime)

    top_animes = sorted(processed_data, key=lambda x: x.get('qualityScore', 0), reverse=True)[:15]

    return jsonify(top_animes)


def get_popular_style_combination_chart():
    """
    找出最受欢迎的“风格组合”（两种类型的搭配），并按平均收藏数排序。

    该函数遍历所有番剧，找出所有两两风格的组合。然后，计算每个组合下的
    作品总数和平均收藏数。只考虑作品数达到一定门槛（默认为5）的组合，
    并返回平均收藏数排名前20的组合。

    Returns:
        Response: 一个 JSON 响应，数据格式为 [{'name': '类型A + 类型B', 'avgFavorites': avg_fav, ...}, ...]。
    """
    animes = _get_animes_from_rank_cache()

    combinations = {}
    for anime in animes:
        styles = anime.get('styles')
        if styles and isinstance(styles, list) and len(styles) >= 2:
            sorted_styles = sorted(styles)
            for i in range(len(sorted_styles)):
                for j in range(i + 1, len(sorted_styles)):
                    combo_key = f"{sorted_styles[i]} + {sorted_styles[j]}"
                    if combo_key not in combinations:
                        combinations[combo_key] = {'totalFavorites': 0, 'count': 0, 'animes': []}

                    favorites = int(anime.get('favorites', 0))
                    combinations[combo_key]['totalFavorites'] += favorites
                    combinations[combo_key]['count'] += 1
                    combinations[combo_key]['animes'].append({
                        'title': anime.get('title'),
                        'cover': anime.get('cover'),
                        'score': anime.get('score'),
                        'favorites': favorites,
                        'season_id': anime.get('season_id')
                    })

    min_anime_count = 5
    top_combinations = sorted(
        [
            {
                'name': name,
                'count': data['count'],
                'avgFavorites': data['totalFavorites'] / data['count'] if data['count'] > 0 else 0,
                'animes': sorted(data['animes'], key=lambda x: x['favorites'], reverse=True)
            }
            for name, data in combinations.items() if data['count'] >= min_anime_count
        ],
        key=lambda x: x['avgFavorites'],
        reverse=True
    )[:20]

    return jsonify(top_combinations)


def get_rank_list():
    """
    获取经过处理的番剧排名列表。

    该函数替代了前端直接访问 rank_cache 的逻辑，并在后端处理筛选、排序和创新的随机化刷新。
    它将排序后的番剧分为三个等级，并从每个等级中随机抽取一定数量的番剧，
    以确保每次刷新都能看到部分新面孔，同时保持结果的高质量。

    Query Parameters:
        sortBy (str): 排序依据，可选值为 'score', 'followers', 'views'。默认为 'score'。
        isPreferenceMode (str): 'true' 或 'false'，指示是否启用偏好筛选。默认为 'false'。
        preferences (str): 逗号分隔的用户偏好类型字符串，例如 '奇幻,战斗,搞笑'。

    Returns:
        Response: 一个包含10个番剧对象的JSON响应列表。
    """
    # 1. 获取查询参数
    sort_by = request.args.get('sortBy', 'score')
    is_preference_mode = request.args.get('isPreferenceMode', 'false').lower() == 'true'
    preferences_str = request.args.get('preferences', '')
    user_preferences = preferences_str.split(',') if preferences_str else []

    # 2. 读取基础数据
    all_animes = _get_animes_from_rank_cache()

    # 3. 根据偏好进行筛选
    if is_preference_mode and user_preferences:
        filtered_animes = [
            anime for anime in all_animes
            if anime.get('styles') and any(style in user_preferences for style in anime['styles'])
        ]
    else:
        filtered_animes = all_animes

    # 4. 根据指定字段排序
    sort_key = 'favorites' if sort_by == 'followers' else sort_by
    sorted_animes = sorted(
        filtered_animes,
        key=lambda x: (
            float(x.get(sort_key, 0)) if str(x.get(sort_key, '0')).replace('.', '', 1).isdigit() else 0
        ),
        reverse=True
    )

    # 5. 实现带随机性的分层抽样逻辑
    total_count = len(sorted_animes)
    animes_to_return = []

    if total_count <= 10:
        animes_to_return = sorted_animes
    else:
        # 定义三个等级的范围
        tier1_end = max(5, int(total_count * 0.1))
        tier2_end = max(tier1_end + 15, int(total_count * 0.3))

        tier1 = sorted_animes[:tier1_end]
        tier2 = sorted_animes[tier1_end:tier2_end]
        tier3 = sorted_animes[tier2_end:]

        # 定义从每个等级抽取的数量
        picks = {'tier1': 4, 'tier2': 4, 'tier3': 2}

        # 从每个等级安全地抽取番剧
        tier1_picks = random.sample(tier1, min(len(tier1), picks['tier1']))
        tier2_picks = random.sample(tier2, min(len(tier2), picks['tier2']))
        tier3_picks = random.sample(tier3, min(len(tier3), picks['tier3']))

        combined_picks = tier1_picks + tier2_picks + tier3_picks

        # 如果数量不足10，从剩余的番剧中补充
        if len(combined_picks) < 10:
            remaining_animes = [anime for anime in sorted_animes if anime not in combined_picks]
            needed = 10 - len(combined_picks)
            combined_picks.extend(remaining_animes[:needed])

        # 按原始排名（即排序键）对最终选出的番剧再次排序
        animes_to_return = sorted(
            combined_picks,
            key=lambda x: (
                float(x.get(sort_key, 0)) if str(x.get(sort_key, '0')).replace('.', '', 1).isdigit() else 0
            ),
            reverse=True
        )[:10]

    return jsonify(animes_to_return)


def image_proxy():
    """
    代理图片请求，实现图片缓存功能。
    """
    image_url = request.args.get('url')
    title = request.args.get('title')
    season_id = request.args.get('season_id')
    if not all([image_url, title, season_id]):
        return "缺少必要的参数 (url, title, season_id)", 400

    os.makedirs(COVER_CACHE_DIR, exist_ok=True)

    safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
    _, ext = os.path.splitext(image_url)
    if not ext: ext = '.jpg'
    filename = f"{safe_title}_{season_id}_cover{ext}"
    local_filepath = os.path.join(COVER_CACHE_DIR, filename)

    if not os.path.exists(local_filepath):
        print(f"缓存未命中，正在下载图片: {image_url}")
        try:
            headers = {'Referer': 'https://www.bilibili.com/'}
            response = requests.get(image_url, headers=headers, stream=True, timeout=10)
            response.raise_for_status()
            with open(local_filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"图片已成功缓存到: {local_filepath}")
        except requests.exceptions.RequestException as e:
            print(f"下载图片失败: {e}")
            return "图片下载失败", 500
    else:
        print(f"缓存命中，直接提供图片: {filename}")
    return send_from_directory(os.path.dirname(local_filepath), os.path.basename(local_filepath))


class BilibiliAnalyticsApp:
    def __init__(self):
        """
        初始化 BilibiliAnalyticsApp 类。
        """
        self.app = Flask(__name__)
        CORS(self.app)

        self.cache_file_path = CACHE_FILE
        print(f"[*] 应用启动，将使用位于以下路径的缓存文件: {self.cache_file_path}")

        self.app.config['SCHEDULER_API_ENABLED'] = True
        self.scheduler = APScheduler()
        self.scheduler.init_app(self.app)
        self.scraper = BilibiliBangumiScraper()
        self.data_manager = BangumiDataManager(pages_to_fetch=5)  # 使用默认值初始化
        self.cache_lock = threading.Lock()
        self._register_routes()

        self.scheduler.add_job(
            func=self.update_all_tracked_bangumi,
            trigger='cron',
            id='update_online_viewers_job',
            hour='0,4,8,12,16,20',
            minute='0',
            misfire_grace_time=None
        )

        self.scheduler.add_job(
            func=self.run_monthly_aggregation_job,
            trigger='cron',
            id='monthly_aggregation_job',
            day='1',
            hour='2',
            minute='0'
        )

        self.scheduler.start()

    def _register_routes(self):
        """
        在 Flask 应用中注册路由。
        """
        self.app.route('/search', methods=['POST'])(self.search)
        self.app.route('/api/image_proxy')(image_proxy)
        self.app.route('/api/monthly_data/<int:month>', methods=['GET'])(self.get_monthly_data)
        self.app.route('/api/rank_list', methods=['GET'])(get_rank_list)
        self.app.route('/health_check', methods=['GET'])(self.health_check)
        self.app.route('/api/type_distribution_chart', methods=['GET'])(get_type_distribution_chart)
        self.app.route('/api/reputation_popularity_chart', methods=['GET'])(get_reputation_popularity_chart)
        self.app.route('/api/yearly_quantity_chart', methods=['GET'])(get_yearly_quantity_chart)
        self.app.route('/api/preference_difference_chart', methods=['GET'])(get_preference_difference_chart)
        self.app.route('/api/reputation_heat_index_chart', methods=['GET'])(get_reputation_heat_index_chart)
        self.app.route('/api/popular_style_combination_chart', methods=['GET'])(get_popular_style_combination_chart)

    def _read_cache(self) -> dict:
        """
        从缓存文件中读取数据。

        Returns:
            dict: 包含已追踪关键词和番剧数据的字典。
        """
        with self.cache_lock:
            if not os.path.exists(self.cache_file_path):
                return {"tracked_keywords": [], "bangumi_data": {}}
            try:
                with open(self.cache_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    return json.loads(content) if content else {"tracked_keywords": [], "bangumi_data": {}}
            except (json.JSONDecodeError, FileNotFoundError):
                return {"tracked_keywords": [], "bangumi_data": {}}

    def _write_cache(self, data: dict):
        """
        将数据写入缓存文件。

        Args:
            data (dict): 要写入缓存的字典。
        """
        with self.cache_lock:
            with open(self.cache_file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

    def run_monthly_aggregation_job(self):
        """
        由调度器调用的月度聚合任务的包装器方法。
        """
        print(f"--- [MONTHLY JOB at {datetime.now()}] ---")
        print("--- 开始执行月度数据聚合... ---")
        try:
            self.data_manager.run_monthly_aggregation()
            print("--- [MONTHLY JOB] 月度数据聚合任务成功完成。 ---")
        except Exception as e:
            print(f"--- [MONTHLY JOB ERROR] 月度数据聚合任务失败: {e} ---")

    def update_all_tracked_bangumi(self, is_health_check=False) -> dict:
        """
        定时任务：更新所有已追踪番剧的在线人数。

        Args:
            is_health_check (bool): 如果为True，则表示此调用来自健康检查。
                                    它将只检查一个番剧并且不会将结果写入缓存。

        Returns:
            dict: 一个包含执行结果摘要的字典。
        """
        # 1. 根据调用来源，决定是否打印常规日志
        if not is_health_check:
            print(f"--- [SCHEDULED JOB at {datetime.now()}] ---")

        # 2. 初始化用于返回的摘要字典
        summary = {"status": "ok", "updated_count": 0, "details": ""}

        try:
            # 3. 读取缓存文件
            cache = self._read_cache()
            tracked_keywords = cache.get("tracked_keywords", [])

            # 如果没有追踪的番剧，直接返回
            if not tracked_keywords:
                summary["details"] = "没有需要追踪的番剧，任务跳过。"
                if not is_health_check:
                    print(summary["details"])
                return summary

            # 4. 准备更新数据
            current_time_slot = datetime.now().strftime('%H:%M')
            if not is_health_check:
                print(f"当前时间槽: {current_time_slot}. 开始更新 {len(tracked_keywords)} 个已追踪的番剧...")

            updated_count = 0

            # 5. 遍历追踪列表并获取数据
            for keyword in tracked_keywords:
                # 如果是健康检查，只处理第一个就跳出循环
                if is_health_check and updated_count > 0:
                    break

                bangumi_info = cache["bangumi_data"].get(keyword)
                if not bangumi_info or 'episodes' not in bangumi_info.get('data', {}):
                    continue

                episodes = bangumi_info['data']['episodes']
                for i, episode in enumerate(episodes):
                    bvid, cid = episode.get('bvid'), episode.get('cid')
                    if not (bvid and cid):
                        continue

                    # 调用 scraper 获取在线人数
                    online_count = self.scraper.get_online_viewers(bvid, cid)

                    if online_count is None:
                        # 在健康检查模式下，一次失败就足以报告问题
                        if is_health_check:
                            raise ConnectionError(f"获取'{keyword}'在线人数失败 (bvid:{bvid})")
                        continue

                    # 在内存中更新 cache 字典
                    if 'online_history' not in episode:
                        episode['online_history'] = {}
                    episode['online_history'][current_time_slot] = online_count
                    cache["bangumi_data"][keyword]['data']['episodes'][i] = episode
                    time.sleep(0.5)  # 保持礼貌的请求间隔

                updated_count += 1

            # 6. 【关键判断】: 只有在不是健康检查的情况下才写入文件
            if not is_health_check:
                self._write_cache(cache)
                print("--- [SCHEDULED JOB] 所有番剧更新完毕。 ---")

            # 7. 准备最终的返回信息
            summary["updated_count"] = updated_count
            if is_health_check:
                summary["details"] = f"成功模拟更新了 {updated_count} 个番剧的数据（未写入缓存）。"
            else:
                summary["details"] = f"成功更新了 {updated_count} 个番剧的在线人数数据。"

        except Exception as e:
            # 8. 捕获任何异常，并记录到摘要中
            summary["status"] = "error"
            summary["details"] = f"任务执行失败: {str(e)}"

        return summary

    def search(self):
        """
        根据关键词搜索番剧，如果缓存中存在则直接返回，否则抓取并存入缓存。
        """
        keyword = request.json.get('keyword')
        if not keyword:
            return jsonify({'status': 'error', 'message': '请输入番剧名'}), 400

        cache = self._read_cache()
        bangumi_data = cache.get("bangumi_data", {})

        if keyword in bangumi_data:
            bangumi_info = bangumi_data[keyword]
            first_fetched_timestamp = bangumi_info.get("first_fetched_timestamp", 0)
            current_timestamp = time.time()
            cache_age_seconds = current_timestamp - first_fetched_timestamp
            if cache_age_seconds < 43200:
                print(f"'{keyword}' 命中有效缓存，直接返回数据。")
                return jsonify({'status': 'cached', 'data': bangumi_info['data']})
            else:
                print(f"'{keyword}' 的缓存已过期，执行安全增量更新...")

                old_data = bangumi_info.get('data', {})
                season_id = self.scraper.get_bangumi_id(keyword)

                if not season_id:
                    return jsonify({'status': 'cached_stale', 'message': '缓存已过期但更新失败', 'data': old_data}), 200

                fresh_dynamic_data = self.scraper.get_bangumi_details(season_id)

                if fresh_dynamic_data:
                    updated_data = old_data.copy()

                    new_stats = fresh_dynamic_data.get('stats', {})
                    if new_stats.get('views') is not None and new_stats.get('favorites') is not None:
                        updated_data['stats'] = new_stats
                        print(f"  -> 'stats' 数据已更新。")
                    else:
                        print(f"  -> 'stats' 数据获取异常，保留旧数据。")

                    old_episodes_map = {ep.get('cid'): ep for ep in old_data.get('episodes', []) if ep.get('cid')}

                    merged_episodes = []
                    new_episodes_list = fresh_dynamic_data.get('episodes', [])

                    for new_ep in new_episodes_list:
                        cid = new_ep.get('cid')
                        old_ep = old_episodes_map.get(cid)

                        if old_ep:
                            new_ep['online_history'] = old_ep.get('online_history', {})

                        merged_episodes.append(new_ep)

                    updated_data['episodes'] = merged_episodes
                    print(f"  -> 'episodes' 列表已合并，保留了 online_history。")

                    cache["bangumi_data"][keyword] = {
                        'first_fetched_timestamp': time.time(),
                        'data': updated_data
                    }
                    self._write_cache(cache)

                    print(f"'{keyword}' 已成功增量更新并返回最新数据。")
                    return jsonify({'status': 'success_updated', 'data': updated_data})
                else:
                    print(f"'{keyword}' 增量更新失败，暂时返回旧数据。")
                    return jsonify({'status': 'cached_stale', 'message': '缓存已过期但更新失败', 'data': old_data}), 200

        print(f"'{keyword}' 是新的番剧，执行首次信息抓取。")
        full_details = self.scraper.get_full_details_by_keyword(keyword)

        if full_details:
            cache["bangumi_data"][keyword] = {
                'first_fetched_timestamp': time.time(),
                'data': full_details
            }
            if keyword not in cache["tracked_keywords"]:
                cache["tracked_keywords"].append(keyword)
            self._write_cache(cache)
            print(f"'{keyword}' 已成功抓取并添加到追踪列表。")
            return jsonify({'status': 'success', 'data': full_details})
        else:
            return jsonify({'status': 'error', 'message': f"未能找到“{keyword}”的相关数据"}), 404

    @staticmethod
    def get_monthly_data(month):
        """
        获取指定月份的聚合数据。

        Args:
            month (int): 月份。

        Returns:
            Response: 包含月度数据的 JSON 响应。
        """
        if not 1 <= month <= 12:
            return jsonify({"error": "无效的月份"}), 400
        filename = f"rank_fetcher_{month}th.json"
        file_path = os.path.join(CURRENT_DIR, filename)
        if not os.path.exists(file_path):
            return jsonify({"error": f"未找到 {month} 月的数据"}), 404
        return send_from_directory(CURRENT_DIR, filename)

    def health_check(self):
        """
        执行健康检查，验证应用及其依赖项的状态。

        Returns:
            Response: 包含健康检查状态的 JSON 响应。
        """
        print("🚀 [HEALTH CHECK] 开始执行健康检查...")
        status = {
            "app_status": "ok",
            "timestamp": datetime.now().isoformat(),
            "checks": []
        }

        try:
            self._read_cache()
            status["checks"].append({"name": "Cache Readability", "status": "ok", "details": "cache.json is readable."})
        except Exception as e:
            status["checks"].append({"name": "Cache Readability", "status": "error", "details": str(e)})
            status["app_status"] = "error"

        rank_cache_path = os.path.join(CURRENT_DIR, "rank_cache.json")
        if os.path.exists(rank_cache_path):
            status["checks"].append(
                {"name": "Rank Cache Existence", "status": "ok", "details": "rank_cache.json found."})
        else:
            status["checks"].append(
                {"name": "Rank Cache Existence", "status": "error", "details": "File not found. Run data_manager.py."})
            status["app_status"] = "error"

        try:
            test_season_id = "102891"  # 碧蓝之海 第二季的ID
            details = self.scraper.get_bangumi_details(test_season_id)
            if details and 'title' in details:
                status["checks"].append({"name": "Bilibili API (via Scraper)", "status": "ok",
                                         "details": f"Successfully fetched details for '{details['title']}'"})
            else:
                raise ValueError("Scraper returned empty details.")
        except Exception as e:
            status["checks"].append({"name": "Bilibili API (via Scraper)", "status": "error", "details": str(e)})
            status["app_status"] = "error"

        print("  -> [HEALTH CHECK] 正在执行定时任务检查...")
        task_summary = self.update_all_tracked_bangumi(is_health_check=True)

        check_item = {
            "name": "Scheduled Job (Online Viewers)",
            "status": task_summary["status"],
            "details": task_summary["details"]
        }
        status["checks"].append(check_item)

        if task_summary["status"] == "error":
            status["app_status"] = "error"

        print(f"🏁 [HEALTH CHECK] 检查完成，总体状态: {status['app_status']}")

        http_status_code = 200 if status['app_status'] == 'ok' else 503
        return jsonify(status), http_status_code

    def run(self, debug=False, port=5000, use_reloader=False):
        """
        运行 Flask 应用。

        Args:
            debug (bool): 是否启用调试模式。
            port (int): 运行端口。
            use_reloader (bool): 是否使用重载器。
        """
        self.app.run(debug=debug, port=port, use_reloader=use_reloader)


# --- 应用启动入口 ---
if __name__ == '__main__':
    analytics_app = BilibiliAnalyticsApp()
    analytics_app.run()
