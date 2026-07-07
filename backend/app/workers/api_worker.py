"""
API Worker入口
处理HTTP请求，不运行Telegram监控
"""
import os
import sys
import asyncio
import signal
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
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>API-{worker_id}</cyan> | <cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
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
    from app.api import health

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """应用生命周期"""
        logger.info(f"API Worker 启动 (ID: {worker_manager.worker_id})")
        yield
        logger.info(f"API Worker 关闭 (ID: {worker_manager.worker_id})")

    app = FastAPI(
        title=f"{settings.PROJECT_NAME} - API Worker {worker_manager.worker_id}",
        version=settings.VERSION,
        lifespan=lifespan
    )

    # CORS配置
    allow_credentials = "*" not in settings.CORS_ORIGINS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["*"],
    )

    # 注册路由
    api_prefix = settings.API_PREFIX
    app.include_router(health.router, prefix=api_prefix)
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
