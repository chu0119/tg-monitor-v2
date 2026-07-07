"""审计日志模型"""
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.core.database import Base


class AuditLog(Base):
    """审计日志表"""
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    operator = Column(String(100), index=True, comment="操作人")
    action = Column(String(50), nullable=False, index=True, comment="操作类型")
    target_type = Column(String(50), index=True, comment="目标类型")
    target_id = Column(String(50), comment="目标ID")
    detail = Column(JSON, comment="详情")
    ip_address = Column(String(50), comment="IP地址")
    created_at = Column(DateTime, server_default=func.now(), index=True, comment="创建时间")

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action}, operator={self.operator})>"
