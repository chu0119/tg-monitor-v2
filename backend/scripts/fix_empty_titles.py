"""修复数据库中title为空的会话，通过Telethon获取真实名称"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models import Conversation
from app.telegram.client import client_manager


async def get_telethon_entity_id(chat_id: int) -> int:
    if chat_id < -1000000000000:
        return -(chat_id + 1000000000000)
    return chat_id


async def fix_empty_titles():
    """遍历所有title为空的会话，尝试获取真实名称"""
    fixed_count = 0
    fallback_count = 0
    error_count = 0

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Conversation).where(
                (Conversation.title.is_(None)) | (Conversation.title == "")
            )
        )
        conversations = result.scalars().all()
        total = len(conversations)
        print(f"发现 {total} 个title为空的会话")

        for conv in conversations:
            title = None
            try:
                client = await client_manager.get_client(conv.account_id)
                if client:
                    entity_id = get_telethon_entity_id(conv.chat_id)
                    entity = await client.get_entity(entity_id)
                    if hasattr(entity, 'first_name'):
                        title = entity.first_name or ""
                        if hasattr(entity, 'last_name') and entity.last_name:
                            title += f" {entity.last_name}"
                    if not title and hasattr(entity, 'title'):
                        title = entity.title
            except Exception as e:
                error_count += 1
                print(f"  ❌ 会话 {conv.id} (chat_id={conv.chat_id}): 获取失败 - {e}")
                continue

            if title:
                conv.title = title
                fixed_count += 1
                print(f"  ✅ 会话 {conv.id}: '{title}'")
            else:
                if conv.chat_type == 'private':
                    title = f"用户#{conv.chat_id}"
                else:
                    title = f"会话#{conv.id}"
                conv.title = title
                fallback_count += 1
                print(f"  ⚠️ 会话 {conv.id}: 无法获取名称，使用 '{title}'")

        await db.commit()

    print(f"\n修复完成: 成功获取 {fixed_count}, fallback {fallback_count}, 失败 {error_count}, 总计 {total}")


if __name__ == "__main__":
    asyncio.run(fix_empty_titles())
