# ai_service.py
"""
AI 助手服务
处理与豆包 AI 的交互，并对相同消息进行 TTL 缓存以减少重复外部调用
"""
import hashlib
import json
import threading
import requests
from typing import Optional, Dict, Any
from fastapi import HTTPException
from cachetools import TTLCache

from .config import settings
from .logger import app_logger

# ──────────────────────────────────────────────────────────────────────────────
# AI 响应缓存：最多缓存 128 条结果，每条 TTL 10 分钟
# 以 (message, context) 的 SHA256 摘要为键，避免缓存对象过大
# cachetools 不是线程安全的，使用 RLock 保护并发读写
# ──────────────────────────────────────────────────────────────────────────────
_ai_cache: TTLCache = TTLCache(maxsize=128, ttl=600)
_ai_cache_lock = threading.RLock()


class AIService:
    """AI 助手服务类"""

    def __init__(self):
        self.api_key = settings.doubao_api_key
        self.api_url = settings.doubao_api_url
        self.model = settings.doubao_model

    def check_service_status(self) -> Dict[str, Any]:
        """
        检查 AI 服务状态

        Returns:
            服务状态信息
        """
        return {
            "status": "online" if self.api_key else "offline",
            "configured": bool(self.api_key),
            "model": self.model
        }

    def chat(self, message: str, context: Optional[str] = None) -> str:
        """
        与 AI 助手对话

        相同 (message, context) 组合的响应将在 TTL 缓存内直接返回，
        避免对同一问题重复消耗 API 配额。

        Args:
            message: 用户消息
            context: 可选的上下文信息

        Returns:
            AI 回复内容

        Raises:
            HTTPException: 服务不可用或请求失败
        """
        if not self.api_key:
            raise HTTPException(
                status_code=503,
                detail="AI 服务未配置，请设置 DOUBAO_API_KEY 环境变量"
            )

        # ── 缓存命中检查 ─────────────────────────────────────────────────────
        cache_key = hashlib.sha256(
            f"{message}||{context or ''}".encode("utf-8")
        ).hexdigest()
        with _ai_cache_lock:
            cached = _ai_cache.get(cache_key)
        if cached is not None:
            app_logger.debug("AI 响应缓存命中，跳过外部请求（key={}...）", cache_key[:8])
            return cached

        # 构建系统提示词
        system_content = "你是一个B站数据分析助手，帮助用户理解B站番剧数据、用户行为分析报告和系统使用。"
        if context:
            system_content += f"\n\n当前上下文：{context}"

        try:
            request_body = {
                "model": self.model,
                "input": [
                    {
                        "role": "system",
                        "content": [
                            {
                                "type": "input_text",
                                "text": system_content
                            }
                        ]
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": message
                            }
                        ]
                    }
                ]
            }

            response = requests.post(
                self.api_url,
                json=request_body,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.api_key}'
                },
                timeout=30
            )
            response.raise_for_status()

            data = response.json()

            reply = ""
            if "output" in data:
                for output_item in data["output"]:
                    if output_item.get("type") == "message" and output_item.get("role") == "assistant":
                        content_list = output_item.get("content", [])
                        for content_item in content_list:
                            if content_item.get("type") == "output_text":
                                reply += content_item.get("text", "")
            if not reply:
                app_logger.warning("未能从 AI 响应中解析出文本，原始响应: {}", data)
                raise HTTPException(status_code=500, detail="解析 AI 响应失败")

            # 写入缓存
            with _ai_cache_lock:
                _ai_cache[cache_key] = reply
            return reply

        except requests.exceptions.RequestException as e:
            app_logger.error("AI 服务请求失败: {}", e)
            raise HTTPException(
                status_code=500,
                detail=f"AI 服务暂时不可用: {str(e)}"
            )

    def generate_insight(self, data: Any, context_hint: str = "") -> str:
        """
        Auto-EDA：接收图表 JSON 数据，生成结构化数据洞察报告。

        Args:
            data:         前端传来的图表数据（字典或列表，可序列化为 JSON）
            context_hint: 可选的额外上下文说明（如番剧名称）

        Returns:
            约 300 字的结构化数据洞察文本

        Raises:
            HTTPException: AI 服务不可用或请求失败
        """
        data_str = json.dumps(data, ensure_ascii=False, default=str)
        prefix = f"番剧「{context_hint}」" if context_hint else "该番剧"
        prompt = (
            f"你是一个资深二次元数据分析师。以下是{prefix}的数据特征 JSON：\n{data_str}\n\n"
            "请从播放趋势、观众情感流向两个维度，写一份 300 字以内的结构化数据洞察报告。"
            "用简洁的要点式列举，突出最值得关注的数据变化与可能的原因。"
        )
        return self.chat(message=prompt)

    def text_to_sql(self, natural_language: str, schema_hint: str = "") -> str:
        """
        Text-to-SQL：将用户自然语言转换为可在 SQLite 中执行的 SELECT 语句。

        系统提示词包含数据库 Schema 说明，豆包只需输出 SQL，
        后端再拦截执行，不允许任何 DDL / DML 操作。

        Args:
            natural_language: 用户的自然语言查询（中文）
            schema_hint:      额外 schema 说明（默认使用内置 schema）

        Returns:
            纯 SQL 字符串（无其余解释文字）

        Raises:
            HTTPException: AI 服务不可用或请求失败
        """
        default_schema = (
            "数据库包含以下表（SQLite）：\n"
            "1. anime(season_id INT PK, title TEXT, area TEXT, rating REAL, release_date TEXT,\n"
            "         total_coins INT, total_danmakus INT, total_likes INT, total_reply INT,\n"
            "         total_share INT, rating_count INT, is_finish INT, copyright TEXT)\n"
            "2. daily_stats(id INT PK, season_id INT FK→anime, date DATETIME, views INT, favorites INT)\n"
            "3. episode_stats(id INT PK, season_id INT FK→anime, episode_title TEXT, bvid TEXT,\n"
            "                 views INT, danmaku INT, reply INT, favorite INT, coin INT, like INT)\n"
            "4. danmu_records(id INT PK, season_id INT FK→anime, episode_number INT, content TEXT,\n"
            "                 video_time REAL, sentiment_score REAL)\n"
            "5. comment_records(id INT PK, season_id INT FK→anime, content TEXT, likes INT,\n"
            "                   replies INT, sentiment_score REAL)"
        )
        schema = schema_hint or default_schema
        system_msg = (
            f"你是一个 SQLite 专家。已知数据库结构如下：\n{schema}\n"
            "用户会用中文描述查询需求，你只需要返回对应的 SELECT SQL 语句，"
            "不需要任何解释文字，不允许使用 DDL 或 DML 语句。"
        )
        return self.chat(message=natural_language, context=system_msg)
