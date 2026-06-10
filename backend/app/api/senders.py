"""发送者查询 API"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.api.deps import get_db
from app.models.sender import Sender
from app.models.alert import Alert

router = APIRouter(prefix="/senders", tags=["发送者查询"])


@router.get("")
async def list_senders(
    has_phone: Optional[bool] = Query(None, description="筛选有手机号的发送者"),
    keyword: Optional[str] = Query(None, description="搜索用户名或手机号"),
    country: Optional[str] = Query(None, description="按国家筛选"),
    phone_location: Optional[str] = Query(None, description="按归属地筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """获取发送者列表 - 支持筛选和搜索"""
    conditions = []

    if has_phone:
        conditions.append(Sender.phone.isnot(None))
        conditions.append(Sender.phone != "")
    if keyword:
        conditions.append(
            or_(
                Sender.username.ilike(f"%{keyword}%"),
                Sender.first_name.ilike(f"%{keyword}%"),
                Sender.phone.ilike(f"%{keyword}%"),
            )
        )
    if country:
        conditions.append(Sender.country == country)
    if phone_location:
        conditions.append(Sender.phone_location.ilike(f"%{phone_location}%"))

    # 总数
    count_query = select(func.count(Sender.id))
    if conditions:
        from sqlalchemy import and_
        count_query = count_query.where(and_(*conditions))
    total = (await db.execute(count_query)).scalar()

    # 分页数据：告警数以 alerts 表实时聚合为准，避免 Sender.alert_count 冗余字段不同步
    alert_counts = (
        select(
            Alert.sender_id,
            func.count(Alert.id).label("real_alert_count"),
        )
        .group_by(Alert.sender_id)
        .subquery()
    )
    query = select(
        Sender,
        func.coalesce(alert_counts.c.real_alert_count, 0).label("real_alert_count"),
    ).outerjoin(alert_counts, alert_counts.c.sender_id == Sender.id)
    if conditions:
        from sqlalchemy import and_
        query = query.where(and_(*conditions))
    query = query.order_by(Sender.message_count.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    sender_rows = result.all()

    items = []
    for s, real_alert_count in sender_rows:
        items.append({
            "id": s.id,
            "user_id": s.user_id,
            "username": s.username,
            "first_name": s.first_name,
            "last_name": s.last_name,
            "phone": s.phone,
            "is_bot": s.is_bot,
            "is_verified": s.is_verified,
            "is_premium": s.is_premium,
            "message_count": s.message_count,
            "alert_count": real_alert_count or 0,
            "country": s.country or "",
            "country_code": s.country_code or "",
            "phone_location": s.phone_location or "",
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total else 0,
    }


@router.get("/{sender_id}")
async def get_sender_detail(
    sender_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取发送者详情"""
    from app.models.message import Message
    result = await db.execute(select(Sender).where(Sender.id == sender_id))
    sender = result.scalar_one_or_none()
    if not sender:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="发送者不存在")

    # 实时统计告警数
    alert_count_result = await db.execute(
        select(func.count(Alert.id)).where(Alert.sender_id == sender_id)
    )
    alert_count = alert_count_result.scalar() or 0

    # 统计消息类型分布
    type_result = await db.execute(
        select(Message.message_type, func.count(Message.id))
        .where(Message.sender_id == sender_id)
        .group_by(Message.message_type)
    )
    message_types = {row[0]: row[1] for row in type_result.all()}

    return {
        "id": sender.id,
        "user_id": sender.user_id,
        "username": sender.username,
        "first_name": sender.first_name,
        "last_name": sender.last_name,
        "phone": sender.phone,
        "is_bot": sender.is_bot,
        "is_verified": sender.is_verified,
        "is_premium": sender.is_premium,
        "message_count": sender.message_count,
        "alert_count": alert_count,
        "message_types": message_types,
        "created_at": sender.created_at.isoformat() if sender.created_at else None,
    }


@router.get("/{sender_id}/messages")
async def get_sender_messages(
    sender_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """获取发送者的消息历史"""
    from app.models.message import Message
    from app.models.conversation import Conversation

    # 验证发送者存在
    sender_result = await db.execute(select(Sender).where(Sender.id == sender_id))
    if not sender_result.scalar_one_or_none():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="发送者不存在")

    # 总数
    count_result = await db.execute(
        select(func.count(Message.id)).where(Message.sender_id == sender_id)
    )
    total = count_result.scalar() or 0

    # 分页查询
    query = (
        select(Message, Conversation.title)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Message.sender_id == sender_id)
        .order_by(Message.date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    rows = result.all()

    items = []
    for msg, conv_title in rows:
        items.append({
            "id": msg.id,
            "conversation_id": msg.conversation_id,
            "conversation_title": conv_title,
            "message_type": msg.message_type,
            "text": msg.text,
            "caption": msg.caption,
            "date": msg.date.isoformat() if msg.date else None,
            "views": msg.views,
            "forwards": msg.forwards,
            "has_media": msg.has_media,
            "is_reply": msg.is_reply,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total else 0,
    }


@router.get("/countries/list")
async def list_countries(db: AsyncSession = Depends(get_db)):
    """获取所有国家/地区列表（去重）"""
    from sqlalchemy import text
    result = await db.execute(
        text("SELECT DISTINCT country, COUNT(*) as cnt FROM senders WHERE country IS NOT NULL AND country != '' GROUP BY country ORDER BY cnt DESC")
    )
    return [{"name": row[0], "count": row[1]} for row in result.all()]


@router.get("/locations/list")
async def list_locations(
    country: Optional[str] = Query(None, description="按国家筛选"),
    db: AsyncSession = Depends(get_db),
):
    """获取归属地列表（去重）"""
    from sqlalchemy import text
    if country:
        result = await db.execute(
            text("SELECT DISTINCT phone_location, COUNT(*) as cnt FROM senders WHERE phone_location IS NOT NULL AND phone_location != '' AND country = :country GROUP BY phone_location ORDER BY cnt DESC"),
            {"country": country}
        )
    else:
        result = await db.execute(
            text("SELECT DISTINCT phone_location, COUNT(*) as cnt FROM senders WHERE phone_location IS NOT NULL AND phone_location != '' GROUP BY phone_location ORDER BY cnt DESC")
        )
    return [{"name": row[0], "count": row[1]} for row in result.all()]
