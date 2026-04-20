# 智能服务模块实现文件
"""
AI 助手服务
处理与豆包 AI 的交互，并对相同消息进行 TTL 缓存以减少重复外部调用。

架构说明：
  - _request_api(message, system_prompt)  ← 核心私有方法：鉴权、组包、HTTP 请求、错误处理、TTLCache
  - chat(message, context)                ← 通用问答，system_prompt = B站数据分析助手人设
  - generate_insight(data, context_hint)  ← Auto-EDA，system_prompt = 资深二次元数据分析师人设
  - text_to_sql(natural_language)         ← Text-to-SQL，system_prompt = SQLite 专家 + Schema

缓存键 = SHA256(message + "||" + system_prompt)，不同人设下相同问题各自独立缓存。
"""
import hashlib
import json
import threading
import time
import requests
from typing import Optional, Dict, Any
from fastapi import HTTPException
from cachetools import TTLCache

from .config import settings
from .logger import app_logger
from .database import engine
from .models import AITelemetry
from sqlmodel import Session

# ──────────────────────────────────────────────────────────────────────────────
# AI 响应缓存：最多缓存 128 条结果，每条 TTL 10 分钟
# 以 (message, system_prompt) 的 SHA256 摘要为键，确保不同人设下不冲突
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

    # ── 公开方法 ────────────────────────────────────────────────────────────

    def check_service_status(self) -> Dict[str, Any]:
        """
        检查 AI 服务状态

        返回:
            服务状态信息
        """
        return {
            "status": "online" if self.api_key else "offline",
            "configured": bool(self.api_key),
            "model": self.model
        }

    def chat(self, message: str, context: Optional[str] = None) -> str:
        """
        通用问答：B站数据分析助手人设。

        参数:
            message: 用户消息
            context: 可选的额外上下文（将追加到 system_prompt 末尾）

        返回:
            AI 回复内容

        异常:
            HTTPException: 服务不可用或请求失败
        """
        system_prompt = (
            "你是一个B站数据分析助手，帮助用户理解B站番剧数据、用户行为分析报告和系统使用。"
        )
        if context:
            system_prompt += f"\n\n当前上下文：{context}"
        return self._request_api(message=message, system_prompt=system_prompt)

    def generate_insight(self, data: Any, context_hint: str = "") -> str:
        """
        Auto-EDA：资深二次元数据分析师人设，生成结构化数据洞察报告。

        参数:
            data:         前端传来的图表数据（字典或列表，可序列化为 JSON）
            context_hint: 可选的番剧名称等上下文

        返回:
            约 300 字的结构化数据洞察文本

        异常:
            HTTPException: AI 服务不可用或请求失败
        """
        data_str = json.dumps(data, ensure_ascii=False, default=str)
        prefix = f"番剧「{context_hint}」" if context_hint else "该番剧"

        system_prompt = (
            "你是一个资深二次元数据分析师，专注于 B 站番剧的播放数据和观众行为解读。"
            "请根据用户提供的数据 JSON，从播放趋势和观众情感流向两个维度给出结构化洞察，"
            "使用要点式列举，控制在 300 字以内，突出最有价值的发现与可能的原因。"
        )
        user_message = (
            f"以下是{prefix}的数据特征 JSON：\n{data_str}\n\n"
            "请写一份结构化数据洞察报告。"
        )
        return self._request_api(message=user_message, system_prompt=system_prompt)

    def text_to_sql(self, natural_language: str, schema_hint: str = "") -> str:
        """
        Text-to-SQL：SQLite 专家人设，将自然语言转换为 SELECT 语句。

        参数:
            natural_language: 用户的自然语言查询（中文）
            schema_hint:      额外 schema 说明（默认使用内置 schema）

        返回:
            纯 SQL 字符串（无其余解释文字）

        异常:
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
        system_prompt = (
            f"你是一个 SQLite 专家。已知数据库结构如下：\n{schema}\n\n"
            "用户会用中文描述查询需求，你只需要返回对应的 SELECT SQL 语句，"
            "不需要任何解释文字，不允许使用 DDL 或 DML 语句，"
            "不要用 markdown 代码块包裹，直接输出裸 SQL。"
        )
        return self._request_api(message=natural_language, system_prompt=system_prompt)

    # ── 私有核心方法 ────────────────────────────────────────────────────────

    def _request_api(self, message: str, system_prompt: str) -> str:
        """
        向豆包 API 发起请求的核心私有方法。

        职责：
          1. 检查 API Key 是否已配置
          2. 以 (message, system_prompt) 的 SHA256 摘要作为缓存键，命中则直接返回
          3. 组装符合豆包 /api/v3/responses 格式的请求体
          4. 发起 HTTP POST，附带鉴权头
          5. 解析响应，提取 assistant 的 output_text
          6. 将结果写入缓存
          7. 对网络异常和 API 返回异常进行分类日志记录和错误透传

        参数:
            message:       用户侧的输入文本（user role）
            system_prompt: 本次调用的系统提示词（system role）

        返回:
            AI 回复的纯文本内容

        异常:
            HTTPException 503: API Key 未配置
            HTTPException 500: 网络异常、响应解析失败或其他意外错误
        """
        if not self.api_key:
            self._record_telemetry(
                api_type="request",
                latency_ms=0,
                is_success=False,
                error_code="missing_api_key",
            )
            raise HTTPException(
                status_code=503,
                detail="AI 服务未配置，请设置 DOUBAO_API_KEY 环境变量"
            )

        # ── 缓存命中检查（键包含 system_prompt，不同人设下不冲突）────────────
        cache_key = hashlib.sha256(
            f"{message}||{system_prompt}".encode("utf-8")
        ).hexdigest()
        with _ai_cache_lock:
            cached = _ai_cache.get(cache_key)
        if cached is not None:
            app_logger.debug("AI 响应缓存命中，跳过外部请求（key={}...）", cache_key[:8])
            return cached

        # ── 组装请求体 ────────────────────────────────────────────────────
        request_body = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}]
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": message}]
                }
            ]
        }

        # ── HTTP 请求 ─────────────────────────────────────────────────────
        request_start = time.perf_counter()
        try:
            response = requests.post(
                self.api_url,
                json=request_body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                timeout=300,
            )
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            # 记录 HTTP 状态码与响应体，便于排查鉴权失败、限流等问题
            status_code = exc.response.status_code if exc.response is not None else None
            body = exc.response.text[:500] if exc.response is not None else ""
            app_logger.error(
                "豆包 API HTTP 错误 status={} body={}: {}", status_code, body, exc
            )
            status_str = str(status_code) if status_code is not None else "unknown"
            detail = f"AI 服务请求失败（HTTP {status_str}）"
            if body:
                detail += f"：{body}"
            self._record_telemetry(
                api_type="request",
                latency_ms=int((time.perf_counter() - request_start) * 1000),
                is_success=False,
                error_code=f"http_{status_str}",
            )
            raise HTTPException(status_code=500, detail=detail)
        except requests.exceptions.ConnectionError as exc:
            app_logger.error("豆包 API 连接失败（网络不可达）: {}", exc)
            self._record_telemetry(
                api_type="request",
                latency_ms=int((time.perf_counter() - request_start) * 1000),
                is_success=False,
                error_code="connection_error",
            )
            raise HTTPException(
                status_code=500,
                detail=f"AI 服务连接失败，请检查网络或 API 地址配置：{str(exc)}"
            )
        except requests.exceptions.Timeout as exc:
            app_logger.error("豆包 API 请求超时: {}", exc)
            self._record_telemetry(
                api_type="request",
                latency_ms=int((time.perf_counter() - request_start) * 1000),
                is_success=False,
                error_code="timeout",
            )
            raise HTTPException(
                status_code=500,
                detail="AI 服务请求超时（30s），请稍后重试"
            )
        except requests.exceptions.RequestException as exc:
            app_logger.error("豆包 API 请求异常: {}", exc)
            self._record_telemetry(
                api_type="request",
                latency_ms=int((time.perf_counter() - request_start) * 1000),
                is_success=False,
                error_code="request_exception",
            )
            raise HTTPException(
                status_code=500,
                detail=f"AI 服务暂时不可用：{str(exc)}"
            )

        # ── 解析响应 ──────────────────────────────────────────────────────
        try:
            data = response.json()
        except ValueError as exc:
            app_logger.error("豆包 API 返回了非 JSON 响应: {}", exc)
            raise HTTPException(
                status_code=500,
                detail="AI 服务返回了无法解析的响应，请检查 API 地址是否正确"
            )

        reply = ""
        if "output" in data:
            for output_item in data["output"]:
                if (
                    output_item.get("type") == "message"
                    and output_item.get("role") == "assistant"
                ):
                    for content_item in output_item.get("content", []):
                        if content_item.get("type") == "output_text":
                            reply += content_item.get("text", "")

        if not reply:
            app_logger.error(
                "未能从豆包 API 响应中解析出 assistant 文本。"
                "可能是响应格式变更，原始响应（前 500 字符）: {}",
                json.dumps(data, ensure_ascii=False)[:500],
            )
            self._record_telemetry(
                api_type="request",
                latency_ms=int((time.perf_counter() - request_start) * 1000),
                is_success=False,
                error_code="empty_reply",
            )
            raise HTTPException(
                status_code=500,
                detail=(
                    "解析 AI 响应失败：响应体中无 assistant output_text。"
                    "请检查 DOUBAO_MODEL 配置与 API 版本是否匹配。"
                )
            )

        # ── 写入缓存 ──────────────────────────────────────────────────────
        with _ai_cache_lock:
            _ai_cache[cache_key] = reply

        usage = data.get("usage", {}) if isinstance(data, dict) else {}
        total_tokens = usage.get("total_tokens") if isinstance(usage, dict) else None
        self._record_telemetry(
            api_type="request",
            latency_ms=int((time.perf_counter() - request_start) * 1000),
            is_success=True,
            token_usage=total_tokens if isinstance(total_tokens, int) else None,
        )

        return reply

    def _record_telemetry(
        self,
        api_type: str,
        latency_ms: Optional[int],
        is_success: bool,
        token_usage: Optional[int] = None,
        error_code: Optional[str] = None,
    ) -> None:
        """
        持久化 AI 调用遥测数据。
        记录失败不应影响主流程，因此内部吞掉异常并输出日志。
        """
        try:
            with Session(engine) as session:
                session.add(
                    AITelemetry(
                        api_type=api_type,
                        latency_ms=latency_ms,
                        is_success=is_success,
                        token_usage=token_usage,
                        error_code=error_code,
                    )
                )
                session.commit()
        except Exception as exc:
            app_logger.warning("AI 遥测写入失败: {}", exc)
