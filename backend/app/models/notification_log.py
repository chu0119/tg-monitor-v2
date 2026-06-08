"""通知日志模型"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Enum, JSON
from sqlalchemy.sql import func
from app.core.database import Base


class NotificationLog(Base):
    """通知发送日志表"""

    __tablename__ = "notification_logs"

    id = Column(Integer, primary_key=True, index=True, comment="日志ID")
    alert_id = Column(Integer, ForeignKey("alerts.id"), index=True, comment="告警ID")
    config_id = Column(Integer, ForeignKey("notification_configs.id"), index=True, comment="配置ID")

    # 发送信息
    notification_type = Column(String(50), nullable=False, index=True, comment="通知类型")
    recipient = Column(String(255), comment="接收者")
    title = Column(String(500), comment="通知标题")
    content = Column(Text, comment="通知内容")

    # 状态
    status = Column(String(20), nullable=False, index=True, comment="状态: success/failed/pending")
    error_message = Column(Text, comment="错误信息")
    retry_count = Column(Integer, default=0, comment="重试次数")

    # 响应信息
    response = Column(JSON, comment="响应内容")

    # 元数据
    created_at = Column(DateTime, server_default=func.now(), index=True, comment="创建时间")
    sent_at = Column(DateTime, comment="发送完成时间")

    def __repr__(self):
        return f"<NotificationLog(id={self.id}, type={self.notification_type}, status={self.status})>"
