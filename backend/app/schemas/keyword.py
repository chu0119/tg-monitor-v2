"""关键词相关的 Pydantic 模型"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_serializer
from app.models.keyword import MatchType, AlertLevel
from app.utils import datetime_to_iso


class KeywordGroupBase(BaseModel):
    """关键词组基础模型"""
    name: str = Field(..., min_length=1, max_length=100, description="关键词组名称")
    description: Optional[str] = Field(None, description="描述")


class KeywordGroupCreate(KeywordGroupBase):
    """创建关键词组"""
    match_type: MatchType = Field(MatchType.CONTAINS, description="匹配类型")
    case_sensitive: bool = Field(False, description="是否区分大小写")
    alert_level: AlertLevel = Field(AlertLevel.MEDIUM, description="告警级别")
    enable_notification: bool = Field(True, description="启用通知")
    notification_channels: Optional[List[str]] = Field(None, description="通知渠道")
    priority: int = Field(0, description="优先级")
    color: Optional[str] = Field(None, description="显示颜色")


class KeywordGroupUpdate(BaseModel):
    """更新关键词组"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="关键词组名称")
    description: Optional[str] = Field(None, description="描述")
    match_type: Optional[MatchType] = Field(None, description="匹配类型")
    case_sensitive: Optional[bool] = Field(None, description="是否区分大小写")
    alert_level: Optional[AlertLevel] = Field(None, description="告警级别")
    enable_notification: Optional[bool] = Field(None, description="启用通知")
    notification_channels: Optional[List[str]] = Field(None, description="通知渠道")
    is_active: Optional[bool] = Field(None, description="是否激活")
    priority: Optional[int] = Field(None, description="优先级")
    color: Optional[str] = Field(None, description="显示颜色")


class KeywordGroupResponse(BaseModel):
    """关键词组响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str]
    match_type: MatchType
    case_sensitive: bool
    alert_level: AlertLevel
    enable_notification: bool
    notification_channels: Optional[List[str]]
    is_active: bool
    priority: int
    total_keywords: Optional[int] = None
    total_matches: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    color: Optional[str]

    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        """序列化datetime为ISO格式（带时区信息）"""
        return datetime_to_iso(dt)


class KeywordBase(BaseModel):
    """关键词基础模型"""
    word: str = Field(..., min_length=1, max_length=500, description="关键词内容")


class KeywordCreate(KeywordBase):
    """创建关键词"""
    group_id: int = Field(..., description="关键词组ID")
    case_sensitive: Optional[bool] = Field(None, description="是否区分大小写")
    match_type: Optional[MatchType] = Field(None, description="匹配类型")
    alert_level: Optional[AlertLevel] = Field(None, description="告警级别")
    note: Optional[str] = Field(None, description="备注")


class KeywordUpdate(BaseModel):
    """更新关键词"""
    word: Optional[str] = Field(None, min_length=1, max_length=500, description="关键词内容")
    case_sensitive: Optional[bool] = Field(None, description="是否区分大小写")
    match_type: Optional[MatchType] = Field(None, description="匹配类型")
    alert_level: Optional[AlertLevel] = Field(None, description="告警级别")
    is_active: Optional[bool] = Field(None, description="是否激活")
    note: Optional[str] = Field(None, description="备注")


class KeywordResponse(BaseModel):
    """关键词响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_id: int
    word: str
    match_type: Optional[str]
    case_sensitive: Optional[bool]
    alert_level: Optional[str]
    match_count: Optional[int] = None
    last_matched_at: Optional[datetime]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    note: Optional[str]

    @field_serializer('last_matched_at', 'created_at', 'updated_at')
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        """序列化datetime为ISO格式（带时区信息）"""
        return datetime_to_iso(dt)


class KeywordBatchImport(BaseModel):
    """批量导入关键词"""
    group_id: int = Field(..., description="关键词组ID")
    keywords: List[str] = Field(..., description="关键词列表")
    overwrite: bool = Field(False, description="是否覆盖现有关键词")


class KeywordMatchResult(BaseModel):
    """关键词匹配结果"""
    keyword_id: int
    keyword: str
    group_id: int
    group_name: str
    alert_level: AlertLevel
    matched_text: str
    position: int


class KeywordTestMatchRequest(BaseModel):
    """测试关键词匹配请求"""
    text: str = Field(..., min_length=1, description="要测试的文本")
    keyword_ids: Optional[List[int]] = Field(None, description="要测试的关键词ID列表，如果为空则测试所有")
