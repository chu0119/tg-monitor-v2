"""手机号记录模型"""
import sqlalchemy
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Text
from sqlalchemy.sql import func
from app.core.database import Base


class PhoneRecord(Base):
    """手机号记录 - 记录平台捕获到的所有手机号信息"""

    __tablename__ = "phone_records"

    id = Column(Integer, primary_key=True, index=True, comment="记录ID")
    phone = Column(String(20), nullable=False, index=True, comment="标准化手机号（去掉+号）")
    phone_display = Column(String(30), comment="原始显示格式")
    country_code = Column(String(10), index=True, comment="国家代码")
    country = Column(String(50), comment="国家名")
    phone_location = Column(String(100), comment="归属地")
    carrier = Column(String(50), comment="运营商")
    source_type = Column(String(20), nullable=False, index=True, comment="来源类型：sender/message/alert")
    source_id = Column(BigInteger, nullable=False, comment="来源ID")
    source_detail = Column(Text, comment="来源详情摘要")
    conversation_id = Column(Integer, index=True, comment="所属会话ID")
    first_seen_at = Column(DateTime, comment="首次发现时间")
    last_seen_at = Column(DateTime, comment="最后发现时间")
    occurrence_count = Column(Integer, default=1, comment="出现次数")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def __repr__(self):
        return f"<PhoneRecord(id={self.id}, phone={self.phone}, source_type={self.source_type})>"
