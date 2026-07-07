"""
系统健康检查 API
提供全面的系统状态监控和性能指标
"""
import time
import psutil
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.api.deps import get_db
from app.utils.redis_cache import redis_cache

router = APIRouter(prefix="/health", tags=["健康检查"])

_start_time = time.time()


@router.get("")
async def health_check(db: AsyncSession = Depends(get_db)):
    """基础健康检查 - 负载均衡器探活"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@router.get("/detailed")
async def detailed_health_check(db: AsyncSession = Depends(get_db)):
    """详细健康检查 - 包含所有组件状态"""
    checks = {}
    overall_status = "healthy"

    # 1. 数据库检查
    try:
        start = time.time()
        async with db.begin():
            await db.execute(text("SELECT 1"))
        db_latency = round((time.time() - start) * 1000, 2)
        checks["database"] = {"status": "healthy", "latency_ms": db_latency}
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}
        overall_status = "unhealthy"

    # 2. Redis检查
    try:
        start = time.time()
        redis_cache.client.ping()
        redis_latency = round((time.time() - start) * 1000, 2)
        redis_info = redis_cache.client.info("memory")
        checks["redis"] = {
            "status": "healthy",
            "latency_ms": redis_latency,
            "memory_used": redis_info.get("used_memory_human", "unknown"),
            "memory_max": redis_info.get("maxmemory_human", "unknown"),
            "keys": redis_cache.client.dbsize()
        }
    except Exception as e:
        checks["redis"] = {"status": "unhealthy", "error": str(e)}
        overall_status = "degraded"

    # 3. 系统资源检查
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        checks["system"] = {
            "status": "healthy" if cpu_percent < 90 and memory.percent < 90 else "warning",
            "cpu_percent": cpu_percent,
            "memory": {
                "total_gb": round(memory.total / (1024**3), 1),
                "used_gb": round(memory.used / (1024**3), 1),
                "percent": memory.percent
            },
            "disk": {
                "total_gb": round(disk.total / (1024**3), 1),
                "used_gb": round(disk.used / (1024**3), 1),
                "percent": disk.percent
            }
        }
        if checks["system"]["status"] == "warning":
            overall_status = "degraded"
    except Exception as e:
        checks["system"] = {"status": "unknown", "error": str(e)}

    # 4. Telegram监控检查
    try:
        from app.telegram.monitor import message_monitor
        from app.telegram.client import client_manager
        checks["telegram"] = {
            "status": "healthy",
            "active_monitors": len(message_monitor.active_monitors),
            "connected_clients": len(client_manager.clients)
        }
    except Exception as e:
        checks["telegram"] = {"status": "unknown", "error": str(e)}

    return {
        "status": overall_status,
        "uptime_seconds": round(time.time() - _start_time),
        "timestamp": datetime.now().isoformat(),
        "checks": checks
    }


@router.get("/metrics")
async def get_metrics(db: AsyncSession = Depends(get_db)):
    """获取系统性能指标"""
    try:
        result = await db.execute(text(
            "SELECT (SELECT COUNT(*) FROM alerts), "
            "(SELECT COUNT(*) FROM alerts WHERE status = 'pending'), "
            "(SELECT COUNT(*) FROM messages), "
            "(SELECT COUNT(*) FROM conversations WHERE status = 'active'), "
            "(SELECT COUNT(*) FROM telegram_accounts WHERE is_active = 1)"
        ))
        row = result.fetchone()
        db_stats = {
            "total_alerts": row[0], "pending_alerts": row[1],
            "total_messages": row[2], "active_conversations": row[3],
            "active_accounts": row[4]
        }
    except Exception as e:
        db_stats = {"error": str(e)}

    try:
        info = redis_cache.client.info("stats")
        redis_stats = {
            "keys": redis_cache.client.dbsize(),
            "memory_used": redis_cache.client.info("memory").get("used_memory_human"),
            "hits": info.get("keyspace_hits", 0),
            "misses": info.get("keyspace_misses", 0)
        }
    except Exception as e:
        redis_stats = {"error": str(e)}

    try:
        system_metrics = {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent
        }
    except Exception as e:
        system_metrics = {"error": str(e)}

    return {
        "database": db_stats, "redis": redis_stats,
        "system": system_metrics,
        "uptime_seconds": round(time.time() - _start_time)
    }
