"""通知配置模型"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Enum, JSON
from sqlalchemy.sql import func
from app.core.database import Base
import enum


class NotificationType(str, enum.Enum):
    """通知类型枚举"""
    EMAIL = "email"  # 邮件
    DINGTALK = "dingtalk"  # 钉钉
    WECOM = "wecom"  # 企业微信
    SERVERCHAN = "serverchan"  # Server酱
    WEBHOOK = "webhook"  # 自定义Webhook
    TELEGRAM = "telegram"  # Telegram推送


class NotificationConfig(Base):
    """通知配置表"""

    __tablename__ = "notification_configs"

    id = Column(Integer, primary_key=True, index=True, comment="配置ID")
    name = Column(String(100), nullable=False, unique=True, comment="配置名称")
    notification_type = Column(Enum(NotificationType), nullable=False, index=True, comment="通知类型")

    # 配置内容
    config = Column(JSON, nullable=False, comment="配置详情")
    # 各类型配置示例:
    # EMAIL: {smtp_host, smtp_port, smtp_user, smtp_password, from_email, to_emails}
    # DINGTALK: {webhook, secret}
    # WECOM: {webhook}
    # SERVERCHAN: {sckey}
    # WEBHOOK: {url, method, headers, body_template}
    # TELEGRAM: {bot_token, chat_id}

    # 过滤配置
    min_alert_level = Column(String(20), comment="最低告警级别")
    keyword_groups = Column(JSON, comment="适用关键词组")
    conversations = Column(JSON, comment="适用会话")

    # 模板配置
    title_template = Column(Text, comment="标题模板")
    body_template = Column(Text, comment="内容模板")

    # 状态
    is_active = Column(Boolean, default=True, comment="是否激活")
    priority = Column(Integer, default=0, comment="优先级")

    # 统计
    total_sent = Column(Integer, default=0, comment="总发送次数")
    total_failed = Column(Integer, default=0, comment="失败次数")
    last_sent_at = Column(DateTime, comment="最后发送时间")
    last_error = Column(Text, comment="最后错误信息")

    # 元数据
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    note = Column(Text, comment="备注")

    def __repr__(self):
        return f"<NotificationConfig(id={self.id}, name={self.name}, type={self.notification_type})>"
