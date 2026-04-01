"""认证和权限管理服务"""
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, List
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.core.config import settings
from app.models.user import User, Role, AuditLog


# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """认证服务"""

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """获取密码哈希"""
        return pwd_context.hash(password)

    async def create_user(
        self,
        db: AsyncSession,
        username: str,
        password: str,
        email: Optional[str] = None,
        full_name: Optional[str] = None,
        is_superuser: bool = False
    ) -> User:
        """创建用户"""
        hashed_password = self.get_password_hash(password)

        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            is_active=True,
            is_superuser=is_superuser
        )
        db.add(user)

        # 分配默认角色
        if not is_superuser:
            result = await db.execute(select(Role).where(Role.name == "user"))
            default_role = result.scalar_one_or_none()
            if default_role:
                user.roles.append(default_role)

        await db.commit()
        await db.refresh(user)

        # 记录审计日志
        await self.log_action(
            db, user.id, "user.created",
            resource_type="user",
            resource_id=user.id,
            details={"username": username}
        )

        return user

    async def authenticate_user(
        self,
        db: AsyncSession,
        username: str,
        password: str
    ) -> Optional[User]:
        """验证用户"""
        result = await db.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()

        if not user:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        if not user.is_active:
            return None

        # 更新最后登录时间
        user.last_login_at = datetime.now()
        await db.commit()

        return user

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """创建访问令牌"""
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.now() + expires_delta
        else:
            expire = datetime.now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

        return encoded_jwt

    async def get_current_user(
        self,
        db: AsyncSession,
        token: str
    ) -> Optional[User]:
        """获取当前用户"""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                return None
        except JWTError:
            return None

        result = await db.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()

        return user

    async def create_password_reset_token(self, db: AsyncSession, user: User) -> str:
        """创建密码重置令牌"""
        token = secrets.token_urlsafe(32)
        user.reset_token = self.get_password_hash(token)  # 存储哈希值
        user.reset_token_expires = datetime.now() + timedelta(hours=1)

        await db.commit()

        return token

    async def reset_password(
        self,
        db: AsyncSession,
        token: str,
        new_password: str
    ) -> bool:
        """重置密码"""
        # 查找具有此令牌的用户
        result = await db.execute(
            select(User).where(
                User.reset_token.isnot(None),
                User.reset_token_expires > datetime.now()
            )
        )
        users = result.scalars().all()

        for user in users:
            if self.verify_password(token, user.reset_token):
                user.hashed_password = self.get_password_hash(new_password)
                user.reset_token = None
                user.reset_token_expires = None
                await db.commit()

                # 记录审计日志
                await self.log_action(
                    db, user.id, "user.password_reset",
                    resource_type="user",
                    resource_id=user.id
                )

                return True

        return False

    async def log_action(
        self,
        db: AsyncSession,
        user_id: Optional[int],
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status: str = "success",
        error_message: Optional[str] = None
    ):
        """记录审计日志"""
        log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            error_message=error_message
        )
        db.add(log)
        await db.commit()

    async def get_user_permissions(self, db: AsyncSession, user: User) -> List[str]:
        """获取用户权限列表"""
        permissions = set()

        for role in user.roles:
            if role.permissions:
                permissions.update(role.permissions)

        return list(permissions)


class PermissionService:
    """权限服务"""

    # 预定义权限
    PERMISSIONS = {
        # 账号管理
        "accounts.view": "查看账号",
        "accounts.create": "创建账号",
        "accounts.edit": "编辑账号",
        "accounts.delete": "删除账号",

        # 会话管理
        "conversations.view": "查看会话",
        "conversations.create": "添加会话",
        "conversations.edit": "编辑会话",
        "conversations.delete": "删除会话",
        "conversations.monitor": "启动/停止监控",

        # 消息查看
        "messages.view": "查看消息",
        "messages.export": "导出消息",

        # 关键词管理
        "keywords.view": "查看关键词",
        "keywords.create": "创建关键词",
        "keywords.edit": "编辑关键词",
        "keywords.delete": "删除关键词",

        # 告警管理
        "alerts.view": "查看告警",
        "alerts.handle": "处理告警",
        "alerts.delete": "删除告警",

        # 通知配置
        "notifications.view": "查看通知配置",
        "notifications.create": "创建通知配置",
        "notifications.edit": "编辑通知配置",
        "notifications.delete": "删除通知配置",

        # 数据分析
        "analysis.view": "查看分析",
        "analysis.export": "导出报告",

        # 系统设置
        "settings.view": "查看设置",
        "settings.edit": "修改设置",

        # 用户管理
        "users.view": "查看用户",
        "users.create": "创建用户",
        "users.edit": "编辑用户",
        "users.delete": "删除用户",

        # 审计日志
        "audit.view": "查看审计日志",
    }

    async def has_permission(self, db: AsyncSession, user: User, permission: str) -> bool:
        """检查用户是否有权限"""
        # 超级管理员拥有所有权限
        if user.is_superuser:
            return True

        # 获取用户权限
        auth_service = AuthService()
        permissions = await auth_service.get_user_permissions(db, user)

        return permission in permissions

    async def require_permission(
        self,
        db: AsyncSession,
        user: User,
        permission: str
    ):
        """要求权限，如果没有则抛出异常"""
        if not await self.has_permission(db, user, permission):
            from fastapi import HTTPException
            raise HTTPException(
                status_code=403,
                detail=f"权限不足: {permission}"
            )

    async def init_default_roles(self, db: AsyncSession):
        """初始化默认角色"""
        # 检查是否已初始化
        result = await db.execute(select(Role))
        if result.scalar_one_or_none():
            return

        # 管理员角色 - 所有权限
        admin_role = Role(
            name="admin",
            description="管理员",
            permissions=list(self.PERMISSIONS.keys())
        )

        # 用户角色 - 基本权限
        user_permissions = [
            "conversations.view",
            "conversations.monitor",
            "messages.view",
            "messages.export",
            "keywords.view",
            "alerts.view",
            "alerts.handle",
            "notifications.view",
            "analysis.view",
            "analysis.export",
            "settings.view",
        ]
        user_role = Role(
            name="user",
            description="普通用户",
            permissions=user_permissions
        )

        # 只读用户角色
        viewer_permissions = [
            "conversations.view",
            "messages.view",
            "keywords.view",
            "alerts.view",
            "notifications.view",
            "analysis.view",
            "settings.view",
        ]
        viewer_role = Role(
            name="viewer",
            description="只读用户",
            permissions=viewer_permissions
        )

        db.add_all([admin_role, user_role, viewer_role])
        await db.commit()

        logger.info("默认角色初始化完成")


# 全局服务实例
auth_service = AuthService()
permission_service = PermissionService()
