"""数据导入服务"""
import csv
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.message import Message
from app.models.conversation import Conversation
from app.models.sender import Sender


class ImportService:
    """导入服务 - 支持消息数据的 CSV/JSON 导入"""

    def __init__(self):
        self.import_dir = Path("imports")
        self.import_dir.mkdir(exist_ok=True)

    async def import_messages_from_csv(
        self,
        db: AsyncSession,
        file_path: str,
        conversation_id: Optional[int] = None,
        skip_duplicates: bool = True,
    ) -> Dict:
        """从 CSV 文件导入消息

        CSV 格式要求（列名）：
        id, conversation_id, sender_id, message_type, text, date
        可选列：caption, views, forwards, has_media

        Args:
            db: 数据库会话
            file_path: CSV 文件路径
            conversation_id: 默认会话ID（CSV中未指定时使用）
            skip_duplicates: 是否跳过重复消息
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        imported = 0
        skipped = 0
        errors = 0

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, 2):
                try:
                    msg_id = int(row.get("id", 0))
                    if not msg_id:
                        skipped += 1
                        continue

                    # 检查重复
                    if skip_duplicates:
                        existing = await db.execute(
                            select(Message).where(Message.id == msg_id)
                        )
                        if existing.scalar_one_or_none():
                            skipped += 1
                            continue

                    # 解析日期
                    date_str = row.get("date", "")
                    date_val = None
                    if date_str:
                        try:
                            date_val = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                            if date_val.tzinfo:
                                date_val = date_val.replace(tzinfo=None)
                        except ValueError:
                            errors += 1
                            continue

                    if not date_val:
                        errors += 1
                        continue

                    message = Message(
                        id=msg_id,
                        conversation_id=int(row.get("conversation_id", conversation_id or 0)),
                        sender_id=int(row["sender_id"]) if row.get("sender_id") else None,
                        message_type=row.get("message_type", "text") or "text",
                        text=row.get("text", ""),
                        caption=row.get("caption", ""),
                        views=int(row["views"]) if row.get("views") else None,
                        forwards=int(row["forwards"]) if row.get("forwards") else None,
                        has_media=row.get("has_media", "").lower() == "true",
                        date=date_val,
                    )
                    db.add(message)
                    imported += 1

                except Exception as e:
                    logger.warning(f"导入 CSV 第 {row_num} 行失败: {e}")
                    errors += 1

        if imported > 0:
            await db.commit()

        return {
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
            "message": f"导入完成: {imported} 条成功, {skipped} 条跳过, {errors} 条错误"
        }

    async def import_messages_from_json(
        self,
        db: AsyncSession,
        file_path: str,
        conversation_id: Optional[int] = None,
        skip_duplicates: bool = True,
    ) -> Dict:
        """从 JSON 文件导入消息

        JSON 格式：数组，每个元素包含:
        id, conversation_id, sender_id, message_type, text, date
        可选: caption, views, forwards, has_media
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError("JSON 格式错误: 期望数组")

        imported = 0
        skipped = 0
        errors = 0

        for item in data:
            try:
                msg_id = int(item.get("id", 0))
                if not msg_id:
                    skipped += 1
                    continue

                if skip_duplicates:
                    existing = await db.execute(
                        select(Message).where(Message.id == msg_id)
                    )
                    if existing.scalar_one_or_none():
                        skipped += 1
                        continue

                date_str = item.get("date", "")
                date_val = None
                if date_str:
                    try:
                        date_val = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
                        if date_val.tzinfo:
                            date_val = date_val.replace(tzinfo=None)
                    except ValueError:
                        errors += 1
                        continue

                if not date_val:
                    errors += 1
                    continue

                message = Message(
                    id=msg_id,
                    conversation_id=int(item.get("conversation_id", conversation_id or 0)),
                    sender_id=int(item["sender_id"]) if item.get("sender_id") else None,
                    message_type=item.get("message_type", "text") or "text",
                    text=item.get("text", ""),
                    caption=item.get("caption", ""),
                    views=int(item["views"]) if item.get("views") else None,
                    forwards=int(item["forwards"]) if item.get("forwards") else None,
                    has_media=item.get("has_media", False),
                    date=date_val,
                )
                db.add(message)
                imported += 1

            except Exception as e:
                logger.warning(f"导入 JSON 消息失败: {e}")
                errors += 1

        if imported > 0:
            await db.commit()

        return {
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
            "message": f"导入完成: {imported} 条成功, {skipped} 条跳过, {errors} 条错误"
        }


# 全局导入服务实例
import_service = ImportService()
