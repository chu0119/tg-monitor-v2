"""监控管理 API"""
import httpx
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
    """获取监控状态（带缓存，5秒）"""
    # 尝试缓存（5秒 TTL，减少对 9010 和 DB 的压力）
    from app.utils.cache import memory_cache
    cached = memory_cache.get("monitoring_status", ttl=5)
    if cached:
        return cached

    # trust_env=False: 不走外部代理，直连本地 monitor_worker
    async with httpx.AsyncClient(timeout=5.0, trust_env=False) as c:
        try:
            monitor_resp = await c.get("http://127.0.0.1:9010/status")
            monitor_data = monitor_resp.json()
        except Exception as e:
            logger.warning(f"查询 monitor_worker 9010/status 失败: {e}")
            monitor_data = {"active_monitors": 0, "connected_clients": 0, "account_ids": []}

    # 从数据库获取账号列表，结合 monitor 数据判断连接状态
    result = await db.execute(select(TelegramAccount))
    accounts = result.scalars().all()

    account_ids = monitor_data.get("account_ids", [])
    connected_clients = monitor_data.get("connected_clients", 0)

    result = {
        "active_monitors": monitor_data.get("active_monitors", 0),
        "connected_clients": connected_clients,
        "accounts": [
            {
                "account_id": a.id,
                "phone": a.phone,
                "connected": a.id in account_ids and connected_clients > 0
            }
            for a in accounts
        ]
    }
    memory_cache.set("monitoring_status", result, ttl=5)
    return result


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
