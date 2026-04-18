# routers/ai.py
"""
AI 助手相关的 API 路由
"""
import re
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text as sa_text
from sqlmodel import Session

from ..ai_service import AIService
from ..database import get_session, engine
from ..analytics import get_sentiment_timeline, get_top_comments
from ..logger import app_logger

router = APIRouter(prefix="/api", tags=["AI助手"])

# 实例化 AI 服务
ai_service = AIService()

# SQL 语句安全白名单：只允许 SELECT，禁止 DDL / DML
_SAFE_SQL_RE = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
# 检测多语句注入（分号分隔的多条 SQL）
_MULTI_STMT_RE = re.compile(r";(?!\s*$)", re.IGNORECASE)


class ChatMessage(BaseModel):
    """聊天消息模型"""
    message: str


class InsightRequest(BaseModel):
    """Auto-EDA 洞察请求模型"""
    data: Any                            # 图表数据（JSON 可序列化）
    context_hint: Optional[str] = ""    # 可选番剧名称等上下文


class TextToSQLRequest(BaseModel):
    """Text-to-SQL 请求模型"""
    query: str                           # 用户自然语言
    schema_hint: Optional[str] = ""     # 可选自定义 schema


class SentimentTimelineRequest(BaseModel):
    """情感时间线查询请求"""
    season_id: int


@router.get("/aiservicestatus", response_model=dict)
def get_ai_service_status():
    """
    获取 AI 服务状态

    Returns:
        服务状态信息
    """
    return ai_service.check_service_status()


@router.post("/chat", response_model=dict)
def chat_with_ai(chat_message: ChatMessage):
    """
    与 AI 助手对话

    Args:
        chat_message: 聊天消息

    Returns:
        AI 回复
    """
    try:
        reply = ai_service.chat(message=chat_message.message)
        return {"success": True, "reply": reply}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"系统内部错误: {str(e)}")


@router.post("/chat/stream")
def chat_with_ai_stream(chat_message: ChatMessage):
    """
    与 AI 助手对话（SSE 流式输出）。
    """
    def event_generator():
        try:
            for chunk in ai_service.chat_stream(message=chat_message.message):
                payload = json.dumps(
                    {"type": "delta", "content": chunk},
                    ensure_ascii=False,
                )
                yield f"data: {payload}\n\n"
            yield "data: {\"type\":\"done\"}\n\n"
        except HTTPException as he:
            payload = json.dumps(
                {"type": "error", "error": he.detail},
                ensure_ascii=False,
            )
            yield f"data: {payload}\n\n"
        except Exception as exc:
            app_logger.exception("AI 流式接口异常: {}", exc)
            payload = json.dumps(
                {"type": "error", "error": "系统内部错误，请稍后重试"},
                ensure_ascii=False,
            )
            yield f"data: {payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/ai/generate-insight", response_model=dict)
def generate_insight(req: InsightRequest):
    """
    Auto-EDA 智能洞察：接收图表 JSON，返回 300 字以内的结构化分析报告。

    Args:
        req: 包含 data（图表 JSON）和 context_hint（番剧名等上下文）

    Returns:
        {"success": True, "insight": "...报告文字..."}
    """
    try:
        insight = ai_service.generate_insight(
            data=req.data,
            context_hint=req.context_hint or "",
        )
        return {"success": True, "insight": insight}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"洞察生成失败: {str(e)}")


@router.post("/ai/text-to-sql", response_model=dict)
def text_to_sql(req: TextToSQLRequest, session: Session = Depends(get_session)):
    """
    Text-to-SQL：将自然语言转为 SQL，在只读权限下执行并返回结果。

    为安全起见，只允许 SELECT 语句；任何 DDL/DML 均会被拒绝。

    Args:
        req: 包含 query（自然语言）和可选 schema_hint

    Returns:
        {"success": True, "sql": "...", "rows": [...], "columns": [...]}
    """
    try:
        sql_raw = ai_service.text_to_sql(
            natural_language=req.query,
            schema_hint=req.schema_hint or "",
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SQL 生成失败: {str(e)}")

    # 从 AI 回复中提取 SQL（兼容带 markdown code block 的情况）
    sql = sql_raw.strip()
    # 去除 ```sql ... ``` 包裹
    sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\s*```$", "", sql)
    sql = sql.strip()

    # 安全检查：只允许 SELECT
    if not _SAFE_SQL_RE.match(sql):
        raise HTTPException(
            status_code=400,
            detail="AI 生成了非 SELECT 语句，已被安全策略拒绝。请重新描述您的查询需求。",
        )
    # 安全检查：拒绝多语句（防止 SELECT ...; DROP TABLE 之类的注入）
    if _MULTI_STMT_RE.search(sql):
        raise HTTPException(
            status_code=400,
            detail="检测到多语句 SQL，已被安全策略拒绝。请描述单次查询需求。",
        )

    try:
        with engine.connect() as conn:
            result = conn.execute(sa_text(sql))
            columns: List[str] = list(result.keys())
            rows: List[Dict] = [dict(zip(columns, row)) for row in result.fetchall()]
        return {"success": True, "sql": sql, "columns": columns, "rows": rows}
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"SQL 执行失败（{type(exc).__name__}）: {exc}",
        )


@router.get("/ai/sentiment-timeline/{season_id}", response_model=dict)
def get_sentiment_timeline_api(
    season_id: int,
    session: Session = Depends(get_session),
):
    """
    获取指定番剧按集数聚合的弹幕情感均分，用于前端折线图。

    Args:
        season_id: 番剧 season_id

    Returns:
        {"success": True, "timeline": [{"episode_number": 1, "avg_sentiment": 0.72, "danmu_count": 500}, ...]}
    """
    timeline = get_sentiment_timeline(session, season_id)
    return {"success": True, "timeline": timeline}


@router.get("/ai/top-comments/{season_id}", response_model=dict)
def get_top_comments_api(
    season_id: int,
    limit: int = 50,
    session: Session = Depends(get_session),
):
    """
    返回指定番剧高赞评论列表（含情感得分），供 AI 分析或前端展示。

    Args:
        season_id: 番剧 season_id
        limit:     最多返回条数（默认 50）

    Returns:
        {"success": True, "comments": [...]}
    """
    comments = get_top_comments(session, season_id, limit=limit)
    return {"success": True, "comments": comments}
