"""爬虫包通用辅助工具。"""

import re
from datetime import datetime, timedelta
from typing import Any


def convert_order_to_int(order_str: Any) -> int:
    """将带单位的热度字符串转换为整数。

    参数:
        order_str: 原始热度文本，可能包含“万”“亿”等单位。

    返回:
        解析后的整数值；无法解析时返回 0。
    """
    if not isinstance(order_str, str):
        return 0
    num_match = re.search(r"(\d+(\.\d+)?)", order_str)
    if not num_match:
        return 0
    num = float(num_match.group(1))
    if "亿" in order_str:
        return int(num * 100_000_000)
    if "万" in order_str:
        return int(num * 10_000)
    return int(num)


def is_valid_main_episode(episode: dict[str, Any]) -> bool:
    """判断分集是否属于正片。

    参数:
        episode: 单集信息字典。

    返回:
        若为正片返回 True，否则返回 False。
    """
    badge = episode.get("badge", "")
    if badge in ["预告", "PV", "CM", "特报", "花絮"]:
        return False

    title = episode.get("title", "")
    long_title = episode.get("long_title", "")
    combined_title = f"{title} {long_title}"

    invalid_keywords = ["预告", "PV", "NCOP", "NCED", "先行图", "总集篇"]
    return all(keyword not in combined_title for keyword in invalid_keywords)


def get_quarter_month(month: int) -> int | None:
    """根据月份返回季度首月。

    参数:
        month: 月份（1-12）。

    返回:
        所属季度首月；输入非法时返回 None。
    """
    if 1 <= month <= 3:
        return 1
    if 4 <= month <= 6:
        return 4
    if 7 <= month <= 9:
        return 7
    if 10 <= month <= 12:
        return 10
    return None


def parse_release_date_from_order(order_str: Any) -> tuple[Any | None, int | None]:
    """从开播文案中提取年份与季度首月。

    参数:
        order_str: B 站接口返回的开播相关文本。

    返回:
        (year, quarter_month) 元组；year 可能为整数或“敬请期待/更早”。
    """
    if not isinstance(order_str, str) or not order_str.strip():
        return None, None

    if "敬请期待" in order_str:
        return "敬请期待", None

    if "昨日开播" in order_str:
        yesterday = datetime.now() - timedelta(days=1)
        return yesterday.year, get_quarter_month(yesterday.month)

    year_only_match = re.search(r"(\d{4})开播", order_str)
    if year_only_match:
        year_only = int(year_only_match.group(1))
        if year_only < 2015:
            return "更早", None
        return None, None

    match = re.search(r"(?:(\d{2,4})年)?(\d+)月", order_str)
    if not match:
        return None, None

    year_str, month_str = match.groups()
    month = int(month_str)
    quarter_month = get_quarter_month(month)
    if quarter_month is None:
        return None, None

    year: int | None = None
    if year_str:
        year = int(year_str)
        if year < 100:
            current_yy = datetime.now().year % 100
            year = (1900 + year) if year > current_yy else (2000 + year)
        if year < 2015:
            return "更早", None

    return year, quarter_month


def read_proto_varint(buf: bytes, start: int) -> tuple[int | None, int]:
    """读取 protobuf varint。

    参数:
        buf: 原始二进制缓冲区。
        start: 起始偏移量。

    返回:
        (解析后的整数值或 None, 下一偏移量) 元组。
    """
    value = 0
    shift = 0
    offset = start
    while offset < len(buf):
        byte = buf[offset]
        value |= (byte & 0x7F) << shift
        offset += 1
        if (byte & 0x80) == 0:
            return value, offset
        if shift >= 63:
            return None, offset
        shift += 7
    return None, offset
