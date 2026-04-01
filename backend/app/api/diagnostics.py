"""频道诊断API - 检查频道可达性和监控状态"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from app.core.config import settings
from typing import List, Dict, Any
from datetime import datetime

from app.core.database import get_db
from app.models import Conversation, Message as MessageModel
from app.telegram.client import client_manager

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


class ConversationDiagnostic:
    """会话诊断结果"""

    def __init__(
        self,
        id: int,
        title: str,
        chat_id: int,
        chat_type: str,
        status: str,
        total_messages: int,
        last_message_at: datetime = None,
        accessible: bool = False,
        error_message: str = None,
        has_recent_activity: bool = False,
    ):
        self.id = id
        self.title = title
        self.chat_id = chat_id
        self.chat_type = chat_type
        self.status = status
        self.total_messages = total_messages
        self.last_message_at = last_message_at
        self.accessible = accessible
        self.error_message = error_message
        self.has_recent_activity = has_recent_activity

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "chat_id": self.chat_id,
            "chat_type": self.chat_type,
            "status": self.status,
            "total_messages": self.total_messages,
            "last_message_at": self.last_message_at.isoformat() if self.last_message_at else None,
            "accessible": self.accessible,
            "error_message": self.error_message,
            "has_recent_activity": self.has_recent_activity,
        }


async def check_conversation_accessibility(
    conversation: Conversation, client
) -> tuple[bool, str | None]:
    """
    检查会话是否可访问

    返回: (是否可访问, 错误信息)
    """
    try:
        # 尝试获取会话实体
        entity = await client.get_entity(conversation.chat_id)

        # 检查是否被限制
        if hasattr(entity, "restricted") and entity.restricted:
            return False, "频道受限，可能无法获取完整消息"

        if hasattr(entity, "left") and entity.left:
            return False, "已退出该频道/群组"

        if hasattr(entity, "kicked") and entity.kicked:
            return False, "已被踢出该频道/群组"

        # 尝试获取1条最新消息来验证连接
        try:
            messages = await client.get_messages(conversation.chat_id, limit=1)
            if messages and len(messages) > 0:
                return True, None
            else:
                return False, "无法获取消息（频道可能为空）"
        except Exception as e:
            return False, f"获取消息失败: {str(e)}"

    except Exception as e:
        error_str = str(e).lower()
        if "channel" in error_str and "invalid" in error_str:
            return False, "无效的频道ID"
        elif "privacy" in error_str or "forbidden" in error_str:
            return False, "无权访问（私有频道或需要加入）"
        elif "not found" in error_str or "does not exist" in error_str:
            return False, "频道不存在或已删除"
        else:
            return False, f"连接失败: {str(e)}"


@router.get("/conversations")
async def diagnose_conversations(
    db: AsyncSession = Depends(get_db),
    check_accessibility: bool = True,
    limit: int = 50,
):
    """
    诊断所有会话的状态

    参数:
    - check_accessibility: 是否检查可达性（较慢，默认True）
    - limit: 限制检查的会话数量（默认50，用于避免超时）
    """
    from app.telegram.monitor import message_monitor

    # 获取所有会话
    result = await db.execute(
        select(Conversation).order_by(Conversation.total_messages.asc()).limit(limit)
    )
    conversations = result.scalars().all()

    diagnostics = []
    accessible_count = 0
    inaccessible_count = 0
    monitoring_count = 0

    # 按账号分组，减少客户端连接次数
    account_groups = {}
    for conv in conversations:
        if conv.account_id not in account_groups:
            account_groups[conv.account_id] = []
        account_groups[conv.account_id].append(conv)

    for account_id, account_conversations in account_groups.items():
        # 获取客户端
        client = await client_manager.get_client(account_id)
        if not client:
            error_msg = f"账号 {account_id} 客户端未连接"
            for conv in account_conversations:
                diagnostic = ConversationDiagnostic(
                    id=conv.id,
                    title=conv.title or "未命名",
                    chat_id=conv.chat_id,
                    chat_type=conv.chat_type,
                    status=conv.status,
                    total_messages=conv.total_messages,
                    last_message_at=conv.last_message_at,
                    accessible=False,
                    error_message=error_msg,
                    has_recent_activity=conv.id in message_monitor.active_monitors,
                )
                diagnostics.append(diagnostic.to_dict())
                inaccessible_count += 1
            continue

        # 检查每个会话
        for conv in account_conversations:
            accessible = None
            error_message = None
            has_recent_activity = conv.id in message_monitor.active_monitors

            if check_accessibility:
                accessible, error_message = await check_conversation_accessibility(
                    conv, client
                )
                if accessible:
                    accessible_count += 1
                else:
                    inaccessible_count += 1

            if has_recent_activity:
                monitoring_count += 1

            # 判断是否有最近的消息（24小时内）
            has_recent_messages = False
            if conv.last_message_at:
                time_diff = (datetime.now() - conv.last_message_at).total_seconds()
                has_recent_messages = time_diff < 86400  # 24小时

            diagnostic = ConversationDiagnostic(
                id=conv.id,
                title=conv.title or "未命名",
                chat_id=conv.chat_id,
                chat_type=conv.chat_type,
                status=conv.status,
                total_messages=conv.total_messages,
                last_message_at=conv.last_message_at,
                accessible=accessible,
                error_message=error_message,
                has_recent_activity=has_recent_activity,
            )
            diagnostics.append(diagnostic.to_dict())

    # 生成统计信息
    total_checked = len(diagnostics)

    # 获取总体统计
    stats_result = await db.execute(
        select(
            func.count(Conversation.id).label("total"),
            func.sum(
                case((Conversation.total_messages == 0, 1), else_=0)
            ).label("no_messages"),
            func.sum(
                case((Conversation.status == "active", 1), else_=0)
            ).label("active"),
        )
    )
    stats = stats_result.one()

    return {
        "summary": {
            "total_conversations": stats.total or 0,
            "conversations_with_no_messages": int(stats.no_messages or 0),
            "active_conversations": int(stats.active or 0),
            "checked": total_checked,
            "accessible": accessible_count if check_accessibility else None,
            "inaccessible": inaccessible_count if check_accessibility else None,
            "being_monitored": monitoring_count,
        },
        "diagnostics": diagnostics,
        "recommendations": generate_recommendations(diagnostics),
    }


@router.post("/conversations/{conversation_id}/fix")
async def fix_conversation(
    conversation_id: int,
    action: str = "restart_monitor",
    db: AsyncSession = Depends(get_db),
):
    """
    尝试修复会话监控问题

    参数:
    - action: 修复操作
      - "restart_monitor": 重启监控
      - "try_fetch": 尝试获取消息
      - "mark_error": 标记为错误状态
    """
    from app.telegram.monitor import message_monitor

    # 获取会话
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在")

    client = await client_manager.get_client(conversation.account_id)
    if not client:
        raise HTTPException(status_code=400, detail="Telegram客户端未连接")

    fix_results = []

    if action == "restart_monitor":
        # 停止并重启监控
        if conversation_id in message_monitor.active_monitors:
            await message_monitor.stop_monitor(conversation_id)
            fix_results.append("已停止旧监控")

        await message_monitor.start_monitor(conversation_id)
        fix_results.append("已重启监控")

        # 检查是否成功启动
        if conversation_id in message_monitor.active_monitors:
            fix_results.append("✓ 监控已成功启动")
        else:
            fix_results.append("✗ 监控启动失败")

    elif action == "try_fetch":
        # 尝试获取最新消息
        try:
            messages = await client.get_messages(conversation.chat_id, limit=5)
            if messages and len(messages) > 0:
                fix_results.append(f"✓ 成功获取 {len(messages)} 条消息")

                # 处理这些消息
                processed = 0
                for msg in messages:
                    if msg.id:
                        try:
                            await message_monitor.process_message(msg, conversation_id)
                            processed += 1
                        except Exception as e:
                            fix_results.append(f"处理消息 {msg.id} 失败: {str(e)}")

                if processed > 0:
                    fix_results.append(f"✓ 成功处理 {processed} 条消息")
            else:
                fix_results.append("✗ 没有获取到消息")
        except Exception as e:
            fix_results.append(f"✗ 获取消息失败: {str(e)}")

    elif action == "mark_error":
        # 标记为错误状态
        conversation.status = "error"
        await db.commit()
        fix_results.append("✓ 已标记为错误状态")

        # 停止监控
        if conversation_id in message_monitor.active_monitors:
            await message_monitor.stop_monitor(conversation_id)
            fix_results.append("✓ 已停止监控")

    else:
        raise HTTPException(status_code=400, detail=f"未知的操作: {action}")

    return {
        "conversation_id": conversation_id,
        "action": action,
        "results": fix_results,
    }


def generate_recommendations(diagnostics: List[Dict[str, Any]]) -> List[str]:
    """根据诊断结果生成建议"""
    recommendations = []

    inaccessible_count = sum(1 for d in diagnostics if not d.get("accessible", True))
    no_messages_count = sum(1 for d in diagnostics if d.get("total_messages", 0) == 0)
    not_monitored_count = sum(1 for d in diagnostics if not d.get("has_recent_activity", False))

    if inaccessible_count > 0:
        recommendations.append(
            f"发现 {inaccessible_count} 个无法访问的频道，可能是私有频道、已删除或无权访问"
        )

    if no_messages_count > 0:
        recommendations.append(
            f"有 {no_messages_count} 个频道没有任何消息，建议检查是否为空频道或需要拉取历史消息"
        )

    if not_monitored_count > 0:
        recommendations.append(
            f"有 {not_monitored_count} 个频道未被监控，建议重启监控系统"
        )

    if not recommendations:
        recommendations.append("所有检查的频道状态正常")

    return recommendations


@router.post("/fix-all")
async def fix_all_issues(
    action: str = "restart_monitor",
    db: AsyncSession = Depends(get_db),
):
    """
    批量修复所有问题会话

    参数:
    - action: 修复操作
      - "restart_monitor": 重启所有监控
      - "mark_inaccessible": 标记无法访问的会话
    """
    from app.telegram.monitor import message_monitor

    # 获取所有活跃状态的会话
    result = await db.execute(
        select(Conversation).where(Conversation.status == "active")
    )
    conversations = result.scalars().all()

    results = {
        "total": len(conversations),
        "success": 0,
        "failed": 0,
        "errors": [],
    }

    if action == "restart_monitor":
        # 重启所有监控
        await message_monitor.stop_all_monitors()
        results["errors"].append("已停止所有监控")

        # 等待一下
        import asyncio

        await asyncio.sleep(2)

        # 重新启动
        await message_monitor.start_all_monitors()
        results["success"] = len(message_monitor.active_monitors)
        results["errors"].append(f"已启动 {results['success']} 个监控")

    return results

@router.get("/internet-status")
async def check_internet_status():
    """检测与 Telegram 服务器的连通性"""
    from app.telegram.client import client_manager
    
    # 有在线客户端说明 TG 连通
    if client_manager.clients:
        return {"online": True, "checked_url": "telegram_client"}
    
    # 检测代理端口是否可达
    socks5_url = getattr(settings, 'SOCKS5_PROXY', None)
    if socks5_url and socks5_url.startswith('socks5://'):
        import re
        import socket
        m = re.match(r'socks5://(?:([^:]+):([^@]+)@)?([^:]+):(\d+)', socks5_url)
        if m:
            host, port = m.group(3), int(m.group(4))
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                def check_in_thread():
                    try:
                        sock = socket.create_connection((host, port), timeout=3)
                        sock.close()
                        return True
                    except:
                        return False
                proxy_ok = await loop.run_in_executor(None, check_in_thread)
                if proxy_ok:
                    return {"online": True, "checked_url": "proxy_reachable"}
            except:
                pass
    
    return {"online": False, "checked_url": None}
