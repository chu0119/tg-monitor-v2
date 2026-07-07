"""案件管理相关 Pydantic 模型"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_serializer
from app.utils.json_encoder import datetime_to_local_iso


class CaseResponse(BaseModel):
    """案件响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_number: str
    case_name: str
    case_type: Optional[str] = None
    status: str = "open"
    description: Optional[str] = None
    lead_investigator: Optional[str] = None
    priority: str = "medium"
    alert_count: int = 0
    person_count: int = 0
    created_by: Optional[str] = None
    closed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @field_serializer('created_at', 'updated_at', 'closed_at')
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        return datetime_to_local_iso(dt)


class CaseDetailResponse(CaseResponse):
    """案件详情响应（含关联数据）"""
    alerts: List[dict] = Field(default_factory=list, description="关联告警列表")
    persons: List[dict] = Field(default_factory=list, description="关联人员列表")


class CaseCreate(BaseModel):
    """创建案件"""
    case_name: str = Field(..., min_length=1, max_length=200, description="案件名称")
    case_type: Optional[str] = Field(None, max_length=50, description="案件类型")
    description: Optional[str] = Field(None, description="案件描述")
    lead_investigator: Optional[str] = Field(None, max_length=100, description="主办人")
    priority: str = Field("medium", description="优先级: low/medium/high/critical")
    created_by: Optional[str] = Field(None, max_length=100, description="创建人")


class CaseUpdate(BaseModel):
    """更新案件"""
    case_name: Optional[str] = Field(None, min_length=1, max_length=200, description="案件名称")
    case_type: Optional[str] = Field(None, max_length=50, description="案件类型")
    status: Optional[str] = Field(None, description="状态: open/investigating/closed/archived")
    description: Optional[str] = Field(None, description="案件描述")
    lead_investigator: Optional[str] = Field(None, max_length=100, description="主办人")
    priority: Optional[str] = Field(None, description="优先级: low/medium/high/critical")


class CaseAlertAdd(BaseModel):
    """添加告警到案件"""
    alert_id: int = Field(..., description="告警ID")
    added_by: Optional[str] = Field(None, max_length=100, description="添加人")


class CasePersonAdd(BaseModel):
    """添加人员到案件"""
    sender_id: int = Field(..., description="发送者ID")
    role: Optional[str] = Field("related", max_length=50, description="角色: suspect/witness/victim/related")
    added_by: Optional[str] = Field(None, max_length=100, description="添加人")
