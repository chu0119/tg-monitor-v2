"""仪表盘相关的 Pydantic 模型"""
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_serializer
from app.utils import datetime_to_local_iso


class DashboardStats(BaseModel):
    """仪表盘统计数据"""
    # 账号统计
    total_accounts: int = Field(..., description="总账号数")
    active_accounts: int = Field(..., description="活跃账号数")

    # 会话统计
    total_conversations: int = Field(..., description="总会话数")
    active_conversations: int = Field(..., description="监控中会话数")

    # 消息统计
    total_messages: int = Field(..., description="总消息数")
    today_messages: int = Field(..., description="今日消息数")
    messages_24h: List[dict] = Field(..., description="24小时消息分布")

    # 告警统计
    total_alerts: int = Field(..., description="总告警数")
    pending_alerts: int = Field(..., description="待处理告警数")
    today_alerts: int = Field(..., description="今日告警数")
    alerts_by_level: Dict[str, int] = Field(..., description="按级别统计告警")

    # 关键词统计
    total_keywords: int = Field(..., description="总关键词数")
    active_keywords: int = Field(..., description="激活关键词数")
    keyword_groups: int = Field(..., description="关键词组数")

    # 发送者统计
    total_senders: int = Field(..., description="总发送者数")

    # 更新时间
    updated_at: datetime = Field(..., description="更新时间")

    @field_serializer('updated_at')
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        """序列化datetime为ISO格式（本地时区 +08:00）"""
        return datetime_to_local_iso(dt)


class MessageTrend(BaseModel):
    """消息趋势"""
    dates: List[str] = Field(..., description="日期列表")
    counts: List[int] = Field(..., description="消息数量")
    by_conversation: List[dict] = Field(..., description="各会话趋势")


class KeywordTrend(BaseModel):
    """关键词趋势"""
    keyword_group: str = Field(..., description="关键词组")
    dates: List[str] = Field(..., description="日期列表")
    counts: List[int] = Field(..., description="匹配次数")
    top_keywords: List[dict] = Field(..., description="热门关键词")


class SenderRanking(BaseModel):
    """发送者排行"""
    sender_id: int = Field(..., description="发送者ID")
    username: Optional[str] = Field(None, description="用户名")
    first_name: Optional[str] = Field(None, description="名字")
    message_count: int = Field(..., description="消息数")
    alert_count: int = Field(..., description="告警数")
    rank: int = Field(..., description="排名")


class ConversationActivity(BaseModel):
    """会话活跃度"""
    conversation_id: int = Field(..., description="会话ID")
    title: str = Field(..., description="标题")
    chat_type: str = Field(..., description="类型")
    message_count: int = Field(..., description="消息数")
    sender_count: int = Field(..., description="活跃发送者数")
    alert_count: int = Field(..., description="告警数")
    last_message_at: Optional[datetime] = Field(None, description="最后消息时间")

    @field_serializer('last_message_at')
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        """序列化datetime为ISO格式（本地时区 +08:00）"""
        return datetime_to_local_iso(dt)
