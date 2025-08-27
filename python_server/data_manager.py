# data_manager.py
import argparse
import json
import os
import re
import time
from datetime import datetime

import requests
from apscheduler.schedulers.blocking import BlockingScheduler

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))


class BangumiDataManager:
    """
    一个统一的数据管理模块，负责：
    1. 从B站API按不同风格批量抓取番剧排名数据，并为每部番剧添加风格数组。
    2. 确保所有番剧（包括无风格的）都被写入缓存。
    3. 合并播放量和追番量，生成 rank_cache.json。
    4. 对排名数据进行月度聚合，并生成月度报告JSON文件。
    """

    # B站番剧索引API的URL
    BASE_API_URL = "https://api.bilibili.com/pgc/season/index/result"
    # 最终生成的排名缓存文件名
    RANK_CACHE_FILE = os.path.join(CURRENT_DIR, 'rank_cache.json')

    STYLE_MAP = {
        10010: '原创', 10011: '漫画改', 10012: '小说改', 10013: '游戏改',
        10102: '特摄', 10015: '布袋戏', 10016: '热血', 10017: '穿越',
        10018: '奇幻', 10020: '战斗', 10021: '搞笑', 10022: '日常',
        10023: '科幻', 10024: '萌系', 10025: '治愈', 10026: '校园',
        10027: '少儿', 10028: '泡面', 10029: '恋爱', 10030: '少女',
        10031: '魔法', 10032: '冒险', 10033: '历史', 10034: '架空',
        10035: '机战', 10036: '神魔', 10037: '声控', 10038: '运动',
        10039: '励志', 10040: '音乐', 10041: '推理', 10042: '社团',
        10043: '智斗', 10044: '催泪', 10045: '美食', 10046: '偶像',
        10047: '乙女', 10048: '职场'
    }

    # 伪装成浏览器的请求头
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://www.bilibili.com/'
    }

    def __init__(self, pages_to_fetch=4, pagesize=820):
        """
        构造函数。

        Args:
            pages_to_fetch (int): 每次抓取时要请求的页数。
            pagesize (int): 每页请求的数据条目数 (B站API似乎有上限)。
        """
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.pages_to_fetch = pages_to_fetch
        self.pagesize = pagesize
        self.style_map = self.STYLE_MAP
        print(f"--- 管理器已初始化：将抓取 {self.pages_to_fetch} 页，每页最多 {self.pagesize} 条 ---")
        print(f"--- 已内置 {len(self.style_map)} 个番剧风格 ---")

    @staticmethod
    def _convert_order_to_int(order_str: str) -> int:
        """
        静态工具方法，用于将接口返回的 'order' 字段（如 "9.9亿" 的播放量）转换为整数。

        Args:
            order_str (str): 原始的、可能带单位的数字字符串。

        Returns:
            int: 转换后的整数。
        """
        if not isinstance(order_str, str): return 0
        # 使用正则表达式提取数字部分
        num_match = re.search(r'(\d+(\.\d+)?)', order_str)
        if not num_match: return 0
        num = float(num_match.group(1))
        if '亿' in order_str: return int(num * 100_000_000)
        if '万' in order_str: return int(num * 10_000)
        return int(num)

    def _fetch_pages(self, order_type: int, style_id: int) -> tuple[list, int]:
        """
        一个内部方法，用于分页抓取指定排序类型和风格的数据。
        """
        all_items, total_count = [], 0
        # --- 修改：为 style_id=-1 提供 "全部" 标签 ---
        style_name = self.style_map.get(style_id, "全部" if style_id == -1 else f"未知ID {style_id}")
        print(f"--- 正在抓取风格为“{style_name}”的数据 ---")

        for i in range(1, self.pages_to_fetch + 1):
            # API请求参数
            params = {
                'st': 1, 'order': order_type, 'season_version': -1, 'spoken_language_type': -1,
                'area': -1, 'is_finish': -1, 'copyright': -1, 'season_status': -1,
                'season_month': -1, 'year': -1, 'style_id': style_id, 'sort': 0,
                'season_type': 1, 'type': 1,
                'page': i, 'pagesize': self.pagesize
            }
            try:
                response = self.session.get(self.BASE_API_URL, params=params, timeout=15)
                response.raise_for_status()
                data = response.json()
                if data.get('code') == 0 and 'data' in data:
                    api_data = data['data']
                    page_list = api_data.get('list', [])
                    # 仅在第一页获取总数
                    if i == 1 and 'total' in api_data: total_count = api_data['total']
                    print(f"  ✅ 成功获取第 {i} 页，共 {len(page_list)} 条。")
                    all_items.extend(page_list)
                    if len(page_list) < self.pagesize:
                        break
                else:
                    print(f"  ❌ 第 {i} 页API返回错误: {data.get('message', '未知错误')}")
                    break
                time.sleep(2)
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                print(f"  ❌ 第 {i} 页请求或解析失败: {e}")
                break
        return all_items, total_count

    def update_rank_cache(self) -> dict | None:
        """
        核心功能：更新排名缓存文件 (rank_cache.json)。
        """
        print("🚀 [任务: 更新排名缓存]")

        all_bangumis = {}

        # --- 1. 获取全量番剧列表作为基础数据 ---
        base_list, _ = self._fetch_pages(order_type=2, style_id=-1)
        if not base_list:
            print("❌ 无法获取基础番剧列表，任务终止。")
            return None

        # --- 2. 初始化所有番剧，并设置空的 styles 列表 ---
        for item in base_list:
            season_id = item.get('season_id')
            if not season_id: continue
            item['styles'] = []  # 初始化为空列表
            item['views'] = self._convert_order_to_int(item.get('order', '0'))
            all_bangumis[season_id] = item

        print(f"\n--- 已获取 {len(all_bangumis)} 部番剧作为基础数据，开始填充风格信息 ---")

        # --- 3. 遍历所有具体风格，为已有番剧填充风格 ---
        if not self.style_map:
            print("⚠️ 警告: 没有可用的风格数据，将仅保存无风格的番剧列表。")
        else:
            for style_id, style_name in self.style_map.items():
                style_list, _ = self._fetch_pages(order_type=2, style_id=style_id)

                for item in style_list:
                    season_id = item.get('season_id')
                    if season_id in all_bangumis:
                        # 如果番剧已在我们的基础列表里，追加风格
                        if style_name not in all_bangumis[season_id]['styles']:
                            all_bangumis[season_id]['styles'].append(style_name)

        # --- 4. 获取全量追番数据并合并 ---
        print("\n--- 开始获取全量追番数据以合并 ---")
        favorites_list, _ = self._fetch_pages(order_type=3, style_id=-1)
        favorites_map = {item['season_id']: self._convert_order_to_int(item.get('order', '0')) for item in
                         favorites_list}

        for season_id, item in all_bangumis.items():
            item['favorites'] = favorites_map.get(season_id, 0)

        # --- 5. 写入文件 ---
        merged_list = list(all_bangumis.values())
        cache_data = {"total": len(merged_list), "list": merged_list,
                      "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

        try:
            with open(self.RANK_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=4)
            print(f"\n🎉 成功！排名缓存已更新到 '{self.RANK_CACHE_FILE}'，总计 {len(merged_list)} 条独立番剧。")
            return cache_data
        except IOError as e:
            print(f"❌ 写入排名缓存失败: {e}")
            return None

    def run_monthly_aggregation(self):
        """
        执行月度聚合任务。
        这个任务会先调用 update_rank_cache() 获取最新的数据，然后对数据进行汇总，
        最后将聚合结果写入一个以月份命名的JSON文件。
        """
        print("=" * 60)
        print(f"📅 [任务: 月度聚合] at {datetime.now()}")
        print("=" * 60)

        # 聚合前，总是先获取一次最新数据
        latest_rank_data = self.update_rank_cache()

        if not latest_rank_data or not latest_rank_data.get('list'):
            print("❌ 未能获取到番剧数据，月度聚合任务终止。")
            return

        bangumi_list = latest_rank_data['list']

        # 计算总追番和总播放
        total_favorites = sum(item.get('favorites', 0) for item in bangumi_list)
        total_views = sum(item.get('views', 0) for item in bangumi_list)

        print("\n📊 数据聚合完成:")
        print(f"  - 总追番数 (Total Favorites): {total_favorites:,}")
        print(f"  - 总播放量 (Total Views):     {total_views:,}")

        current_month = datetime.now().month
        output_filename = f"rank_fetcher_{current_month}th.json"
        output_filepath = os.path.join(CURRENT_DIR, output_filename)
        aggregated_data = {
            "month": current_month,
            "calculation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_favorites": total_favorites,
            "total_views": total_views,
            "source_bangumi_count": len(bangumi_list)
        }

        try:
            with open(output_filepath, 'w', encoding='utf-8') as f:
                json.dump(aggregated_data, f, ensure_ascii=False, indent=4)
            print(f"\n✅ 成功！聚合数据已写入文件: '{output_filepath}'")
        except IOError as e:
            print(f"\n❌ 写入月度聚合文件失败: {e}")


def main():
    """
    主函数，用于解析命令行参数并执行相应操作。
    """
    # 使用 argparse 创建命令行接口
    parser = argparse.ArgumentParser(
        description="B站番剧数据管理器。可以更新排名缓存或执行月度聚合。",
        formatter_class=argparse.RawTextHelpFormatter
    )
    # 添加必须的位置参数 'action'
    parser.add_argument(
        "action",
        choices=['fetch', 'aggregate', 'schedule'],
        help=(
            "执行的操作:\n"
            "  fetch      - 仅抓取最新排名数据并更新 rank_cache.json。\n"
            "  aggregate  - 执行一次月度聚合任务（先fetch，再计算总和并保存）。\n"
            "  schedule   - 启动定时调度器，在每个月1号自动执行聚合任务。"
        )
    )
    # 添加可选参数 '--pages'，并提供默认值
    parser.add_argument(
        "--pages",
        type=int,
        default=5,
        help="指定要抓取的页数，默认为5。"
    )
    args = parser.parse_args()

    # 使用命令行传入的pages参数实例化管理器
    manager = BangumiDataManager(pages_to_fetch=args.pages)

    # 根据action参数执行不同逻辑
    if args.action == 'fetch':
        manager.update_rank_cache()
    elif args.action == 'aggregate':
        manager.run_monthly_aggregation()
    elif args.action == 'schedule':
        # 配置定时任务调度器
        scheduler = BlockingScheduler(timezone="Asia/Shanghai")
        # 'cron' 表示这是一个定时任务，在每月的第1天的凌晨2点触发
        scheduler.add_job(manager.run_monthly_aggregation, 'cron', day=1, hour=2)

        print("🚀 月度定时调度器已启动。")
        print("🕒 任务将在每个月的1号凌晨2点运行。")
        print(" (按 Ctrl+C 退出程序)")

        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            print("\n🛑 调度器已停止。")


if __name__ == "__main__":
    main()
