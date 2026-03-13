# ai_service.py
"""
AI 助手服务
处理与豆包 AI 的交互
"""
import requests
from typing import Optional, Dict, Any
from fastapi import HTTPException

from .config import settings


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
        
        # 构建系统提示词
        system_content = "你是一个B站数据分析助手，帮助用户理解B站番剧数据、用户行为分析报告和系统使用。"
        if context:
            system_content += f"\n\n当前上下文：{context}"
        
        try:
            request_body = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": system_content
                    },
                    {
                        "role": "user",
                        "content": message
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 500
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
            reply = data['choices'][0]['message']['content']
            
            return reply
            
        except requests.exceptions.RequestException as e:
            print(f"AI 服务错误: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"AI 服务暂时不可用: {str(e)}"
            )
