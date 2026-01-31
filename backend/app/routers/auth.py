# routers/auth.py
"""
用户认证相关的 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..database import get_session
from ..schemas import UserCreate, UserLogin, UserResponse, PreferenceUpdate
from ..auth import AuthService


router = APIRouter(prefix="/api", tags=["认证"])


@router.post("/register", response_model=dict)
def register(user_create: UserCreate, session: Session = Depends(get_session)):
    """
    用户注册
    
    Args:
        user_create: 用户注册信息
        session: 数据库会话
        
    Returns:
        注册成功信息
    """
    auth_service = AuthService(session)
    user = auth_service.register_user(user_create)
    
    return {
        "success": True,
        "message": "注册成功",
        "user": user
    }


@router.post("/login", response_model=dict)
def login(user_login: UserLogin, session: Session = Depends(get_session)):
    """
    用户登录
    
    Args:
        user_login: 登录凭证
        session: 数据库会话
        
    Returns:
        登录结果，包含 token 和用户信息
    """
    auth_service = AuthService(session)
    return auth_service.login(user_login)


@router.get("/user-info", response_model=dict)
def get_user_info(username: str, session: Session = Depends(get_session)):
    """
    获取用户信息
    
    Args:
        username: 用户名
        session: 数据库会话
        
    Returns:
        用户信息
    """
    auth_service = AuthService(session)
    user = auth_service.get_user_by_username(username)
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    import json
    preferences = []
    if user.preferences:
        try:
            preferences = json.loads(user.preferences)
        except:
            pass
    
    return {
        "success": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "preferences": preferences,
            "created_at": user.created_at.isoformat()
        }
    }


@router.post("/updatePreferences", response_model=dict)
def update_preferences(
    preference_update: PreferenceUpdate,
    session: Session = Depends(get_session)
):
    """
    更新用户偏好设置
    
    Args:
        preference_update: 偏好更新数据
        session: 数据库会话
        
    Returns:
        更新结果
    """
    auth_service = AuthService(session)
    auth_service.update_user_preferences(
        preference_update.username,
        preference_update.preferences
    )
    
    return {
        "success": True,
        "message": "偏好设置已保存"
    }
