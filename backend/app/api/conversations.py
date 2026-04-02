"""会话管理 API"""
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from pydantic import BaseModel


class ConversationBatchDelete(BaseModel):
    """批量删除会话请求模型"""
    conversation_ids: List[int]


def normalize_chat_id(chat_id: int, chat_type: str) -> int:
    """
    标准化chat_id格式

    对于频道（channel），Telegram返回的chat_id通常是正数，
    但在存储和使用时需要转换为-100前缀的负数格式。

    Args:
        chat_id: 原始chat_id
        chat_type: 会话类型（channel, group, supergroup, private）

    Returns:
        标准化后的chat_id
    """
    # 对于频道，如果chat_id是正数，转换为-100前缀格式
    # 如果已经是-100前缀的负数，不再转换
    if chat_type == 'channel' and chat_id > 0:
        return -1000000000000 + chat_id

    # 对于其他类型（group, supergroup, private），保持原样
    return chat_id


from app.api.deps import get_db
from app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    ConversationMonitorConfig,
    ConversationBatchUpdate,
)
from app.models.conversation import Conversation, ConversationStatus
from app.models.message import Message
from app.models.account import TelegramAccount
from app.telegram.monitor import message_monitor
from app.utils import to_local_naive

router = APIRouter(prefix="/conversations", tags=["会话管理"])

# 批量操作大小限制
MAX_BATCH_SIZE = 100


# ==================== 批量操作路由 (必须在参数化路由之前) ====================

@router.post("/batch")
async def batch_create_conversations(
    conversations_data: List[ConversationCreate],
    force: bool = Query(False, description="强制重新添加（忽略已存在检查）"),
    db: AsyncSession = Depends(get_db),
):
    """批量创建会话 - 自动跳过已存在的会话（优化版）"""
    if not conversations_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="会话列表不能为空"
        )

    # 批量操作大小限制
    if len(conversations_data) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"批量操作最多支持 {MAX_BATCH_SIZE} 条，当前为 {len(conversations_data)} 条"
        )

    # 批量检查已存在的会话（一次性查询所有）
    chat_id_pairs = [(c.account_id, c.chat_id) for c in conversations_data]

    # 使用 CASE WHEN 批量查询已存在的会话
    existing_query = select(
        Conversation.id,
        Conversation.account_id,
        Conversation.chat_id
    ).where(
        # 构建复杂的 OR 条件
        or_(*[
            and_(
                Conversation.account_id == acc_id,
                Conversation.chat_id == chat_id
            )
            for acc_id, chat_id in chat_id_pairs
        ])
    )

    existing_result = await db.execute(existing_query)
    existing_records = existing_result.all()

    # 创建已存在的映射：{(account_id, chat_id): conversation_id}
    existing_map = {(r.account_id, r.chat_id): r.id for r in existing_records}

    created_count = 0
    skipped_count = 0
    skipped_chats = []
    results = []
    new_conversations = []

    for conv_data in conversations_data:
        key = (conv_data.account_id, conv_data.chat_id)

        if key in existing_map and not force:
            skipped_count += 1
            skipped_chats.append({
                "chat_id": conv_data.chat_id,
                "title": conv_data.title,
                "existing_id": existing_map[key]
            })
            results.append({
                "chat_id": conv_data.chat_id,
                "title": conv_data.title,
                "status": "skipped",
                "reason": "已存在",
                "id": existing_map[key]
            })
        else:
            # 如果 force=True 且已存在，先删除旧的
            if key in existing_map and force:
                old_id = existing_map[key]
                await db.execute(delete(Conversation).where(Conversation.id == old_id))
            # 创建新会话对象（不立即写入数据库）
            # 标准化chat_id格式（特别是频道）
            normalized_chat_id = normalize_chat_id(
                conv_data.chat_id,
                conv_data.chat_type or 'channel'
            )

            conversation = Conversation(**conv_data.model_dump())
            # 覆盖chat_id为标准化后的值
            conversation.chat_id = normalized_chat_id
            new_conversations.append(conversation)
            results.append({
                "chat_id": conversation.chat_id,
                "title": conv_data.title,
                "status": "created",
                "id": 0  # 占位，flush 后更新
            })

    # 批量添加新会话
    monitor_conv_ids = []
    for conversation in new_conversations:
        db.add(conversation)
        await db.flush()

        # 更新结果中的 ID
        for r in results:
            if (r["chat_id"] == conversation.chat_id and
                r["status"] == "created"):
                r["id"] = conversation.id

        # 收集需要启动监控的会话ID（commit后再启动）
        if conversation.status == "active" and conversation.enable_realtime:
            monitor_conv_ids.append(conversation.id)

        created_count += 1

    # 先commit，确保数据写入数据库后再启动监控
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        # 死锁重试一次
        logger.warning(f"批量创建会话commit失败，重试: {e}")
        try:
            await db.commit()
        except Exception as e2:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"创建会话失败: {e2}")

    # commit后再启动监控（此时数据已持久化，其他session可查到）
    for conv_id in monitor_conv_ids:
        try:
            await message_monitor.start_monitor(conv_id)
        except Exception as e:
            logger.error(f"启动监控失败 (conversation_id={conv_id}): {e}")

    # 批量更新账号的总会话数（只更新实际新增的）
    if created_count > 0:
        account_counts = defaultdict(int)
        for conv in new_conversations:
            account_counts[conv.account_id] += 1

        for account_id, count in account_counts.items():
            await db.execute(
                update(TelegramAccount)
                .where(TelegramAccount.id == account_id)
                .values(total_conversations=TelegramAccount.total_conversations + count)
            )

    return {
        "message": f"批量操作完成",
        "created": created_count,
        "skipped": skipped_count,
        "total": len(conversations_data),
        "skipped_chats": skipped_chats,
        "results": results
    }


