"""会话相关的 Pydantic 模型"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_serializer
from app.models.conversation import ConversationType, ConversationStatus
from app.utils import datetime_to_iso


class ConversationBase(BaseModel):
    """会话基础模型"""
    chat_id: int = Field(..., description="Telegram Chat ID")
    chat_type: ConversationType = Field(..., description="会话类型")
    title: Optional[str] = Field(None, description="标题")
    username: Optional[str] = Field(None, description="用户名/群组名")


class ConversationCreate(ConversationBase):
    """创建会话"""
    account_id: int = Field(..., description="关联账号ID")
    description: Optional[str] = Field(None, description="描述")
    invite_link: Optional[str] = Field(None, description="邀请链接")


class ConversationMonitorConfig(BaseModel):
    """监控配置"""
    enable_realtime: Optional[bool] = Field(None, description="启用实时监控")
    enable_history: Optional[bool] = Field(None, description="启用历史拉取")
    history_days: Optional[int] = Field(None, ge=1, le=365, description="历史回溯天数")
    history_limit: Optional[int] = Field(None, ge=1, le=100000, description="历史消息限制")
    keyword_groups: Optional[List[int]] = Field(None, description="关联关键词组")
    enable_all_keywords: Optional[bool] = Field(None, description="启用所有关键词")


class ConversationUpdate(BaseModel):
    """更新会话"""
    status: Optional[ConversationStatus] = Field(None, description="监控状态")
    note: Optional[str] = Field(None, description="备注")
    monitor_config: Optional[ConversationMonitorConfig] = Field(None, description="监控配置")


class ConversationBatchUpdate(BaseModel):
    """批量更新会话请求模型"""
    conversation_ids: List[int] = Field(..., description="会话ID列表")
    update_data: ConversationUpdate = Field(..., description="更新数据")


class ConversationResponse(BaseModel):
    """会话响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    chat_id: int
    account_id: int
    chat_type: ConversationType
    title: Optional[str]
    username: Optional[str]
    description: Optional[str]
    invite_link: Optional[str]
    status: Optional[ConversationStatus]
    enable_realtime: Optional[bool]
    enable_history: Optional[bool]
    history_days: Optional[int]
    history_limit: Optional[int]
    keyword_groups: Optional[List[int]]
    enable_all_keywords: Optional[bool]
    total_messages: Optional[int]
    total_alerts: Optional[int]
    last_message_id: Optional[int]
    last_message_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    note: Optional[str]

    @field_serializer('last_message_at', 'created_at', 'updated_at')
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        """序列化datetime为ISO格式（带时区信息）"""
        return datetime_to_iso(dt)

    model_config = ConfigDict(from_attributes=True, ser_json_timedelta='float')
