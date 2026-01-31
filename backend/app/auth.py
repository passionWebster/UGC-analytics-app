# auth.py
"""
用户认证服务
处理用户登录、注册、token 生成等认证相关逻辑
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from sqlmodel import Session, select
from fastapi import HTTPException, status

from .models import User
from .schemas import UserCreate, UserLogin, UserResponse
from .config import settings


class AuthService:
    """用户认证服务类"""
    
    def __init__(self, session: Session):
        self.session = session
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """
        创建 JWT 访问令牌
        
        Args:
            data: 要编码的数据字典
            expires_delta: 过期时间增量
            
        Returns:
            JWT token 字符串
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str) -> Optional[str]:
        """
        验证 JWT token
        
        Args:
            token: JWT token
            
        Returns:
            用户名或 None
        """
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            username: str = payload.get("sub")
            if username is None:
                return None
            return username
        except JWTError:
            return None
    
    def register_user(self, user_create: UserCreate) -> UserResponse:
        """
        注册新用户
        
        Args:
            user_create: 用户创建数据
            
        Returns:
            创建的用户信息
            
        Raises:
            HTTPException: 如果用户名或邮箱已存在
        """
        # 检查用户名是否已存在
        existing_user = self.session.exec(
            select(User).where(User.username == user_create.username)
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="用户名已存在"
            )
        
        # 检查邮箱是否已存在
        existing_email = self.session.exec(
            select(User).where(User.email == user_create.email)
        ).first()
        
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="邮箱已存在"
            )
        
        # 创建新用户
        # 注意：实际生产环境中应该使用密码哈希（如 bcrypt）
        new_user = User(
            username=user_create.username,
            email=user_create.email,
            password=user_create.password,  # TODO: 应该哈希密码
            preferences=None,
            created_at=datetime.now()
        )
        
        self.session.add(new_user)
        self.session.commit()
        self.session.refresh(new_user)
        
        return UserResponse(
            id=new_user.id,
            username=new_user.username,
            email=new_user.email,
            preferences=new_user.preferences,
            created_at=new_user.created_at
        )
    
    def authenticate_user(self, user_login: UserLogin) -> Optional[User]:
        """
        验证用户凭证
        
        Args:
            user_login: 用户登录数据
            
        Returns:
            用户对象或 None
        """
        user = self.session.exec(
            select(User).where(
                User.username == user_login.username,
                User.password == user_login.password  # TODO: 应该使用密码哈希验证
            )
        ).first()
        
        return user
    
    def login(self, user_login: UserLogin) -> dict:
        """
        用户登录
        
        Args:
            user_login: 登录凭证
            
        Returns:
            包含 token 和用户信息的字典
            
        Raises:
            HTTPException: 如果凭证无效
        """
        user = self.authenticate_user(user_login)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )
        
        # 创建访问令牌
        access_token = self.create_access_token(data={"sub": user.username})
        
        # 检查是否有偏好设置
        has_preferences = bool(
            user.preferences and 
            user.preferences.strip() and 
            user.preferences not in ['null', '[]']
        )
        
        return {
            "success": True,
            "message": "登录成功",
            "access_token": access_token,
            "token_type": "bearer",
            "hasPreferences": has_preferences,
            "preferences": user.preferences,
            "user": UserResponse(
                id=user.id,
                username=user.username,
                email=user.email,
                preferences=user.preferences,
                created_at=user.created_at
            )
        }
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """
        根据用户名获取用户
        
        Args:
            username: 用户名
            
        Returns:
            用户对象或 None
        """
        return self.session.exec(
            select(User).where(User.username == username)
        ).first()
    
    def update_user_preferences(self, username: str, preferences: list) -> bool:
        """
        更新用户偏好设置
        
        Args:
            username: 用户名
            preferences: 偏好列表
            
        Returns:
            成功返回 True
            
        Raises:
            HTTPException: 如果用户不存在
        """
        user = self.get_user_by_username(username)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        import json
        user.preferences = json.dumps(preferences, ensure_ascii=False)
        self.session.commit()
        
        return True
