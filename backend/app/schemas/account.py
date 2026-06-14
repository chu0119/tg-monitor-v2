"""Telegram 账号相关的 Pydantic 模型"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_serializer
from app.utils import datetime_to_iso


class TelegramAccountBase(BaseModel):
    """账号基础模型"""
    phone: str = Field(..., description="手机号")
    note: Optional[str] = Field(None, description="备注")


class TelegramAccountCreate(TelegramAccountBase):
    """创建账号"""
    proxy_config: Optional[dict] = Field(None, description="代理配置")


class TelegramAccountUpdate(BaseModel):
    """更新账号"""
    is_active: Optional[bool] = Field(None, description="是否激活")
    note: Optional[str] = Field(None, description="备注")
    proxy_config: Optional[dict] = Field(None, description="代理配置")


class TelegramAccountLogin(BaseModel):
    """登录请求"""
    phone: str = Field(..., description="手机号")
    api_id: Optional[int] = Field(None, description="API ID（不填则使用全局配置）")
    api_hash: Optional[str] = Field(None, description="API Hash（不填则使用全局配置）")
    password: Optional[str] = Field(None, description="两步验证密码")
    proxy_config: Optional[dict] = Field(None, description="代理配置")


class TelegramAccountLoginCode(BaseModel):
    """输入验证码"""
    phone: str = Field(..., description="手机号")
    code: str = Field(..., description="验证码")
    api_id: Optional[int] = Field(None, description="API ID（不填则使用全局配置）")
    api_hash: Optional[str] = Field(None, description="API Hash（不填则使用全局配置）")
    password: Optional[str] = Field(None, description="两步验证密码")


class TelegramAccountResponse(BaseModel):
    """账号响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    phone: str
    user_id: Optional[int]
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    is_premium: Optional[bool] = False
    is_bot: Optional[bool] = False
    is_active: Optional[bool] = True
    is_authorized: Optional[bool] = False
    is_active: bool
    is_authorized: bool
    last_used_at: Optional[datetime]
    proxy_config: Optional[dict]
    api_id: Optional[int]
    api_hash: Optional[str]
    total_messages: Optional[int] = 0
    total_conversations: Optional[int] = 0
    created_at: datetime
    updated_at: datetime
    note: Optional[str]

    @field_serializer('last_used_at', 'created_at', 'updated_at')
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        """序列化datetime为ISO格式（带时区信息）"""
        return datetime_to_iso(dt)
