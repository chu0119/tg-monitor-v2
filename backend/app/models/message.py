"""消息模型"""
from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, Text, ForeignKey, JSON, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class MessageType(str, enum.Enum):
    """消息类型枚举"""
    TEXT = "text"
    PHOTO = "photo"
    VIDEO = "video"
    DOCUMENT = "document"
    AUDIO = "audio"
    VOICE = "voice"
    STICKER = "sticker"
    ANIMATION = "animation"
    POLL = "poll"
    SERVICE = "service"


class Message(Base):
    """消息表"""

    __tablename__ = "messages"

    # 使用 Telegram 消息 ID 作为主键（可能非常大，需要 BigInteger）
    id = Column(BigInteger, primary_key=True, autoincrement=False, comment="Telegram消息ID")
    # telegram_id 字段已废弃，保留用于兼容旧数据
    telegram_id = Column(BigInteger, index=True, comment="Telegram Message ID (已废弃)")
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("senders.id"), index=True)

    # 消息内容
    message_type = Column(String(20), nullable=False, index=True)
    text = Column(Text)
    caption = Column(Text)

    # 媒体信息
    media_file_id = Column(String(255))
    media_file_unique_id = Column(String(255))
    media_file_size = Column(BigInteger)

    # 转发信息
    forward_from = Column(JSON)
    reply_to_msg_id = Column(BigInteger, comment="回复的消息ID")

    # 元数据
    date = Column(DateTime, nullable=False, index=True)
    views = Column(Integer)
    forwards = Column(Integer)
    has_media = Column(Boolean, default=False)
    is_reply = Column(Boolean, default=False)

    # 告警标记
    matched_keywords = Column(JSON)
    alert_id = Column(Integer, ForeignKey("alerts.id"), index=True)

    # 创建时间
    created_at = Column(DateTime, server_default=func.now())

    # 关系 - 移除循环引用
    conversation = relationship("Conversation", backref="messages")
    sender = relationship("Sender", backref="messages")

    # 组合索引 - 优化查询性能
    __table_args__ = (
        Index('ix_message_conversation_date', 'conversation_id', 'date'),
        Index('ix_message_alert_date', 'alert_id', 'date'),
        Index('ix_message_sender_date', 'sender_id', 'date'),
    )

    def __repr__(self):
        return f"<Message(id={self.id}, type={self.message_type}, date={self.date})>"
