"""重点关注名单模型"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.core.database import Base


class Watchlist(Base):
    """重点关注名单表"""
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(20), nullable=False, index=True, comment="实体类型: sender/phone/username")
    entity_value = Column(String(200), nullable=False, index=True, comment="实体值")
    entity_name = Column(String(200), comment="实体名称")
    threat_level = Column(String(20), default="medium", index=True, comment="威胁级别: low/medium/high/critical")
    reason = Column(Text, comment="原因")
    case_id = Column(Integer, comment="关联案件ID")
    tags = Column(JSON, comment="标签列表")
    added_by = Column(String(100), comment="添加人")
    is_active = Column(Boolean, default=True, index=True, comment="是否激活")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def __repr__(self):
        return f"<Watchlist(id={self.id}, entity_type={self.entity_type}, entity_value={self.entity_value})>"
