# 智能服务模块实现文件
"""
AI 助手服务
处理与豆包 AI 的交互，并对相同消息进行 TTL 缓存以减少重复外部调用。

架构说明：
  - _request_api(message, system_prompt)  ← 核心私有方法：鉴权、组包、HTTP 请求、错误处理、TTLCache
  - chat(message, context)                ← 通用问答，system_prompt = UGC流媒体平台数据分析助手人设
  - generate_insight(data, context_hint)  ← Auto-EDA，system_prompt = 资深二次元数据分析师人设
  - text_to_sql(natural_language)         ← Text-to-SQL，system_prompt = SQLite 专家 + Schema

缓存键 = SHA256(message + "||" + system_prompt)，不同人设下相同问题各自独立缓存。
"""
import hashlib
import json
import re
import threading
import time
from pathlib import Path
from typing import Any

import requests
from cachetools import TTLCache
from fastapi import HTTPException
from sqlmodel import Session

from .config import settings
from .database import engine
from .logger import app_logger
from .models import AITelemetry

# ──────────────────────────────────────────────────────────────────────────────
# AI 响应缓存：最多缓存 128 条结果，每条 TTL 10 分钟
# 以 (message, system_prompt) 的 SHA256 摘要为键，确保不同人设下不冲突
# cachetools 不是线程安全的，使用 RLock 保护并发读写
# ──────────────────────────────────────────────────────────────────────────────
_ai_cache: TTLCache = TTLCache(maxsize=128, ttl=600)
_ai_cache_lock = threading.RLock()

_PROJECT_KNOWLEDGE_FILES = (
    "README.md",
    "backend/app/main.py",
    "backend/app/config.py",
    "backend/app/database.py",
    "backend/app/models.py",
    "backend/app/crud.py",
    "backend/app/analytics.py",
    "backend/app/ai_service.py",
    "backend/app/routers/ai.py",
    "backend/app/routers/analytics.py",
    "backend/app/routers/crawler.py",
    "backend/app/routers/auth.py",
    "backend/app/routers/user_space.py",
    "backend/app/scraper/crawler.py",
    "frontend/src/router/index.ts",
    "frontend/src/api/index.ts",
    "frontend/src/components/AiChat.vue",
    "frontend/src/views/Home.vue",
    "frontend/src/views/Overview.vue",
    "frontend/src/views/Report.vue",
    "frontend/src/views/Status.vue",
)

# 语料分片上限：约等价于 6k~8k 中英混合 token，控制 prompt 体积与响应延迟。
_MAX_KNOWLEDGE_CHARS_PER_FILE = 24000
_MAX_RAG_DOCS = 4
_MAX_RAG_LINES_PER_DOC = 3
_MAX_QUERY_TERMS = 12
_MAX_SNIPPET_LINE_CHARS = 180
_ASCII_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
_CHINESE_TERM_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,}")


