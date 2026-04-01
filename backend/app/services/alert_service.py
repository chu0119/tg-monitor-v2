"""告警服务"""
from typing import List
from datetime import datetime
from sqlalchemy import select
import re
import asyncio
from loguru import logger
from app.core.database import AsyncSessionLocal
from app.models import (
    Alert, Message, Sender, Keyword, NotificationConfig, Conversation
)
from app.services.notification_service import notification_service
from app.utils import now_utc

# 全局后台任务集合，用于追踪通知发送任务
_notification_tasks = set()


class AlertService:
    """告警服务"""

    def __init__(self):
        self.notification_service = notification_service

    def _highlight_keyword(self, text: str, keyword: str) -> str:
        """在文本中高亮关键词（使用 HTML 标记）"""
        if not text or not keyword:
            return text

        # 转义 HTML 特殊字符
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        # 使用正则表达式进行不区分大小写的替换，保留原始大小写
        pattern = re.compile(f'({re.escape(keyword)})', re.IGNORECASE)
        highlighted = pattern.sub(r'<mark class="highlight-keyword">\1</mark>', text)

        return highlighted

    async def create_alerts(
        self,
        db,
        message: Message,
        sender: Sender,
        matched_keywords: List[dict]
    ):
        """创建告警"""
        # 获取完整消息内容
        full_message = message.text or getattr(message, "caption", None) or ""

        for match in matched_keywords:
            # 检查是否已存在该消息和关键词的告警
            existing = await db.execute(
                select(Alert).where(
                    Alert.message_id == message.id,
                    Alert.keyword_id == match["keyword_id"]
                )
            )
            if existing.scalar_one_or_none():
                continue

            # 生成带高亮的消息内容
            highlighted_message = self._highlight_keyword(full_message, match["word"])

            alert = Alert(
                message_id=message.id,
                conversation_id=message.conversation_id,
                keyword_id=match["keyword_id"],
                sender_id=sender.id,
                keyword_text=match["word"],
                keyword_group_name=match["group_name"],
                alert_level=match["alert_level"],
                status="pending",
                matched_text=match.get("matched_text", ""),
                message_preview=full_message,  # 存储完整消息
                highlighted_message=highlighted_message,  # 存储带高亮的消息
            )

            db.add(alert)
            await db.flush()

            # 刷新 alert 对象，确保所有属性都已加载
            await db.refresh(alert)

            # 更新会话告警计数
            from sqlalchemy import update
            await db.execute(
                update(Conversation)
                .where(Conversation.id == message.conversation_id)
                .values(total_alerts=Conversation.total_alerts + 1)
            )

            # 注意：不在此处 commit，由调用方统一管理事务
            logger.info(f"告警已创建: alert_id={alert.id}, 等待事务提交后发送通知")

            # 异步发送通知（不阻塞主流程）
            task = asyncio.create_task(
                self._send_notification_async(alert.id, message.id, sender.id)
            )
            _notification_tasks.add(task)
            task.add_done_callback(_notification_tasks.discard)
            logger.info(f"异步通知任务已创建: alert_id={alert.id}")

    async def _send_notification_async(self, alert_id: int, message_id: int, sender_id: int):
        """异步发送通知（后台任务）"""
        logger.info(f"开始异步发送通知: alert_id={alert_id}, message_id={message_id}, sender_id={sender_id}")
        try:
            async with AsyncSessionLocal() as db:
                # 查询告警、消息、发送者
                result = await db.execute(
                    select(Alert).where(Alert.id == alert_id)
                )
                alert = result.scalar_one_or_none()
                if not alert:
                    logger.warning(f"异步通知: 告警不存在 alert_id={alert_id}")
                    return

                # 获取消息和发送者
                msg_result = await db.execute(
                    select(Message).where(Message.id == message_id)
                )
                message = msg_result.scalar_one_or_none()
                if not message:
                    logger.warning(f"异步通知: 消息不存在 message_id={message_id}")
                    return

                sender_result = await db.execute(
                    select(Sender).where(Sender.id == sender_id)
                )
                sender = sender_result.scalar_one_or_none()
                if not sender:
                    logger.warning(f"异步通知: 发送者不存在 sender_id={sender_id}")
                    return

                logger.info(f"异步通知: 开始发送通知 alert_id={alert_id}")
                # 发送通知
                await self._send_notification(db, alert, message, sender)
                await db.commit()
                logger.info(f"异步通知: 发送完成 alert_id={alert_id}")
        except Exception as e:
            logger.error(f"异步发送通知失败 (alert_id={alert_id}): {e}")
            import traceback
            logger.error(traceback.format_exc())

    async def _send_notification(
        self,
        db,
        alert: Alert,
        message: Message,
        sender: Sender
    ):
        """发送告警通知"""
        # 获取适用的通知配置
        result = await db.execute(
            select(NotificationConfig).where(
                NotificationConfig.is_active == True
            )
        )
        configs = result.scalars().all()

        if not configs:
            return

        # 提前提取告警数据，避免循环中触发懒加载
        alert_level = alert.alert_level
        keyword_group_name = alert.keyword_group_name
        conversation_id = alert.conversation_id

        # 预先查询关键词组 ID（如果需要过滤）
        keyword_group_id = None
        needs_keyword_filter = any(c.keyword_groups for c in configs)
        if needs_keyword_filter:
            from sqlalchemy import select as sel
            from app.models.keyword import KeywordGroup

            kg_result = await db.execute(
                sel(KeywordGroup.id).where(KeywordGroup.name == keyword_group_name)
            )
            keyword_group_id = kg_result.scalar_one_or_none()

        notification_results = {}

        for config in configs:
            # 检查告警级别过滤
            if config.min_alert_level:
                level_order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
                if level_order.get(alert_level, 0) < level_order.get(config.min_alert_level, 0):
                    logger.debug(f"告警 {alert.id} 级别 {alert_level} 低于配置最低级别 {config.min_alert_level}，跳过")
                    continue

            # 检查关键词组过滤
            if config.keyword_groups:
                if keyword_group_id is None or keyword_group_id not in config.keyword_groups:
                    logger.debug(f"告警 {alert.id} 关键词组 {keyword_group_name} (ID: {keyword_group_id}) 不在配置列表中，跳过")
                    continue

            # 检查会话过滤
            if config.conversations and conversation_id not in config.conversations:
                logger.debug(f"告警 {alert.id} 会话 {conversation_id} 不在配置列表中，跳过")
                continue

            logger.info(f"发送通知: config_id={config.id}, type={config.notification_type}, alert_id={alert.id}")
            # 发送通知
            success, error = await self.notification_service.send_notification(
                config,
                alert,
                message,
                sender
            )
            logger.info(f"通知发送结果: config_id={config.id}, success={success}, error={error}")

            notification_results[str(config.notification_type)] = {
                "success": success,
                "error": error,
                "sent_at": now_utc().isoformat() if success else None
            }

            if success:
                config.total_sent += 1
                config.last_sent_at = now_utc()
            else:
                config.total_failed += 1
                config.last_error = error

        alert.notification_sent = True
        alert.notification_channels = notification_results

        logger.info(f"告警 {alert.id} 通知发送完成: {notification_results}")

    async def handle_alert(
        self,
        alert_id: int,
        status: str,
        handler: str,
        handler_note: str = None
    ):
        """处理告警"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Alert).where(Alert.id == alert_id)
            )
            alert = result.scalar_one_or_none()

            if not alert:
                raise ValueError(f"告警 {alert_id} 不存在")

            alert.status = status
            alert.handler = handler
            alert.handler_note = handler_note
            alert.handled_at = now_utc()

            await db.commit()

        logger.info(f"告警 {alert_id} 已处理: {status} by {handler}")

    async def get_alert_stats(self) -> dict:
        """获取告警统计"""
        from sqlalchemy import func
        async with AsyncSessionLocal() as db:
            # 总数统计 - 使用 func.count() 优化性能
            total_result = await db.execute(select(func.count(Alert.id)))
            total = total_result.scalar()

            # 按状态统计 - 一次性查询所有状态
            status_result = await db.execute(
                select(Alert.status, func.count(Alert.id)).group_by(Alert.status)
            )
            status_rows = status_result.all()
            status_stats = {status: count for status, count in status_rows}

            # 按级别统计 - 一次性查询所有级别
            level_result = await db.execute(
                select(Alert.alert_level, func.count(Alert.id)).group_by(Alert.alert_level)
            )
            level_rows = level_result.all()
            level_stats = {level: count for level, count in level_rows}

            return {
                "total": total or 0,
                "pending": status_stats.get("pending", 0),
                "processing": status_stats.get("processing", 0),
                "resolved": status_stats.get("resolved", 0),
                "ignored": status_stats.get("ignored", 0),
                "false_positive": status_stats.get("false_positive", 0),
                "by_level": level_stats,
            }


# 全局告警服务实例
alert_service = AlertService()