@router.post("/batch-update")
async def batch_update_conversations(
    request: ConversationBatchUpdate,
    db: AsyncSession = Depends(get_db),
):
    """批量更新会话"""
    conversation_ids = request.conversation_ids
    update_data = request.update_data

    if not conversation_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="会话ID列表不能为空"
        )

    # 获取所有要更新的会话
    result = await db.execute(
        select(Conversation).where(Conversation.id.in_(conversation_ids))
    )
    conversations = result.scalars().all()

    if not conversations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到任何会话"
        )

    updated_count = 0
    monitors_to_start = []
    monitors_to_stop = []

    for conversation in conversations:
        if update_data.status is not None:
            old_status = conversation.status
            conversation.status = update_data.status

            # 记录需要启动/停止的监控
            if update_data.status == "active" and old_status != "active":
                monitors_to_start.append(conversation.id)
            elif update_data.status != "active" and old_status == "active":
                monitors_to_stop.append(conversation.id)

        if update_data.note is not None:
            conversation.note = update_data.note
        if update_data.monitor_config is not None:
            config = update_data.monitor_config
            if config.enable_realtime is not None:
                conversation.enable_realtime = config.enable_realtime
            if config.enable_history is not None:
                conversation.enable_history = config.enable_history
            if config.history_days is not None:
                conversation.history_days = config.history_days
            if config.history_limit is not None:
                conversation.history_limit = config.history_limit
            if config.keyword_groups is not None:
                conversation.keyword_groups = config.keyword_groups
            if config.enable_all_keywords is not None:
                conversation.enable_all_keywords = config.enable_all_keywords

            # 根据监控配置更新启动/停止列表
            if config.enable_realtime and conversation.status == "active":
                if conversation.id not in monitors_to_start:
                    monitors_to_start.append(conversation.id)
            elif not config.enable_realtime:
                if conversation.id not in monitors_to_stop:
                    monitors_to_stop.append(conversation.id)

        updated_count += 1

    await db.commit()

    # 批量启动/停止监控
    for conv_id in monitors_to_start:
        try:
            await message_monitor.start_monitor(conv_id)
        except Exception as e:
            logger.error(f"启动监控失败 (conversation_id={conv_id}): {e}")

    for conv_id in monitors_to_stop:
        try:
            await message_monitor.stop_monitor(conv_id)
        except Exception as e:
            logger.error(f"停止监控失败 (conversation_id={conv_id}): {e}")

    return {
        "message": f"批量更新完成",
        "updated": updated_count,
        "requested": len(conversation_ids)
    }


