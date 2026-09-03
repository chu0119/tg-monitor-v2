"""告警模型 - 修复循环引用"""
from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, Text, ForeignKey, Enum, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class AlertStatus(str, enum.Enum):
    """告警状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    RESOLVED = "resolved"
    IGNORED = "ignored"
    FALSE_POSITIVE = "false_positive"


class AlertLevel(str, enum.Enum):
    """告警级别枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Alert(Base):
    """告警表"""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(BigInteger, ForeignKey("messages.id"), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), index=True)
    keyword_id = Column(Integer, ForeignKey("keywords.id"), index=True)
    sender_id = Column(Integer, ForeignKey("senders.id"), index=True)

    # 告警信息
    keyword_text = Column(String(500), comment="匹配的关键词文本")
    keyword_group_name = Column(String(100), comment="关键词组名称")
    alert_level = Column(String(20), nullable=False, index=True)
    status = Column(String(20), default="pending", index=True)

    # 摘要
    matched_text = Column(Text)
    message_preview = Column(Text)
    highlighted_message = Column(Text, comment="带关键词高亮的消息内容 (HTML)")

    # 处理信息
    handler = Column(String(100))
    handler_note = Column(Text)
    handled_at = Column(DateTime)

    # 通知信息
    notification_sent = Column(Boolean, default=False)
    notification_channels = Column(JSON)
    notification_status = Column(JSON)

    # 元数据
    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


    # 增强功能字段
    dedup_key = Column(String(64), index=True, comment="去重键")
    assigned_to = Column(String(100), index=True, comment="分配给")
    assignee = Column(String(100), comment="指派人(旧)")
    assignee_note = Column(Text, comment="指派备注(旧)")
    assigned_at = Column(DateTime, comment="分配时间")
    workflow_status = Column(String(30), index=True, comment="工作流状态")
    handler_result = Column(String(50), comment="处理结果")
    case_id = Column(Integer, ForeignKey("cases.id"), index=True, comment="关联案件ID")
    priority_score = Column(Integer, index=True, comment="优先级评分")
    is_merged = Column(Boolean, default=False, comment="是否已合并")
    merged_into_id = Column(BigInteger, comment="合并到的主告警ID")

    # 关系 - 移除循环引用
    message = relationship("Message", foreign_keys=[message_id])
    conversation = relationship("Conversation")
    keyword = relationship("Keyword")
    sender = relationship("Sender")

    def __repr__(self):
        return f"<Alert(id={self.id}, keyword={self.keyword_text}, status={self.status})>"
