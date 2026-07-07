"""重点关注名单相关 Pydantic 模型"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_serializer
from app.utils.json_encoder import datetime_to_local_iso


class WatchlistResponse(BaseModel):
    """名单条目响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: str
    entity_value: str
    entity_name: Optional[str] = None
    threat_level: str = "medium"
    reason: Optional[str] = None
    case_id: Optional[int] = None
    tags: Optional[list] = None
    added_by: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        return datetime_to_local_iso(dt)


class WatchlistCreate(BaseModel):
    """添加到名单"""
    entity_type: str = Field(..., description="实体类型: sender/phone/username")
    entity_value: str = Field(..., min_length=1, description="实体值")
    entity_name: Optional[str] = Field(None, max_length=200, description="实体名称")
    threat_level: str = Field("medium", description="威胁级别: low/medium/high/critical")
    reason: Optional[str] = Field(None, description="原因")
    case_id: Optional[int] = Field(None, description="关联案件ID")
    tags: Optional[list] = Field(None, description="标签")
    added_by: Optional[str] = Field(None, max_length=100, description="添加人")


class WatchlistUpdate(BaseModel):
    """更新名单条目"""
    entity_name: Optional[str] = Field(None, max_length=200, description="实体名称")
    threat_level: Optional[str] = Field(None, description="威胁级别: low/medium/high/critical")
    reason: Optional[str] = Field(None, description="原因")
    case_id: Optional[int] = Field(None, description="关联案件ID")
    tags: Optional[list] = Field(None, description="标签")
    is_active: Optional[bool] = Field(None, description="是否激活")
    added_by: Optional[str] = Field(None, max_length=100, description="操作人")


class WatchlistCheckResult(BaseModel):
    """名单检查结果"""
    found: bool = Field(False, description="是否在名单中")
    entries: List[WatchlistResponse] = Field(default_factory=list, description="匹配的名单条目")
