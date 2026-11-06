"""仪表盘 API"""
from datetime import datetime, timedelta
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_, text
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

# Redis缓存（可选）
try:
    from app.utils.redis_cache import redis_cache
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis_cache = None

router = APIRouter(prefix="/dashboard", tags=["仪表盘"])
# 缓存变量
_sender_ranking_cache = {}
_sender_ranking_cache_time = 0
_conversation_activity_cache = {}
_conversation_activity_cache_time = 0
CACHE_TTL_SLOW = 60  # 慢查询缓存60秒


# 简单的内存缓存（30秒）
last_stats_time = 0
last_stats_data = None
CACHE_TTL = 30  # 优化：增加缓存时间到30秒

async def get_cached_stats():
    """获取缓存的统计数据（Redis）"""
    if not REDIS_AVAILABLE or redis_cache is None:
        return None
    try:
        cached = redis_cache.get("dashboard_stats")
        return cached
    except Exception as e:
        from loguru import logger
        logger.warning(f"dashboard_stats缓存获取失败: {e}")
        return None

async def set_cached_stats(data):
    """设置缓存（Redis）"""
    if not REDIS_AVAILABLE or redis_cache is None:
        return
    try:
        # 将data转换为字典
        if hasattr(data, 'dict'):
            cache_data = data.dict()
        elif hasattr(data, '__dict__'):
            cache_data = data.__dict__
        else:
            cache_data = data
        redis_cache.set("dashboard_stats", cache_data, CACHE_TTL)
    except Exception as e:
        from loguru import logger
        logger.warning(f"dashboard_stats缓存设置失败: {e}")


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """获取仪表盘统计数据（带缓存）"""
    # 尝试从缓存获取
    cached = await get_cached_stats()
    if cached:
        return cached

    now_local_dt = now_local()
    from datetime import timezone as tz
    today_local_start_tz = start_of_day_local(now_local_dt)
    today_local_start_utc = to_utc(today_local_start_tz).replace(tzinfo=None)

    # 优化：使用information_schema获取近似行数（毫秒级）
    approx_sql = text("""
        SELECT
            table_name,
            table_rows
        FROM information_schema.tables
        WHERE table_schema = DATABASE()
        AND table_name IN ('telegram_accounts', 'conversations', 'messages', 'alerts', 'keywords', 'keyword_groups', 'senders')
    """)
    approx_result = await db.execute(approx_sql)
    approx_rows = {row[0]: row[1] for row in approx_result.fetchall()}

    # 精确统计小表（毫秒级）
    small_tables_sql = text("""
        SELECT
            (SELECT COUNT(*) FROM telegram_accounts) as total_accounts,
            (SELECT COUNT(*) FROM telegram_accounts WHERE is_active = 1 AND is_authorized = 1) as active_accounts,
            (SELECT COUNT(*) FROM conversations) as total_conversations,
            (SELECT COUNT(*) FROM conversations WHERE status = 'active') as active_conversations,
            (SELECT COUNT(*) FROM keywords) as total_keywords,
            (SELECT COUNT(*) FROM keywords WHERE match_count > 0) as active_keywords,
            (SELECT COUNT(*) FROM keyword_groups) as keyword_groups,
            (SELECT COUNT(*) FROM senders) as total_senders
    """)
    small_result = await db.execute(small_tables_sql)
    small_row = small_result.fetchone()

    total_accounts = small_row[0]
    active_accounts = small_row[1] or 0
    total_conversations = small_row[2]
    active_conversations = small_row[3] or 0
    total_keywords = small_row[4]
    active_keywords = small_row[5] or 0
    keyword_groups = small_row[6] or 0
    total_senders = small_row[7]

    # 使用近似值（大表）或精确值（小表）
    total_messages = approx_rows.get('messages', 0)
    total_alerts = approx_rows.get('alerts', 0)

    # 今日统计 — 优化：messages 使用有索引的 date 列；pending 用 total - non-pending 避免全表扫描
    today_sql = text("""
        SELECT
            (SELECT COUNT(*) FROM messages WHERE date >= :today) as today_messages,
            (SELECT COUNT(*) FROM alerts WHERE created_at >= :today) as today_alerts,
            (SELECT COUNT(*) FROM alerts WHERE status != 'pending') as non_pending_alerts
    """)
    today_result = await db.execute(today_sql, {"today": today_local_start_utc})
    today_row = today_result.fetchone()
    today_messages = today_row[0] or 0
    today_alerts = today_row[1] or 0
    # pending = total - non_pending (non_pending 通常极少，查询极快)
    pending_alerts = max(0, (total_alerts or 0) - (today_row[2] or 0))

    # 24小时消息分布
    messages_24h = []
    now_utc_time = datetime.now(tz.utc).replace(tzinfo=None)
    start_24h_utc = now_utc_time - timedelta(hours=24)

    hour_result = await db.execute(
        select(func.hour(Message.date), func.count(Message.id))
        .where(Message.date >= start_24h_utc, Message.date < now_utc_time)
        .group_by(func.hour(Message.date))
    )
    hour_counts = {row[0]: row[1] for row in hour_result.all()}

    now_local_naive = to_local_naive(now_local_dt)
    for i in range(23, -1, -1):
        hour_end_utc = now_utc_time - timedelta(hours=i)
        hour_label_local = to_local_naive(to_utc(hour_end_utc.replace(tzinfo=tz.utc)))
        utc_hour = (now_utc_time - timedelta(hours=i)).hour
        messages_24h.append({
            "hour": f"{hour_label_local.hour:02d}:00",
            "count": hour_counts.get(utc_hour, 0)
        })

    # 告警级别统计 — 使用最近7天数据（利用 created_at 索引，避免全表扫描）
    alerts_since = now_utc_time - timedelta(days=7)
    alerts_by_level_result = await db.execute(
        select(Alert.alert_level, func.count(Alert.id))
        .where(Alert.created_at >= alerts_since)
        .group_by(Alert.alert_level)
    )
    alerts_by_level = {row[0]: row[1] for row in alerts_by_level_result.all()}

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

    # date 列为 UTC：按北京时间日期聚合（CONVERT_TZ），否则 0-8 点的消息会记到前一天
    local_day = func.date(func.convert_tz(Message.date, '+00:00', '+08:00'))
    trend_result = await db.execute(
        select(local_day, func.count(Message.id))
        .where(*base_query_filter)
        .group_by(local_day)
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
    top_conv_rows = top_convs.all()
    top_conv_ids = [c[0] for c in top_conv_rows]
    top_conv_map = {c[0]: c[1] for c in top_conv_rows}

    if top_conv_ids:
        local_day2 = func.date(func.convert_tz(Message.date, '+00:00', '+08:00')).label('day')
        trend_result = await db.execute(
            select(
                Message.conversation_id,
                local_day2,
                func.count(Message.id).label('count')
            )
            .where(
                Message.conversation_id.in_(top_conv_ids),
                Message.date >= today_utc_start - timedelta(days=days - 1),
                Message.date < today_utc_start + timedelta(days=1)
            )
            .group_by(Message.conversation_id, local_day2)
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
    sort_by: str = Query("messages"),
    db: AsyncSession = Depends(get_db)
):
    """获取发送者排行（带Redis缓存）"""
    # 检查Redis缓存
    cache_key = f"sender_ranking_{limit}_{sort_by}"
    if REDIS_AVAILABLE and redis_cache is not None:
        cached = redis_cache.get(cache_key)
        if cached is not None:
            return [SenderRanking(**item) for item in cached]

    if sort_by not in {"messages", "alerts"}:
        sort_by = "messages"

    # 优化：使用原生SQL子查询，避免大表JOIN
    if sort_by == "alerts":
        # 按告警数排序：先统计告警数，再关联发送者信息
        # 使用缓存（1分钟），避免每次查询都扫描 600 万行 alerts
        from app.utils.cache import memory_cache
        cached = memory_cache.get("sender_ranking_alerts", ttl=60)
        if cached:
            return [SenderRanking(**item) for item in cached]

        # 按告警数排序：直接用 senders.alert_count 冗余列（告警创建时原子维护），
        # 原全表 GROUP BY alerts 在 226 万行上代价过高
        sql = text("""
            SELECT s.id, s.username, s.first_name, s.message_count, s.alert_count
            FROM senders s
            WHERE s.alert_count > 0
            ORDER BY s.alert_count DESC, s.message_count DESC
            LIMIT :limit
        """)
        result = await db.execute(sql, {"limit": limit})
        rows = result.fetchall()
        items = []
        for i, r in enumerate(rows, 1):
            items.append({"sender_id": r[0], "username": r[1] or "", "first_name": r[2] or "",
                          "message_count": r[3] or 0, "alert_count": r[4] or 0, "rank": i})
        memory_cache.set("sender_ranking_alerts", items)
        return [SenderRanking(**item) for item in items]
    else:
        # 按消息数排序：直接使用索引
        sql = text("""
            SELECT id, username, first_name, message_count, 0 as alert_count
            FROM senders
            ORDER BY message_count DESC
            LIMIT :limit
        """)
        result = await db.execute(sql, {"limit": limit})

    rows = result.fetchall()

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

    # 保存到Redis缓存
    if REDIS_AVAILABLE and redis_cache is not None:
        redis_cache.set(cache_key, [r.dict() for r in rankings], CACHE_TTL_SLOW)

    return rankings


@router.get("/conversation-activity", response_model=List[ConversationActivity])
async def get_conversation_activity(
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """获取会话活跃度（带缓存）"""
    # 检查Redis缓存
    cache_key = "conv_activity_top12"
    if REDIS_AVAILABLE and redis_cache is not None:
        cached = redis_cache.get(cache_key)
        if cached is not None:
            return [ConversationActivity(**item) for item in cached]

    # 优化：直接使用预计算的sender_count字段
    sql = text("""
        SELECT
            id,
            title,
            chat_type,
            total_messages,
            total_alerts,
            last_message_at,
            sender_count
        FROM conversations
        ORDER BY total_messages DESC
        LIMIT :limit
    """)
    result = await db.execute(sql, {"limit": limit})
    rows = result.fetchall()

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

    # 保存到Redis缓存
    if REDIS_AVAILABLE and redis_cache is not None:
        redis_cache.set(cache_key, [a.dict() for a in activities], CACHE_TTL_SLOW)

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
