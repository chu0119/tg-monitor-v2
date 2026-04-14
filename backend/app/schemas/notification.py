"""通知相关的 Pydantic 模型"""
from datetime import datetime
from typing import Optional, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict, field_serializer, field_validator
from app.models.notification_config import NotificationType
from app.utils import datetime_to_iso


class NotificationConfigBase(BaseModel):
    """通知配置基础模型"""
    name: str = Field(..., min_length=1, max_length=100, description="配置名称")
    notification_type: NotificationType = Field(..., description="通知类型")


class NotificationConfigCreate(NotificationConfigBase):
    """创建通知配置"""
    config: Dict[str, Any] = Field(..., description="配置详情")
    min_alert_level: Optional[Union[str, int]] = Field(None, description="最低告警级别")
    keyword_groups: Optional[list] = Field(None, description="适用关键词组")
    conversations: Optional[list] = Field(None, description="适用会话")
    title_template: Optional[str] = Field(None, description="标题模板")
    body_template: Optional[str] = Field(None, description="内容模板")
    priority: int = Field(0, description="优先级")
    note: Optional[str] = Field(None, description="备注")
    is_active: bool = Field(True, description="是否激活")

    @field_validator('min_alert_level', mode='before')
    @classmethod
    def convert_min_alert_level(cls, v):
        """将 int 类型的告警级别转换为 str"""
        if isinstance(v, int):
            level_map = {1: "low", 2: "medium", 3: "high", 4: "critical"}
            return level_map.get(v, "low")
        return v


class NotificationConfigUpdate(BaseModel):
    """更新通知配置"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="配置名称")
    notification_type: Optional[NotificationType] = Field(None, description="通知类型")
    config: Optional[Dict[str, Any]] = Field(None, description="配置详情")
    min_alert_level: Optional[Union[str, int]] = Field(None, description="最低告警级别")
    keyword_groups: Optional[list] = Field(None, description="适用关键词组")
    conversations: Optional[list] = Field(None, description="适用会话")
    title_template: Optional[str] = Field(None, description="标题模板")
    body_template: Optional[str] = Field(None, description="内容模板")
    is_active: Optional[bool] = Field(None, description="是否激活")
    priority: Optional[int] = Field(None, description="优先级")
    note: Optional[str] = Field(None, description="备注")

    @field_validator('min_alert_level', mode='before')
    @classmethod
    def convert_min_alert_level(cls, v):
        """将 int 类型的告警级别转换为 str"""
        if isinstance(v, int):
            level_map = {1: "low", 2: "medium", 3: "high", 4: "critical"}
            return level_map.get(v, "low")
        return v


class NotificationConfigResponse(BaseModel):
    """通知配置响应"""
    model_config = ConfigDict(from_attributes=True, ser_json_timedelta='float')

    id: int
    name: str
    notification_type: NotificationType
    config: Dict[str, Any]
    min_alert_level: Optional[str]
    keyword_groups: Optional[list]
    conversations: Optional[list]
    title_template: Optional[str]
    body_template: Optional[str]
    is_active: bool
    priority: int
    total_sent: int
    total_failed: int
    last_sent_at: Optional[datetime]
    last_error: Optional[str]
    created_at: datetime
    updated_at: datetime
    note: Optional[str]

    @field_serializer('last_sent_at', 'created_at', 'updated_at')
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        """序列化datetime为ISO格式（带时区信息）"""
        return datetime_to_iso(dt)


class NotificationTest(BaseModel):
    """测试通知"""
    config_id: int = Field(..., description="配置ID")
    test_message: Optional[str] = Field("这是一条测试消息", description="测试内容")
