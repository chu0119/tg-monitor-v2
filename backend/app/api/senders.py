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
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total else 0,
    }
