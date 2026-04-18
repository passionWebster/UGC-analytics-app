# auth.py
"""
用户认证服务
处理用户登录、注册、token 生成等认证相关逻辑
"""
from datetime import datetime, timedelta
from typing import Optional
import secrets
from jose import JWTError, jwt
from sqlmodel import Session, select
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

try:
    import bcrypt as _bcrypt

    if not hasattr(_bcrypt, "__about__") and hasattr(_bcrypt, "__version__"):
        class _BcryptAbout:
            __version__ = _bcrypt.__version__

        _bcrypt.__about__ = _BcryptAbout()  # type: ignore[attr-defined]
except (ImportError, AttributeError):
    pass

from passlib.context import CryptContext

from .models import User
from .schemas import UserCreate, UserLogin, UserResponse
from .config import settings
from .database import get_session

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """用户认证服务类"""
    
    def __init__(self, session: Session):
        self.session = session

    @classmethod
    def is_password_hashed(cls, password: str) -> bool:
        return bool(PWD_CONTEXT.identify(password))

    @classmethod
    def hash_password(cls, password: str) -> str:
        return PWD_CONTEXT.hash(password)

    @classmethod
    def verify_password(cls, plain_password: str, stored_password: str) -> bool:
        # 兼容历史明文密码数据：验证成功后由调用方触发升级
        if cls.is_password_hashed(stored_password):
            return PWD_CONTEXT.verify(plain_password, stored_password)
        return secrets.compare_digest(plain_password, stored_password)
    
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
        
        # 创建新用户（bcrypt 哈希存储）
        new_user = User(
            username=user_create.username,
            email=user_create.email,
            password=self.hash_password(user_create.password),
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
            is_admin=new_user.is_admin,
            is_active=new_user.is_active,
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
            select(User).where(User.username == user_login.username)
        ).first()

        if not user:
            return None

        if not self.verify_password(user_login.password, user.password):
            return None

        # 历史明文密码首次登录后自动升级为哈希
        if not self.is_password_hashed(user.password):
            user.password = self.hash_password(user_login.password)
            self.session.add(user)
            self.session.commit()

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

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账户已被停用，请联系管理员"
            )
        
        # 创建访问令牌
        access_token = self.create_access_token(
            data={"sub": user.username, "is_admin": user.is_admin}
        )
        
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
                is_admin=user.is_admin,
                is_active=user.is_active,
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

    def change_password(self, user: User, old_password: str, new_password: str) -> None:
        """
        修改用户密码（需校验旧密码）。
        """
        if not self.verify_password(old_password, user.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="旧密码错误"
            )

        user.password = self.hash_password(new_password)
        self.session.add(user)
        self.session.commit()


# ─────────────────────────────────────────────────────────
# 依赖函数：获取当前登录用户 / 管理员
# ─────────────────────────────────────────────────────────
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: Session = Depends(get_session),
) -> User:
    """
    基于 JWT 的当前用户获取依赖。若 token 无效或用户被禁用则抛出 HTTP 401/403。
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少认证凭证"
        )

    username = AuthService.verify_token(credentials.credentials)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的认证凭证"
        )

    user = session.exec(select(User).where(User.username == username)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被停用，请联系管理员"
        )

    return user


def get_current_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    仅管理员可访问的依赖。
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可执行此操作"
        )
    return current_user
