# routers/ai.py
"""
AI 助手相关的 API 路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import requests

from ..config import settings


router = APIRouter(prefix="/api", tags=["AI助手"])


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
    return {
        "status": "online",
        "timestamp": "2026-01-31T08:00:00Z",
        "version": "2.0.0"
    }


@router.post("/chat", response_model=dict)
def chat_with_ai(chat_message: ChatMessage):
    """
    与 AI 助手对话
    
    Args:
        chat_message: 聊天消息
        
    Returns:
        AI 回复
    """
    if not settings.doubao_api_key:
        raise HTTPException(
            status_code=503,
            detail="AI 服务未配置，请设置 DOUBAO_API_KEY 环境变量"
        )
    
    try:
        request_body = {
            "model": settings.doubao_model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个B站数据分析助手，帮助用户理解B站番剧数据、用户行为分析报告和系统使用。"
                },
                {
                    "role": "user",
                    "content": chat_message.message
                }
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        response = requests.post(
            settings.doubao_api_url,
            json=request_body,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {settings.doubao_api_key}'
            },
            timeout=30
        )
        response.raise_for_status()
        
        data = response.json()
        reply = data['choices'][0]['message']['content']
        
        return {
            "success": True,
            "reply": reply
        }
        
    except requests.exceptions.RequestException as e:
        print(f"AI 服务错误: {e}")
        raise HTTPException(
            status_code=500,
            detail="AI 服务暂时不可用，请稍后再试"
        )
