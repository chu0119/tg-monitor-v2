"""数据导出服务"""
import csv
import json
from pathlib import Path
from typing import Tuple
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from app.models.message import Message
from app.models.conversation import Conversation
from app.models.sender import Sender
from app.schemas.message import MessageFilter, MessageExport
from app.utils import now_utc, format_datetime, to_local_naive


class ExportService:
    """导出服务"""

    def __init__(self):
        self.export_dir = Path("exports")
        self.export_dir.mkdir(exist_ok=True)

    async def export_messages(
        self,
        db: AsyncSession,
        export_data: MessageExport
    ) -> Tuple[str, str]:
        """导出消息"""
        # 构建查询
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

        # 获取消息
        result = await db.execute(query.order_by(Message.date.desc()))
        messages = result.scalars().all()

        # 根据格式导出
        timestamp = to_local_naive(now_utc()).strftime("%Y%m%d_%H%M%S")

        if export_data.format == "csv":
            file_path = self.export_dir / f"messages_{timestamp}.csv"
            await self._export_csv(messages, file_path, export_data, db)
            return str(file_path), "text/csv"

        elif export_data.format == "json":
            file_path = self.export_dir / f"messages_{timestamp}.json"
            await self._export_json(messages, file_path, export_data, db)
            return str(file_path), "application/json"

        elif export_data.format == "xlsx":
            file_path = self.export_dir / f"messages_{timestamp}.xlsx"
            await self._export_xlsx(messages, file_path, export_data, db)
            return str(file_path), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        else:
            raise ValueError(f"不支持的导出格式: {export_data.format}")

    async def _export_csv(self, messages, file_path: Path, export_data: MessageExport, db):
        """导出为CSV"""
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # 写入表头
            headers = ["ID", "会话ID", "发送者ID", "类型", "文本", "日期"]
            if export_data.include_sender:
                headers.extend(["发送者用户名", "发送者名字"])
            if export_data.include_conversation:
                headers.extend(["会话标题"])

            writer.writerow(headers)

            # 写入数据
            for msg in messages:
                row = [
                    msg.id,
                    msg.conversation_id,
                    msg.sender_id,
                    msg.message_type,
                    (msg.text or "")[:1000],  # 限制长度
                    format_datetime(msg.date) if msg.date else "",
                ]

                if export_data.include_sender and msg.sender_id:
                    sender_result = await db.execute(
                        select(Sender).where(Sender.id == msg.sender_id)
                    )
                    sender = sender_result.scalar_one_or_none()
                    if sender:
                        row.extend([sender.username or "", sender.first_name or ""])
                    else:
                        row.extend(["", ""])

                if export_data.include_conversation and msg.conversation_id:
                    conv_result = await db.execute(
                        select(Conversation).where(Conversation.id == msg.conversation_id)
                    )
                    conv = conv_result.scalar_one_or_none()
                    if conv:
                        row.append(conv.title or "")
                    else:
                        row.append("")

                writer.writerow(row)

    async def _export_json(self, messages, file_path: Path, export_data: MessageExport, db):
        """导出为JSON"""
        data = []

        for msg in messages:
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

            if export_data.include_sender and msg.sender_id:
                sender_result = await db.execute(
                    select(Sender).where(Sender.id == msg.sender_id)
                )
                sender = sender_result.scalar_one_or_none()
                if sender:
                    item["sender"] = {
                        "username": sender.username,
                        "first_name": sender.first_name,
                        "last_name": sender.last_name,
                    }

            if export_data.include_conversation and msg.conversation_id:
                conv_result = await db.execute(
                    select(Conversation).where(Conversation.id == msg.conversation_id)
                )
                conv = conv_result.scalar_one_or_none()
                if conv:
                    item["conversation"] = {
                        "title": conv.title,
                        "type": conv.chat_type,
                    }

            data.append(item)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    async def _export_xlsx(self, messages, file_path: Path, export_data: MessageExport, db):
        """导出为Excel"""
        try:
            import openpyxl
            from openpyxl.styles import Font, Alignment
        except ImportError:
            raise ImportError("请安装 openpyxl: pip install openpyxl")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "消息"

        # 设置表头
        headers = ["ID", "会话ID", "发送者ID", "类型", "文本", "日期"]
        if export_data.include_sender:
            headers.extend(["发送者用户名", "发送者名字"])
        if export_data.include_conversation:
            headers.extend(["会话标题"])

        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True)

        # 写入数据
        for row_idx, msg in enumerate(messages, 2):
            ws.cell(row=row_idx, column=1, value=msg.id)
            ws.cell(row=row_idx, column=2, value=msg.conversation_id)
            ws.cell(row=row_idx, column=3, value=msg.sender_id)
            ws.cell(row=row_idx, column=4, value=msg.message_type)
            ws.cell(row=row_idx, column=5, value=(msg.text or "")[:1000])
            ws.cell(row=row_idx, column=6, value=format_datetime(msg.date) if msg.date else "")

            col = 7
            if export_data.include_sender and msg.sender_id:
                sender_result = await db.execute(
                    select(Sender).where(Sender.id == msg.sender_id)
                )
                sender = sender_result.scalar_one_or_none()
                if sender:
                    ws.cell(row=row_idx, column=col, value=sender.username or "")
                    ws.cell(row=row_idx, column=col + 1, value=sender.first_name or "")
                    col += 2

            if export_data.include_conversation:
                conv_result = await db.execute(
                    select(Conversation).where(Conversation.id == msg.conversation_id)
                )
                conv = conv_result.scalar_one_or_none()
                if conv:
                    ws.cell(row=row_idx, column=col, value=conv.title or "")

        wb.save(file_path)


# 全局导出服务实例
export_service = ExportService()
