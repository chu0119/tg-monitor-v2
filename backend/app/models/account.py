"""Telegram账号模型"""
from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.core.database import Base


class TelegramAccount(Base):
    """Telegram 账号表"""

    __tablename__ = "telegram_accounts"

    id = Column(Integer, primary_key=True, index=True, comment="账号ID")
    phone = Column(String(20), unique=True, index=True, nullable=False, comment="手机号")
    user_id = Column(BigInteger, index=True, comment="Telegram用户ID")
    username = Column(String(100), comment="用户名")
    first_name = Column(String(100), comment="名字")
    last_name = Column(String(100), comment="姓氏")
    is_premium = Column(Boolean, default=False, comment="是否Premium")
    is_bot = Column(Boolean, default=False, comment="是否Bot")

    # API 凭据（为空时使用全局配置）
    api_id = Column(BigInteger, nullable=True, comment="API ID（为空时使用全局配置）")
    api_hash = Column(String(100), nullable=True, comment="API Hash（为空时使用全局配置）")

    # 会话状态
    session_file = Column(String(255), unique=True, comment="会话文件路径")
    is_active = Column(Boolean, default=True, comment="是否激活")
    is_authorized = Column(Boolean, default=False, comment="是否已授权")
    last_used_at = Column(DateTime, comment="最后使用时间")

    # 代理配置
    proxy_config = Column(JSON, comment="代理配置")

    # 统计信息
    total_messages = Column(Integer, default=0, comment="总消息数")
    total_conversations = Column(Integer, default=0, comment="总会话数")

    # 元数据
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    note = Column(Text, comment="备注")

    def __repr__(self):
        return f"<TelegramAccount(id={self.id}, phone={self.phone}, is_active={self.is_active})>"
