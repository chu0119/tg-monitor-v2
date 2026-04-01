"""仪表盘 API"""
from datetime import datetime, timedelta
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from functools import lru_cache
from asyncio import Lock
import time

from app.api.deps import get_db
from app.schemas.dashboard import (
    DashboardStats,
    MessageTrend,
    KeywordTrend,
    SenderRanking,
    ConversationActivity,
)
from app.models import (
    TelegramAccount, Conversation, Message, Sender,
    KeywordGroup, Keyword, Alert
)
from app.utils import start_of_day_local, end_of_day_local, to_local, to_utc, now_local, to_local_naive, now_utc

router = APIRouter(prefix="/dashboard", tags=["仪表盘"])

# 简单的内存缓存（30秒）
last_stats_time = 0
last_stats_data = None
CACHE_TTL = 30  # 缓存30秒

async def get_cached_stats():
    """获取缓存的统计数据"""
    global last_stats_time, last_stats_data
    current_time = time.time()

    # 检查缓存
    if last_stats_data and current_time - last_stats_time < CACHE_TTL:
        return last_stats_data

    return None

async def set_cached_stats(data):
    """设置缓存"""
    global last_stats_time, last_stats_data
    last_stats_data = data
    last_stats_time = time.time()


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """获取仪表盘统计数据（带缓存）"""
    # 尝试从缓存获取
    cached = await get_cached_stats()
    if cached:
        return cached

    now_local_dt = now_local()
    # 获取今天本地时间的开始时间（用于"今日"统计）
    # 本地今天 00:00 对应的 UTC 时间
    from datetime import timezone as tz
    today_local_start_tz = start_of_day_local(now_local_dt)  # 本地今天 00:00（带时区）
    today_local_start_utc = to_utc(today_local_start_tz).replace(tzinfo=None)  # 转换为UTC naive，用于查询数据库

    # 账号统计
    total_accounts = await db.execute(select(func.count(TelegramAccount.id)))
    total_accounts = total_accounts.scalar()
    active_accounts = await db.execute(
        select(func.count(TelegramAccount.id))
        .where(TelegramAccount.is_active == True, TelegramAccount.is_authorized == True)
    )
    active_accounts = active_accounts.scalar()

    # 会话统计
    total_conversations = await db.execute(select(func.count(Conversation.id)))
    total_conversations = total_conversations.scalar()
    active_conversations = await db.execute(
        select(func.count(Conversation.id))
        .where(Conversation.status == "active")
    )
    active_conversations = active_conversations.scalar()

    # 消息统计
    total_messages = await db.execute(select(func.count(Message.id)))
    total_messages = total_messages.scalar()

    # 今日消息（本地时间今天 00:00 开始到现在）
    today_messages = await db.execute(
        select(func.count(Message.id))
        .where(Message.created_at >= today_local_start_utc)
    )
    today_messages = today_messages.scalar()

    # 24小时消息分布 - 单条 GROUP BY 查询替代循环24次
    messages_24h = []
    from datetime import timezone as tz
    now_utc_time = datetime.now(tz.utc).replace(tzinfo=None)
    start_24h_utc = now_utc_time - timedelta(hours=24)

    # MySQL: HOUR() 返回 0-23 的UTC小时，按此分组
    hour_result = await db.execute(
        select(func.hour(Message.date), func.count(Message.id))
        .where(Message.date >= start_24h_utc, Message.date < now_utc_time)
        .group_by(func.hour(Message.date))
    )
    hour_counts = {row[0]: row[1] for row in hour_result.all()}

    # 生成从早到晚的24小时分布，标签使用本地时间
    now_local_naive = to_local_naive(now_local_dt)
    for i in range(23, -1, -1):
        hour_end_utc = now_utc_time - timedelta(hours=i)
        hour_label_local = to_local_naive(to_utc(hour_end_utc.replace(tzinfo=tz.utc)))
        utc_hour = (now_utc_time - timedelta(hours=i)).hour
        messages_24h.append({
            "hour": f"{hour_label_local.hour:02d}:00",
            "count": hour_counts.get(utc_hour, 0)
        })

    # 告警统计
    total_alerts = await db.execute(select(func.count(Alert.id)))
    total_alerts = total_alerts.scalar()
    pending_alerts = await db.execute(
        select(func.count(Alert.id))
        .where(Alert.status == "pending")
    )
    pending_alerts = pending_alerts.scalar()
    today_alerts = await db.execute(
        select(func.count(Alert.id))
        .where(Alert.created_at >= today_local_start_utc)
    )
    today_alerts = today_alerts.scalar()

    alerts_by_level_result = await db.execute(
        select(Alert.alert_level, func.count(Alert.id))
        .group_by(Alert.alert_level)
    )
    alerts_by_level = {row[0]: row[1] for row in alerts_by_level_result.all()}

    # 关键词统计
    total_keywords = await db.execute(select(func.count(Keyword.id)))
    total_keywords = total_keywords.scalar()
    active_keywords = await db.execute(
        select(func.count(Keyword.id))
        .where(Keyword.match_count > 0)
    )
    active_keywords = active_keywords.scalar()
    keyword_groups = await db.execute(select(func.count(KeywordGroup.id)))
    keyword_groups = keyword_groups.scalar()

    # 发送者统计
    total_senders = await db.execute(select(func.count(Sender.id)))
    total_senders = total_senders.scalar()

    result = DashboardStats(
        total_accounts=total_accounts,
        active_accounts=active_accounts,
        total_conversations=total_conversations,
        active_conversations=active_conversations,
        total_messages=total_messages,
        today_messages=today_messages,
        messages_24h=messages_24h,
        total_alerts=total_alerts,
        pending_alerts=pending_alerts,
        today_alerts=today_alerts,
        alerts_by_level=alerts_by_level,
        total_keywords=total_keywords,
        active_keywords=active_keywords,
        keyword_groups=keyword_groups,
        total_senders=total_senders,
        updated_at=now_local_dt  # 使用带时区的datetime
    )

    # 缓存结果
    await set_cached_stats(result)

    return result


