"""数据导出服务 - 高性能版本"""
import csv
import json
from pathlib import Path
from typing import Tuple, Optional, Set
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from app.models.message import Message
from app.models.conversation import Conversation
from app.models.sender import Sender
from app.schemas.message import MessageFilter, MessageExport
from app.utils import now_utc, format_datetime, to_local_naive

BATCH_SIZE = 5000


class ExportService:
    """导出服务 - 分批处理，支持大数据量"""

    def __init__(self):
        self.export_dir = Path("exports")
        self.export_dir.mkdir(exist_ok=True)

    def _build_base_query(self, export_data: MessageExport):
        """构建基础查询"""
        query = select(Message)

        if export_data.filter:
            f = export_data.filter
            if f.conversation_ids:
                query = query.where(Message.conversation_id.in_(f.conversation_ids))
            if f.sender_ids:
                query = query.where(Message.sender_id.in_(f.sender_ids))
            if f.keyword:
                query = query.where(Message.text.ilike(f"%{f.keyword}%"))
            if f.message_type:
                query = query.where(Message.message_type == f.message_type)
            if f.has_alert is not None:
                if f.has_alert:
                    query = query.where(Message.alert_id.isnot(None))
                else:
                    query = query.where(Message.alert_id.is_(None))
            if f.start_date:
                query = query.where(Message.date >= f.start_date)
            if f.end_date:
                query = query.where(Message.date <= f.end_date)

        if export_data.message_ids:
            query = query.where(Message.id.in_(export_data.message_ids))

        return query.order_by(Message.date.desc())

    async def _fetch_all_messages(self, db: AsyncSession, query):
        """分批获取所有消息，避免一次性加载"""
        messages = []
        offset = 0
        while True:
            batch_query = query.offset(offset).limit(BATCH_SIZE)
            result = await db.execute(batch_query)
            batch = result.scalars().all()
            if not batch:
                break
            messages.extend(batch)
            offset += BATCH_SIZE
            if len(batch) < BATCH_SIZE:
                break
        return messages

    async def _precache_senders(self, db: AsyncSession, sender_ids: Set[int]) -> dict:
        """批量预加载所有发送者到缓存"""
        cache = {}
        if not sender_ids:
            return cache
        id_list = list(sender_ids)
        for i in range(0, len(id_list), BATCH_SIZE):
            batch = id_list[i:i + BATCH_SIZE]
            result = await db.execute(
                select(Sender).where(Sender.id.in_(batch))
            )
            for sender in result.scalars().all():
                cache[sender.id] = sender
        return cache

    async def _precache_conversations(self, db: AsyncSession, conv_ids: Set[int]) -> dict:
        """批量预加载所有会话到缓存"""
        cache = {}
        if not conv_ids:
            return cache
        id_list = list(conv_ids)
        for i in range(0, len(id_list), BATCH_SIZE):
            batch = id_list[i:i + BATCH_SIZE]
            result = await db.execute(
                select(Conversation).where(Conversation.id.in_(batch))
            )
            for conv in result.scalars().all():
                cache[conv.id] = conv
        return cache

    async def export_messages(
        self,
        db: AsyncSession,
        export_data: MessageExport
    ) -> Tuple[str, str]:
        """导出消息 - 分批处理版本"""
        timestamp = to_local_naive(now_utc()).strftime("%Y%m%d_%H%M%S")
        fmt = export_data.format

        if fmt == "csv":
            file_path = self.export_dir / f"messages_{timestamp}.csv"
            count = await self._export_csv(db, export_data, file_path)
            return str(file_path), "text/csv"
        elif fmt == "json":
            file_path = self.export_dir / f"messages_{timestamp}.json"
            count = await self._export_json(db, export_data, file_path)
            return str(file_path), "application/json"
        elif fmt == "xlsx":
            file_path = self.export_dir / f"messages_{timestamp}.xlsx"
            count = await self._export_xlsx(db, export_data, file_path)
            return str(file_path), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            raise ValueError(f"不支持的导出格式: {fmt}")

    async def _export_csv(
        self, db: AsyncSession, export_data: MessageExport, file_path: Path
    ) -> int:
        """导出 CSV - 分批处理"""
        query = self._build_base_query(export_data)
        include_sender = export_data.include_sender
        include_conv = export_data.include_conversation

        # 分批获取消息并收集关联 ID
        sender_ids = set()
        conv_ids = set()
        all_messages = []
        offset = 0
        while True:
            batch_query = query.offset(offset).limit(BATCH_SIZE)
            result = await db.execute(batch_query)
            batch = result.scalars().all()
            if not batch:
                break
            all_messages.extend(batch)
            for msg in batch:
                if include_sender and msg.sender_id:
                    sender_ids.add(msg.sender_id)
                if include_conv and msg.conversation_id:
                    conv_ids.add(msg.conversation_id)
            offset += BATCH_SIZE
            if len(batch) < BATCH_SIZE:
                break

        # 批量预加载缓存
        sender_cache = await self._precache_senders(db, sender_ids)
        conv_cache = await self._precache_conversations(db, conv_ids)

        # 写入 CSV
        headers = ["ID", "会话ID", "发送者ID", "类型", "文本", "日期"]
        if include_sender:
            headers.extend(["发送者用户名", "发送者名字"])
        if include_conv:
            headers.extend(["会话标题"])

        count = 0
        with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

            for msg in all_messages:
                row = [
                    msg.id,
                    msg.conversation_id,
                    msg.sender_id,
                    msg.message_type,
                    (msg.text or "")[:1000],
                    format_datetime(msg.date) if msg.date else "",
                ]
                if include_sender and msg.sender_id:
                    sender = sender_cache.get(msg.sender_id)
                    if sender:
                        row.extend([sender.username or "", sender.first_name or ""])
                    else:
                        row.extend(["", ""])
                if include_conv and msg.conversation_id:
                    conv = conv_cache.get(msg.conversation_id)
                    if conv:
                        row.append(conv.title or "")
                    else:
                        row.append("")
                writer.writerow(row)
                count += 1

        logger.info(f"CSV 导出完成: {count} 条消息 -> {file_path}")
        return count

    async def _export_json(
        self, db: AsyncSession, export_data: MessageExport, file_path: Path
    ) -> int:
        """导出 JSON - 分批处理"""
        query = self._build_base_query(export_data)
        include_sender = export_data.include_sender
        include_conv = export_data.include_conversation

        # 分批获取消息并收集关联 ID
        sender_ids = set()
        conv_ids = set()
        all_messages = []
        offset = 0
        while True:
            batch_query = query.offset(offset).limit(BATCH_SIZE)
            result = await db.execute(batch_query)
            batch = result.scalars().all()
            if not batch:
                break
            all_messages.extend(batch)
            for msg in batch:
                if include_sender and msg.sender_id:
                    sender_ids.add(msg.sender_id)
                if include_conv and msg.conversation_id:
                    conv_ids.add(msg.conversation_id)
            offset += BATCH_SIZE
            if len(batch) < BATCH_SIZE:
                break

        sender_cache = await self._precache_senders(db, sender_ids)
        conv_cache = await self._precache_conversations(db, conv_ids)

        # 写入 JSON
        count = 0
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("[\n")
            first = True
            for msg in all_messages:
                item = {
                    "id": msg.id,
                    "conversation_id": msg.conversation_id,
                    "sender_id": msg.sender_id,
                    "type": msg.message_type,
                    "text": msg.text,
                    "caption": msg.caption,
                    "date": msg.date.isoformat() if msg.date else None,
                    "views": msg.views,
                    "forwards": msg.forwards,
                    "has_media": msg.has_media,
                }
                if include_sender and msg.sender_id:
                    sender = sender_cache.get(msg.sender_id)
                    if sender:
                        item["sender"] = {
                            "username": sender.username,
                            "first_name": sender.first_name,
                            "last_name": sender.last_name,
                        }
                if include_conv and msg.conversation_id:
                    conv = conv_cache.get(msg.conversation_id)
                    if conv:
                        item["conversation"] = {
                            "title": conv.title,
                            "type": conv.chat_type,
                        }

                if not first:
                    f.write(",\n")
                f.write(json.dumps(item, ensure_ascii=False))
                first = False
                count += 1

            f.write("\n]")

        logger.info(f"JSON 导出完成: {count} 条消息 -> {file_path}")
        return count

    async def _export_xlsx(
        self, db: AsyncSession, export_data: MessageExport, file_path: Path
    ) -> int:
        """导出 Excel - 分批处理"""
        try:
            import openpyxl
            from openpyxl.styles import Font
        except ImportError:
            raise ImportError("请安装 openpyxl: pip install openpyxl")

        query = self._build_base_query(export_data)
        include_sender = export_data.include_sender
        include_conv = export_data.include_conversation

        # 分批获取消息并收集关联 ID
        sender_ids = set()
        conv_ids = set()
        all_messages = []
        offset = 0
        while True:
            batch_query = query.offset(offset).limit(BATCH_SIZE)
            result = await db.execute(batch_query)
            batch = result.scalars().all()
            if not batch:
                break
            all_messages.extend(batch)
            for msg in batch:
                if include_sender and msg.sender_id:
                    sender_ids.add(msg.sender_id)
                if include_conv and msg.conversation_id:
                    conv_ids.add(msg.conversation_id)
            offset += BATCH_SIZE
            if len(batch) < BATCH_SIZE:
                break

        sender_cache = await self._precache_senders(db, sender_ids)
        conv_cache = await self._precache_conversations(db, conv_ids)

        # 创建工作簿（使用 write_only 模式减少内存）
        wb = openpyxl.Workbook(write_only=True)
        ws = wb.create_sheet("消息")

        headers = ["ID", "会话ID", "发送者ID", "类型", "文本", "日期"]
        if include_sender:
            headers.extend(["发送者用户名", "发送者名字"])
        if include_conv:
            headers.extend(["会话标题"])
        ws.append(headers)

        count = 0
        for msg in all_messages:
            row = [
                msg.id,
                msg.conversation_id,
                msg.sender_id,
                msg.message_type,
                (msg.text or "")[:1000],
                format_datetime(msg.date) if msg.date else "",
            ]
            if include_sender and msg.sender_id:
                sender = sender_cache.get(msg.sender_id)
                if sender:
                    row.extend([sender.username or "", sender.first_name or ""])
                else:
                    row.extend(["", ""])
            if include_conv and msg.conversation_id:
                conv = conv_cache.get(msg.conversation_id)
                if conv:
                    row.append(conv.title or "")
                else:
                    row.append("")
            ws.append(row)
            count += 1

        wb.save(file_path)
        logger.info(f"XLSX 导出完成: {count} 条消息 -> {file_path}")
        return count


# 全局导出服务实例
export_service = ExportService()
