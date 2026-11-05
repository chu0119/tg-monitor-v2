"""监控管理 API"""
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.api.deps import get_db
from app.services.audit_service import log_audit
from app.models.account import TelegramAccount

router = APIRouter(prefix="/monitoring", tags=["监控管理"])

# monitor_worker 状态/控制服务地址（监控操作必须在持有 session 文件的 monitor 进程执行，
# API 进程只做转发，避免跨进程并发使用同一 Telethon session）
MONITOR_CONTROL_BASE = "http://127.0.0.1:9010"


async def _forward_to_monitor(method: str, path: str):
    """把监控控制指令转发给 monitor_worker"""
    async with httpx.AsyncClient(timeout=30.0, trust_env=False) as c:
        try:
            resp = await c.request(method, f"{MONITOR_CONTROL_BASE}{path}")
            if resp.status_code == 404:
                detail = resp.json().get("detail", "资源不存在")
                raise HTTPException(status_code=404, detail=detail)
            if resp.status_code == 409:
                detail = resp.json().get("detail", "资源不属于当前 Worker")
                raise HTTPException(status_code=409, detail=detail)
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="monitor_worker 控制服务不可用（9010 端口），请检查 tgmonitor-monitor-0 服务状态",
            )


@router.post("/restart")
async def restart_monitoring(db: AsyncSession = Depends(get_db)):
    """重启所有监控任务（转发给 monitor_worker 执行）"""
    try:
        result = await _forward_to_monitor("POST", "/control/restart")
        await log_audit(db, "restart_monitoring", "monitoring", detail={"result": result.get("connected_accounts")})
        return result
    except HTTPException:
        raise
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
    memory_cache.set("monitoring_status", result)
    return result


@router.post("/start/{conversation_id}")
async def start_conversation_monitor(conversation_id: int, db: AsyncSession = Depends(get_db)):
    """启动指定会话的监控（转发给 monitor_worker 执行）"""
    try:
        return await _forward_to_monitor("POST", f"/control/start/{conversation_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动监控失败 (conversation_id={conversation_id}): {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/stop/{conversation_id}")
async def stop_conversation_monitor(conversation_id: int):
    """停止指定会话的监控（转发给 monitor_worker 执行）"""
    try:
        return await _forward_to_monitor("POST", f"/control/stop/{conversation_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"停止监控失败 (conversation_id={conversation_id}): {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