@router.get("/message-trend", response_model=MessageTrend)
async def get_message_trend(
    days: int = 7,
    conversation_id: int = None,
    db: AsyncSession = Depends(get_db)
):
    """获取消息趋势（按本地日期统计）"""
    # 获取今天本地时间 00:00 对应的 UTC 时间
    # 这样可以正确按本地日期分组统计
    today_local_start = start_of_day_local(now_local())
    today_utc_start = to_utc(today_local_start).replace(tzinfo=None)

    dates = []
    counts = []

    # 单条 GROUP BY 查询替代循环
    start_utc = today_utc_start - timedelta(days=days - 1)
    end_utc = today_utc_start + timedelta(days=1)
    base_query_filter = [Message.date >= start_utc, Message.date < end_utc]
    if conversation_id:
        base_query_filter.append(Message.conversation_id == conversation_id)

    trend_result = await db.execute(
        select(func.date(Message.date), func.count(Message.id))
        .where(*base_query_filter)
        .group_by(func.date(Message.date))
    )
    trend_map = {str(row[0]): row[1] for row in trend_result.all()}

    for i in range(days):
        date_label = today_local_start - timedelta(days=days - 1 - i)
        dates.append(date_label.strftime("%Y-%m-%d"))
        counts.append(trend_map.get(date_label.strftime("%Y-%m-%d"), 0))

    # 各会话趋势 - 单条 GROUP BY 查询替代循环
    by_conversation = []
    top_convs = await db.execute(
        select(Conversation.id, Conversation.title)
        .order_by(Conversation.total_messages.desc())
        .limit(5)
    )
    top_conv_ids = [c[0] for c in top_convs.all()]
    top_conv_map = {c[0]: c[1] for c in top_convs.all()}

    if top_conv_ids:
        trend_result = await db.execute(
            select(
                Message.conversation_id,
                func.date(Message.date).label('day'),
                func.count(Message.id).label('count')
            )
            .where(
                Message.conversation_id.in_(top_conv_ids),
                Message.date >= today_utc_start - timedelta(days=days - 1),
                Message.date < today_utc_start + timedelta(days=1)
            )
            .group_by(Message.conversation_id, func.date(Message.date))
        )
        trend_map = {}
        for row in trend_result.all():
            trend_map.setdefault(row.conversation_id, {})[str(row.day)] = row.count

        for conv_id in top_conv_ids:
            conv_counts = []
            for i in range(days):
                date_label = today_local_start - timedelta(days=days - 1 - i)
                day_key = date_label.strftime("%Y-%m-%d")
                conv_counts.append(trend_map.get(conv_id, {}).get(day_key, 0))
            by_conversation.append({
                "conversation_id": conv_id,
                "title": top_conv_map[conv_id],
                "counts": conv_counts
            })

    return MessageTrend(
        dates=dates,
        counts=counts,
        by_conversation=by_conversation
    )


