"""案件管理模型"""
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.core.database import Base


class Case(Base):
    """案件表"""
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    case_number = Column(String(50), unique=True, index=True, nullable=False, comment="案件编号 CASE-YYYYMMDD-NNN")
    case_name = Column(String(200), nullable=False, comment="案件名称")
    case_type = Column(String(50), comment="案件类型")
    status = Column(String(20), default="open", index=True, comment="状态: open/investigating/closed/archived")
    description = Column(Text, comment="案件描述")
    lead_investigator = Column(String(100), comment="主办人")
    priority = Column(String(20), default="medium", index=True, comment="优先级: low/medium/high/critical")
    alert_count = Column(Integer, default=0, comment="关联告警数")
    person_count = Column(Integer, default=0, comment="关联人员数")
    created_by = Column(String(100), comment="创建人")
    closed_at = Column(DateTime, comment="关闭时间")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def __repr__(self):
        return f"<Case(id={self.id}, case_number={self.case_number}, status={self.status})>"


class CaseAlert(Base):
    """案件-告警关联表"""
    __tablename__ = "case_alerts"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, nullable=False, index=True, comment="案件ID")
    alert_id = Column(Integer, nullable=False, index=True, comment="告警ID")
    added_by = Column(String(100), comment="添加人")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    def __repr__(self):
        return f"<CaseAlert(case_id={self.case_id}, alert_id={self.alert_id})>"


class CasePerson(Base):
    """案件-人员关联表"""
    __tablename__ = "case_persons"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, nullable=False, index=True, comment="案件ID")
    sender_id = Column(Integer, nullable=False, index=True, comment="发送者ID")
    role = Column(String(50), default="related", comment="角色: suspect/witness/victim/related")
    added_by = Column(String(100), comment="添加人")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    def __repr__(self):
        return f"<CasePerson(case_id={self.case_id}, sender_id={self.sender_id})>"
