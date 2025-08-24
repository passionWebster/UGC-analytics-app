# app.py
import os
import json
import time
import threading
import re
import requests
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_apscheduler import APScheduler
from scraper import BilibiliBangumiScraper
from flask_cors import CORS


# --- 应用配置 ---
class Config:
    """Flask-APScheduler的配置类"""
    SCHEDULER_API_ENABLED = True


# --- 全局常量 ---
CACHE_FILE = 'cache.json'  # 用于存储用户搜索和追踪的番剧数据
COVER_CACHE_DIR = "cover_cache"  # 存储从B站下载的番剧封面图

# --- Flask应用初始化 ---
app = Flask(__name__)
app.config.from_object(Config())
CORS(app)  # 启用跨域资源共享，允许前端从不同源访问API

# --- 全局实例初始化 ---
scraper = BilibiliBangumiScraper()  # B站数据抓取器
scheduler = APScheduler()  # 定时任务调度器
scheduler.init_app(app)
scheduler.start()
cache_lock = threading.Lock()  # 线程锁，用于保证多线程环境下对CACHE_FILE读写的原子性，防止数据损坏


# --- 核心函数 ---

def read_cache() -> dict:
    """
    线程安全地读取 cache.json 文件的内容。
    如果文件不存在或内容为空/格式错误，返回一个初始化的空字典结构。

    Returns:
        dict: 包含 "tracked_keywords" 和 "bangumi_data" 的字典。
    """
    with cache_lock:
        if not os.path.exists(CACHE_FILE):
            return {"tracked_keywords": [], "bangumi_data": {}}
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                # 防止文件为空时json.load报错
                content = f.read()
                if not content:
                    return {"tracked_keywords": [], "bangumi_data": {}}
                return json.loads(content)
        except (json.JSONDecodeError, FileNotFoundError):
            # 如果文件存在但解析失败，也返回一个安全默认值
            return {"tracked_keywords": [], "bangumi_data": {}}


def write_cache(data: dict):
    """
    线程安全地将数据写入 cache.json 文件。

    Args:
        data (dict): 要写入文件的数据字典。
    """
    with cache_lock:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)


@scheduler.task('cron', id='update_online_viewers_job', hour='0,4,8,12,16,20', minute='0')
def update_all_tracked_bangumi():
    """
    一个定时任务，每天在指定时间点 (0, 4, 8, 12, 16, 20点) 自动执行。
    它会遍历 cache.json 中所有被追踪的番剧，获取每一集的当前在线人数，并记录下来。
    """
    print(f"--- [SCHEDULED JOB at {datetime.now()}] ---")
    cache = read_cache()
    tracked_keywords = cache.get("tracked_keywords", [])
    if not tracked_keywords:
        print("没有需要追踪的番剧，任务结束。")
        return

    # 使用当前时间作为历史记录的键，例如 "16:00"
    current_time_slot = datetime.now().strftime('%H:%M')
    print(f"当前时间槽: {current_time_slot}. 开始更新 {len(tracked_keywords)} 个已追踪的番剧...")

    # 遍历所有追踪的关键词
    for keyword in tracked_keywords:
        bangumi_info = cache["bangumi_data"].get(keyword)
        # 确保番剧数据和分集列表存在
        if not bangumi_info or 'episodes' not in bangumi_info.get('data', {}):
            continue

        print(f"  -> 正在更新 '{keyword}'...")
        episodes = bangumi_info['data']['episodes']
        for i, episode in enumerate(episodes):
            bvid, cid = episode.get('bvid'), episode.get('cid')
            if not (bvid and cid):
                continue

            # 调用scraper获取在线人数
            online_count = scraper.get_online_viewers(bvid, cid)
            if online_count is None:
                continue  # 获取失败则跳过

            # 初始化历史记录字典
            if 'online_history' not in episode:
                episode['online_history'] = {}
            # 记录当前时间点的在线人数
            episode['online_history'][current_time_slot] = online_count

            # 更新缓存中的数据
            cache["bangumi_data"][keyword]['data']['episodes'][i] = episode
            time.sleep(1)  # 增加请求间隔

    # 将更新后的数据写回文件
    write_cache(cache)
    print("--- [SCHEDULED JOB] 所有番剧更新完毕。 ---")


# --- API 路由 ---