@router.get("/keyword-trend", response_model=List[KeywordTrend])
async def get_keyword_trend(
    days: int = 7,
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """获取关键词趋势（按本地日期统计）"""
    # 获取今天本地时间 00:00 对应的 UTC 时间
    today_local_start = start_of_day_local(now_local())
    today_utc_start = to_utc(today_local_start).replace(tzinfo=None)

    # 获取匹配次数最多的关键词组
    group_result = await db.execute(
        select(KeywordGroup)
        .order_by(KeywordGroup.total_matches.desc())
        .limit(limit)
    )
    groups = group_result.scalars().all()

    if not groups:
        return []

    group_ids = [g.id for g in groups]
    group_names = {g.id: g.name for g in groups}

    # 计算UTC时间的日期范围
    start_date_utc = today_utc_start - timedelta(days=days - 1)
    end_date_utc = today_utc_start + timedelta(days=1)

    # 查询所有告警数据（按天分组）
    # 注意：func.date() 返回的是UTC日期，我们需要手动转换为本地日期
    alert_stats_result = await db.execute(
        select(
            Alert.keyword_group_name,
            func.date(Alert.created_at).label('date'),
            func.count(Alert.id).label('count')
        )
        .where(
            Alert.keyword_group_name.in_(group_names.values()),
            Alert.created_at >= start_date_utc,
            Alert.created_at < end_date_utc
        )
        .group_by(Alert.keyword_group_name, func.date(Alert.created_at))
        .limit(limit * days)  # 安全限制：最多 limit*days 行
    )
    alert_stats_raw = alert_stats_result.all()

    # 按关键词组组织数据
    # 需要将UTC日期转换为本地日期（用于显示）
    from datetime import timezone as tz, timedelta as td
    alert_stats_by_group = {}
    for stat in alert_stats_raw:
        if stat.keyword_group_name not in alert_stats_by_group:
            alert_stats_by_group[stat.keyword_group_name] = {}
        # 将UTC日期转换为本地日期
        # stat.date 可能是 datetime.date 对象或字符串
        if isinstance(stat.date, str):
            utc_date = datetime.strptime(stat.date, "%Y-%m-%d").replace(tzinfo=tz.utc)
        else:
            # 如果是 date 对象，先转为 datetime
            utc_date = datetime.combine(stat.date, datetime.min.time()).replace(tzinfo=tz.utc)
        local_date = to_local(utc_date).date()
        # 如果转换后导致重复，取较大的值
        existing = alert_stats_by_group[stat.keyword_group_name].get(local_date)
        if existing is None or stat.count > existing:
            alert_stats_by_group[stat.keyword_group_name][local_date] = stat.count

    # 一次性查询所有组的热门关键词
    top_keywords_result = await db.execute(
        select(
            Keyword.group_id,
            Keyword.word,
            Keyword.match_count
        )
        .where(Keyword.group_id.in_(group_ids))
        .order_by(Keyword.group_id, Keyword.match_count.desc())
    )
    all_keywords = top_keywords_result.all()

    # 组织数据
    trends = []
    for group in groups:
        dates = []
        counts = []

        group_stats = alert_stats_by_group.get(group.name, {})

        for i in range(days):
            # 使用本地时间作为日期标签
            date_label_local = today_local_start - timedelta(days=days - 1 - i)
            date_key = date_label_local.date()
            dates.append(date_label_local.strftime("%Y-%m-%d"))
            counts.append(group_stats.get(date_key, 0))

        # 获取该组的热门关键词
        top_keywords = [
            {"word": kw.word, "count": kw.match_count}
            for kw in all_keywords
            if kw.group_id == group.id
        ][:5]

        trends.append(KeywordTrend(
            keyword_group=group.name,
            dates=dates,
            counts=counts,
            top_keywords=top_keywords
        ))

    return trends


@router.get("/sender-ranking", response_model=List[SenderRanking])
async def get_sender_ranking(
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """获取发送者排行"""
    result = await db.execute(
        select(
            Sender.id, Sender.username, Sender.first_name,
            Sender.message_count,
            func.coalesce(Sender.alert_count, 0).label("alert_count"),
        )
        .order_by(Sender.message_count.desc())
        .limit(limit)
    )
    rows = result.all()

    rankings = []
    for i, row in enumerate(rows, 1):
        rankings.append(SenderRanking(
            sender_id=row.id,
            username=row.username,
            first_name=row.first_name,
            message_count=row.message_count,
            alert_count=row.alert_count,
            rank=i
        ))

    return rankings


@router.get("/conversation-activity", response_model=List[ConversationActivity])
async def get_conversation_activity(
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """获取会话活跃度 - 优化版本，避免 N+1 查询"""
    # 一次性获取所有会话和它们的活跃发送者统计
    result = await db.execute(
        select(
            Conversation.id,
            Conversation.title,
            Conversation.chat_type,
            Conversation.total_messages,
            Conversation.total_alerts,
            Conversation.last_message_at,
            func.count(func.distinct(Message.sender_id)).label('sender_count')
        )
        .outerjoin(Message, Conversation.id == Message.conversation_id)
        .group_by(Conversation.id)
        .order_by(Conversation.total_messages.desc())
        .limit(limit)
    )
    rows = result.all()

    activities = []
    for row in rows:
        activities.append(ConversationActivity(
            conversation_id=row.id,
            title=row.title or "Unknown",
            chat_type=row.chat_type,
            message_count=row.total_messages,
            sender_count=row.sender_count or 0,
            alert_count=row.total_alerts,
            last_message_at=row.last_message_at
        ))

    return activities


@router.get("/alerts/recent")
async def get_recent_alerts(
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """获取最近的告警列表（用于仪表盘展示）"""
    from sqlalchemy.orm import selectinload
    from app.models.alert import Alert
    from app.models.sender import Sender
    from app.models.conversation import Conversation

    # 查询最近的告警，预加载关联数据
    result = await db.execute(
        select(Alert)
        .options(
            selectinload(Alert.sender),
            selectinload(Alert.conversation)
        )
        .order_by(Alert.created_at.desc())
        .limit(limit)
    )
    alerts = result.scalars().all()

    # 构建响应数据
    response_alerts = []
    for alert in alerts:
        alert_dict = {
            "id": alert.id,
            "keyword_text": alert.keyword_text,
            "keyword_group_name": alert.keyword_group_name,
            "alert_level": alert.alert_level,
            "status": alert.status,
            "matched_text": alert.matched_text,
            "created_at": alert.created_at.isoformat() if alert.created_at else None,
            "conversation_id": alert.conversation_id,
            "sender_id": alert.sender_id,
        }

        # 添加发送者信息
        if alert.sender:
            alert_dict["sender_username"] = alert.sender.username or alert.sender.first_name or f"User_{alert.sender.user_id}"
            alert_dict["sender_first_name"] = alert.sender.first_name

        # 添加会话信息
        if alert.conversation:
            alert_dict["conversation_title"] = alert.conversation.title

        response_alerts.append(alert_dict)

    return {"items": response_alerts, "total": len(response_alerts)}
