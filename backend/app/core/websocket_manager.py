"""
WebSocket 连接管理器

从 app.main 提取，供 api_worker 与 main 共用。
提供连接管理、广播、ping/pong 处理。
"""
import asyncio
import time

from fastapi import WebSocket, Query
from loguru import logger


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
        self.active_connections[websocket] = (time.monotonic(), conn_id)
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
        now = time.monotonic()

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
            except Exception:
                pass
            self.disconnect(conn)

    async def send_personal(self, message: dict, websocket: WebSocket):
        """发送个人消息"""
        try:
            await asyncio.wait_for(websocket.send_json(message), timeout=5.0)
            # 更新活跃时间
            if websocket in self.active_connections:
                now = time.monotonic()
                _, conn_id = self.active_connections[websocket]
                self.active_connections[websocket] = (now, conn_id)
        except asyncio.TimeoutError:
            logger.warning("发送个人消息超时，可能已断开")
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
        now = time.monotonic()
        stale_connections = [
            ws for ws, (last_active, _) in self.active_connections.items()
            if now - last_active > self.CONNECTION_TIMEOUT
        ]

        if stale_connections:
            logger.info(f"发现 {len(stale_connections)} 个僵尸连接，开始清理...")
            for ws in stale_connections:
                try:
                    await ws.close()
                except Exception:
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


# 共享单例
manager = ConnectionManager()


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


async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(default="", description="认证令牌")
):
    """WebSocket 端点 - 处理连接、ping/pong、订阅"""
    from app.core.config import settings

    # 只有在配置了WS_TOKEN时才验证
    if hasattr(settings, 'WS_TOKEN') and settings.WS_TOKEN:
        if token != settings.WS_TOKEN:
            await websocket.close(code=1008, reason="Invalid token")
            logger.warning("WebSocket 连接被拒绝: 无效的令牌")
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

    except Exception as e:
        # 包含 WebSocketDisconnect 与其他异常
        if e.__class__.__name__ != "WebSocketDisconnect":
            logger.error(f"WebSocket 错误: {e}")
        manager.disconnect(websocket)
