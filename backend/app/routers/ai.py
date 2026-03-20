# routers/ai.py
"""
AI 助手相关的 API 路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# 引入我们刚才重构好的服务
from ..ai_service import AIService

router = APIRouter(prefix="/api", tags=["AI助手"])

# 实例化 AI 服务
ai_service = AIService()


class ChatMessage(BaseModel):
    """聊天消息模型"""
    message: str


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
        
        return {
            "success": True,
            "reply": reply
        }
    
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"系统内部错误: {str(e)}"
        )