class AIService:
    """AI 助手服务类"""

    def __init__(self):
        self.api_key = settings.doubao_api_key
        self.api_url = settings.doubao_api_url
        self.model = settings.doubao_model
        self.repo_root = Path(__file__).resolve().parents[2]
        self.knowledge_corpus = self._load_project_knowledge_corpus()

    # ── 公开方法 ────────────────────────────────────────────────────────────

    def check_service_status(self) -> dict[str, Any]:
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

    def chat(self, message: str, context: str | None = None) -> str:
        """
        通用问答：UGC流媒体平台数据分析助手人设。

        Args:
            message: 用户消息
            context: 可选的额外上下文（将追加到 system_prompt 末尾）

        Returns:
            AI 回复内容

        Raises:
            HTTPException: 服务不可用或请求失败
        """
        project_context = self._build_project_context(message=message, context=context or "")
        system_prompt = (
            "你是 UGC-analytics-app 项目的技术助手。"
            "你的回答必须优先依据提供的项目知识摘要与相关模块片段（RAG检索结果）。"
            "回答项目问题时请尽量明确指出对应的模块、文件或接口路径。"
            "如果上下文不足以确定答案，你必须先说明信息不足并提出澄清问题，严禁编造项目中不存在的实现。"
            "\n\n"
            f"{project_context}"
        )
        return self._request_api(message=message, system_prompt=system_prompt)

    def _build_project_context(self, message: str, context: str) -> str:
        """
        组装聊天上下文：项目知识摘要 + RAG 片段 + 调用方附加上下文。

        Args:
            message: 用户提问
            context: 调用方传入的附加上下文

        Returns:
            可直接注入 system_prompt 的上下文文本
        """
        knowledge_summary = (
            "项目名称：UGC-analytics-app。\n"
            "后端：FastAPI（backend/app），核心包含 routers、crud、analytics、ai_service、scraper 子模块。\n"
            "前端：Vue3 + TypeScript（frontend/src），核心包含 views、components/AiChat、api 与 router。\n"
            "数据层：SQLite 为主（SQLModel），并支持 MongoDB 存储原始弹幕。\n"
            "AI 能力：/api/chat 通用对话，/api/ai/generate-insight 自动洞察，/api/ai/text-to-sql 自然语言转只读 SQL。"
        )
        rag_snippets = self._retrieve_relevant_snippets(message)
        sections = [
            "【项目知识摘要】",
            knowledge_summary,
            "【相关模块片段（RAG检索结果）】",
            rag_snippets,
        ]
        if context.strip():
            sections.extend(["【调用侧附加上下文】", context.strip()])
        return "\n".join(sections)

    def _load_project_knowledge_corpus(self) -> list[dict[str, str]]:
        """
        预加载项目知识语料，用于后续本地 RAG 检索。

        Returns:
            语料列表，每项包含 path 与 content
        """
        corpus: list[dict[str, str]] = []
        for rel_path in _PROJECT_KNOWLEDGE_FILES:
            file_path = self.repo_root / rel_path
            if not file_path.exists() or not file_path.is_file():
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError as exc:
                app_logger.warning("项目语料加载失败 path={} error={}", rel_path, exc)
                continue
            corpus.append(
                {
                    "path": rel_path,
                    "content": content[:_MAX_KNOWLEDGE_CHARS_PER_FILE],
                }
            )
        return corpus

    def _extract_query_terms(self, message: str) -> list[str]:
        """
        从用户问题中提取检索关键词。

        Args:
            message: 用户提问文本

        Returns:
            去重后的关键词列表
        """
        lowered_message = message.lower()
        ascii_terms = _ASCII_IDENTIFIER_PATTERN.findall(lowered_message)
        han_terms = _CHINESE_TERM_PATTERN.findall(lowered_message)
        terms: list[str] = []
        for term in [*ascii_terms, *han_terms]:
            normalized = term.lower()
            if normalized not in terms:
                terms.append(normalized)
            if len(terms) >= _MAX_QUERY_TERMS:
                break
        return terms

    def _retrieve_relevant_snippets(self, message: str) -> str:
        """
        在本地项目语料中检索与用户问题相关的片段，生成可注入提示词的证据文本。

        Args:
            message: 用户提问

        Returns:
            格式化后的检索片段文本
        """
        if not self.knowledge_corpus:
            return "未加载到项目语料。"

        terms = self._extract_query_terms(message)
        if not terms:
            return "未从问题中提取到明确关键词。"

        ranked_docs: list[dict[str, Any]] = []
        for doc in self.knowledge_corpus:
            path = doc["path"]
            content = doc["content"]
            lines = content.splitlines()
            lower_path = path.lower()
            matched_lines: list[tuple[int, str]] = []
            score = 0

            for term in terms:
                term_hit_path = term.lower() in lower_path
                if term_hit_path:
                    score += 3

            for idx, line in enumerate(lines, start=1):
                line_lower = line.lower()
                for term in terms:
                    if term in line_lower:
                        score += 2
                        if len(matched_lines) < _MAX_RAG_LINES_PER_DOC:
                            compressed = " ".join(line.strip().split())
                            matched_lines.append((idx, compressed[:_MAX_SNIPPET_LINE_CHARS]))
                        break

            if score > 0:
                ranked_docs.append(
                    {
                        "path": path,
                        "score": score,
                        "matches": matched_lines,
                    }
                )

        if not ranked_docs:
            return "未检索到强相关代码片段，请先澄清问题再结合项目知识摘要回答。"

        ranked_docs.sort(key=lambda item: item["score"], reverse=True)
        selected = ranked_docs[:_MAX_RAG_DOCS]
        snippets: list[str] = []
        for doc in selected:
            snippets.append(f"- 文件: {doc['path']}")
            if doc["matches"]:
                for line_no, line in doc["matches"]:
                    snippets.append(f"  - L{line_no}: {line}")
            else:
                snippets.append("  - 匹配到文件路径关键词，但未命中具体行内容")
        return "\n".join(snippets)

    def generate_insight(self, data: Any, context_hint: str = "") -> str:
        """
        Auto-EDA：资深二次元数据分析师人设，生成结构化数据洞察报告。

        Args:
            data:         前端传来的图表数据（字典或列表，可序列化为 JSON）
            context_hint: 可选的番剧名称等上下文

        Returns:
            约 300 字的结构化数据洞察文本

        Raises:
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

        Args:
            message:       用户侧的输入文本（user role）
            system_prompt: 本次调用的系统提示词（system role）

        Returns:
            AI 回复的纯文本内容

        Raises:
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
            f"{message}||{system_prompt}".encode()
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
        latency_ms: int | None,
        is_success: bool,
        token_usage: int | None = None,
        error_code: str | None = None,
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
