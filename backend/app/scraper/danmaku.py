"""Danmaku fetch, parse and signature service."""

from __future__ import annotations

import hashlib
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from functools import reduce
from typing import TYPE_CHECKING, Any

from ..config import settings
from ..logger import scraper_logger as logger
from .constants import (
    DM_HISTORY_STOP_CODES as SCRAPER_DM_HISTORY_STOP_CODES,
)
from .constants import (
    MIXIN_KEY_ENC_TAB as SCRAPER_MIXIN_KEY_ENC_TAB,
)
from .helpers import read_proto_varint

if TYPE_CHECKING:
    from .crawler import BilibiliBangumiCrawler


class DanmakuService:
    """Handle current/history danmaku crawling and payload normalization."""

    _MIXIN_KEY_ENC_TAB = SCRAPER_MIXIN_KEY_ENC_TAB
    _wbi_keys_cache: tuple[str, str] | None = None
    _wbi_keys_fetched_at: float | None = None
    _WBI_CACHE_TTL = 3600
    DM_HISTORY_STOP_CODES = SCRAPER_DM_HISTORY_STOP_CODES

    def __init__(self, crawler: BilibiliBangumiCrawler) -> None:
        """Bind the service to the shared crawler runtime context.

        Args:
            crawler: Shared scraper facade providing session, request helpers and config.
        """
        self._crawler = crawler

    def __getattr__(self, name: str) -> Any:
        """Fallback unknown attributes to the shared crawler facade."""
        return getattr(self._crawler, name)

    def __setattr__(self, name: str, value: Any) -> None:
        """Route unknown attribute writes to the shared crawler facade."""
        if name == "_crawler" or "_crawler" not in self.__dict__:
            object.__setattr__(self, name, value)
            return
        if hasattr(type(self), name):
            object.__setattr__(self, name, value)
            return
        setattr(self._crawler, name, value)

    def fetch_danmaku_xml(self, cid: str) -> list[dict[str, Any]]:
        """
        通过 B站弹幕 XML 接口获取当前弹幕池。

        Args:
            cid: 分 P 的弹幕 ID

        Returns:
            弹幕记录列表。
            其中 progress/ctime/sender_hash 为新字段，video_time/timestamp 为兼容字段。
        """
        url = f"https://comment.bilibili.com/{cid}.xml"
        try:
            resp = self._request_get(url, timeout=settings.bilibili_request_timeout)
            if resp is None:
                return []
            resp.encoding = "utf-8"
            return self._parse_danmaku_xml_payload(
                cid=cid,
                xml_text=resp.text,
                source="current_pool",
            )
        except Exception as exc:
            logger.exception("❌ 获取当前弹幕失败 cid={}: {}", cid, exc)
        return []

    def fetch_danmaku_history(
        self, cid: str, *, publish_ts: int | None = None
    ) -> list[dict[str, Any]]:
        """
        抓取历史弹幕（需要 SESSDATA）。

        通过 history/index 获取可用日期，再逐日抓取 protobuf。
        """
        if not (settings.bilibili_sessdata or "").strip():
            return []

        index_url = "https://api.bilibili.com/x/v2/dm/history/index"
        all_dates: list[str] = []
        months = self._iter_history_months(publish_ts)
        logger.info("🗓️ 开始抓取历史弹幕日期索引 cid={} months={}", cid, len(months))

        for idx, month in enumerate(months, start=1):
            logger.info("  📅 索引进度 cid={} month={}/{} ({})", cid, idx, len(months), month)
            resp = self._request_get(
                index_url,
                params={"type": 1, "oid": str(cid), "month": month},
                timeout=settings.bilibili_request_timeout,
            )
            if resp is None:
                logger.warning("⚠️ 历史弹幕日期索引请求失败 cid={} month={}", cid, month)
                continue
            try:
                payload = resp.json()
            except Exception:
                logger.warning("⚠️ 历史弹幕日期索引解析失败 cid={} month={}", cid, month)
                continue
            code = payload.get("code")
            if code != 0:
                logger.warning(
                    "⚠️ 历史弹幕日期索引返回错误 cid={} month={} code={} message={}",
                    cid,
                    month,
                    code,
                    payload.get("message"),
                )
                # 未登录或权限不足时，无需继续请求更多月份
                if code in self.DM_HISTORY_STOP_CODES:
                    break
                continue
            day_list = payload.get("data") or []
            all_dates.extend([str(d) for d in day_list if d])
            logger.info(
                "  ✅ 索引完成 cid={} month={} days={} cumulative_days={}",
                cid,
                month,
                len(day_list),
                len(all_dates),
            )

        if not all_dates:
            logger.info("🕰️ 历史弹幕索引为空 cid={}", cid)
            return []

        history_items: list[dict[str, Any]] = []
        # 保序去重：history/index 可能返回重复日期，按首次出现顺序去重后逐日抓取。
        dedup_dates = list(dict.fromkeys(all_dates))
        logger.info("🕰️ 开始抓取历史弹幕数据 cid={} dates={}", cid, len(dedup_dates))
        for idx, date_str in enumerate(dedup_dates, start=1):
            logger.info(
                "  📥 历史弹幕进度 cid={} date={}/{} ({})", cid, idx, len(dedup_dates), date_str
            )
            day_items = self._fetch_danmaku_history_proto_for_date(cid, date_str)
            history_items.extend(day_items)
            logger.info(
                "    ✅ 单日完成 cid={} date={} items={} cumulative_items={}",
                cid,
                date_str,
                len(day_items),
                len(history_items),
            )
        logger.info(
            "🕰️ 历史弹幕抓取完成 cid={} dates={} items={}", cid, len(dedup_dates), len(history_items)
        )
        return history_items

    def fetch_danmaku_history_xml(
        self, cid: str, *, publish_ts: int | None = None
    ) -> list[dict[str, Any]]:
        """兼容旧调用：历史弹幕抓取已迁移为 protobuf 接口实现。"""
        return self.fetch_danmaku_history(cid, publish_ts=publish_ts)

    def _get_mixin_key(self, img_key: str, sub_key: str) -> str:
        """根据 img_key 和 sub_key 生成混淆后的 mixin key（取前 32 位）"""
        raw = img_key + sub_key
        return reduce(lambda s, i: s + raw[i], self._MIXIN_KEY_ENC_TAB, "")[:32]

    def _get_wbi_keys(self) -> tuple[str, str]:
        """
        获取 Wbi 签名所需的 img_key 和 sub_key。
        每小时刷新一次，减少重复请求。
        """
        now = time.time()
        if (
            self._wbi_keys_cache is not None
            and self._wbi_keys_fetched_at is not None
            and now - self._wbi_keys_fetched_at < self._WBI_CACHE_TTL
        ):
            return self._wbi_keys_cache

        url = "https://api.bilibili.com/x/web-interface/nav"
        try:
            resp = self._request_get(url, timeout=settings.bilibili_request_timeout)
            if resp is None:
                return "", ""
            nav = resp.json().get("data", {})
            img_url: str = nav.get("wbi_img", {}).get("img_url", "")
            sub_url: str = nav.get("wbi_img", {}).get("sub_url", "")
            img_key = img_url.rsplit("/", 1)[-1].split(".")[0]
            sub_key = sub_url.rsplit("/", 1)[-1].split(".")[0]
            self.__class__._wbi_keys_cache = (img_key, sub_key)
            self.__class__._wbi_keys_fetched_at = now
            return img_key, sub_key
        except Exception as exc:
            logger.error(
                "❌ 获取 Wbi 密钥失败（后续 API 请求的签名将无效，建议检查网络连接与 Cookie）: {}",
                exc,
            )
            # 降级：返回空字符串，后续签名会失败但不会崩溃
            return "", ""

    def _sign_wbi_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        对请求参数进行 Wbi 签名，自动附加 wts 和 w_rid 字段。

        Args:
            params: 原始请求参数字典

        Returns:
            含有 wts、w_rid 签名字段的新参数字典
        """
        img_key, sub_key = self._get_wbi_keys()
        # 如果获取 Wbi 密钥失败（降级返回空字符串），则跳过签名，避免后续崩溃
        if not img_key or not sub_key:
            logger.warning("⚠️ Wbi 密钥为空，本次请求将不进行 Wbi 签名，直接使用原始参数。")
            return dict(params)
        mixin_key = self._get_mixin_key(img_key, sub_key)
        wts = int(time.time())
        signed = dict(params)
        signed["wts"] = wts

        pattern = r"[!#$&+,/:;=?@\\[\\]]"

        query = "&".join(f"{k}={re.sub(pattern, '', str(v))}" for k, v in sorted(signed.items()))

        w_rid = hashlib.md5((query + mixin_key).encode()).hexdigest()
        signed["w_rid"] = w_rid
        return signed

    def _parse_danmaku_xml_payload(
        self,
        *,
        cid: str,
        xml_text: str,
        source: str,
    ) -> list[dict[str, Any]]:
        """解析弹幕 XML 文本，统一返回标准字段。"""
        danmaku_list: list[dict[str, Any]] = []
        try:
            root = ET.fromstring(xml_text)
            for d in root.findall("d"):
                attrs = d.get("p", "")
                text = (d.text or "").strip()
                if not text:
                    continue
                # p 属性格式: 时间,类型,大小,颜色,时间戳,弹幕池,用户ID,弹幕ID
                parts = attrs.split(",")
                try:
                    video_time = float(parts[0]) if parts and parts[0] else 0.0
                    ts_unix = int(parts[4]) if len(parts) > 4 and parts[4] else 0
                    sender_hash = parts[6] if len(parts) > 6 else None
                except (TypeError, ValueError):
                    logger.debug("跳过异常弹幕元数据 cid={} source={} attrs={}", cid, source, attrs)
                    continue
                ctime = datetime.fromtimestamp(ts_unix) if ts_unix else None
                danmaku_list.append(
                    {
                        "content": text,
                        "video_time": video_time,  # 保持兼容旧字段
                        "progress": video_time,
                        "timestamp": ctime,  # 保持兼容旧字段
                        "ctime": ctime,
                        "sender_hash": sender_hash,  # B站匿名用户哈希
                    }
                )
        except ET.ParseError as exc:
            logger.warning("⚠️ 解析弹幕 XML 失败 cid={} source={}: {}", cid, source, exc)
        except Exception as exc:
            logger.exception("❌ 解析弹幕 XML 异常 cid={} source={}: {}", cid, source, exc)
        return danmaku_list

    def _iter_history_months(self, publish_ts: int | None) -> list[str]:
        """根据发布时间推导历史弹幕索引查询月份（倒序，YYYY-MM）。"""
        now = datetime.now()
        max_months = max(1, settings.crawler_history_months)
        cursor = datetime(now.year, now.month, 1)
        start_month: datetime | None = None
        if publish_ts:
            try:
                start_month = datetime.fromtimestamp(int(publish_ts)).replace(day=1)
            except (ValueError, OSError, OverflowError, TypeError):
                logger.warning("⚠️ 非法发布时间戳，改用固定回溯窗口 publish_ts={}", publish_ts)
        months: list[str] = []
        while len(months) < max_months:
            if start_month and cursor < start_month:
                break
            months.append(cursor.strftime("%Y-%m"))
            if cursor.month == 1:
                cursor = datetime(cursor.year - 1, 12, 1)
            else:
                cursor = datetime(cursor.year, cursor.month - 1, 1)
        return months

    @staticmethod
    def _make_danmaku_dedup_key(item: dict[str, Any]) -> tuple[str, Any, Any, str]:
        """构造弹幕去重键：(content, video_time, timestamp, sender_hash)。"""
        return (
            str(item.get("content") or ""),
            item.get("video_time"),
            item.get("timestamp"),
            str(item.get("sender_hash") or ""),
        )

    @staticmethod
    def _read_proto_varint(buf: bytes, start: int) -> tuple[int | None, int]:
        """读取 protobuf varint，返回 (value, next_offset)。"""
        return read_proto_varint(buf, start)

    def _parse_danmaku_seg_protobuf(
        self,
        *,
        cid: str,
        payload: bytes,
        source: str,
    ) -> list[dict[str, Any]]:
        """
        解析 DmSegMobileReply protobuf（二进制）为统一弹幕字段。
        仅提取当前入库所需字段，忽略未知字段，保证向后兼容。
        """
        FIELD_MODE = 3
        FIELD_FONT_SIZE = 4
        FIELD_COLOR = 5
        FIELD_POOL = 11
        items: list[dict[str, Any]] = []
        offset = 0
        while offset < len(payload):
            tag, offset = self._read_proto_varint(payload, offset)
            if tag is None:
                break
            field_no = tag >> 3
            wire_type = tag & 0x7

            if wire_type == 2:
                size, offset = self._read_proto_varint(payload, offset)
                if size is None or offset + size > len(payload):
                    break
                chunk = payload[offset : offset + size]
                offset += size
                # DmSegMobileReply.elem -> field_no=1, length-delimited message
                if field_no != 1:
                    continue
                elem_values: dict[int, Any] = {}
                elem_offset = 0
                while elem_offset < len(chunk):
                    elem_tag, elem_offset = self._read_proto_varint(chunk, elem_offset)
                    if elem_tag is None:
                        break
                    elem_field_no = elem_tag >> 3
                    elem_wire_type = elem_tag & 0x7
                    if elem_wire_type == 0:
                        raw, elem_offset = self._read_proto_varint(chunk, elem_offset)
                        if raw is None:
                            break
                        elem_values[elem_field_no] = raw
                    elif elem_wire_type == 2:
                        l, elem_offset = self._read_proto_varint(chunk, elem_offset)
                        if l is None or elem_offset + l > len(chunk):
                            break
                        raw_bytes = chunk[elem_offset : elem_offset + l]
                        elem_offset += l
                        elem_values[elem_field_no] = raw_bytes
                    elif elem_wire_type == 5:
                        if elem_offset + 4 > len(chunk):
                            break
                        elem_offset += 4
                    elif elem_wire_type == 1:
                        if elem_offset + 8 > len(chunk):
                            break
                        elem_offset += 8
                    else:
                        break

                content_raw = elem_values.get(7, b"")
                content = (
                    content_raw.decode("utf-8", errors="ignore").strip()
                    if isinstance(content_raw, (bytes, bytearray))
                    else str(content_raw or "").strip()
                )
                if not content:
                    continue
                progress_ms = int(elem_values.get(2, 0) or 0)
                ctime_ts = int(elem_values.get(8, 0) or 0)
                sender_raw = elem_values.get(6, b"")
                sender_hash = (
                    sender_raw.decode("utf-8", errors="ignore")
                    if isinstance(sender_raw, (bytes, bytearray))
                    else str(sender_raw or "")
                )
                id_str_raw = elem_values.get(12, b"")
                dmid = (
                    id_str_raw.decode("utf-8", errors="ignore")
                    if isinstance(id_str_raw, (bytes, bytearray))
                    else str(id_str_raw or "")
                ) or str(elem_values.get(1, "") or "")
                ctime = datetime.fromtimestamp(ctime_ts) if ctime_ts else None
                items.append(
                    {
                        "content": content,
                        "video_time": (progress_ms / 1000.0) if progress_ms > 0 else 0.0,
                        "progress": progress_ms,
                        "timestamp": ctime,
                        "ctime": ctime,
                        "sender_hash": sender_hash,
                        "mode": int(elem_values.get(FIELD_MODE, 0) or 0) or None,
                        "font_size": int(elem_values.get(FIELD_FONT_SIZE, 0) or 0) or None,
                        "color": int(elem_values.get(FIELD_COLOR, 0) or 0) or None,
                        "pool": int(elem_values.get(FIELD_POOL, 0) or 0) or None,
                        "dmid": dmid or None,
                        "attrs_raw": source,
                    }
                )
            elif wire_type == 0:
                _, offset = self._read_proto_varint(payload, offset)
            elif wire_type == 5:
                offset += 4
            elif wire_type == 1:
                offset += 8
            else:
                break
        return items

    def _fetch_danmaku_history_proto_for_date(
        self, cid: str, date_str: str
    ) -> list[dict[str, Any]]:
        """抓取并解析单日历史弹幕 protobuf。"""
        url = "https://api.bilibili.com/x/v2/dm/web/history/seg.so"
        resp = self._request_get(
            url,
            params={"type": 1, "oid": str(cid), "date": date_str},
            timeout=settings.bilibili_request_timeout,
        )
        if resp is None:
            logger.warning("⚠️ 历史弹幕 protobuf 请求失败 cid={} date={}", cid, date_str)
            return []
        body = resp.content or b""
        if not body:
            logger.warning("⚠️ 历史弹幕 protobuf 响应为空 cid={} date={}", cid, date_str)
            return []
        if body.lstrip().startswith(b"{"):
            try:
                err = resp.json()
                logger.warning(
                    "⚠️ 历史弹幕 protobuf 接口返回错误 cid={} date={} code={} message={}",
                    cid,
                    date_str,
                    err.get("code"),
                    err.get("message"),
                )
            except Exception:
                logger.warning(
                    "⚠️ 历史弹幕 protobuf 接口返回非二进制内容 cid={} date={}", cid, date_str
                )
            return []
        return self._parse_danmaku_seg_protobuf(
            cid=cid,
            payload=body,
            source=f"history-proto:{date_str}",
        )
