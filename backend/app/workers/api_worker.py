"""
API Worker入口
处理HTTP请求，不运行Telegram监控
"""
import os
import sys
from contextlib import asynccontextmanager

import uvicorn
from loguru import logger

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.core.config import settings
from app.core.worker_config import worker_manager


def setup_logging(worker_id: int):
    """配置日志"""
    log_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, f'api_worker_{worker_id}.log')

    logger.remove()
    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | API Worker | {function}:{line} - {message}"
    )
    logger.add(
        log_file,
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        encoding="utf-8",
        level=settings.LOG_LEVEL,
        enqueue=True,
        backtrace=True,
        diagnose=True
    )


def create_app():
    """创建FastAPI应用"""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from app.api import accounts, conversations, messages, keywords, alerts, notifications, dashboard, analysis, settings as settings_api, database, backups, diagnostics, monitoring, senders
    from app.api import phone_records, personnel, cases, watchlist, audit
    from app.api import proxy, system, update, migration
    from app.api import health, health_detailed
    from app.api.keywords import list_keyword_groups_internal
    from app.api.deps import get_db
    from fastapi import Depends
    from app.core.error_handler import (
        AppException, app_exception_handler, general_exception_handler,
    )
    from app.api.auth import APIKeyAuthMiddleware

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """应用生命周期"""
        logger.info(f"API Worker 启动 (ID: {worker_manager.worker_id})")

        # 初始化数据库
        from app.core.database import init_db
        await init_db()
        logger.info("数据库初始化完成")

        # 加载代理配置
        from app.services.runtime_proxy_service import get_proxy_config, apply_proxy_config
        from app.core.database import AsyncSessionLocal
        try:
            async with AsyncSessionLocal() as db:
                proxy_cfg = await get_proxy_config(db)
            apply_proxy_config(proxy_cfg)
        except Exception as e:
            logger.warning(f"加载代理配置失败: {e}")

        # 启动 Redis pub/sub 订阅，将 monitor_worker 的事件转发到 WebSocket
        import asyncio
        from app.core.websocket_manager import broadcast_new_message, broadcast_new_alert, manager
        from app.core.pubsub import subscribe

        _relay_task: asyncio.Task | None = None

        async def _relay():
            async def _handler(data):
                # 按 publish 时注入的 type 字段分发到对应的广播函数
                event_type = data.pop("type", "new_message")
                if event_type == "new_alert":
                    await broadcast_new_alert(data)
                elif event_type == "stats_update":
                    await manager.broadcast_stats(data)
                else:
                    # new_message 及未知类型统一走消息广播，保持向后兼容
                    await broadcast_new_message(data)
            await subscribe(_handler)

        _relay_task = asyncio.create_task(_relay())
        logger.info("Redis pub/sub 订阅任务已启动")

        # 启动 WebSocket 连接清理任务
        await manager.start_cleanup_task()

        # ===== 以下后台任务原本只在 main.py 中启动，多进程架构迁移时遗漏，此处恢复 =====
        _background_tasks: list[asyncio.Task] = []

        # 1. 登录会话清理（每5分钟，清理过期的登录验证会话）
        from app.telegram.client import client_manager

        async def cleanup_login_sessions():
            while True:
                try:
                    await asyncio.sleep(300)  # 每5分钟
                    await client_manager.cleanup_expired_login_sessions()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"登录会话清理异常: {e}")

        _background_tasks.append(asyncio.create_task(cleanup_login_sessions()))
        logger.info("登录会话清理任务已启动")

        # 2. 数据自动清理（按 settings 中 data_retention_days 保留策略）
        from app.services.data_cleanup_service import data_cleanup_service

        async def run_cleanup_task():
            try:
                await data_cleanup_service.start_auto_cleanup()
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"自动清理任务异常: {e}")

        _background_tasks.append(asyncio.create_task(run_cleanup_task()))
        logger.info("自动清理任务已启动（后台运行）")

        # 3. 自动备份任务
        from app.services.auto_backup_service import auto_backup_service

        async def run_backup_task():
            try:
                await auto_backup_service.start_auto_backup()
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"自动备份任务异常: {e}")

        _background_tasks.append(asyncio.create_task(run_backup_task()))
        logger.info("自动备份任务已启动（后台运行）")

        # 4. 告警自动升级任务（每30分钟检查一次）
        from app.services.alert_aggregation_service import alert_aggregation_service

        async def run_escalation_task():
            while True:
                try:
                    await asyncio.sleep(1800)  # 每30分钟
                    async with AsyncSessionLocal() as db:
                        result = await alert_aggregation_service.escalate_stale_alerts(db)
                        if result.get("escalated_count", 0) > 0:
                            logger.info(f"告警自动升级完成: {result['message']}")
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"告警自动升级任务异常: {e}")

        _background_tasks.append(asyncio.create_task(run_escalation_task()))
        logger.info("告警自动升级任务已启动（每30分钟）")

        yield
        logger.info(f"API Worker 关闭 (ID: {worker_manager.worker_id})")

        # 取消本 Worker 的后台任务
        for task in _background_tasks:
            if not task.done():
                task.cancel()

        # 停止 WebSocket 清理任务
        await manager.stop_cleanup_task()

        # 清理订阅任务
        if _relay_task is not None:
            _relay_task.cancel()

    app = FastAPI(
        title=f"{settings.PROJECT_NAME} - API Worker {worker_manager.worker_id}",
        version=settings.VERSION,
        lifespan=lifespan
    )

    # 注册异常处理器
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    # CORS配置
    allow_credentials = "*" not in settings.CORS_ORIGINS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["*"],
    )

    # API Key认证中间件
    app.add_middleware(APIKeyAuthMiddleware)

    # 注册路由
    api_prefix = settings.API_PREFIX
    app.include_router(health.router, prefix=api_prefix)
    app.include_router(health_detailed.router)
    app.include_router(accounts.router, prefix=api_prefix)
    app.include_router(conversations.router, prefix=api_prefix)
    app.include_router(messages.router, prefix=api_prefix)
    app.include_router(keywords.router, prefix=api_prefix)
    app.include_router(alerts.router, prefix=api_prefix)
    app.include_router(notifications.router, prefix=api_prefix)
    app.include_router(dashboard.router, prefix=api_prefix)
    app.include_router(analysis.router, prefix=api_prefix)
    app.include_router(settings_api.router, prefix=api_prefix)
    app.include_router(database.router, prefix=api_prefix)
    app.include_router(backups.router, prefix=api_prefix)
    app.include_router(diagnostics.router, prefix=api_prefix)
    app.include_router(monitoring.router, prefix=api_prefix)
    app.include_router(senders.router, prefix=api_prefix)
    app.include_router(proxy.router, prefix=api_prefix)
    app.include_router(system.router, prefix=api_prefix)
    app.include_router(update.router, prefix=api_prefix)
    app.include_router(migration.router, prefix=api_prefix)
    app.include_router(phone_records.router, prefix=api_prefix)
    app.include_router(personnel.router, prefix=api_prefix)
    app.include_router(cases.router, prefix=api_prefix)
    app.include_router(watchlist.router, prefix=api_prefix)
    app.include_router(audit.router, prefix=api_prefix)

    # WebSocket 端点 (无 prefix，路径为 /ws)
    from app.core.websocket_manager import websocket_endpoint
    app.add_websocket_route("/ws", websocket_endpoint)

    # 兼容旧路由
    @app.get(f"{api_prefix}/keyword-groups")
    async def keyword_groups_alias(db=Depends(get_db)):
        return await list_keyword_groups_internal(db)

    @app.get("/")
    async def root():
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "worker_id": worker_manager.worker_id,
            "worker_type": "api",
            "status": "running"
        }

    return app


def main():
    """主函数"""
    config = worker_manager.get_worker_config()

    setup_logging(config.worker_id)
    logger.info(f"启动 API Worker {config.worker_id}，端口: {config.port}")

    app = create_app()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=config.port,
        log_level="info",
        access_log=True
    )


if __name__ == "__main__":
    main()