@app.route('/search', methods=['POST'])
def search():
    # noinspection GrazieInspection
    """
        处理前端的番剧搜索请求。
        - 如果番剧已在缓存中，直接返回缓存数据。
        - 如果是新番，调用 scraper 抓取详细信息，存入缓存，然后返回给前端。
        """
    keyword = request.json.get('keyword')
    if not keyword:
        return jsonify({'status': 'error', 'message': '请输入番剧名'}), 400

    cache = read_cache()

    # 检查缓存
    if keyword in cache.get("bangumi_data", {}):
        print(f"'{keyword}' 命中缓存，直接返回数据。")
        return jsonify({'status': 'cached', 'data': cache["bangumi_data"][keyword]['data']})

    # 缓存未命中，执行新的抓取
    print(f"'{keyword}' 是新的番剧，执行首次信息抓取。")
    full_details = scraper.get_full_details_by_keyword(keyword)

    if full_details:
        # 抓取成功，更新缓存
        cache["bangumi_data"][keyword] = {
            'first_fetched_timestamp': time.time(),
            'data': full_details
        }
        if keyword not in cache["tracked_keywords"]:
            cache["tracked_keywords"].append(keyword)
        write_cache(cache)
        print(f"'{keyword}' 已成功抓取并添加到追踪列表。")
        return jsonify({'status': 'success', 'data': full_details})
    else:
        # 抓取失败
        return jsonify({'status': 'error', 'message': f"未能找到“{keyword}”的相关数据"}), 404


@app.route('/api/image_proxy')
def image_proxy():
    """
    一个图片代理和缓存服务。
    当前端请求一个B站图片URL时，此接口会先检查本地是否有缓存。
    - 如果有，直接从本地提供图片。
    - 如果没有，就下载该图片，保存到本地缓存目录，再提供给前端。
    这可以有效解决B站图片的防盗链问题。
    """
    # 1. 从URL查询参数中获取必要信息
    image_url = request.args.get('url')
    title = request.args.get('title')
    season_id = request.args.get('season_id')

    if not all([image_url, title, season_id]):
        return "缺少必要的参数 (url, title, season_id)", 400

    # 2. 构造本地缓存路径
    base_dir = os.path.dirname(__file__)
    cache_dir = os.path.join(base_dir, '..', COVER_CACHE_DIR)
    os.makedirs(cache_dir, exist_ok=True)  # 确保目录存在

    # 清理文件名中的非法字符
    safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
    _, ext = os.path.splitext(image_url)
    if not ext: ext = '.jpg'  # 默认扩展名
    filename = f"{safe_title}_{season_id}_cover{ext}"
    local_filepath = os.path.join(cache_dir, filename)

    # 3. 检查本地缓存是否存在，不存在则下载
    if not os.path.exists(local_filepath):
        print(f"缓存未命中，正在下载图片: {image_url}")
        try:
            # 伪装Referer头来绕过防盗链
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

    # 4. 从本地缓存目录安全地发送文件
    return send_from_directory(cache_dir, filename)


@app.route('/api/monthly_data/<int:month>', methods=['GET'])
def get_monthly_data(month: int):
    """
    提供由 data_manager.py 生成的月度聚合数据文件的API接口。
    前端可以通过 /api/monthly_data/8 来获取8月份的数据。
    """
    if not 1 <= month <= 12:
        return jsonify({"error": "无效的月份"}), 400

    filename = f"rank_fetcher_{month}th.json"
    current_directory = os.path.dirname(os.path.abspath(__file__))

    # 检查文件是否存在
    if not os.path.exists(os.path.join(current_directory, filename)):
        print(f"警告: 前端请求了不存在的文件 '{filename}'")
        return jsonify({"error": f"未找到 {month} 月的数据"}), 404

    return send_from_directory(current_directory, filename)


@app.route('/api/rank_cache', methods=['GET'])
def get_rank_cache():
    """
    提供 rank_cache.json 文件的API接口。
    这个文件包含了所有番剧的排名、播放量、追番量等核心数据。
    """
    current_directory = os.path.dirname(os.path.abspath(__file__))
    filename = "rank_cache.json"

    # 检查文件是否存在
    if not os.path.exists(os.path.join(current_directory, filename)):
        print(f"错误: 前端请求了不存在的文件 '{filename}'。请先运行 data_manager.py fetch。")
        return jsonify({"error": f"排名缓存文件未找到"}), 404

    return send_from_directory(current_directory, filename)


# --- 应用启动 ---
if __name__ == '__main__':
    # debug=False 和 use_reloader=False 在生产或与调度器一同运行时是推荐的设置，
    # 因为Flask的重载器会创建两个进程，可能导致调度任务执行两次。
    app.run(debug=False, port=5000, use_reloader=False)