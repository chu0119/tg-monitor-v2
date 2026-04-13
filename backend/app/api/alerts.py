"""告警管理 API"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update, and_, or_, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from loguru import logger
import csv
import io
from datetime import datetime, timedelta, timezone

from app.api.deps import get_db
from app.utils import datetime_to_iso
from app.schemas.alert import (
    AlertResponse,
    AlertFilter,
    AlertHandle,
    AlertStatusUpdate,
    AlertStats,
)
from app.models.alert import Alert, AlertStatus, AlertLevel
from app.models.keyword import KeywordGroup, Keyword
from app.models.conversation import Conversation
from app.services.alert_service import alert_service
from app.services.alert_aggregation_service import alert_aggregation_service
from app.utils import (
    start_of_day_local, end_of_day_local, to_local,
    to_local_naive, now_utc, format_datetime, datetime_to_iso
)

router = APIRouter(prefix="/alerts", tags=["告警管理"])


@router.get("")
async def list_alerts(
    status: AlertStatus = Query(None),
    alert_level: AlertLevel = Query(None),
    keyword_group_id: int = Query(None),
    conversation_id: int = Query(None),
    sender_id: int = Query(None),
    keyword: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """获取告警列表 - 返回分页数据"""
    # 用原生 SQL 查询，避免 ORM selectinload 对大表的性能问题
    where_clauses = []
    params = {}
    if status:
        where_clauses.append("a.status = :status")
        params["status"] = status
    if alert_level:
        where_clauses.append("a.alert_level = :alert_level")
        params["alert_level"] = alert_level
    if conversation_id:
        where_clauses.append("a.conversation_id = :conversation_id")
        params["conversation_id"] = conversation_id
    if sender_id:
        where_clauses.append("a.sender_id = :sender_id")
        params["sender_id"] = sender_id
    if keyword:
        matching_keywords_result = await db.execute(
            select(Keyword.id).where(Keyword.word.ilike(f"%{keyword}%"))
        )
        matching_keyword_ids = [row[0] for row in matching_keywords_result.fetchall()]
        if matching_keyword_ids:
            placeholders = ", ".join(f":kw_{j}" for j in range(len(matching_keyword_ids)))
            where_clauses.append(f"a.keyword_id IN ({placeholders})")
            for j, kw_id in enumerate(matching_keyword_ids):
                params[f"kw_{j}"] = kw_id
        else:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}

    if keyword_group_id:
        group_result = await db.execute(
            select(KeywordGroup.name).where(KeywordGroup.id == keyword_group_id)
        )
        keyword_group_name = group_result.scalar_one_or_none()
        if keyword_group_name:
            where_clauses.append("a.keyword_group_name = :kg_name")
            params["kg_name"] = keyword_group_name
        else:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    # count
    count_result = await db.execute(text(f"SELECT count(*) FROM alerts a{where_sql}"), params)
    total = count_result.scalar()

    # 分页数据 - 直接 JOIN 取关联字段
    offset = (page - 1) * page_size
    data_sql = f"""
        SELECT a.id, a.message_id, a.conversation_id, a.keyword_id, a.sender_id,
               a.keyword_text, a.keyword_group_name, a.alert_level, a.status,
               a.matched_text, a.message_preview, a.highlighted_message,
               a.handler, a.handler_note, a.handled_at,
               a.notification_sent, a.notification_channels, a.notification_status,
               a.created_at, a.updated_at,
               s.user_id AS sender_tg_id,
               COALESCE(s.username, COALESCE(s.first_name, CONCAT('User_', s.user_id))) AS sender_username,
               s.first_name AS sender_first_name,
               s.phone AS sender_phone,
               c.title AS conversation_title
        FROM alerts a
        LEFT JOIN senders s ON a.sender_id = s.id
        LEFT JOIN conversations c ON a.conversation_id = c.id
        {where_sql}
        ORDER BY a.created_at DESC
        LIMIT :lim OFFSET :off
    """
    params["lim"] = page_size
    params["off"] = offset
    result = await db.execute(text(data_sql), params)
    rows = result.fetchall()

    response_alerts = []
    for row in rows:
        alert_dict = dict(row._mapping)
        if alert_dict.get("created_at"):
            if isinstance(alert_dict["created_at"], datetime):
                alert_dict["created_at"] = datetime_to_iso(alert_dict["created_at"])
            else:
                alert_dict["message_date"] = str(alert_dict["created_at"])
        response_alerts.append(alert_dict)

    # 返回分页格式
    return {
        "items": response_alerts,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@router.get("/stats", response_model=AlertStats)
async def get_alert_stats(db: AsyncSession = Depends(get_db)):
    """获取告警统计"""
    stats = await alert_service.get_alert_stats()

    # 获取按关键词组统计
    group_result = await db.execute(
        select(
            Alert.keyword_group_name,
            func.count(Alert.id).label("count")
        )
        .group_by(Alert.keyword_group_name)
        .order_by(func.count(Alert.id).desc())
        .limit(10)
    )
    by_keyword_group = [
        {"group": row.keyword_group_name, "count": row.count}
        for row in group_result.all()
    ]
    stats["by_keyword_group"] = by_keyword_group

    # 获取按会话统计 - 使用 JOIN 避免 N+1 查询
    from app.models.conversation import Conversation
    conv_result = await db.execute(
        select(
            Alert.conversation_id,
            Conversation.title,
            func.count(Alert.id).label("count")
        )
        .join(Conversation, Alert.conversation_id == Conversation.id)
        .group_by(Alert.conversation_id, Conversation.title)
        .order_by(func.count(Alert.id).desc())
        .limit(10)
    )
    by_conversation = [
        {
            "conversation_id": row.conversation_id,
            "title": row.title,
            "count": row.count
        }
        for row in conv_result.all()
    ]
    stats["by_conversation"] = by_conversation

    # 获取趋势数据（最近7天）- 单条 GROUP BY 查询
    today_start = to_local_naive(start_of_day_local(now_utc()))
    start_7d = today_start - timedelta(days=6)
    end_7d = today_start + timedelta(days=1)

    trend_result = await db.execute(
        select(func.date(Alert.created_at), func.count(Alert.id))
        .where(Alert.created_at >= start_7d, Alert.created_at < end_7d)
        .group_by(func.date(Alert.created_at))
    )
    trend_map = {str(row[0]): row[1] for row in trend_result.all()}

    trend_data = []
    for i in range(7):
        date = start_7d + timedelta(days=i)
        trend_data.append({
            "date": date.strftime("%Y-%m-%d"),
            "count": trend_map.get(date.strftime("%Y-%m-%d"), 0)
        })
    stats["trend"] = trend_data

    return AlertStats(**stats)


@router.get("/export/csv")
async def export_alerts_csv(
    status: AlertStatus = Query(None),
    alert_level: AlertLevel = Query(None),
    keyword_group_id: int = Query(None),
    conversation_id: int = Query(None),
    sender_id: int = Query(None),
    keyword: str = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """导出告警为 CSV 文件"""
    # 构建查询条件
    conditions = []

    if status:
        conditions.append(Alert.status == status)
    if alert_level:
        conditions.append(Alert.alert_level == alert_level)
    if conversation_id:
        conditions.append(Alert.conversation_id == conversation_id)
    if sender_id:
        conditions.append(Alert.sender_id == sender_id)
    if keyword:
        # 优化：先在 keywords 表中查找匹配的关键词 ID，再用 ID 查询 alerts
        # keyword_id 有索引，比 keyword_text IN 查询快得多
        matching_keywords_result = await db.execute(
            select(Keyword.id).where(Keyword.word.ilike(f"%{keyword}%"))
        )
        matching_keyword_ids = [row[0] for row in matching_keywords_result.fetchall()]
        if matching_keyword_ids:
            conditions.append(Alert.keyword_id.in_(matching_keyword_ids))
    if keyword_group_id:
        conditions.append(Alert.keyword_group_name == select(KeywordGroup.name).where(
            KeywordGroup.id == keyword_group_id
        ).scalar_subquery())
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            # 转换为UTC naive datetime用于数据库查询
            if start_dt.tzinfo is not None:
                start_dt = start_dt.astimezone(timezone.utc).replace(tzinfo=None)
            conditions.append(Alert.created_at >= start_dt)
        except ValueError:
            logger.warning(f"Invalid start_date format: {start_date}")
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            # 转换为UTC naive datetime用于数据库查询
            if end_dt.tzinfo is not None:
                end_dt = end_dt.astimezone(timezone.utc).replace(tzinfo=None)
            conditions.append(Alert.created_at <= end_dt)
        except ValueError:
            logger.warning(f"Invalid end_date format: {end_date}")

    # 流式分批查询，避免全量加载 OOM
    BATCH_SIZE = 1000
    offset = 0

    # 构建 WHERE 子句（原生SQL）
    where_clauses_export = []
    params_export = {}
    if status:
        where_clauses_export.append("a.status = :status")
        params_export["status"] = status
    if alert_level:
        where_clauses_export.append("a.alert_level = :alert_level")
        params_export["alert_level"] = alert_level
    if conversation_id:
        where_clauses_export.append("a.conversation_id = :conversation_id")
        params_export["conversation_id"] = conversation_id
    if sender_id:
        where_clauses_export.append("a.sender_id = :sender_id")
        params_export["sender_id"] = sender_id
    if keyword:
        matching_keywords_result = await db.execute(
            select(Keyword.id).where(Keyword.word.ilike(f"%{keyword}%"))
        )
        matching_keyword_ids = [row[0] for row in matching_keywords_result.fetchall()]
        if matching_keyword_ids:
            placeholders = ", ".join(f":kw_{j}" for j in range(len(matching_keyword_ids)))
            where_clauses_export.append(f"a.keyword_id IN ({placeholders})")
            for j, kw_id in enumerate(matching_keyword_ids):
                params_export[f"kw_{j}"] = kw_id
    if keyword_group_id:
        group_result = await db.execute(
            select(KeywordGroup.name).where(KeywordGroup.id == keyword_group_id)
        )
        keyword_group_name = group_result.scalar_one_or_none()
        if keyword_group_name:
            where_clauses_export.append("a.keyword_group_name = :kg_name")
            params_export["kg_name"] = keyword_group_name
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            if start_dt.tzinfo is not None:
                start_dt = start_dt.astimezone(timezone.utc).replace(tzinfo=None)
            where_clauses_export.append("a.created_at >= :start_date")
            params_export["start_date"] = start_dt
        except ValueError:
            logger.warning(f"Invalid start_date format: {start_date}")
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            if end_dt.tzinfo is not None:
                end_dt = end_dt.astimezone(timezone.utc).replace(tzinfo=None)
            where_clauses_export.append("a.created_at <= :end_date")
            params_export["end_date"] = end_dt
        except ValueError:
            logger.warning(f"Invalid end_date format: {end_date}")

    where_sql_export = (" WHERE " + " AND ".join(where_clauses_export)) if where_clauses_export else ""

    # 创建 CSV 内容
    output = io.StringIO()
    writer = csv.writer(output)

    # 写入表头
    headers = [
        "告警ID",
        "创建时间",
        "告警级别",
        "状态",
        "关键词",
        "关键词组",
        "匹配文本",
        "消息ID",
        "会话ID",
        "会话标题",
        "发送者ID",
        "发送者用户名",
        "发送者名称",
        "发送者手机号",
        "处理人",
        "处理时间",
        "处理备注",
        "通知已发送",
    ]
    writer.writerow(headers)

    # 分批读取并写入 CSV
    while True:
        export_sql = f"""
            SELECT a.id, a.created_at, a.alert_level, a.status,
                   a.keyword_text, a.keyword_group_name, a.matched_text,
                   a.message_id, a.conversation_id, a.sender_id,
                   a.handler, a.handled_at, a.handler_note, a.notification_sent,
                   COALESCE(s.username, COALESCE(s.first_name, CONCAT('User_', s.user_id))) AS sender_username,
                   s.first_name AS sender_first_name,
                   s.phone AS sender_phone,
                   c.title AS conversation_title
            FROM alerts a
            LEFT JOIN senders s ON a.sender_id = s.id
            LEFT JOIN conversations c ON a.conversation_id = c.id
            {where_sql_export}
            ORDER BY a.created_at DESC
            LIMIT :batch_size OFFSET :batch_offset
        """
        params_export["batch_size"] = BATCH_SIZE
        params_export["batch_offset"] = offset
        result = await db.execute(text(export_sql), params_export)
        rows = result.fetchall()
        if not rows:
            break
        for row in rows:
            d = dict(row._mapping)
            writer.writerow([
                d.get("id", ""),
                format_datetime(d.get("created_at")) if d.get("created_at") else "",
                d.get("alert_level", ""),
                d.get("status", ""),
                d.get("keyword_text") or "",
                d.get("keyword_group_name") or "",
                d.get("matched_text") or "",
                d.get("message_id") or "",
                d.get("conversation_id") or "",
                d.get("conversation_title") or "",
                d.get("sender_id") or "",
                d.get("sender_username") or "",
                d.get("sender_first_name") or "",
                d.get("sender_phone") or "",
                d.get("handler") or "",
                format_datetime(d.get("handled_at")) if d.get("handled_at") else "",
                d.get("handler_note") or "",
                "是" if d.get("notification_sent") else "否",
            ])
        offset += BATCH_SIZE
        if len(rows) < BATCH_SIZE:
            break

    # 准备响应
    output.seek(0)
    csv_content = output.getvalue()

    # 生成文件名
    now_local_dt = to_local_naive(now_utc())
    filename = f"alerts_export_{now_local_dt.strftime('%Y%m%d_%H%M%S')}.csv"

    # 返回 CSV 文件
    return StreamingResponse(
        io.BytesIO(csv_content.encode("utf-8-sig")),  # 使用 UTF-8 BOM 以支持 Excel
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


# ==================== 批量操作 ====================

@router.put("/batch-status")
async def batch_update_alert_status(
    data: dict,
    db: AsyncSession = Depends(get_db),
):
    """批量更新告警状态"""
    alert_ids = data.get("alert_ids", [])
    new_status = data.get("status")
    handler_note = data.get("handler_note")
    if not alert_ids or not new_status:
        raise HTTPException(status_code=400, detail="alert_ids 和 status 不能为空")

    values = {"status": new_status}
    if handler_note is not None:
        values["handler_note"] = handler_note

    result = await db.execute(
        update(Alert)
        .where(Alert.id.in_(alert_ids))
        .values(**values)
    )
    await db.commit()
    return {"message": f"已更新 {result.rowcount} 条告警状态"}


@router.delete("/batch")
async def batch_delete_alerts(
    data: dict,
    db: AsyncSession = Depends(get_db),
):
    """批量删除告警"""
    alert_ids = data.get("alert_ids", [])
    if not alert_ids:
        raise HTTPException(status_code=400, detail="alert_ids 不能为空")

    result = await db.execute(
        update(Alert)
        .where(Alert.id.in_(alert_ids))
        .values(status="deleted")
    )
    await db.commit()
    return {"message": f"已删除 {result.rowcount} 条告警"}


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: int, db: AsyncSession = Depends(get_db)):
    """获取告警详情"""
    result = await db.execute(
        select(Alert).where(Alert.id == alert_id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="告警不存在"
        )
    return alert


@router.put("/{alert_id}/handle")
async def handle_alert(
    alert_id: int,
    handle_data: AlertHandle,
):
    """处理告警"""
    try:
        await alert_service.handle_alert(
            alert_id=alert_id,
            status=handle_data.status,
            handler=handle_data.handler,
            handler_note=handle_data.handler_note
        )
        return {"message": "告警已处理"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"处理告警失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="处理失败"
        )


@router.put("/{alert_id}/status")
async def update_alert_status(
    alert_id: int,
    data: AlertStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新告警状态"""
    result = await db.execute(
        select(Alert).where(Alert.id == alert_id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="告警不存在"
        )

    alert.status = data.status
    await db.commit()

    return {"message": "状态已更新"}


@router.delete("/{alert_id}")
async def delete_alert(alert_id: int, db: AsyncSession = Depends(get_db)):
    """删除告警"""
    result = await db.execute(
        select(Alert).where(Alert.id == alert_id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="告警不存在"
        )

    await db.delete(alert)
    await db.commit()

    return {"message": "告警已删除"}


# ==================== 告警聚合 ====================

@router.get("/aggregation/summary")
async def get_alert_aggregation_summary(
    window_minutes: int = Query(30, ge=1, le=1440, description="聚合窗口（分钟）"),
    db: AsyncSession = Depends(get_db),
):
    """获取聚合告警摘要 - 同一会话+关键词组的告警自动合并"""
    summaries = await alert_aggregation_service.get_aggregated_alerts(
        db, window_minutes=window_minutes
    )
    return {"items": summaries, "window_minutes": window_minutes}


@router.post("/aggregation/escalate")
async def escalate_stale_alerts(db: AsyncSession = Depends(get_db)):
    """升级超时未处理的告警（24h->medium, 48h->high, 72h->critical）"""
    result = await alert_aggregation_service.escalate_stale_alerts(db)
    return result


@router.get("/aggregation/trend")
async def get_alert_trend(
    days: int = Query(7, ge=1, le=90, description="统计天数"),
    group_by: str = Query("day", description="分组方式: day/hour"),
    db: AsyncSession = Depends(get_db),
):
    """获取告警趋势统计"""
    trend = await alert_aggregation_service.get_alert_trend(db, days=days, group_by=group_by)
    return {"items": trend, "days": days, "group_by": group_by}
