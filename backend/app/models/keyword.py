"""关键词模型"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class MatchType(str, enum.Enum):
    """匹配类型枚举"""
    EXACT = "exact"  # 精确匹配
    CONTAINS = "contains"  # 包含匹配
    REGEX = "regex"  # 正则匹配
    FUZZY = "fuzzy"  # 模糊匹配


class AlertLevel(str, enum.Enum):
    """告警级别枚举"""
    LOW = "low"  # 低
    MEDIUM = "medium"  # 中
    HIGH = "high"  # 高
    CRITICAL = "critical"  # 严重


class KeywordGroup(Base):
    """关键词组表"""

    __tablename__ = "keyword_groups"

    id = Column(Integer, primary_key=True, index=True, comment="关键词组ID")
    name = Column(String(100), nullable=False, unique=True, comment="关键词组名称")
    description = Column(Text, comment="描述")

    # 配置
    match_type = Column(String(20), default=MatchType.CONTAINS, comment="匹配类型")
    case_sensitive = Column(Boolean, default=False, comment="是否区分大小写")
    alert_level = Column(String(20), default=AlertLevel.MEDIUM, comment="告警级别")

    # 通知配置
    enable_notification = Column(Boolean, default=True, comment="启用通知")
    notification_channels = Column(JSON, comment="通知渠道列表")

    # 状态
    is_active = Column(Boolean, default=True, comment="是否激活")
    priority = Column(Integer, default=0, comment="优先级")

    # 统计
    total_keywords = Column(Integer, default=0, comment="关键词数量")
    total_matches = Column(Integer, default=0, comment="总匹配次数")

    # 元数据
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    color = Column(String(20), comment="显示颜色")

    # 关系
    keywords = relationship("Keyword", back_populates="group", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<KeywordGroup(id={self.id}, name={self.name}, is_active={self.is_active})>"


class Keyword(Base):
    """关键词表"""

    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True, index=True, comment="关键词ID")
    group_id = Column(Integer, ForeignKey("keyword_groups.id"), nullable=False, index=True, comment="关键词组ID")
    word = Column(String(500), nullable=False, comment="关键词内容")

    # 配置
    match_type = Column(String(20), comment="匹配类型(覆盖组设置)")
    case_sensitive = Column(Boolean, comment="是否区分大小写(覆盖组设置)")
    alert_level = Column(String(20), comment="告警级别(覆盖组设置)")

    # 统计
    match_count = Column(Integer, default=0, comment="匹配次数")
    last_matched_at = Column(DateTime, comment="最后匹配时间")

    # 状态
    is_active = Column(Boolean, default=True, comment="是否激活")

    # 元数据
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    note = Column(Text, comment="备注")

    # 关系
    group = relationship("KeywordGroup", back_populates="keywords")

    def __repr__(self):
        return f"<Keyword(id={self.id}, word={self.word}, group_id={self.group_id})>"
