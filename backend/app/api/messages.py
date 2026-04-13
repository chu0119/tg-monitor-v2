"""消息查询 API"""
from typing import List, Optional, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from loguru import logger

from app.api.deps import get_db
from app.schemas.message import MessageResponse, MessageFilter, MessageExport
from app.models.message import Message
from app.models.conversation import Conversation
from app.models.sender import Sender
from app.services.export_service import export_service
from app.services.import_service import import_service
from app.utils import to_local_naive

router = APIRouter(prefix="/messages", tags=["消息查询"])


@router.get("/search")
async def advanced_search_messages(
    keyword: Optional[str] = Query(None, description="搜索关键词（支持全文匹配）"),
    conversation_id: Optional[int] = Query(None),
    sender_id: Optional[int] = Query(None),
    message_type: Optional[str] = Query(None),
    has_alert: Optional[bool] = Query(None),
    alert_level: Optional[str] = Query(None, description="告警级别过滤"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    sort_by: str = Query("date", description="排序字段: date/views/forwards"),
    sort_order: str = Query("desc", description="排序方向: asc/desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """高级搜索消息 - 支持多条件组合 + 全文匹配 + 排序"""
    from app.models.alert import Alert as AlertModel

    conditions = []

    if conversation_id:
        conditions.append(Message.conversation_id == conversation_id)
    if sender_id:
        conditions.append(Message.sender_id == sender_id)
    if message_type:
        conditions.append(Message.message_type == message_type)
    if has_alert is not None:
        if has_alert:
            conditions.append(Message.alert_id.isnot(None))
        else:
            conditions.append(Message.alert_id.is_(None))
    if alert_level:
        alert_subq = select(AlertModel.id).where(
            AlertModel.id == Message.alert_id,
            AlertModel.alert_level == alert_level,
        ).exists()
        conditions.append(alert_subq)

    # 关键词搜索 - 使用 ILIKE 模糊匹配
    if keyword:
        conditions.append(
            or_(
                Message.text.ilike(f"%{keyword}%"),
                Message.caption.ilike(f"%{keyword}%"),
            )
        )

    # 日期过滤
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            if start_dt.tzinfo:
                start_dt = start_dt.astimezone(timezone.utc).replace(tzinfo=None)
            conditions.append(Message.date >= start_dt)
        except ValueError:
            pass
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            if end_dt.tzinfo:
                end_dt = end_dt.astimezone(timezone.utc).replace(tzinfo=None)
            conditions.append(Message.date <= end_dt)
        except ValueError:
            pass

    # 总数
    count_query = select(func.count(Message.id))
    if conditions:
        count_query = count_query.where(and_(*conditions))
    total = (await db.execute(count_query)).scalar()

    # 排序
    order_col = getattr(Message, sort_by, Message.date)
    if sort_order == "asc":
        query = select(Message).options(selectinload(Message.sender), selectinload(Message.conversation))
        if conditions:
            query = query.where(and_(*conditions))
        query = query.order_by(order_col.asc())
    else:
        query = select(Message).options(selectinload(Message.sender), selectinload(Message.conversation))
        if conditions:
            query = query.where(and_(*conditions))
        query = query.order_by(order_col.desc())

    query = query.offset((page - 1) * page_size).limit(page_size)
    messages = (await db.execute(query)).scalars().all()

    response_messages = []
    for msg in messages:
        msg_dict = MessageResponse.model_validate(msg).model_dump()
        if msg.sender:
            msg_dict["sender_username"] = msg.sender.username or msg.sender.first_name or f"User_{msg.sender.user_id}"
            msg_dict["sender_first_name"] = msg.sender.first_name
            msg_dict["sender_telegram_id"] = msg.sender.user_id
            msg_dict["sender_phone"] = msg.sender.phone
        if msg.conversation:
            msg_dict["conversation_title"] = msg.conversation.title
        response_messages.append(msg_dict)

    return {
        "items": response_messages,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total else 0,
    }


@router.post("/search/fulltext/setup")
async def setup_fulltext_index(db: AsyncSession = Depends(get_db)):
    """创建全文搜索索引（MySQL FULLTEXT）"""
    from sqlalchemy import text
    try:
        await db.execute(text(
            "ALTER TABLE messages ADD FULLTEXT INDEX ft_message_text (text) WITH PARSER ngram"
        ))
        await db.commit()
        return {"message": "全文搜索索引创建成功"}
    except Exception as e:
        error_msg = str(e)
        if "Duplicate key name" in error_msg or "already exists" in error_msg.lower():
            return {"message": "全文搜索索引已存在"}
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"创建全文索引失败: {error_msg}")


@router.get("")
async def list_messages(
    conversation_id: Optional[int] = Query(None),
    sender_id: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None),
    message_type: Optional[str] = Query(None),
    has_alert: Optional[bool] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """获取消息列表 - 返回分页数据"""
    # 构建查询条件
    conditions = []

    if conversation_id:
        conditions.append(Message.conversation_id == conversation_id)
    if sender_id:
        conditions.append(Message.sender_id == sender_id)
    if message_type:
        conditions.append(Message.message_type == message_type)
    if has_alert is not None:
        if has_alert:
            conditions.append(Message.alert_id.isnot(None))
        else:
            conditions.append(Message.alert_id.is_(None))
    if keyword:
        conditions.append(or_(
            Message.text.ilike(f"%{keyword}%"),
            Message.caption.ilike(f"%{keyword}%")
        ))

    # 日期过滤
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            # 转换为UTC naive datetime用于数据库查询
            if start_dt.tzinfo is not None:
                start_dt = start_dt.astimezone(timezone.utc).replace(tzinfo=None)
            conditions.append(Message.date >= start_dt)
        except ValueError:
            logger.warning(f"Invalid start_date format: {start_date}")

    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            # 转换为UTC naive datetime用于数据库查询
            if end_dt.tzinfo is not None:
                end_dt = end_dt.astimezone(timezone.utc).replace(tzinfo=None)
            conditions.append(Message.date <= end_dt)
        except ValueError:
            logger.warning(f"Invalid end_date format: {end_date}")

    # 先获取总数
    count_query = select(func.count(Message.id))
    if conditions:
        count_query = count_query.where(and_(*conditions))
    count_result = await db.execute(count_query)
    total = count_result.scalar()

    # 获取分页数据 - 使用 selectinload 避免 N+1 查询
    query = select(Message).options(
        selectinload(Message.sender),
        selectinload(Message.conversation)
    )
    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(Message.date.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    messages = result.scalars().all()

    # 补充关联信息 - 已通过 selectinload 预加载，直接使用
    response_messages = []
    for msg in messages:
        msg_dict = MessageResponse.model_validate(msg).model_dump()

        # 获取发送者信息 - 已预加载，直接访问
        if msg.sender:
            # 优先使用 username，其次 first_name，最后显示 user_id
            if msg.sender.username:
                msg_dict["sender_username"] = msg.sender.username
            elif msg.sender.first_name:
                msg_dict["sender_username"] = msg.sender.first_name
            else:
                msg_dict["sender_username"] = f"User_{msg.sender.user_id}"
            msg_dict["sender_first_name"] = msg.sender.first_name
            msg_dict["sender_telegram_id"] = msg.sender.user_id
            msg_dict["sender_phone"] = msg.sender.phone
        elif msg.sender_id:
            logger.warning(f"Sender not found for sender_id={msg.sender_id}, message_id={msg.id}")
            msg_dict["sender_username"] = f"Unknown (ID: {msg.sender_id})"

        # 获取会话信息 - 已预加载，直接访问
        if msg.conversation:
            msg_dict["conversation_title"] = msg.conversation.title
        elif msg.conversation_id:
            msg_dict["conversation_title"] = f"Conversation_{msg.conversation_id}"

        response_messages.append(msg_dict)

    # 返回分页格式
    return {
        "items": response_messages,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@router.get("/{message_id}", response_model=MessageResponse)
async def get_message(message_id: int, db: AsyncSession = Depends(get_db)):
    """获取消息详情"""
    result = await db.execute(
        select(Message).where(Message.id == message_id)
    )
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="消息不存在"
        )
    return message


@router.post("/export")
async def export_messages(export_data: MessageExport, db: AsyncSession = Depends(get_db)):
    """导出消息"""
    try:
        file_path, file_type = await export_service.export_messages(
            db, export_data
        )
        return {
            "file_path": file_path,
            "file_type": file_type,
            "message": "导出成功"
        }
    except Exception as e:
        logger.error(f"导出失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/export/incremental")
async def export_messages_incremental(
    conversation_id: Optional[int] = Query(None),
    since_date: str = Query(..., description="导出此时间之后的消息 (ISO格式)"),
    format: str = Query("csv", description="导出格式: csv, json, xlsx"),
    include_sender: bool = Query(True),
    include_conversation: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    """增量导出 - 只导出指定时间之后的消息"""
    from app.schemas.message import MessageExport, MessageFilter

    try:
        since_dt = datetime.fromisoformat(since_date.replace("Z", "+00:00"))
        if since_dt.tzinfo:
            since_dt = since_dt.replace(tzinfo=None)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式无效，请使用 ISO 8601 格式")

    filter_data = MessageFilter(start_date=since_dt)
    if conversation_id:
        filter_data.conversation_ids = [conversation_id]

    export_data = MessageExport(
        filter=filter_data,
        format=format,
        include_sender=include_sender,
        include_conversation=include_conversation,
    )

    try:
        file_path, file_type = await export_service.export_messages(db, export_data)
        return FileResponse(
            path=file_path,
            media_type=file_type,
            filename=file_path.split("/")[-1],
        )
    except Exception as e:
        logger.error(f"增量导出失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import")
async def import_messages(
    file_path: str = Query(..., description="导入文件路径 (CSV 或 JSON)"),
    conversation_id: Optional[int] = Query(None, description="默认会话ID"),
    skip_duplicates: bool = Query(True, description="跳过重复消息"),
    db: AsyncSession = Depends(get_db),
):
    """导入消息数据 (CSV 或 JSON)"""
    path = file_path.lower()
    try:
        if path.endswith(".csv"):
            result = await import_service.import_messages_from_csv(
                db, file_path, conversation_id, skip_duplicates
            )
        elif path.endswith(".json"):
            result = await import_service.import_messages_from_json(
                db, file_path, conversation_id, skip_duplicates
            )
        else:
            raise HTTPException(status_code=400, detail="不支持的文件格式，请使用 CSV 或 JSON")
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"导入失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
