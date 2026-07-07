"""
输入验证模块
提供统一的验证器和验证规则
"""
from typing import Any, Optional, List
from pydantic import BaseModel, Field, field_validator
from app.core.error_handler import ValidationException


class PaginationParams(BaseModel):
    """分页参数"""
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(50, ge=1, le=500, description="每页数量")

    @field_validator('page')
    @classmethod
    def validate_page(cls, v):
        if v < 1:
            raise ValidationException('页码必须大于0')
        return v

    @field_validator('page_size')
    @classmethod
    def validate_page_size(cls, v):
        if v < 1 or v > 500:
            raise ValidationException('每页数量必须在1-500之间')
        return v


class SearchParams(BaseModel):
    """搜索参数"""
    keyword: Optional[str] = Field(None, max_length=100, description="搜索关键词")

    @field_validator('keyword')
    @classmethod
    def validate_keyword(cls, v):
        if v is not None and len(v) > 100:
            raise ValidationException('搜索关键词长度不能超过100个字符')
        if v is not None and not v.strip():
            return None
        return v.strip() if v else v


class DateRangeParams(BaseModel):
    """日期范围参数"""
    start_date: Optional[str] = Field(None, description="开始日期")
    end_date: Optional[str] = Field(None, description="结束日期")

    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_date(cls, v):
        if v is not None:
            try:
                from datetime import datetime
                datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                raise ValidationException(f'日期格式无效: {v}，请使用ISO格式')
        return v


class AlertFilterParams(PaginationParams, SearchParams):
    """告警筛选参数"""
    status: Optional[str] = Field(None, description="状态")
    alert_level: Optional[str] = Field(None, description="告警级别")
    has_phone: Optional[bool] = Field(None, description="是否有手机号")
    sender_country: Optional[str] = Field(None, max_length=50, description="发送者国家")
    sender_location: Optional[str] = Field(None, max_length=100, description="发送者归属地")
    keyword_group_id: Optional[int] = Field(None, description="关键词组ID")
    conversation_id: Optional[int] = Field(None, description="会话ID")
    sender_id: Optional[int] = Field(None, description="发送者ID")

    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        if v is not None:
            valid_statuses = ['pending', 'processing', 'resolved', 'ignored', 'false_positive']
            if v not in valid_statuses:
                raise ValidationException(f'无效的状态值: {v}，有效值: {valid_statuses}')
        return v

    @field_validator('alert_level')
    @classmethod
    def validate_alert_level(cls, v):
        if v is not None:
            valid_levels = ['low', 'medium', 'high', 'critical']
            if v not in valid_levels:
                raise ValidationException(f'无效的告警级别: {v}，有效值: {valid_levels}')
        return v

    @field_validator('sender_country')
    @classmethod
    def validate_sender_country(cls, v):
        if v is not None and len(v) > 50:
            raise ValidationException('国家名称长度不能超过50个字符')
        return v

    @field_validator('sender_location')
    @classmethod
    def validate_sender_location(cls, v):
        if v is not None and len(v) > 100:
            raise ValidationException('归属地长度不能超过100个字符')
        return v


class IDParam(BaseModel):
    """ID参数"""
    id: int = Field(..., description="ID")

    @field_validator('id')
    @classmethod
    def validate_id(cls, v):
        if v <= 0:
            raise ValidationException('ID必须大于0')
        return v


class BatchOperationParams(BaseModel):
    """批量操作参数"""
    ids: List[int] = Field(..., min_length=1, max_length=100, description="ID列表")

    @field_validator('ids')
    @classmethod
    def validate_ids(cls, v):
        if not v:
            raise ValidationException('ID列表不能为空')
        if len(v) > 100:
            raise ValidationException('一次最多操作100条记录')
        if any(id <= 0 for id in v):
            raise ValidationException('ID必须大于0')
        return v


def validate_string_length(value: Any, max_length: int, field_name: str) -> str:
    """验证字符串长度"""
    if value is not None and isinstance(value, str):
        if len(value) > max_length:
            raise ValidationException(f'{field_name}长度不能超过{max_length}个字符')
        return value.strip()
    return value


def validate_required(value: Any, field_name: str) -> Any:
    """验证必填字段"""
    if value is None:
        raise ValidationException(f'{field_name}不能为空')
    return value


def validate_enum(value: Any, valid_values: List[Any], field_name: str) -> Any:
    """验证枚举值"""
    if value is not None and value not in valid_values:
        raise ValidationException(f'无效的{field_name}: {value}，有效值: {valid_values}')
    return value

