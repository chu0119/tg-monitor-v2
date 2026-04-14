"""告警相关的 Pydantic 模型"""
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, ConfigDict, field_serializer
from app.models.alert import AlertStatus, AlertLevel
from app.utils.json_encoder import datetime_to_local_iso


class AlertResponse(BaseModel):
    """告警响应"""
    model_config = ConfigDict(from_attributes=True, ser_json_timedelta='float')

    id: int
    message_id: int
    conversation_id: int
    keyword_id: Optional[int]
    sender_id: Optional[int]
    keyword_text: Optional[str]
    keyword_group_name: Optional[str]
    alert_level: AlertLevel
    status: AlertStatus
    matched_text: Optional[str]
    message_preview: Optional[str]
    highlighted_message: Optional[str] = None  # 带关键词高亮的消息内容
    handler: Optional[str]
    handler_note: Optional[str]
    handled_at: Optional[datetime]
    notification_sent: bool
    created_at: datetime
    updated_at: datetime

    # 关联信息
    sender_username: Optional[str] = None
    conversation_title: Optional[str] = None
    message_date: Optional[datetime] = None

    @field_serializer('created_at', 'updated_at', 'handled_at', 'message_date')
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        """序列化datetime为ISO格式（使用本地时区 Asia/Shanghai）"""
        return datetime_to_local_iso(dt)


class AlertFilter(BaseModel):
    """告警筛选"""
    status: Optional[AlertStatus] = Field(None, description="告警状态")
    alert_level: Optional[AlertLevel] = Field(None, description="告警级别")
    keyword_group_id: Optional[int] = Field(None, description="关键词组ID")
    conversation_id: Optional[int] = Field(None, description="会话ID")
    sender_id: Optional[int] = Field(None, description="发送者ID")
    keyword: Optional[str] = Field(None, description="关键词")
    start_date: Optional[datetime] = Field(None, description="开始时间")
    end_date: Optional[datetime] = Field(None, description="结束时间")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(50, ge=1, le=500, description="每页数量")


class AlertUpdate(BaseModel):
    """更新告警级别"""
    alert_level: AlertLevel = Field(..., description="告警级别")


class AlertHandle(BaseModel):
    """处理告警"""
    handler: Optional[str] = Field(None, description="处理人")
    handler_note: Optional[str] = Field(None, description="处理备注")
    status: Optional[AlertStatus] = Field(None, description="处理状态")


class AlertStatusUpdate(BaseModel):
    """更新告警状态"""
    status: AlertStatus = Field(..., description="告警状态")


class AlertStats(BaseModel):
    """告警统计"""
    total: int = Field(default=0, description="总数")
    pending: int = Field(default=0, description="待处理")
    processing: int = Field(default=0, description="处理中")
    resolved: int = Field(default=0, description="已解决")
    ignored: int = Field(default=0, description="已忽略")
    false_positive: int = Field(default=0, description="误报")
    by_level: dict = Field(default_factory=dict, description="按级别统计")
    by_keyword_group: List[dict] = Field(default_factory=list, description="按关键词组统计")
    by_conversation: List[dict] = Field(default_factory=list, description="按会话统计")
    trend: List[dict] = Field(default_factory=list, description="趋势数据")
