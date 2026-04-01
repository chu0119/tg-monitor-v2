"""自定义JSON编码器 - 统一时区处理（UTC）"""
from datetime import datetime, timezone
from typing import Any
from json import JSONEncoder


class CustomJSONEncoder(JSONEncoder):
    """自定义JSON编码器，统一使用UTC时间"""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            # 统一转换为UTC时间返回ISO格式
            return datetime_to_iso(obj)
        return super().default(obj)


def datetime_to_iso(dt: datetime | None) -> str | None:
    """
    将datetime转换为ISO格式字符串（统一使用UTC）

    规则：
    1. 如果有时区信息 → 转换为UTC，返回ISO格式（带+00:00）
    2. 如果没有时区信息 → 假定为UTC时间（数据库存储格式），直接添加UTC时区返回

    这样确保所有API返回的时间都是UTC格式
    """
    if dt is None:
        return None

    # 如果有时区信息，转换为UTC
    if dt.tzinfo is not None:
        utc_dt = dt.astimezone(timezone.utc)
        return utc_dt.isoformat()

    # 如果没有时区信息，假定为UTC时间（数据库存储的是UTC naive datetime）
    utc_dt = dt.replace(tzinfo=timezone.utc)
    return utc_dt.isoformat()


def datetime_to_local_iso(dt: datetime | None) -> str | None:
    """
    将datetime转换为本地时区的ISO格式字符串

    由于数据库已设置 time_zone='+08:00'，func.now() 存储的就是本地时间
    对于没有时区信息的 datetime，直接添加本地时区即可
    """
    if dt is None:
        return None
    from app.core.config import settings

    # 如果有时区信息，转换为本地时区
    if dt.tzinfo is not None:
        local_dt = dt.astimezone(settings.tz_info)
        return local_dt.isoformat()

    # 如果没有时区信息，假定为本地时区时间（数据库存储格式）
    # 直接添加本地时区信息，不做转换
    local_dt = dt.replace(tzinfo=settings.tz_info)
    return local_dt.isoformat()
