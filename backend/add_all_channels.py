#!/usr/bin/env python3
"""自动添加账号上所有频道到监控"""
import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.conversation import Conversation
from app.telegram.client import client_manager
from loguru import logger


async def get_all_dialogs(account_id: int):
    """获取账号的所有对话"""
    client = await client_manager.get_client(account_id)
    if not client:
        logger.error(f"账号 {account_id} 客户端未连接")
        return []

    dialogs = []
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        if hasattr(entity, 'channel') or hasattr(entity, 'megagroup'):
            # 这是频道或超级群组
            dialogs.append({
                'chat_id': entity.id,
                'title': dialog.title,
                'username': getattr(entity, 'username', None),
                'type': 'channel' if hasattr(entity, 'channel') else 'supergroup'
            })

    return dialogs


async def main():
    account_id = 2  # 账号ID

    logger.info(f"开始获取账号 {account_id} 的所有对话...")

    # 获取所有频道
    dialogs = await get_all_dialogs(account_id)
    channels = [d for d in dialogs if d['type'] == 'channel']

    logger.info(f"找到 {len(channels)} 个频道")

    # 获取已添加的频道
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Conversation.chat_id).where(
                Conversation.account_id == account_id,
                Conversation.chat_type == 'channel'
            )
        )
        existing_chat_ids = set([c[0] for c in result.all()])

        logger.info(f"数据库中已有 {len(existing_chat_ids)} 个频道")

        # 找出未添加的频道
        missing_channels = []
        for ch in channels:
            # 标准化chat_id
            chat_id = ch['chat_id']
            if chat_id > 0 and ch['type'] == 'channel':
                chat_id = -1000000000000 + chat_id

            if chat_id not in existing_chat_ids:
                missing_channels.append({
                    'chat_id': chat_id,
                    'title': ch['title'],
                    'username': ch['username']
                })

        logger.info(f"未添加的频道: {len(missing_channels)} 个")

        if missing_channels:
            print("\n需要添加的频道:")
            for i, ch in enumerate(missing_channels[:20], 1):
                print(f"  {i}. {ch['title'][:60]}")
                if ch['username']:
                    print(f"     @{ch['username']}")
                print(f"     chat_id: {ch['chat_id']}")

            if len(missing_channels) > 20:
                print(f"  ... 还有 {len(missing_channels) - 20} 个")

            print(f"\n总共需要添加 {len(missing_channels)} 个频道")
            print("请通过前端界面批量添加这些频道")


if __name__ == "__main__":
    asyncio.run(main())
