"""Backfill denormalized counter fields. Run once after deployment.

Recalculates conversations.total_messages and senders.alert_count from
the canonical tables so the denormalized fields stay correct even if
they drifted (e.g. before the per-transaction maintenance was added).
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import AsyncSessionLocal
from sqlalchemy import text


async def main():
    async with AsyncSessionLocal() as db:
        await db.execute(text("""
            UPDATE conversations c SET total_messages = (
                SELECT COUNT(*) FROM messages WHERE conversation_id = c.id
            )
        """))
        await db.execute(text("""
            UPDATE senders s SET alert_count = (
                SELECT COUNT(*) FROM alerts WHERE sender_id = s.id
            )
        """))
        await db.commit()
        print("Backfill complete")


if __name__ == "__main__":
    asyncio.run(main())
