"""
Detailed health endpoint for api_worker.

Telegram stats are fetched live from monitor_worker's status server (port 9010),
since api_worker does not run Telegram monitoring itself.
"""
import os
import time
from datetime import datetime, timezone

import httpx
import psutil
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.api.deps import get_db
from app.core.database import check_database_connection

router = APIRouter()


@router.get("/health/detailed")
async def detailed_health(db: AsyncSession = Depends(get_db)):
    """详细健康检查 - 返回前端 DashboardPage.tsx HealthStatus 接口期望的结构"""
    return await _build_health(db)


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    """健康检查 - 前端 DashboardPage.tsx 通过 fetch("/health") 调用，返回详细结构"""
    return await _build_health(db)


async def _build_health(db: AsyncSession) -> dict:
    """构建健康检查响应"""
    t0 = time.time()
    db_info = await check_database_connection()
    db_latency_ms = round((time.time() - t0) * 1000, 2)

    # 2. Telegram 状态：从 monitor_worker 9010 /status 拉取
    tg_clients_count = 0
    active_monitors = 0
    try:
        # trust_env=False: 不走外部代理，直连本地 monitor_worker
        async with httpx.AsyncClient(timeout=5.0, trust_env=False) as c:
            resp = await c.get("http://127.0.0.1:9010/status")
            monitor_data = resp.json()
            active_monitors = monitor_data.get("active_monitors", 0)
            tg_clients_count = monitor_data.get("connected_clients", 0)
    except Exception as e:
        logger.warning(f"查询 monitor_worker 9010/status 失败: {e}")

    # api_worker 自身不运行消息队列，队列指标为 0
    message_queue = {"queue_size": 0, "dropped": 0}

    # 3. 告警链路健康
    from app.services.alert_service import alert_service
    try:
        alert_pipeline = await alert_service.get_pipeline_health(db)
    except Exception as e:
        alert_pipeline = {"status": "unknown", "error": str(e)}

    # 4. WebSocket 连接数
    ws_connections = 0
    try:
        from app.core.websocket_manager import manager
        ws_connections = manager.get_connection_count()
    except Exception:
        pass

    # 5. 系统资源
    try:
        process = psutil.Process(os.getpid())
        cpu_percent = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        resource_info = {
            "cpu_percent": round(cpu_percent, 1),
            "memory_total_gb": round(mem.total / (1024 ** 3), 1),
            "memory_used_gb": round(mem.used / (1024 ** 3), 1),
            "memory_percent": round(mem.percent, 1),
            "disk_free_gb": round(disk.free / (1024 ** 3), 1),
            "disk_percent": round(disk.percent, 1),
            "process_memory_mb": round(process.memory_info().rss / (1024 ** 2), 0),
        }
    except Exception as e:
        resource_info = {"error": str(e)}

    is_ok = bool(db_info.get("connected", False))

    return {
        "status": "ok" if is_ok else "error",
        "database": {
            "connected": bool(db_info.get("connected", False)),
            "latency_ms": db_latency_ms,
        },
        "resources": resource_info,
        "telegram": {
            "clients_count": tg_clients_count,
            "active_monitors": active_monitors,
            "message_queue": message_queue,
        },
        "websocket": {"connections": ws_connections},
        "alert_pipeline": alert_pipeline,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
