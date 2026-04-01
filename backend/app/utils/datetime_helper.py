"""时间处理工具模块 - 统一时区处理"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Optional
from app.core.config import settings


def now_utc() -> datetime:
    """获取当前UTC时间（带时区信息）"""
    return datetime.now(timezone.utc)


def now_local() -> datetime:
    """获取当前本地时间（带时区信息）"""
    return datetime.now(settings.tz_info)


def to_utc(dt: datetime) -> datetime:
    """
    将带时区的datetime对象转换为UTC时间
    如果datetime没有时区信息，假定为本地时区
    """
    if dt.tzinfo is None:
        # 没有时区信息，假定为本地时区
        dt = dt.replace(tzinfo=settings.tz_info)
    return dt.astimezone(timezone.utc)


def to_local(dt: datetime) -> datetime:
    """
    将datetime对象转换为本地时区时间
    如果datetime没有时区信息，假定为UTC时间
    """
    if dt.tzinfo is None:
        # 没有时区信息，假定为UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(settings.tz_info)


def to_local_naive(dt: datetime) -> datetime:
    """
    将datetime对象转换为本地时区时间，并移除时区信息
    用于与现有代码兼容
    """
    local_dt = to_local(dt)
    return local_dt.replace(tzinfo=None)


def format_datetime(dt: Optional[datetime], format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    格式化datetime为字符串（使用本地时区）
    """
    if dt is None:
        return ""
    local_dt = to_local(dt) if dt.tzinfo else dt
    return local_dt.strftime(format_str)


def format_datetime_iso(dt: Optional[datetime]) -> str:
    """
    格式化datetime为ISO格式字符串（带时区信息）
    """
    if dt is None:
        return ""
    # 确保有UTC时区信息
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def start_of_day_local(date: Optional[datetime] = None) -> datetime:
    """
    获取本地时区的某天开始时间（00:00:00）
    """
    if date is None:
        date = now_local()
    else:
        date = to_local(date) if date.tzinfo else date.replace(tzinfo=settings.tz_info)
    return date.replace(hour=0, minute=0, second=0, microsecond=0)


def end_of_day_local(date: Optional[datetime] = None) -> datetime:
    """
    获取本地时区的某天结束时间（23:59:59.999999）
    """
    start = start_of_day_local(date)
    return start.replace(hour=23, minute=59, second=59, microsecond=999999)


def parse_datetime_local(date_str: str) -> datetime:
    """
    解析日期字符串（假定为本地时区）
    支持 ISO 格式和其他常见格式
    """
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=settings.tz_info)
        return dt
    except ValueError:
        # 尝试其他格式
        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"]:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.replace(tzinfo=settings.tz_info)
            except ValueError:
                continue
        raise ValueError(f"无法解析日期字符串: {date_str}")


def parse_datetime_utc(date_str: str) -> datetime:
    """
    解析日期字符串（假定为UTC时区）
    """
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        # 尝试其他格式
        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"]:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        raise ValueError(f"无法解析日期字符串: {date_str}")


def get_timezone_name() -> str:
    """获取当前配置的时区名称"""
    return settings.TIMEZONE


def get_timezone_offset() -> int:
    """获取当前时区相对于UTC的偏移小时数"""
    now = now_local()
    return int(now.utcoffset().total_seconds() // 3600)
