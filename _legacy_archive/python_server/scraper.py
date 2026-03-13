# scraper.py
import json
import os
import sys
import time

import requests


def get_base_path():
    """获取应用的基础路径，兼容源码运行和PyInstaller打包运行"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))


BASE_PATH = get_base_path()
CACHE_DIR = os.path.join(BASE_PATH, 'cache')


class BilibiliBangumiScraper:
    """
    一个用于抓取Bilibili番剧信息的类。
    它封装了所有与B站API直接交互的逻辑，包括从本地缓存查找番剧ID、
    获取番剧详细信息、获取单集播放数据以及在线观看人数等。
    """
    # 基础请求头，模拟浏览器访问
    BASE_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/plain, */*'
    }

    def __init__(self, cache_dir=None):
        self.session = requests.Session()
        self.session.headers.update(self.BASE_HEADERS)

        if not cache_dir:
            print("[Scraper WARNING] cache_dir not provided, using default path.")
            self.CACHE_DIR = CACHE_DIR
        else:
            self.CACHE_DIR = cache_dir

        self.RANK_CACHE_FILE = os.path.join(self.CACHE_DIR, 'rank_cache.json')

    @staticmethod
    def _convert_chinese_number_str(num_str: str) -> int | None:
        """
        一个静态工具方法，用于将B站API返回的带单位（如"万", "亿"）的数字字符串转换为整数。
        例如: "3.4万" -> 34000。

        Args:
            num_str (str): 包含中文单位的数字字符串。

        Returns:
            int | None: 转换后的整数，如果转换失败则返回None。
        """
        if not isinstance(num_str, str):
            return None
        try:
            # 移除可能存在的"+"号和两端空格
            num_str = num_str.strip().rstrip('+')
            if '亿' in num_str: return int(float(num_str.replace('亿', '')) * 100_000_000)
            if '万' in num_str: return int(float(num_str.replace('万', '')) * 10_000)
            return int(num_str)
        except (ValueError, TypeError):
            # 如果字符串无法转换为数字，则捕获异常并返回None
            return None

    def get_bangumi_id(self, keyword: str) -> str | None:
        """
        通过本地缓存文件 rank_cache.json 查找番剧的 season_id。
        这避免了每次都进行网络搜索，提高了效率。

        Args:
            keyword (str): 要搜索的番剧名称 (title)。

        Returns:
            str | None: 如果在缓存中找到精确匹配的番剧，则返回其 season_id (字符串格式)；否则返回 None。
        """
        print(f"--- 正在从本地缓存 '{self.RANK_CACHE_FILE}' 中搜索 '{keyword}' ---")

        if not os.path.exists(self.RANK_CACHE_FILE):
            print(f"❌ 错误: 缓存文件 '{self.RANK_CACHE_FILE}' 未找到。请先运行 data_manager.py fetch。")
            return None

        try:
            with open(self.RANK_CACHE_FILE, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            for item in cache_data.get('list', []):
                if item.get('title') == keyword:
                    season_id = item.get('season_id')
                    print(f"✅ 在缓存中找到匹配项: '{keyword}' -> season_id: {season_id}")
                    return str(season_id)

            print(f"⚠️ 在缓存中未能找到标题为 '{keyword}' 的番剧。")
            return None

        except (json.JSONDecodeError, IOError) as e:
            print(f"❌ 读取或解析缓存文件时出错: {e}")
            return None

    def get_episode_views(self, bvid: str) -> int | None:
        """
        根据视频的BVID获取其总播放量。

        Args:
            bvid (str): 视频的BVID。

        Returns:
            int | None: 视频的总播放量，获取失败则返回None。
        """
        if not bvid: return None
        url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        try:
            response = self.session.get(url, timeout=5)  # 增加超时设置
            response.raise_for_status()
            data = response.json()
            if data.get('code') == 0 and 'data' in data:
                return data['data'].get('stat', {}).get('view')
            return None
        except (requests.exceptions.RequestException, ValueError) as e:
            print(f"Error in get_episode_views for bvid {bvid}: {e}")
            return None

    def get_bangumi_details(self, season_id: str) -> dict | None:
        """
        根据番剧的 season_id 获取其详细信息，包括总体统计数据和所有分集的列表。
        对于每一集，还会额外调用 get_episode_views 来获取其播放量。

        Args:
            season_id (str): 番剧的 season_id。

        Returns:
            dict | None: 包含番剧统计数据和分集详细信息的字典，获取失败则返回None。
        """
        if not season_id: return None
        url = f"https://api.bilibili.com/pgc/view/web/season?season_id={season_id}"
        try:
            response = self.session.get(url, timeout=10)  # 增加超时设置
            response.raise_for_status()
            data = response.json()
            if data.get('code') == 0 and 'result' in data:
                result = data['result']
                stats = result.get('stat', {})
                episodes = result.get('episodes', [])

                episodes_details = []
                print(f"  -> 正在获取 '{result.get('title')}' 的 {len(episodes)} 集详细信息...")
                for episode in episodes:
                    bvid = episode.get('bvid')
                    # 确保bvid和cid都存在
                    if bvid and episode.get('cid'):
                        time.sleep(0.2)  # 保持礼貌的请求间隔
                        episode_views = self.get_episode_views(bvid)
                        episodes_details.append({
                            'title': episode.get('long_title', ''),
                            'bvid': bvid,
                            'cid': episode.get('cid'),
                            'views': episode_views
                        })

                return {
                    'title': result.get('title'),  # 优化：将标题也一并返回
                    'cover': result.get('cover'),  # 优化：将封面图URL也返回
                    'stats': {'favorites': stats.get('favorites'),
                              'views': stats.get('views')},
                    'episodes': episodes_details
                }
            return None
        except (requests.exceptions.RequestException, ValueError) as e:
            print(f"Error in get_bangumi_details for season_id {season_id}: {e}")
            return None

    def get_online_viewers(self, bvid: str, cid: str) -> int | None:
        """
        获取指定视频（通过bvid和cid定位）的当前在线观看人数。

        Args:
            bvid (str): 视频的BVID。
            cid (str): 视频的CID (弹幕ID)。

        Returns:
            int | None: 当前在线人数，获取失败则返回None。
        """
        if not bvid or not cid: return None
        url = "https://api.bilibili.com/x/player/online/total"
        params = {'bvid': bvid, 'cid': str(cid)}
        try:
            response = self.session.get(url, params=params, timeout=5)  # 增加超时设置
            response.raise_for_status()
            data = response.json()
            if data.get('code') == 0 and 'data' in data:
                # API返回的数据可能包含 "万" 等单位，需要转换
                return self._convert_chinese_number_str(data['data'].get('total'))
            return None
        except (requests.exceptions.RequestException, ValueError) as e:
            print(f"Error in get_online_viewers for bvid {bvid}: {e}")
            return None

    def get_full_details_by_keyword(self, keyword: str) -> dict | None:
        """
        这是一个高级封装函数，通过一个关键词完成从“查找ID”到“获取详情”的完整流程。

        Args:
            keyword (str): 番剧的名称。

        Returns:
            dict | None: 完整的番剧详情字典，如果任何一步失败则返回None。
        """
        if bangumi_id := self.get_bangumi_id(keyword):
            return self.get_bangumi_details(bangumi_id)
        return None

    def health_check(self, keyword: str = "碧蓝之海 第二季"):
        """
        提供一个简单的健康检查功能，用于快速验证此类中的核心API是否仍然可用。
        它会依次测试获取ID、获取详情、获取在线人数等关键步骤。

        Args:
            keyword (str): 用于测试的番剧名，默认为 "碧蓝之海 第二季"。
        """
        print("=" * 50)
        print(f"🚀 开始执行 Bilibili Scraper 健康检查 (目标: {keyword})")
        print("=" * 50)
        errors = []

        # 1. 测试从缓存获取ID
        print("\n[1/4] 正在测试: 从本地缓存搜索番剧并获取 Season ID...")
        season_id = self.get_bangumi_id(keyword)
        if season_id and season_id.isdigit():
            print(f"  ✅ 成功: 获取到 Season ID -> {season_id}")
        else:
            print(f"  ❌ 失败: 未能获取有效的 Season ID。")
            errors.append("get_bangumi_id")
            self._print_summary(errors)
            return

        # 2. 测试获取番剧详情
        print("\n[2/4] 正在测试: 获取番剧详情 (包括统计和单集播放量)...")
        details = self.get_bangumi_details(season_id)
        if (details and isinstance(details.get('stats'), dict) and
                isinstance(details.get('episodes'), list) and len(details['episodes']) > 0):
            print("  ✅ 成功: 已获取番剧详情。")
        else:
            print(f"  ❌ 失败: 未能获取有效的番剧详情。")
            errors.append("get_bangumi_details / get_episode_views")
            self._print_summary(errors)
            return

        # 3. 测试获取在线人数
        print("\n[3/4] 正在测试: 获取单集在线人数...")
        first_episode = details['episodes'][0]
        bvid = first_episode.get('bvid')
        cid = first_episode.get('cid')
        online_count = self.get_online_viewers(bvid, cid)
        if online_count is not None and isinstance(online_count, int):
            print(f"  ✅ 成功: 获取到在线人数 -> {online_count}")
        else:
            print(f"  ❌ 失败: 未能获取有效的在线人数。")
            errors.append("get_online_viewers")

        # 4. 打印总结
        print("\n[4/4] 健康检查结束。")
        self._print_summary(errors)

    @staticmethod
    def _print_summary(errors):
        """
        一个静态工具方法，用于格式化输出健康检查的最终结果。
        """
        print("=" * 50)
        print("📊 健康检查总结")
        print("=" * 50)
        if not errors:
            print("🎉🎉🎉 所有功能均检测正常！系统运行良好。")
        else:
            print(f"🔥🔥🔥 检测到 {len(errors)} 个问题，请检查以下功能:")
            for error_func in errors:
                print(f"  - {error_func}")
        print("=" * 50)


# 当此文件作为主脚本直接运行时，执行健康检查
if __name__ == "__main__":
    scraper = BilibiliBangumiScraper()
    scraper.health_check()
