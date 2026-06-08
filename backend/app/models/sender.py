"""发送者模型"""
import sqlalchemy
from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.core.database import Base


class Sender(Base):
    """发送者表"""

    __tablename__ = "senders"

    id = Column(Integer, primary_key=True, index=True, comment="发送者ID")
    user_id = Column(BigInteger().with_variant(sqlalchemy.dialects.mysql.BIGINT(unsigned=True), "mysql"), unique=True, index=True, nullable=False, comment="Telegram用户ID")

    # 基本信息
    username = Column(String(100), index=True, comment="用户名")
    first_name = Column(String(100), comment="名字")
    last_name = Column(String(100), comment="姓氏")
    phone = Column(String(20), comment="手机号")
    is_bot = Column(Boolean, default=False, comment="是否Bot")
    is_verified = Column(Boolean, default=False, comment="是否认证")
    is_premium = Column(Boolean, default=False, comment="是否Premium")

    # 统计信息
    message_count = Column(Integer, default=0, comment="消息总数")
    alert_count = Column(Integer, default=0, comment="触发告警数")

    # 元数据
    created_at = Column(DateTime, server_default=func.now(), comment="首次发现时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    extra = Column(JSON, comment="额外信息")

    def __repr__(self):
        return f"<Sender(id={self.id}, user_id={self.user_id}, username={self.username})>"
