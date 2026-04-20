"""DanmakuService domain service for scraper facade."""

from __future__ import annotations

from typing import Any

from ..config import settings
from ..logger import scraper_logger as logger


class DanmakuService:
    """Domain service delegated by ``BilibiliBangumiCrawler`` facade."""

    def __init__(self, crawler: Any) -> None:
        self._crawler = crawler

    def __getattr__(self, name: str) -> Any:
        return getattr(self._crawler, name)

    def __setattr__(self, name: str, value: Any) -> None:
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