@router.delete("/batch")
async def batch_delete_conversations(
    request: ConversationBatchDelete,
    db: AsyncSession = Depends(get_db),
):
    """批量删除会话（优化版）"""
    conversation_ids = request.conversation_ids

    if not conversation_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="会话ID列表不能为空"
        )

    # 获取所有要删除的会话
    result = await db.execute(
        select(Conversation.id, Conversation.account_id).where(Conversation.id.in_(conversation_ids))
    )
    conversations = result.all()

    if not conversations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到任何会话"
        )

    # 批量统计消息数（一次性查询所有）
    conv_id_list = [c.id for c in conversations]
    msg_count_result = await db.execute(
        select(Message.conversation_id, func.count(Message.id).label('count'))
        .where(Message.conversation_id.in_(conv_id_list))
        .group_by(Message.conversation_id)
    )
    msg_counts = {row.conversation_id: row.count for row in msg_count_result.all()}

    # 停止所有监控
    for conv_id in conv_id_list:
        try:
            await message_monitor.stop_monitor(conv_id)
        except Exception as e:
            logger.error(f"停止监控失败 (conversation_id={conv_id}): {e}")

    # 批量删除消息
    await db.execute(
        delete(Message).where(Message.conversation_id.in_(conv_id_list))
    )

    # 批量删除会话
    await db.execute(
        delete(Conversation).where(Conversation.id.in_(conv_id_list))
    )

    # 统计每个账号需要减少的计数
    account_updates = defaultdict(lambda: {"conversations": 0, "messages": 0})
    for conv in conversations:
        account_updates[conv.account_id]["conversations"] += 1
        account_updates[conv.account_id]["messages"] += msg_counts.get(conv.id, 0)

    # 批量更新账号统计
    for account_id, updates in account_updates.items():
        await db.execute(
            update(TelegramAccount)
            .where(TelegramAccount.id == account_id)
            .values(
                total_conversations=TelegramAccount.total_conversations - updates["conversations"],
                total_messages=TelegramAccount.total_messages - updates["messages"]
            )
        )

    await db.commit()

    return {
        "message": f"批量删除完成",
        "deleted": len(conversations),
        "requested": len(conversation_ids)
    }


# ==================== 批量同步路由 ====================

