"""审计日志相关 Pydantic 模型"""
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, ConfigDict, field_serializer
from app.utils.json_encoder import datetime_to_local_iso


class AuditLogResponse(BaseModel):
    """审计日志响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    operator: Optional[str] = None
    action: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    detail: Optional[Any] = None
    ip_address: Optional[str] = None
    created_at: datetime

    @field_serializer('created_at')
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        return datetime_to_local_iso(dt)


class AuditStatsResponse(BaseModel):
    """审计统计响应"""
    by_action: List[dict] = Field(default_factory=list, description="按操作类型统计")
    by_operator: List[dict] = Field(default_factory=list, description="按操作人统计")
    total: int = Field(0, description="总数")
