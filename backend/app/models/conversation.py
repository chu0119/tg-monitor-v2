"""会话/对话模型"""
from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, Text, ForeignKey, Enum, JSON, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class ConversationType(str, enum.Enum):
    """会话类型枚举"""
    PRIVATE = "private"
    GROUP = "group"
    CHANNEL = "channel"
    SUPERGROUP = "supergroup"


class ConversationStatus(str, enum.Enum):
    """会话状态枚举"""
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"
    ERROR = "error"


class Conversation(Base):
    """会话表"""

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(BigInteger, index=True, nullable=False, comment="聊天ID（使用BigInteger支持大数值）")
    account_id = Column(Integer, ForeignKey("telegram_accounts.id"), nullable=False, index=True)

    # 会话信息
    chat_type = Column(String(20), nullable=False, index=True)
    title = Column(String(255))
    username = Column(String(100), index=True)
    invite_link = Column(Text)
    description = Column(Text)

    # 监控配置
    status = Column(String(20), default="active")
    enable_realtime = Column(Boolean, default=True)
    enable_history = Column(Boolean, default=True)
    history_days = Column(Integer, default=7)
    history_limit = Column(Integer, default=1000)

    # 关键词配置
    keyword_groups = Column(JSON)
    enable_all_keywords = Column(Boolean, default=False)

    # 统计信息
    total_messages = Column(Integer, default=0)
    total_alerts = Column(Integer, default=0)
    last_message_id = Column(Integer)
    last_message_at = Column(DateTime)

    # 元数据
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    note = Column(Text)
    extra = Column(JSON)

    # 关系
    account = relationship("TelegramAccount", backref="conversations")

    # 组合索引 - 优化查询性能
    __table_args__ = (
        Index('ix_conversation_account_chat', 'account_id', 'chat_id'),
        Index('ix_conversation_account_status', 'account_id', 'status'),
        Index('ix_conversation_status_realtime', 'status', 'enable_realtime'),
    )

    def __repr__(self):
        return f"<Conversation(id={self.id}, chat_id={self.chat_id}, title={self.title})>"
