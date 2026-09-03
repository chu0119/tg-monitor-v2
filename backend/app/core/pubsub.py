# backend/app/core/pubsub.py
import json

import redis.asyncio as aioredis
from loguru import logger

CHANNEL = "tg_monitor_events"


async def publish(event_type: str, data: dict):
    """发布事件到 Redis 频道"""
    r = aioredis.Redis()
    try:
        await r.publish(CHANNEL, json.dumps({"type": event_type, **data}))
    except Exception as e:
        logger.error(f"Redis publish 失败: {e}")
    finally:
        await r.close()


async def subscribe(handler):
    """订阅 Redis 频道，收到消息后调用 handler"""
    r = aioredis.Redis()
    try:
        async with r.pubsub() as ps:
            await ps.subscribe(CHANNEL)
            logger.info(f"已订阅 Redis 频道: {CHANNEL}")
            async for msg in ps.listen():
                if msg["type"] == "message":
                    try:
                        await handler(json.loads(msg["data"]))
                    except Exception as e:
                        logger.error(f"处理 Redis 消息失败: {e}")
    except Exception as e:
        logger.error(f"Redis subscribe 失败: {e}")
