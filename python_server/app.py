# app.py
import json
import os
import re
import threading
import time
from datetime import datetime

import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_apscheduler import APScheduler
from flask_cors import CORS

from scraper import BilibiliBangumiScraper

# 确定脚本所在的目录
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(CURRENT_DIR, 'cache.json')
COVER_CACHE_DIR = os.path.join(os.path.dirname(CURRENT_DIR), "cover_cache")


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
        self.scheduler.start()

    def _register_routes(self):
        """
        在 Flask 应用中注册路由。
        """
        self.app.route('/search', methods=['POST'])(self.search)
        self.app.route('/api/image_proxy')(self.image_proxy)
        self.app.route('/api/monthly_data/<int:month>', methods=['GET'])(self.get_monthly_data)
        self.app.route('/api/rank_cache', methods=['GET'])(self.get_rank_cache)
        self.app.route('/health_check', methods=['GET'])(self.health_check)

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

    @staticmethod
    def get_rank_cache():
        """
        获取排名缓存数据。

        Returns:
            Response: 包含排名缓存数据的 JSON 响应。
        """
        filename = "rank_cache.json"
        file_path = os.path.join(CURRENT_DIR, filename)
        if not os.path.exists(file_path):
            return jsonify({"error": f"排名缓存文件未找到"}), 404
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
