"""人员档案 API - 一人一档"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.api.deps import get_db
from app.models.sender import Sender
from app.models.message import Message
from app.models.conversation import Conversation
from app.models.alert import Alert

router = APIRouter(prefix="/personnel", tags=["人员档案"])


def _sender_name(s):
    parts = []
    if s.first_name:
        parts.append(s.first_name)
    if s.last_name:
        parts.append(s.last_name)
    return " ".join(parts) if parts else (s.username or str(s.user_id))


@router.get("/search")
async def search_senders(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    db: AsyncSession = Depends(get_db),
):
    """搜索发送者 - 支持用户名/姓名/手机号/TG ID"""
    keyword = f"%{q}%"
    is_numeric = q.isdigit()

    conditions = or_(
        Sender.username.ilike(keyword),
        Sender.first_name.ilike(keyword),
        Sender.last_name.ilike(keyword),
        Sender.phone.ilike(keyword),
    )
    if is_numeric:
        conditions = or_(conditions, Sender.user_id == int(q))

    query = (
        select(Sender)
        .where(conditions)
        .order_by(Sender.message_count.desc())
        .limit(30)
    )
    result = await db.execute(query)
    senders = result.scalars().all()

    return [
        {
            "sender_id": s.id,
            "user_id": s.user_id,
            "username": s.username,
            "first_name": s.first_name,
            "last_name": s.last_name,
            "phone": s.phone,
            "sender_name": _sender_name(s),
            "message_count": s.message_count or 0,
            "group_count": 0,
        }
        for s in senders
    ]


@router.get("/{sender_id}/profile")
async def get_sender_profile(
    sender_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取发送者详细资料"""
    result = await db.execute(select(Sender).where(Sender.id == sender_id))
    sender = result.scalar_one_or_none()
    if not sender:
        return {"error": "人员不存在"}

    alert_count_result = await db.execute(
        select(func.count(Alert.id)).where(Alert.sender_id == sender_id)
    )
    alert_count = alert_count_result.scalar() or 0

    msg_stats = await db.execute(
        select(
            func.count(Message.id).label("total"),
            func.min(Message.date).label("first_seen"),
            func.max(Message.date).label("last_seen"),
            func.count(func.distinct(Message.conversation_id)).label("group_count"),
        ).where(Message.sender_id == sender_id)
    )
    stats = msg_stats.one()

    type_dist = await db.execute(
        select(
            Message.message_type,
            func.count(Message.id).label("count"),
        )
        .where(Message.sender_id == sender_id)
        .group_by(Message.message_type)
        .order_by(func.count(Message.id).desc())
    )
    message_types = {row.message_type: row.count for row in type_dist.all()}

    group_stats = await db.execute(
        select(
            Conversation.id,
            Conversation.title,
            Conversation.chat_type,
            func.count(Message.id).label("msg_count"),
            func.max(Message.date).label("last_msg"),
        )
        .join(Message, Message.conversation_id == Conversation.id)
        .where(Message.sender_id == sender_id)
        .group_by(Conversation.id, Conversation.title, Conversation.chat_type)
        .order_by(func.count(Message.id).desc())
    )
    groups = [
        {
            "conversation_id": row.id,
            "title": row.title or "未知群组",
            "message_count": row.msg_count,
            "last_message_at": row.last_msg.isoformat() if row.last_msg else None,
        }
        for row in group_stats.all()
    ]

    return {
        "sender_id": sender.id,
        "user_id": sender.user_id,
        "username": sender.username,
        "first_name": sender.first_name,
        "last_name": sender.last_name,
        "phone": sender.phone,
        "sender_name": _sender_name(sender),
        "total_messages": stats.total or 0,
        "alert_count": alert_count,
        "group_count": stats.group_count or 0,
        "message_types": message_types,
        "groups": groups,
    }


@router.get("/{sender_id}/messages")
async def get_sender_messages(
    sender_id: int,
    group_by: str = Query("group"),
    conversation_id: Optional[int] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """获取发送者的消息列表"""
    conditions = [Message.sender_id == sender_id]

    if conversation_id:
        conditions.append(Message.conversation_id == conversation_id)
    if date_from:
        conditions.append(Message.date >= date_from)
    if date_to:
        conditions.append(Message.date <= f"{date_to} 23:59:59")
    if keyword:
        conditions.append(
            or_(
                Message.text.ilike(f"%{keyword}%"),
                Message.caption.ilike(f"%{keyword}%"),
            )
        )

    query = (
        select(
            Message.id,
            Message.text,
            Message.caption,
            Message.message_type,
            Message.date,
            Message.has_media,
            Message.is_reply,
            Message.matched_keywords,
            Message.conversation_id,
            Conversation.title.label("conv_title"),
            Message.alert_id,
        )
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(and_(*conditions))
        .order_by(Message.date.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    rows = result.all()

    messages = [
        {
            "id": row.id,
            "conversation_id": row.conversation_id,
            "content": row.text or row.caption or "",
            "message_type": row.message_type,
            "created_at": row.date.isoformat() if row.date else None,
            "group_title": row.conv_title or "未知群组",
            "is_alert": bool(row.alert_id) if row.alert_id else False,
            "alert_level": None,
            "has_media": row.has_media,
            "is_reply": row.is_reply,
            "matched_keywords": row.matched_keywords,
        }
        for row in rows
    ]

    return {
        "messages": messages,
        "has_more": len(messages) == limit,
    }