@router.post("/batch-sync")
async def batch_sync_conversations(
    account_id: int,
    db: AsyncSession = Depends(get_db),
):
    """批量同步账号的对话列表"""
    from app.telegram.client import client_manager

    try:
        dialogs = await client_manager.get_dialogs(account_id)

        created_count = 0
        for dialog in dialogs:
            # 标准化chat_id格式（特别是频道）
            normalized_chat_id = normalize_chat_id(
                dialog["chat_id"],
                dialog["type"]
            )

            # 检查是否已存在（使用标准化后的chat_id）
            existing = await db.execute(
                select(Conversation).where(Conversation.chat_id == normalized_chat_id)
            )
            if not existing.scalar_one_or_none():
                conversation = Conversation(
                    account_id=account_id,
                    chat_id=normalized_chat_id,
                    chat_type=dialog["type"],
                    title=dialog["title"],
                    username=dialog["username"],
                    description=dialog.get("description"),
                    status="active",
                )
                db.add(conversation)
                created_count += 1

        await db.commit()

        return {"message": f"同步完成，新增 {created_count} 个会话"}

    except Exception as e:
        logger.error(f"批量同步失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== 基础 CRUD 路由 ====================

@router.get("")
async def list_conversations(
    status: Optional[ConversationStatus] = None,
    chat_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """获取会话列表 - 返回分页数据"""
    # 构建查询条件
    conditions = []
    if status:
        conditions.append(Conversation.status == status)
    if chat_type:
        conditions.append(Conversation.chat_type == chat_type)

    # 先获取总数
    count_query = select(func.count(Conversation.id))
    if conditions:
        count_query = count_query.where(and_(*conditions))
    count_result = await db.execute(count_query)
    total = count_result.scalar()

    # 获取分页数据
    query = select(Conversation)
    if conditions:
        query = query.where(and_(*conditions))

    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(Conversation.updated_at.desc())

    result = await db.execute(query)
    conversations = result.scalars().all()

    # 实时统计每个会话的消息数
    conv_ids = [c.id for c in conversations]
    msg_counts = {}
    if conv_ids:
        count_result = await db.execute(
            select(Message.conversation_id, func.count(Message.id))
            .where(Message.conversation_id.in_(conv_ids))
            .group_by(Message.conversation_id)
        )
        msg_counts = {row[0]: row[1] for row in count_result.all()}

    items = []
    for c in conversations:
        c.total_messages = msg_counts.get(c.id, 0)
        items.append(c)

    # 返回分页格式
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: int, db: AsyncSession = Depends(get_db)):
    """获取会话详情"""
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )
    return conversation


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    conversation_data: ConversationCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建会话 - 自动检测并避免重复添加"""
    # 检查是否已存在相同 account_id 和 chat_id 的会话
    existing_result = await db.execute(
        select(Conversation).where(
            and_(
                Conversation.account_id == conversation_data.account_id,
                Conversation.chat_id == conversation_data.chat_id
            )
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        # 会话已存在，返回现有会话（幂等性）
        logger.info(f"会话已存在: account_id={conversation_data.account_id}, chat_id={conversation_data.chat_id}, existing_id={existing.id}")
        return existing

    # 创建新会话
    # 标准化chat_id格式（特别是频道）
    normalized_chat_id = normalize_chat_id(
        conversation_data.chat_id,
        conversation_data.chat_type or 'channel'  # 默认为channel类型
    )

    conversation = Conversation(**conversation_data.model_dump())
    # 覆盖chat_id为标准化后的值
    conversation.chat_id = normalized_chat_id
    db.add(conversation)
    await db.flush()

    # 更新账号的总会话数
    await db.execute(
        update(TelegramAccount)
        .where(TelegramAccount.id == conversation.account_id)
        .values(total_conversations=TelegramAccount.total_conversations + 1)
    )

    await db.commit()
    await db.refresh(conversation)

    # 如果会话是活动状态且启用了实时监控，则启动监控
    if conversation.status == "active" and conversation.enable_realtime:
        await message_monitor.start_monitor(conversation.id)

    logger.info(f"创建新会话: id={conversation.id}, chat_id={conversation.chat_id}, title={conversation.title}")
    return conversation


@router.put("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: int,
    update_data: ConversationUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新会话"""
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )

    # 记录更新前的状态，用于判断是否需要启停监控
    old_status = conversation.status
    old_enable_realtime = conversation.enable_realtime

    if update_data.status is not None:
        conversation.status = update_data.status
    if update_data.note is not None:
        conversation.note = update_data.note
    if update_data.monitor_config is not None:
        config = update_data.monitor_config
        if config.enable_realtime is not None:
            conversation.enable_realtime = config.enable_realtime
        if config.enable_history is not None:
            conversation.enable_history = config.enable_history
        if config.history_days is not None:
            conversation.history_days = config.history_days
        if config.history_limit is not None:
            conversation.history_limit = config.history_limit
        if config.keyword_groups is not None:
            conversation.keyword_groups = config.keyword_groups
        if config.enable_all_keywords is not None:
            conversation.enable_all_keywords = config.enable_all_keywords

    await db.commit()
    await db.refresh(conversation)

    # 根据状态变化决定启停监控
    should_monitor = conversation.status == "active" and conversation.enable_realtime
    was_monitoring = old_status == "active" and old_enable_realtime

    if should_monitor and not was_monitoring:
        # 从非监控 -> 监控：启动
        await message_monitor.start_monitor(conversation_id)
        logger.info(f"会话 {conversation_id} 监控已启动")
    elif not should_monitor and was_monitoring:
        # 从监控 -> 非监控：停止
        await message_monitor.stop_monitor(conversation_id)
        logger.info(f"会话 {conversation_id} 监控已停止")

    return conversation


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: int, db: AsyncSession = Depends(get_db)):
    """删除会话"""
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )

    # 停止监控
    await message_monitor.stop_monitor(conversation_id)

    # 获取 account_id 和消息数，用于更新账号统计
    account_id = conversation.account_id

    # 获取该会话的消息数（用于减少账号的总消息数）
    msg_count_result = await db.execute(
        select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
    )
    msg_count = msg_count_result.scalar() or 0

    # 删除该会话的所有消息（避免外键约束错误）
    await db.execute(
        delete(Message).where(Message.conversation_id == conversation_id)
    )

    await db.delete(conversation)

    # 更新账号统计（减少总会话数和总消息数）
    await db.execute(
        update(TelegramAccount)
        .where(TelegramAccount.id == account_id)
        .values(
            total_conversations=TelegramAccount.total_conversations - 1,
            total_messages=TelegramAccount.total_messages - msg_count
        )
    )

    await db.commit()

    return {"message": "会话已删除"}


@router.post("/{conversation_id}/pull-history")
async def pull_history(
    conversation_id: int,
    days: Optional[int] = Query(None, ge=1, le=365),
    limit: Optional[int] = Query(None, ge=1, le=100000),
    db: AsyncSession = Depends(get_db),
):
    """拉取历史消息"""
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )

    history_days = days or conversation.history_days
    history_limit = limit or conversation.history_limit

    # 异步拉取历史消息 - 添加错误处理
    import asyncio

    async def pull_with_error_handling():
        try:
            await message_monitor.pull_history(conversation_id, history_days, history_limit)
        except Exception as e:
            logger.error(f"拉取历史消息失败 (conversation_id={conversation_id}): {e}")

    # 创建后台任务
    asyncio.create_task(pull_with_error_handling())

    return {"message": "历史消息拉取任务已启动"}


