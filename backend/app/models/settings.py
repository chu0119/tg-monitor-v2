"""系统配置模型"""
from sqlalchemy import Column, String, Text, DateTime, func
from app.core.database import Base


class Settings(Base):
    """系统配置表"""

    __tablename__ = "settings"

    key_name = Column(String(100), primary_key=True, comment="配置键名")
    value = Column(Text, comment="配置值")
    category = Column(String(50), default="general", comment="配置分类：general/proxy/notification/account")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def __repr__(self):
        return f"<Settings(key={self.key_name}, category={self.category})>"
