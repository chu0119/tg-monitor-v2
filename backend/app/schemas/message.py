"""消息相关的 Pydantic 模型"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_serializer
from app.utils import datetime_to_iso


class MessageResponse(BaseModel):
    """消息响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    sender_id: Optional[int]
    message_type: str
    text: Optional[str]
    caption: Optional[str]
    date: datetime
    views: Optional[int]
    forwards: Optional[int]
    has_media: bool
    is_reply: bool
    matched_keywords: Optional[List[str]]
    alert_id: Optional[int]
    created_at: datetime

    # 关联信息
    sender_username: Optional[str] = None
    sender_first_name: Optional[str] = None
    conversation_title: Optional[str] = None

    @field_serializer('date', 'created_at')
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        """序列化datetime为ISO格式（带时区信息）"""
        return datetime_to_iso(dt)

    model_config = ConfigDict(from_attributes=True, ser_json_timedelta='float')


class MessageFilter(BaseModel):
    """消息筛选"""
    conversation_ids: Optional[List[int]] = Field(None, description="会话ID列表")
    sender_ids: Optional[List[int]] = Field(None, description="发送者ID列表")
    keyword: Optional[str] = Field(None, description="关键词搜索")
    message_type: Optional[str] = Field(None, description="消息类型")
    has_alert: Optional[bool] = Field(None, description="是否有告警")
    start_date: Optional[datetime] = Field(None, description="开始时间")
    end_date: Optional[datetime] = Field(None, description="结束时间")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(50, ge=1, le=500, description="每页数量")


class MessageExport(BaseModel):
    """消息导出"""
    message_ids: Optional[List[int]] = Field(None, description="指定消息ID列表")
    filter: Optional[MessageFilter] = Field(None, description="筛选条件")
    format: str = Field("csv", description="导出格式: csv, json, xlsx")
    include_sender: bool = Field(True, description="包含发送者信息")
    include_conversation: bool = Field(True, description="包含会话信息")