@router.get("/{conversation_id}/stats")
async def get_conversation_stats(conversation_id: int, db: AsyncSession = Depends(get_db)):
    """获取会话统计"""
    # 消息总数
    msg_result = await db.execute(
        select(func.count(Message.id))
        .where(Message.conversation_id == conversation_id)
    )
    total_messages = msg_result.scalar()

    # 告警总数
    from app.models.alert import Alert
    alert_result = await db.execute(
        select(func.count(Alert.id))
        .where(Alert.conversation_id == conversation_id)
    )
    total_alerts = alert_result.scalar()

    # 每日消息趋势（最近7天）
    trend_data = []
    for i in range(7):
        # 使用UTC时间查询数据库
        date_utc = datetime.now(timezone.utc) - timedelta(days=i)
        next_date_utc = date_utc + timedelta(days=1)
        # 转换为naive datetime用于查询
        date = date_utc.replace(tzinfo=None)
        next_date = next_date_utc.replace(tzinfo=None)

        day_result = await db.execute(
            select(func.count(Message.id))
            .where(
                Message.conversation_id == conversation_id,
                Message.date >= date,
                Message.date < next_date
            )
        )
        count = day_result.scalar()
        trend_data.append({
            "date": date.strftime("%Y-%m-%d"),
            "count": count
        })

    return {
        "total_messages": total_messages,
        "total_alerts": total_alerts,
        "trend": list(reversed(trend_data)),
    }


@router.post("/add-all-channels/{account_id}")
async def add_all_channels_from_account(
    account_id: int,
    enable_realtime: bool = True,
    enable_history: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """
    自动添加账号上的所有频道到监控

    Args:
        account_id: 账号ID
        enable_realtime: 是否启用实时监控
        enable_history: 是否启用历史消息拉取

    Returns:
        添加结果统计
    """
    from app.telegram.client import client_manager

    # 获取客户端
    client = await client_manager.get_client(account_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"账号 {account_id} 客户端未连接"
        )

    # 获取已添加的频道
    result = await db.execute(
        select(Conversation.chat_id).where(
            Conversation.account_id == account_id,
            Conversation.chat_type == 'channel'
        )
    )
    existing_chat_ids = set([c[0] for c in result.all()])

    # 获取账号的所有频道
    added_count = 0
    skipped_count = 0
    error_count = 0
    errors = []

    try:
        async for dialog in client.iter_dialogs():
            entity = dialog.entity

            # 只处理频道
            if not hasattr(entity, 'channel'):
                continue

            chat_id = entity.id
            # 标准化频道chat_id
            if chat_id > 0:
                chat_id = -1000000000000 + chat_id

            # 检查是否已添加
            if chat_id in existing_chat_ids:
                skipped_count += 1
                continue

            # 创建新会话
            try:
                conversation = Conversation(
                    account_id=account_id,
                    chat_id=chat_id,
                    title=dialog.title,
                    username=getattr(entity, 'username', None),
                    chat_type='channel',
                    status='active',
                    enable_realtime=enable_realtime,
                    enable_history=enable_history,
                    total_messages=0
                )
                db.add(conversation)
                await db.flush()
                added_count += 1
                logger.info(f"添加频道: {dialog.title} (chat_id={chat_id})")
            except Exception as e:
                error_count += 1
                errors.append(f"{dialog.title}: {str(e)}")
                logger.error(f"添加频道失败 {dialog.title}: {e}")

        # 提交所有更改
        await db.commit()

        # 启动新添加会话的监控
        if enable_realtime and added_count > 0:
            result = await db.execute(
                select(Conversation.id).where(
                    Conversation.account_id == account_id,
                    Conversation.chat_type == 'channel',
                    Conversation.enable_realtime == True
                )
            )
            for row in result.all():
                await message_monitor.start_monitor(row[0])

        return {
            "message": f"成功添加 {added_count} 个频道",
            "added_count": added_count,
            "skipped_count": skipped_count,
            "error_count": error_count,
            "errors": errors[:10]  # 只返回前10个错误
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"批量添加频道失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
