"""FastAPI 主应用"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
import sys
import asyncio
import os

from app.core.config import settings as config_settings
from app.core.database import init_db
from app.api import accounts, conversations, messages, keywords, alerts, notifications, dashboard, analysis, settings as settings_api, database, backups, diagnostics, monitoring
from app.api import proxy, system
from app.api.deps import get_db


# 配置日志
logger.remove()
logger.add(
    sys.stdout,
    level=config_settings.LOG_LEVEL,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)
logger.add(
    config_settings.LOG_FILE,
    rotation="10 MB",      # 单文件最大10MB后轮转
    retention="7 days",    # 保留7天
    compression="zip",     # 压缩旧日志
    encoding="utf-8",
    level=config_settings.LOG_LEVEL,
    enqueue=True,          # 异步写入，提高性能
    backtrace=True,        # 记录完整堆栈
    diagnose=True,         # 诊断信息
    filter=lambda record: record["level"].name != "DEBUG"  # 不记录DEBUG日志，减少日志量
)


# WebSocket 连接管理器
class ConnectionManager:
    """WebSocket 连接管理器 - 优化版，支持连接清理和超时检测"""

    CONNECTION_TIMEOUT = 300  # 5分钟无活动则断开
    CLEANUP_INTERVAL = 60     # 每60秒清理一次僵尸连接

    def __init__(self):
        # 改用字典存储：WebSocket -> (最后活跃时间, 连接ID)
        self.active_connections: dict[WebSocket, tuple[float, str]] = {}
        self._cleanup_task: asyncio.Task | None = None

    async def connect(self, websocket: WebSocket) -> str:
        """接受连接，返回连接ID"""
        await websocket.accept()
        conn_id = f"{id(websocket)}_{asyncio.get_event_loop().time()}"
        self.active_connections[websocket] = (asyncio.get_event_loop().time(), conn_id)
        logger.info(f"WebSocket 连接建立 (ID: {conn_id})，当前连接数: {len(self.active_connections)}")
        return conn_id

    def disconnect(self, websocket: WebSocket):
        """断开连接"""
        if websocket in self.active_connections:
            _, conn_id = self.active_connections[websocket]
            del self.active_connections[websocket]
            logger.info(f"WebSocket 连接断开 (ID: {conn_id})，当前连接数: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """广播消息，自动清理断开的连接"""
        disconnected = []
        now = asyncio.get_event_loop().time()

        for connection, (last_active, conn_id) in list(self.active_connections.items()):
            # 检查连接超时
            if now - last_active > self.CONNECTION_TIMEOUT:
                logger.warning(f"WebSocket 连接超时 (ID: {conn_id})，将断开")
                disconnected.append(connection)
                continue

            try:
                await asyncio.wait_for(connection.send_json(message), timeout=5.0)
                # 更新活跃时间
                self.active_connections[connection] = (now, conn_id)
            except asyncio.TimeoutError:
                logger.warning(f"WebSocket 发送超时 (ID: {conn_id})")
                disconnected.append(connection)
            except Exception as e:
                logger.error(f"广播消息失败 (ID: {conn_id}): {e}")
                disconnected.append(connection)

        # 清理断开的连接
        for conn in disconnected:
            try:
                await conn.close()
            except:
                pass
            self.disconnect(conn)

    async def send_personal(self, message: dict, websocket: WebSocket):
        """发送个人消息"""
        try:
            await asyncio.wait_for(websocket.send_json(message), timeout=5.0)
            # 更新活跃时间
            if websocket in self.active_connections:
                now = asyncio.get_event_loop().time()
                _, conn_id = self.active_connections[websocket]
                self.active_connections[websocket] = (now, conn_id)
        except asyncio.TimeoutError:
            logger.warning(f"发送个人消息超时，可能已断开")
            self.disconnect(websocket)
        except Exception as e:
            logger.error(f"发送个人消息失败: {e}")
            self.disconnect(websocket)

    def get_connection_count(self) -> int:
        """获取当前连接数"""
        return len(self.active_connections)

    async def start_cleanup_task(self):
        """启动定期清理僵尸连接的后台任务"""
        if self._cleanup_task is not None:
            return

        async def _cleanup_loop():
            while True:
                await asyncio.sleep(self.CLEANUP_INTERVAL)
                await self.cleanup_stale_connections()

        self._cleanup_task = asyncio.create_task(_cleanup_loop())
        logger.info("WebSocket 连接清理任务已启动")

    async def cleanup_stale_connections(self):
        """清理僵尸连接（超时未活跃的连接）"""
        now = asyncio.get_event_loop().time()
        stale_connections = [
            ws for ws, (last_active, _) in self.active_connections.items()
            if now - last_active > self.CONNECTION_TIMEOUT
        ]

        if stale_connections:
            logger.info(f"发现 {len(stale_connections)} 个僵尸连接，开始清理...")
            for ws in stale_connections:
                try:
                    await ws.close()
                except:
                    pass
                self.disconnect(ws)

    async def stop_cleanup_task(self):
        """停止清理任务"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("WebSocket 连接清理任务已停止")


manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理 - 优化版"""
    # 用于追踪所有后台任务
    background_tasks = set()

    # 启动时执行
    logger.info("启动 Telegram 监控告警系统...")

    # 创建必要的目录
    config_settings.UPLOAD_DIR.mkdir(exist_ok=True)
    config_settings.SESSION_DIR.mkdir(exist_ok=True)

    # 创建代理目录
    from pathlib import Path
    proxy_dir = Path("proxy")
    proxy_dir.mkdir(exist_ok=True)

    # 初始化数据库
    await init_db()
    logger.info("数据库初始化完成")

    # 检查是否已初始化
    from app.models.settings import Settings
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import select

    is_initialized = False
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Settings).where(Settings.key_name == "initialized")
            )
            setting = result.scalar_one_or_none()
            is_initialized = setting and setting.value == "true"
    except Exception as e:
        logger.warning(f"检查初始化状态失败: {e}")

    if not is_initialized:
        logger.info("系统未初始化，仅启动API服务，不启动监控")
        # 只启动API，不启动监控功能
        yield
        logger.info("关闭系统...")
        return

    logger.info("系统已初始化，启动完整功能...")

    # 启动 WebSocket 连接清理任务
    await manager.start_cleanup_task()

    # 启动登录会话清理任务
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

    login_cleanup_task = asyncio.create_task(cleanup_login_sessions())
    background_tasks.add(login_cleanup_task)
    logger.info("登录会话清理任务已启动")

    # 预先连接所有已授权的 Telegram 账号（并行连接）
    from app.models import TelegramAccount

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TelegramAccount).where(
                TelegramAccount.is_authorized == True,
                TelegramAccount.is_active == True
            )
        )
        accounts = result.scalars().all()
    logger.info(f"找到 {len(accounts)} 个已授权活跃账号待连接")

    # 启动前先确保mihomo代理可用（如果有配置）
    try:
        from app.proxy.manager import ProxyManager
        proxy_mgr = ProxyManager()
        proxy_status = await proxy_mgr.get_status()
        if proxy_status.get("config_exists") and not proxy_status.get("running"):
            logger.info("检测到代理配置存在但未运行，自动启动mihomo...")
            result = await proxy_mgr.start()
            if result.get("success"):
                logger.info("mihomo自动启动成功")
            else:
                logger.warning(f"mihomo自动启动失败: {result}")
    except Exception as e:
        logger.warning(f"自动启动mihomo失败（非致命）: {e}")

    # 并行连接账号，提高启动速度（每个账号最多等15秒）
    async def connect_account(account):
        try:
            client = await client_manager.get_client(account.id)
            if client:
                logger.info(f"Telegram 账号已连接: {account.phone}")
            else:
                logger.warning(f"Telegram 账号连接失败: {account.phone}")
        except asyncio.TimeoutError:
            logger.warning(f"Telegram 账号连接超时，跳过: {account.phone}")
        except Exception as e:
            logger.error(f"连接 Telegram 账号 {account.phone} 失败: {e}")

    if accounts:
        connect_tasks = [asyncio.create_task(connect_account(acc)) for acc in accounts]
        await asyncio.gather(*connect_tasks, return_exceptions=True)

    # 启动消息监控
    from app.telegram.monitor import message_monitor
    await message_monitor.start_all_monitors()
    await message_monitor.start_heartbeat()  # 启动心跳检测
    logger.info("消息监控已启动")

    # 启动自动清理任务（后台运行）
    from app.services.data_cleanup_service import data_cleanup_service

    async def run_cleanup_task():
        """后台运行自动清理任务"""
        try:
            await data_cleanup_service.start_auto_cleanup()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"自动清理任务异常: {e}")

    cleanup_task = asyncio.create_task(run_cleanup_task())
    background_tasks.add(cleanup_task)
    logger.info("自动清理任务已启动（后台运行）")

    # 启动自动备份任务（后台运行）
    from app.services.auto_backup_service import auto_backup_service

    async def run_backup_task():
        """后台运行自动备份任务"""
        try:
            await auto_backup_service.start_auto_backup()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"自动备份任务异常: {e}")

    backup_task = asyncio.create_task(run_backup_task())
    background_tasks.add(backup_task)
    logger.info("自动备份任务已启动（后台运行）")

    yield

    # 关闭时执行
    logger.info("关闭 Telegram 监控告警系统...")

    # 取消所有后台任务
    for task in list(background_tasks):
        if not task.done():
            task.cancel()

    # 等待所有任务完成（带超时）
    if background_tasks:
        try:
            await asyncio.wait_for(
                asyncio.gather(*background_tasks, return_exceptions=True),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            logger.warning("部分后台任务关闭超时")

    # 停止心跳监控
    await message_monitor.stop_heartbeat()
    await message_monitor.stop_all_monitors()

    # 停止 WebSocket 清理任务
    await manager.stop_cleanup_task()

    # 停止服务
    data_cleanup_service.stop_auto_cleanup()
    await auto_backup_service.stop_auto_backup()

    # 关闭通知服务（清理 aiohttp 会话）
    from app.services.notification_service import notification_service
    try:
        await notification_service.close()
    except Exception:
        pass
    logger.info("通知服务已关闭")

    # 断开所有 Telegram 客户端
    await client_manager.disconnect_all()

    logger.info("系统已关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title=config_settings.PROJECT_NAME,
    version=config_settings.VERSION,
    lifespan=lifespan
)

# 配置 CORS
# 注意：当 allow_origins 包含 "*" 时，不能设置 allow_credentials=True
allow_credentials = "*" not in config_settings.CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config_settings.CORS_ORIGINS,
    allow_credentials=allow_credentials,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)

# 注册路由
api_prefix = config_settings.API_PREFIX
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
app.include_router(proxy.router, prefix=api_prefix)
app.include_router(system.router, prefix=api_prefix)


# ==================== 兼容旧 API 路径 ====================
# 为 /api/v1/keyword-groups 提供兼容路由（前端可能使用此路径）
from app.api.keywords import list_keyword_groups_internal

@app.get(f"{api_prefix}/keyword-groups")
async def keyword_groups_alias(db: AsyncSession = Depends(get_db)):
    """获取关键词组列表（兼容旧路径 /api/v1/keyword-groups）"""
    return await list_keyword_groups_internal(db)


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": config_settings.PROJECT_NAME,
        "version": config_settings.VERSION,
        "status": "running"
    }


@app.get("/health")
async def health():
    """健康检查 - 详细版本，包含系统状态"""
    from app.telegram.client import client_manager
    from app.telegram.monitor import message_monitor
    from app.core.database import check_database_connection
    import psutil
    import os

    # 检查数据库连接
    db_info = await check_database_connection()

    # 检查 Telegram 客户端
    tg_clients = len(client_manager.clients)
    tg_client_status = []
    for account_id, client in client_manager.clients.items():
        try:
            is_connected = client.is_connected()
            tg_client_status.append({
                "account_id": account_id,
                "connected": is_connected
            })
        except Exception as e:
            tg_client_status.append({
                "account_id": account_id,
                "error": str(e)
            })

    # 检查活跃监控
    active_monitors = len(message_monitor.active_monitors)

    # 检查 WebSocket 连接
    ws_connections = manager.get_connection_count()

    # 获取系统资源使用情况（系统级别，非进程级别）
    try:
        process = psutil.Process(os.getpid())
        connections = len(process.connections())
        threads = process.num_threads()

        # 系统级 CPU
        cpu_percent = psutil.cpu_percent(interval=0.5)

        # 系统级内存
        mem = psutil.virtual_memory()

        # 系统级磁盘（根分区）
        disk = psutil.disk_usage('/')

        resource_info = {
            # CPU
            "cpu_percent": round(cpu_percent, 1),
            # 内存
            "memory_total_gb": round(mem.total / 1024 / 1024 / 1024, 1),
            "memory_used_gb": round(mem.used / 1024 / 1024 / 1024, 1),
            "memory_available_gb": round(mem.available / 1024 / 1024 / 1024, 1),
            "memory_percent": round(mem.percent, 1),
            "memory_mb": round(mem.used / 1024 / 1024, 0),
            # 磁盘
            "disk_total_gb": round(disk.total / 1024 / 1024 / 1024, 1),
            "disk_used_gb": round(disk.used / 1024 / 1024 / 1024, 1),
            "disk_free_gb": round(disk.free / 1024 / 1024 / 1024, 1),
            "disk_percent": round(disk.percent, 1),
            # 进程级信息
            "connections": connections,
            "threads": threads,
            "fds": process.num_fds() if hasattr(process, 'num_fds') else None,
            # 进程自身内存
            "process_memory_mb": round(process.memory_info().rss / 1024 / 1024, 0),
        }
    except Exception as e:
        resource_info = {"error": str(e)}

    # 判断整体健康状态
    is_healthy = (
        db_info.get("connected", False) and
        resource_info.get("memory_percent", 100) < 90 and
        resource_info.get("cpu_percent", 100) < 95
    )

    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "database": db_info,
        "telegram": {
            "clients_count": tg_clients,
            "clients_status": tg_client_status,
            "active_monitors": active_monitors
        },
        "websocket": {
            "connections": ws_connections
        },
        "resources": resource_info,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(default="", description="认证令牌")
):
    """WebSocket 端点 - 可选令牌认证"""
    # 验证令牌（如果配置了的话）
    from app.core.config import settings

    # 只有在配置了WS_TOKEN时才验证
    if hasattr(settings, 'WS_TOKEN') and settings.WS_TOKEN and token:
        if token != settings.WS_TOKEN:
            await websocket.close(code=1008, reason="Invalid token")
            logger.warning(f"WebSocket 连接被拒绝: 无效的令牌")
            return

    await manager.connect(websocket)
    logger.info(f"WebSocket 连接建立，当前连接数: {len(manager.active_connections)}")

    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_json()

            # 处理不同类型的消息
            if data.get("type") == "ping":
                await manager.send_personal({"type": "pong"}, websocket)

            elif data.get("type") == "subscribe":
                # 订阅特定频道
                await manager.send_personal({
                    "type": "subscribed",
                    "channel": data.get("channel")
                }, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket 错误: {e}")
        manager.disconnect(websocket)


# 广播新消息的辅助函数（可在其他地方调用）
async def broadcast_new_message(message_data: dict):
    """广播新消息"""
    await manager.broadcast({
        "type": "new_message",
        "data": message_data
    })


async def broadcast_new_alert(alert_data: dict):
    """广播新告警"""
    await manager.broadcast({
        "type": "new_alert",
        "data": alert_data
    })


async def broadcast_stats_update(stats_data: dict):
    """广播统计更新"""
    await manager.broadcast({
        "type": "stats_update",
        "data": stats_data
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=config_settings.HOST,
        port=config_settings.PORT,
        reload=config_settings.DEBUG
    )
