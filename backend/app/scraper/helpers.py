"""Helper utilities for scraper package."""

import re
from datetime import datetime, timedelta
from typing import Any


def convert_order_to_int(order_str: Any) -> int:
    """将 B 站 API 返回的带单位数字字符串转换为整数。"""
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
    """根据 API 返回字段判断是否为正片。"""
    badge = episode.get("badge", "")
    if badge in ["预告", "PV", "CM", "特报", "花絮"]:
        return False

    title = episode.get("title", "")
    long_title = episode.get("long_title", "")
    combined_title = f"{title} {long_title}"

    invalid_keywords = ["预告", "PV", "NCOP", "NCED", "先行图", "总集篇"]
    return all(keyword not in combined_title for keyword in invalid_keywords)


def get_quarter_month(month: int) -> int | None:
    """根据月份获取季度首月。"""
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
    """从 order 字符串解析发布日期，返回 (year, quarter_month)。"""
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
    """读取 protobuf varint，返回 (value, next_offset)。"""
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
