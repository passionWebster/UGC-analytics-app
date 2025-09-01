# data_manager.py
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from typing import Tuple, List, Dict, Any

import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from tqdm import tqdm

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))


class BangumiDataManager:
    """
    一个统一的数据管理模块，负责：
    1. 从B站API按不同风格、不同时间批量抓取番剧排名数据。
    2. 为每部番剧添加风格数组和发布时间数组。
    3. 合并播放量和追番量，生成 rank_cache.json。
    4. 对排名数据进行月度聚合，并生成月度报告JSON文件。
    """

    # B站番剧索引API的URL
    BASE_API_URL = "https://api.bilibili.com/pgc/season/index/result"
    # 最终生成的排名缓存文件名
    RANK_CACHE_FILE = os.path.join(CURRENT_DIR, 'rank_cache.json')

    # 存储所有已知的风格ID及其对应的中文名称
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

    # 常规番剧API（season_type=1）支持的风格ID集合
    REGULAR_API_STYLE_IDS = {
        10010, 10011, 10012, 10013, 10102, 10015, 10016, 10017, 10018, 10020,
        10021, 10022, 10023, 10024, 10025, 10026, 10027, 10028, 10029, 10030,
        10031, 10032, 10033, 10034, 10035, 10036, 10037, 10038, 10039, 10040,
        10041, 10042, 10043, 10044, 10045, 10046, 10047, 10048
    }
    # 国产番剧API（season_type=4）支持的风格ID集合
    DOMESTIC_API_STYLE_IDS = {
        10010, 10011, 10012, 10013, 10014, 10015, 10016, 10018, 10019, 10020,
        10021, 10078, 10022, 10023, 10024, 10025, 10057, 10026, 10027, 10028,
        10029, 10030, 10031, 10033, 10035, 10036, 10037, 10038, 10039, 10040,
        10041, 10042, 10043, 10044, 10045, 10046, 10047, 10048, 10049
    }

    # 伪装成浏览器的请求头
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://www.bilibili.com/'
    }

    def __init__(self, pages_to_fetch=5, pagesize=820):
        """
        BangumiDataManager类的构造函数。
        负责初始化requests会话、设置抓取参数，并打印初始化信息。

        Args:
            pages_to_fetch (int): 在单次抓取任务中，对每个分类要请求的最大页数。
            pagesize (int): 每一页请求的数据条目数。
        """
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.pages_to_fetch = pages_to_fetch
        self.pagesize = pagesize
        self.style_map = self.STYLE_MAP
        print(f"--- 管理器已初始化：将抓取 {self.pages_to_fetch} 页，每页最多 {self.pagesize} 条 ---")
        print(f"--- 已内置 {len(self.style_map)} 个番剧风格 ---")

    @staticmethod
    def _convert_order_to_int(order_str: Any) -> int:
        """
        静态工具方法，用于将B站API返回的、可能带单位的数字字符串（如 "9.9亿"）转换为整数。
        能处理 '亿' 和 '万' 单位，对于不含单位的纯数字字符串也能正确转换。

        Args:
            order_str (Any): 原始的、可能为任意类型的输入，通常是描述播放量或追番量的字符串。

        Returns:
            int: 转换后的整数。如果输入非字符串或无法解析，则返回0。
        """
        if not isinstance(order_str, str): return 0
        num_match = re.search(r'(\d+(\.\d+)?)', order_str)
        if not num_match: return 0
        num = float(num_match.group(1))
        if '亿' in order_str: return int(num * 100_000_000)
        if '万' in order_str: return int(num * 10_000)
        return int(num)

    @staticmethod
    def _get_quarter_month(month: int) -> int | None:
        """
        辅助静态方法，用于根据月份计算其所属季度的起始月份。
        此方法将1-12的整数月份映射到对应的季度。B站API通常使用季度首月（1月、4月、7月、10月）作为筛选参数，此方法正是为了生成该参数。

        Args:
            month (int): 一个表示月份的整数（通常为1-12）。

        Returns:
            int | None: 如果输入月份有效，则返回其所属季度的起始月份（1, 4, 7, 10）；如果输入无效，则返回 None。
        """
        if 1 <= month <= 3:
            return 1
        elif 4 <= month <= 6:
            return 4
        elif 7 <= month <= 9:
            return 7
        elif 10 <= month <= 12:
            return 10
        else:
            return None  # 无效月份

    @staticmethod
    def _parse_release_date_from_order(order_str: Any) -> Tuple[int | str | None, int | None]:
        """
        静态工具方法，用于从B站API返回的 'order' 字符串中解析出年份和季度月份。
        能处理 "21年11月开播"、"6月28日开播" 和 "敬请期待" 等多种格式。

        Args:
            order_str (Any): 原始的 'order' 字段字符串。

        Returns:
            Tuple[int | str | None, int | None]: 一个包含年份和季度月份的元组 (year, quarter_month)。
                                           如果某部分无法解析，则对应值为 None。
        """
        # 检查是否为非字符串或空字符串/空白字符串
        if not isinstance(order_str, str) or not order_str.strip():
            return None, None

        # 处理 "敬请期待" 和 "敬请期待开播"
        if "敬请期待" in order_str:
            return "敬请期待", None

        # 处理 "昨日开播"
        if "昨日开播" in order_str:
            yesterday = datetime.now() - timedelta(days=1)
            year = yesterday.year
            month = yesterday.month
            quarter_month = BangumiDataManager._get_quarter_month(month)
            return year, quarter_month
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

        year = None
        month = int(month_str)
        quarter_month = BangumiDataManager._get_quarter_month(month)

        if quarter_month is None:
            return None, None

        # 解析并转换年份
        if year_str:
            year = int(year_str)
            if year < 100:  # 处理两位数年份
                current_yy = datetime.now().year % 100
                year = (1900 + year) if year > current_yy else (2000 + year)
            if year < 2015:
                return "更早", None
        return year, quarter_month

    def _execute_fetch_task(self, task_name: str, base_params: Dict[str, Any], pbar: tqdm = None) -> Tuple[
        List[Dict[str, Any]], int]:
        """
        统一的数据抓取执行器，封装了分页请求、响应解析、错误处理和进度显示的通用逻辑。
        这是所有抓取方法的核心。

        Args:
            task_name (str): 当前执行的任务名称，用于在控制台打印。
            base_params (Dict[str, Any]): API请求的基础参数字典，不包含 'page' 和 'pagesize'。
            pbar (tqdm, optional): 外部传入的tqdm进度条对象。如果提供，则任务描述会更新到此进度条上。默认为 None。

        Returns:
            Tuple[List[Dict[str, Any]], int]: 一个元组，第一个元素是抓取到的所有数据项的列表，第二个元素是API报告的总数据条数。
        """
        all_items, total_count = [], 0

        # 对于非tqdm模式，仅在开始时打印任务标题
        if not pbar:
            print(f"--- {task_name} ---")

        # 为tqdm的postfix（后缀）构建上下文信息字符串
        context_str = ""
        if pbar:
            context_details = []
            # 提取风格信息
            style_id = base_params.get('style_id', -1)
            if style_id != -1:
                style_name = self.style_map.get(style_id, f'ID {style_id}')
                context_details.append(f"风格: {style_name}")

            # 提取年份信息
            year = base_params.get('year', '-1')
            if year != '-1':
                year_display = str(year).split(',')[0].strip('[')
                context_details.append(f"年份: {year_display}")
            elif base_params.get('st') == 4 and base_params.get('order') == 5:
                context_details.append("年份: 全部")
            area = base_params.get('area', -1)
            if area != -1:
                area_map = {2: "日本", 3: "美国"}
                context_details.append(f"地区: {area_map.get(area, '其他')}")
            is_full_ranking_task = all(base_params.get(k, -1) in ('-1', -1) for k in ['year', 'style_id', 'area'])
            if is_full_ranking_task:
                order = base_params.get('order', -1)
                st = base_params.get('st', -1)
                scope_map = {1: "常规番剧", 4: "国产番剧"}
                scope = scope_map.get(st, "未知范围")
                if order == 2: context_details.append(f"排序: 播放量 ({scope})")
                if order == 3: context_details.append(f"排序: 追番量 ({scope})")
            context_str = " | ".join(context_details)

        for i in range(1, self.pages_to_fetch + 1):
            if pbar:
                # 组合成完整的后缀字符串并更新进度条
                postfix = f"当前任务: [{context_str}] | 页数: {i}/{self.pages_to_fetch} | 已获数据: {len(all_items)}"
                pbar.set_postfix_str(postfix, refresh=True)

            params = base_params.copy()
            params.update({'page': i, 'pagesize': self.pagesize})

            try:
                response = self.session.get(self.BASE_API_URL, params=params, timeout=15)
                response.raise_for_status()
                data = response.json()

                if data.get('code') == 0 and 'data' in data:
                    api_data = data['data']
                    page_list = api_data.get('list', [])

                    if i == 1 and 'total' in api_data:
                        total_count = api_data.get('total', 0)
                    if not pbar: print(f"  ✅ 成功获取第 {i} 页，共 {len(page_list)} 条。")
                    all_items.extend(page_list)

                    if pbar:
                        # 获取到总数后，更新后缀信息以包含总数
                        postfix = f"当前任务: [{context_str}] | 页数: {i}/{self.pages_to_fetch} | 已获数据: {len(all_items)}/{total_count}"
                        pbar.set_postfix_str(postfix, refresh=True)

                    if not api_data.get('has_next', 0):
                        break
                    time.sleep(2)
                else:
                    if not pbar: print(f"  ❌ 第 {i} 页API返回错误: {data.get('message', '未知错误')}")
                    break
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                if not pbar: print(f"  ❌ 第 {i} 页请求或解析失败: {e}")
                break
        return all_items, total_count

    def _fetch_pages(self, order_type: int, style_id: int, year: str = '-1', season_month: int = -1, area: int = -1,
                     pbar: tqdm = None) -> Tuple[List, int]:
        """
        抓取常规番剧数据（非国产，season_type=1）。这是一个具体任务的封装，负责构建参数并调用执行器。

        Args:
            order_type (int): 排序类型 (例如, 2=播放量, 3=追番)。
            style_id (int): 风格ID (-1 表示全部)。
            year (str): 年份字符串 (例如, "2023", "-1" 表示全部)。
            season_month (int): 季度月份 (例如, 1, 4, 7, 10, -1 表示全部)。
            area (int): 地区ID (-1 表示全部, 2=日本, 3=美国)。
            pbar (tqdm, optional): 外部传入的tqdm进度条对象。默认为 None。

        Returns:
            Tuple[List, int]: 抓取到的番剧数据列表和总数。
        """
        style_name = self.style_map.get(style_id, "全部" if style_id == -1 else f"未知ID {style_id}")
        time_desc = f"年份: {'全部' if year == '-1' else year}, 月份: {'全部' if season_month == -1 else season_month}"
        area_name = {2: ", 地区: 日本", 3: ", 地区: 美国"}.get(area, "")
        task_name = f"抓取常规番剧, 风格“{style_name}”, {time_desc}{area_name}"
        params = {
            'st': 1, 'order': order_type, 'season_version': -1, 'spoken_language_type': -1,
            'area': area, 'is_finish': -1, 'copyright': -1, 'season_status': -1,
            'season_month': season_month, 'year': year, 'style_id': style_id, 'sort': 0,
            'season_type': 1, 'type': 1
        }
        return self._execute_fetch_task(task_name, params, pbar)

    def _fetch_domestic_pages(self, year: str = '-1', pbar: tqdm = None) -> Tuple[List, int]:
        """
        按年份抓取国产番剧列表（season_type=4）。

        Args:
            year (str): 年份字符串 ("-1" 表示全部)。
            pbar (tqdm, optional): 外部传入的tqdm进度条对象。默认为 None。

        Returns:
            Tuple[List, int]: 抓取到的国产番剧数据列表和总数。
        """
        task_name = f"抓取国产番剧, 年份: {'全部' if year == '-1' else year}"
        params = {
            'season_version': -1, 'is_finish': -1, 'copyright': -1, 'season_status': -1,
            'year': year, 'style_id': -1, 'order': 5, 'st': 4, 'sort': 0, 'season_type': 4, 'type': 1
        }
        return self._execute_fetch_task(task_name, params, pbar)

    def _fetch_domestic_ranking_pages(self, order_type: int, pbar: tqdm = None) -> Tuple[List, int]:
        """
        抓取国产番剧的全量排名数据（按播放或追番）。

        Args:
            order_type (int): 排序类型 (2=播放量, 3=追番)。
            pbar (tqdm, optional): 外部传入的tqdm进度条对象。默认为 None。

        Returns:
            Tuple[List, int]: 抓取到的国产番剧数据列表和总数。
        """
        order_name = "播放量" if order_type == 2 else "追番量"
        task_name = f"抓取国产番剧排名 ({order_name})"
        params = {
            'season_version': -1, 'is_finish': -1, 'copyright': -1, 'season_status': -1,
            'year': '-1', 'style_id': -1, 'order': order_type, 'st': 4, 'sort': 0, 'season_type': 4, 'type': 1
        }
        return self._execute_fetch_task(task_name, params, pbar)

    def _fetch_domestic_style_pages(self, style_id: int, pbar: tqdm = None) -> Tuple[List, int]:
        """
        按风格ID抓取国产番剧列表。

        Args:
            style_id (int): 国产番剧的风格ID。
            pbar (tqdm, optional): 外部传入的tqdm进度条对象。默认为 None。

        Returns:
            Tuple[List, int]: 抓取到的国产番剧数据列表和总数。
        """
        style_name = self.style_map.get(style_id, f"未知ID {style_id}")
        task_name = f"抓取国产番剧, 风格“{style_name}”"
        params = {
            'season_version': -1, 'is_finish': -1, 'copyright': -1, 'season_status': -1,
            'year': '-1', 'style_id': style_id, 'order': 2, 'st': 4, 'sort': 0, 'season_type': 4, 'type': 1
        }
        return self._execute_fetch_task(task_name, params, pbar)

    def update_rank_cache(self) -> dict | None:
        """
        核心功能：更新排名缓存文件 (rank_cache.json)。
        该函数是数据处理的主流程，依次执行以下步骤：
        1. 获取所有常规番剧的基础信息作为底库。
        2. 获取所有国产番剧的基础信息并合并到底库中。
        3. 为底库中的番剧填充地区信息（日本、美国、其他）。
        4. 根据不同API的可用风格，为番剧填充风格信息。
        5. 获取并合并所有番剧的播放量和追番量数据。
        6. 将最终整合的数据按播放量排序后，写入JSON缓存文件。

        Returns:
            dict | None: 如果成功，返回包含所有番剧信息的字典；如果中途失败，返回 None。
        """
        print("🚀 [任务: 更新排名缓存]")
        all_bangumis = {}

        years_to_scan = list(range(datetime.now().year, 2015, -1))

        # 【修改点】将 file=sys.stdout 添加到所有 tqdm 调用中，以统一输出流
        domestic_years_to_scan = [f"{year}" for year in years_to_scan]
        domestic_years_to_scan.append('-1')
        with tqdm(total=len(domestic_years_to_scan), desc="  - 正在获取国产番剧列表...", file=sys.stdout) as pbar:
            for year_str in domestic_years_to_scan:
                # 根据您的要求，格式化年份参数
                year_param_formatted = year_str
                if year_str != '-1':
                    year_int = int(year_str)
                    # 将 "2025" 格式化为 "[2025,2026)"
                    year_param_formatted = f"[{year_int},{year_int + 1})"

                domestic_list, _ = self._fetch_domestic_pages(year=year_param_formatted, pbar=pbar)

                for item in domestic_list:
                    season_id = item.get('season_id')
                    if not season_id: continue

                    if season_id not in all_bangumis:
                        # --- 修改：初始化为单一值 ---
                        item['styles'] = []
                        item['release_date'] = "更早"
                        item['area'] = "国内"
                        item['views'] = 0
                        all_bangumis[season_id] = item

                    parsed_year, parsed_month = self._parse_release_date_from_order(item.get('order', ''))
                    if parsed_year in ["敬请期待", "更早"]:
                        all_bangumis[season_id]['release_date'] = parsed_year
                        continue

                    year_to_use = parsed_year
                    if not year_to_use:  # 如果 order 字符串中没有年份，则使用循环的年份
                        year_to_use = int(year_str) if year_str != '-1' else None

                    if year_to_use and parsed_month:
                        tag = f"{year_to_use}-{parsed_month:02d}"
                        all_bangumis[season_id]['release_date'] = tag

                pbar.update(1)

        # 2. 补充抓取常规番剧，跳过已存在的国产番剧
        months_to_scan = [1, 4, 7, 10]
        time_params_list = [{'year_val': year, 'month_val': month, 'year_param': f"[{year},{year + 1})"}
                            for year in years_to_scan for month in months_to_scan]
        time_params_list.append({'year_val': -1, 'month_val': -1, 'year_param': '-1'})
        with tqdm(total=len(time_params_list), desc="  - 正在获取常规番剧列表...", file=sys.stdout) as pbar:
            for params in time_params_list:
                time_based_list, _ = self._fetch_pages(order_type=2, style_id=-1, year=params['year_param'],
                                                       season_month=params['month_val'], pbar=pbar)
                for item in time_based_list:
                    season_id = item.get('season_id')
                    if not season_id: continue

                    if season_id in all_bangumis:
                        continue

                    # --- 修改：初始化为单一值 ---
                    item['styles'] = []
                    item['release_date'] = "更早" if params[
                                                         'year_val'] == -1 else f"{params['year_val']}-{params['month_val']:02d}"
                    item['area'] = "其他"
                    item['views'] = self._convert_order_to_int(item.get('order', '0'))
                    all_bangumis[season_id] = item

                pbar.update(1)

        if not all_bangumis:
            print("❌ 未能获取到任何番剧数据，任务终止。")
            return None

        with tqdm(total=1, desc="  - 正在获取日本地区番剧...", file=sys.stdout) as pbar:
            japan_list, _ = self._fetch_pages(order_type=2, style_id=-1, area=2, pbar=pbar)
            pbar.update(1)
        with tqdm(total=1, desc="  - 正在获取美国地区番剧...", file=sys.stdout) as pbar:
            usa_list, _ = self._fetch_pages(order_type=2, style_id=-1, area=3, pbar=pbar)
            pbar.update(1)

        print("\n--- 正在标记地区信息 ---")
        japan_anime_ids = {item.get('season_id') for item in japan_list if item.get('season_id')}
        usa_anime_ids = {item.get('season_id') for item in usa_list if item.get('season_id')}
        for season_id, item in all_bangumis.items():
            if item['area'] == '国内': continue
            if season_id in japan_anime_ids:
                item['area'] = '日本'
            elif season_id in usa_anime_ids:
                item['area'] = '美国'

        with tqdm(total=len(self.REGULAR_API_STYLE_IDS), desc="  - 正在填充常规番剧风格...", file=sys.stdout) as pbar:
            for style_id in self.REGULAR_API_STYLE_IDS:
                style_name = self.style_map.get(style_id)
                if not style_name: continue
                style_list, _ = self._fetch_pages(order_type=2, style_id=style_id, pbar=pbar)
                for item in style_list:
                    season_id = item.get('season_id')
                    if season_id in all_bangumis and style_name not in all_bangumis[season_id]['styles']:
                        all_bangumis[season_id]['styles'].append(style_name)
                pbar.update(1)

        with tqdm(total=len(self.DOMESTIC_API_STYLE_IDS), desc="  - 正在填充国产番剧风格...", file=sys.stdout) as pbar:
            for style_id in self.DOMESTIC_API_STYLE_IDS:
                style_name = self.style_map.get(style_id)
                if not style_name: continue
                style_list, _ = self._fetch_domestic_style_pages(style_id=style_id, pbar=pbar)
                for item in style_list:
                    season_id = item.get('season_id')
                    if season_id in all_bangumis and style_name not in all_bangumis[season_id]['styles']:
                        all_bangumis[season_id]['styles'].append(style_name)
                pbar.update(1)

        views_list = []
        with tqdm(total=1, desc="  - 获取常规番剧播放数据...", file=sys.stdout) as pbar:
            regular_views, _ = self._fetch_pages(order_type=2, style_id=-1, pbar=pbar)
            views_list.extend(regular_views)
            pbar.update(1)
        with tqdm(total=1, desc="  - 获取国产番剧播放数据...", file=sys.stdout) as pbar:
            domestic_views, _ = self._fetch_domestic_ranking_pages(order_type=2, pbar=pbar)
            views_list.extend(domestic_views)
            pbar.update(1)

        favorites_list = []
        with tqdm(total=1, desc="  - 获取常规番剧追番数据...", file=sys.stdout) as pbar:
            regular_favs, _ = self._fetch_pages(order_type=3, style_id=-1, pbar=pbar)
            favorites_list.extend(regular_favs)
            pbar.update(1)
        with tqdm(total=1, desc="  - 获取国产番剧追番数据...", file=sys.stdout) as pbar:
            domestic_favs, _ = self._fetch_domestic_ranking_pages(order_type=3, pbar=pbar)
            favorites_list.extend(domestic_favs)
            pbar.update(1)

        views_map = {item['season_id']: self._convert_order_to_int(item.get('order', '0')) for item in views_list}
        favorites_map = {item['season_id']: self._convert_order_to_int(item.get('order', '0')) for item in
                         favorites_list}

        for season_id, item in all_bangumis.items():
            item['views'] = views_map.get(season_id, item.get('views', 0))
            item['favorites'] = favorites_map.get(season_id, 0)

        merged_list = sorted(list(all_bangumis.values()), key=lambda x: x.get('views', 0), reverse=True)
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
        执行月度数据聚合任务。
        此任务会首先调用 `update_rank_cache()` 来获取最新的全量数据，然后对数据进行统计汇总
        （如总播放量、总追番数），最后将聚合结果写入一个以当前月份命名的JSON报告文件。
        """
        print("=" * 60)
        print(f"📅 [任务: 月度聚合] at {datetime.now()}")
        print("=" * 60)
        latest_rank_data = self.update_rank_cache()
        if not latest_rank_data or not latest_rank_data.get('list'):
            print("❌ 未能获取到番剧数据，月度聚合任务终止。")
            return
        bangumi_list = latest_rank_data['list']
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
    主函数，作为脚本的入口点。
    负责解析命令行参数，并根据用户指定的 `action` 来执行相应的操作，
    例如数据抓取 (`fetch`)、月度聚合 (`aggregate`) 或启动定时任务 (`schedule`)。
    """
    parser = argparse.ArgumentParser(
        description="B站番剧数据管理器。可以更新排名缓存或执行月度聚合。",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "action", choices=['fetch', 'aggregate', 'schedule'],
        help="执行的操作:\n"
             "  fetch      - 仅抓取最新排名数据并更新 rank_cache.json。\n"
             "  aggregate  - 执行一次月度聚合任务（先fetch，再计算总和并保存）。\n"
             "  schedule   - 启动定时调度器，在每个月1号自动执行聚合任务。"
    )
    parser.add_argument(
        "--pages", type=int, default=5, help="指定要抓取的页数，默认为5。"
    )
    args = parser.parse_args()
    manager = BangumiDataManager(pages_to_fetch=args.pages)
    if args.action == 'fetch':
        manager.update_rank_cache()
    elif args.action == 'aggregate':
        manager.run_monthly_aggregation()
    elif args.action == 'schedule':
        scheduler = BlockingScheduler(timezone="Asia/Shanghai")
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