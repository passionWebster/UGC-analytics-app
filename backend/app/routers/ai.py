"""智能助手相关接口路由。"""

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text as sa_text
from sqlmodel import Session

from ..ai_service import AIService
from ..database import get_session, engine
from ..analytics import get_sentiment_timeline, get_top_comments

router = APIRouter(prefix="/api", tags=["AI助手"])

# 实例化智能服务
ai_service = AIService()

# 查询语句安全白名单：仅允许只读查询
_SAFE_SQL_RE = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
# 检测多语句注入风险（分号分隔的多条语句）
_MULTI_STMT_RE = re.compile(r";(?!\s*$)", re.IGNORECASE)


class ChatMessage(BaseModel):
    """聊天消息模型。"""

    message: str


class InsightRequest(BaseModel):
    """自动探索洞察请求模型。"""

    data: Any  # 图表数据（可序列化）
    context_hint: str | None = ""  # 可选番剧名称等上下文


class TextToSQLRequest(BaseModel):
    """自然语言转查询语句请求模型。"""

    query: str  # 用户自然语言
    schema_hint: str | None = ""  # 可选自定义数据结构提示


class SentimentTimelineRequest(BaseModel):
    """情感时间线查询请求。"""

    season_id: int


@router.get("/aiservicestatus", response_model=dict)
def get_ai_service_status() -> dict[str, Any]:
    """
    获取 AI 服务状态

    Returns:
        服务状态信息
    """
    return ai_service.check_service_status()


@router.post("/chat", response_model=dict)
def chat_with_ai(chat_message: ChatMessage) -> dict[str, Any]:
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


@router.post("/ai/generate-insight", response_model=dict)
def generate_insight(req: InsightRequest) -> dict[str, Any]:
    """
    自动探索洞察：接收图表数据，返回 300 字以内的结构化分析报告。

    Args:
        req: 包含图表数据与上下文提示

    Returns:
        结构化洞察结果
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
def text_to_sql(req: TextToSQLRequest, session: Session = Depends(get_session)) -> dict[str, Any]:
    """
    自然语言转查询语句：将自然语言转为只读查询并执行返回结果。

    为安全起见，仅允许只读查询语句；任何写入或结构变更语句都会被拒绝。

    Args:
        req: 包含自然语言查询与可选数据结构提示

    Returns:
        查询执行结果
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

    # 从智能回复中提取查询语句（兼容代码块包裹场景）
    sql = sql_raw.strip()
    # 去除代码块包裹
    sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\s*```$", "", sql)
    sql = sql.strip()

    # 安全检查：仅允许只读查询
    if not _SAFE_SQL_RE.match(sql):
        raise HTTPException(
            status_code=400,
            detail="生成了非只读查询语句，已被安全策略拒绝。请重新描述查询需求。",
        )
    # 安全检查：拒绝多语句，避免拼接注入风险
    if _MULTI_STMT_RE.search(sql):
        raise HTTPException(
            status_code=400,
            detail="检测到多语句查询，已被安全策略拒绝。请描述单次查询需求。",
        )

    try:
        with engine.connect() as conn:
            result = conn.execute(sa_text(sql))
            columns: list[str] = list(result.keys())
            rows: list[dict[str, Any]] = [dict(zip(columns, row)) for row in result.fetchall()]
        return {"success": True, "sql": sql, "columns": columns, "rows": rows}
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"查询执行失败（{type(exc).__name__}）: {exc}",
        )


@router.get("/ai/sentiment-timeline/{season_id}", response_model=dict)
def get_sentiment_timeline_api(
    season_id: int,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """
    获取指定番剧按集数聚合的弹幕情感均分，用于折线图展示。

    Args:
        season_id: 番剧 season_id

    Returns:
        情感时间线结果
    """
    timeline = get_sentiment_timeline(session, season_id)
    return {"success": True, "timeline": timeline}


@router.get("/ai/top-comments/{season_id}", response_model=dict)
def get_top_comments_api(
    season_id: int,
    limit: int = 50,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """
    返回指定番剧高赞评论列表（含情感得分），供智能分析或前端展示。

    Args:
        season_id: 番剧 season_id
        limit:     最多返回条数（默认 50）

    Returns:
        评论列表结果
    """
    comments = get_top_comments(session, season_id, limit=limit)
    return {"success": True, "comments": comments}
