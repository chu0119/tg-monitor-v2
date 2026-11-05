# backend/app/core/pubsub.py
import asyncio
import json

import redis.asyncio as aioredis
from loguru import logger

CHANNEL = "tg_monitor_events"

# 模块级共享连接：每条消息新建 TCP 连接的开销在高消息量下不可接受
_redis_client: aioredis.Redis = None
_client_lock = asyncio.Lock()


async def _get_redis() -> aioredis.Redis:
    """获取共享的 Redis 客户端（带超时与自动重连参数）"""
    global _redis_client
    if _redis_client is None:
        async with _client_lock:
            if _redis_client is None:
                _redis_client = aioredis.Redis(
                    socket_connect_timeout=3,
                    socket_timeout=5,
                    health_check_interval=30,
                    retry_on_timeout=True,
                )
    return _redis_client


async def publish(event_type: str, data: dict):
    """发布事件到 Redis 频道（共享连接，不抛异常——广播失败不能阻断消息处理）"""
    try:
        r = await _get_redis()
        await r.publish(CHANNEL, json.dumps({"type": event_type, **data}))
    except Exception as e:
        logger.error(f"Redis publish 失败: {e}")


async def subscribe(handler):
    """订阅 Redis 频道，收到消息后调用 handler

    断线自动重连（指数退避）：Redis 瞬断后推送链路可自愈，
    否则 api_worker 的 WebSocket 实时推送会永久失效直到重启进程。
    """
    delay = 1.0
    while True:
        r = None
        try:
            r = aioredis.Redis(
                socket_connect_timeout=3,
                socket_timeout=None,  # listen() 需要长阻塞读取
                health_check_interval=30,
            )
            async with r.pubsub() as ps:
                await ps.subscribe(CHANNEL)
                logger.info(f"已订阅 Redis 频道: {CHANNEL}")
                delay = 1.0  # 连接成功后重置退避
                async for msg in ps.listen():
                    if msg["type"] == "message":
                        try:
                            await handler(json.loads(msg["data"]))
                        except Exception as e:
                            logger.error(f"处理 Redis 消息失败: {e}")
        except asyncio.CancelledError:
            logger.info("Redis 订阅任务被取消")
            if r is not None:
                await r.close()
            raise
        except Exception as e:
            logger.error(f"Redis subscribe 异常，{delay:.0f}s 后重连: {e}")
            if r is not None:
                try:
                    await r.close()
                except Exception:
                    pass
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)
