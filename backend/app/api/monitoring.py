"""监控管理 API"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.api.deps import get_db
from app.telegram.monitor import message_monitor
from app.telegram.client import client_manager
from app.models.conversation import Conversation
from app.models.account import TelegramAccount

router = APIRouter(prefix="/monitoring", tags=["监控管理"])


@router.post("/restart")
async def restart_monitoring(db: AsyncSession = Depends(get_db)):
    """重启所有监控任务"""
    try:
        # 停止现有监控
        await message_monitor.stop_all_monitors()
        logger.info("已停止所有监控任务")

        # 重新连接所有账号
        result = await db.execute(select(TelegramAccount).where(TelegramAccount.is_active == True))
        accounts = result.scalars().all()

        connected_count = 0
        for account in accounts:
            try:
                client = await client_manager.get_client(account.id)
                if client and client.is_connected():
                    connected_count += 1
            except Exception as e:
                logger.warning(f"连接账号 {account.id} 失败: {e}")

        # 启动所有监控
        await message_monitor.start_all_monitors()
        await message_monitor.start_heartbeat()

        return {
            "message": "监控已重启",
            "connected_accounts": connected_count,
            "active_monitors": len(message_monitor.active_monitors)
        }
    except Exception as e:
        logger.error(f"重启监控失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/status")
async def get_monitoring_status(db: AsyncSession = Depends(get_db)):
    """获取监控状态"""
    # 获取活跃监控数量
    active_count = len(message_monitor.active_monitors)

    # 获取连接的客户端数量
    connected_clients = len(client_manager.clients)

    # 检查账号状态
    result = await db.execute(
        select(TelegramAccount).where(TelegramAccount.is_active == True)
    )
    active_accounts = result.scalars().all()

    accounts_status = []
    for account in active_accounts:
        client = client_manager.clients.get(account.id)
        accounts_status.append({
            "account_id": account.id,
            "phone": account.phone,
            "connected": client is not None and client.is_connected() if client else False
        })

    return {
        "active_monitors": active_count,
        "connected_clients": connected_clients,
        "accounts": accounts_status
    }


@router.post("/start/{conversation_id}")
async def start_conversation_monitor(conversation_id: int, db: AsyncSession = Depends(get_db)):
    """启动指定会话的监控"""
    try:
        await message_monitor.start_monitor(conversation_id)
        return {"message": f"会话 {conversation_id} 监控已启动"}
    except Exception as e:
        logger.error(f"启动监控失败 (conversation_id={conversation_id}): {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/stop/{conversation_id}")
async def stop_conversation_monitor(conversation_id: int):
    """停止指定会话的监控"""
    try:
        await message_monitor.stop_monitor(conversation_id)
        return {"message": f"会话 {conversation_id} 监控已停止"}
    except Exception as e:
        logger.error(f"停止监控失败 (conversation_id={conversation_id}): {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
