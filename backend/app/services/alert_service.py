"""告警服务"""
from typing import List
from datetime import datetime, timedelta
from sqlalchemy import select, func
import re
import asyncio
from loguru import logger
from app.core.database import AsyncSessionLocal
from app.models import (
    Alert, Message, Sender, Keyword, NotificationConfig, Conversation, NotificationLog
)
from app.services.notification_service import notification_service
from app.utils import now_utc

# 全局后台任务集合，用于追踪通知发送任务
_notification_tasks = set()


class AlertService:
    """告警服务"""

    def __init__(self):
        self.notification_service = notification_service
        self._notification_queue: asyncio.Queue = asyncio.Queue(maxsize=5000)
        self._notification_workers: set[asyncio.Task] = set()
        self._queue_stats = {
            "enqueued": 0,
            "processed": 0,
            "failed": 0,
            "dropped": 0,
            "retried": 0,
        }

    def _ensure_notification_workers(self, worker_count: int = 2):
        """懒启动通知队列 worker，避免每条告警创建无上限后台任务。"""
        live_workers = {task for task in self._notification_workers if not task.done()}
        self._notification_workers = live_workers
        missing = max(0, worker_count - len(live_workers))
        for index in range(missing):
            task = asyncio.create_task(self._notification_worker_loop(index + len(live_workers) + 1))
            self._notification_workers.add(task)

    async def _enqueue_notification(self, alert_id: int, message_id: int, sender_id: int):
        try:
            from app.api.settings import get_settings_snapshot
            async with AsyncSessionLocal() as db:
                settings_snapshot = await get_settings_snapshot(db)
            worker_count = getattr(settings_snapshot, "notification_queue_workers", 2)
        except Exception:
            worker_count = 2

        self._ensure_notification_workers(worker_count)
        item = {
            "alert_id": alert_id,
            "message_id": message_id,
            "sender_id": sender_id,
            "attempt": 0,
        }
        try:
            self._notification_queue.put_nowait(item)
            self._queue_stats["enqueued"] += 1
            logger.info(f"通知已入队: alert_id={alert_id}, queue_size={self._notification_queue.qsize()}")
        except asyncio.QueueFull:
            self._queue_stats["dropped"] += 1
            logger.error(f"通知队列已满，丢弃通知任务: alert_id={alert_id}")

    async def _notification_worker_loop(self, worker_id: int):
        logger.info(f"通知队列 worker 启动: worker_id={worker_id}")
        while True:
            item = await self._notification_queue.get()
            try:
                success = await self._send_notification_async(
                    item["alert_id"],
                    item["message_id"],
                    item["sender_id"],
                )
                if success:
                    self._queue_stats["processed"] += 1
                else:
                    await self._retry_or_mark_failed(item)
            except Exception as e:
                logger.error(f"通知队列 worker 异常: worker_id={worker_id}, item={item}, error={e}")
                await self._retry_or_mark_failed(item)
            finally:
                self._notification_queue.task_done()

    async def _retry_or_mark_failed(self, item: dict):
        try:
            from app.api.settings import get_settings_snapshot
            async with AsyncSessionLocal() as db:
                settings_snapshot = await get_settings_snapshot(db)
            max_retries = getattr(settings_snapshot, "notification_max_retries", 3)
        except Exception:
            max_retries = 3

        attempt = item.get("attempt", 0)
        if attempt < max_retries:
            item["attempt"] = attempt + 1
            self._queue_stats["retried"] += 1
            delay = min(60, 2 ** attempt)
            await asyncio.sleep(delay)
            try:
                self._notification_queue.put_nowait(item)
            except asyncio.QueueFull:
                self._queue_stats["dropped"] += 1
                self._queue_stats["failed"] += 1
                logger.error(f"通知重试入队失败，队列已满: alert_id={item.get('alert_id')}")
        else:
            self._queue_stats["failed"] += 1
            logger.error(f"通知重试耗尽: alert_id={item.get('alert_id')}, attempts={attempt}")

    def get_queue_stats(self) -> dict:
        return {
            **self._queue_stats,
            "queue_size": self._notification_queue.qsize(),
            "workers": len([t for t in self._notification_workers if not t.done()]),
        }

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

            existing_keywords = message.matched_keywords or []
            message.matched_keywords = existing_keywords + [match["word"]]
            if message.alert_id is None:
                message.alert_id = alert.id

            # 更新会话告警计数
            from sqlalchemy import update
            await db.execute(
                update(Conversation)
                .where(Conversation.id == message.conversation_id)
                .values(total_alerts=Conversation.total_alerts + 1)
            )

            # 注意：不在此处 commit，由调用方统一管理事务
            logger.info(f"告警已创建: alert_id={alert.id}, 等待事务提交后发送通知")

            await self._enqueue_notification(alert.id, message.id, sender.id)

    async def _send_notification_async(self, alert_id: int, message_id: int, sender_id: int):
        """异步发送通知（后台任务）"""
        logger.info(f"开始异步发送通知: alert_id={alert_id}, message_id={message_id}, sender_id={sender_id}")
        try:
            async with AsyncSessionLocal() as db:
                alert = None
                message = None
                sender = None

                # create_alerts 的调用方统一提交事务。后台任务可能先于提交执行，
                # 因此短暂重试，避免把正常的提交竞态误判为数据丢失。
                max_attempts = 20
                for attempt in range(max_attempts):
                    result = await db.execute(
                        select(Alert).where(Alert.id == alert_id)
                    )
                    alert = result.scalar_one_or_none()

                    msg_result = await db.execute(
                        select(Message).where(Message.id == message_id)
                    )
                    message = msg_result.scalar_one_or_none()

                    sender_result = await db.execute(
                        select(Sender).where(Sender.id == sender_id)
                    )
                    sender = sender_result.scalar_one_or_none()

                    if alert and message and sender:
                        break

                    if attempt < max_attempts - 1:
                        await db.rollback()
                        await asyncio.sleep(0.5)

                if not alert:
                    logger.warning(f"异步通知: 告警不存在 alert_id={alert_id}")
                    return
                if not message:
                    logger.warning(f"异步通知: 消息不存在 message_id={message_id}")
                    return
                if not sender:
                    logger.warning(f"异步通知: 发送者不存在 sender_id={sender_id}")
                    return

                logger.info(f"异步通知: 开始发送通知 alert_id={alert_id}")
                # 发送通知
                await self._send_notification(db, alert, message, sender)
                await db.commit()
                logger.info(f"异步通知: 发送完成 alert_id={alert_id}")
                return True
        except Exception as e:
            logger.error(f"异步发送通知失败 (alert_id={alert_id}): {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

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

        if await self._should_suppress_notification(db, alert):
            alert.notification_sent = True
            alert.notification_channels = {
                "suppressed": {
                    "success": True,
                    "reason": "同类告警在降噪窗口内已通知",
                    "sent_at": now_utc().isoformat(),
                }
            }
            logger.info(f"告警 {alert.id} 通知已降噪抑制")
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
            channel_key = getattr(config.notification_type, "value", str(config.notification_type))
            db.add(NotificationLog(
                alert_id=alert.id,
                config_id=config.id,
                notification_type=channel_key,
                recipient=self._get_notification_recipient(config),
                title=f"{alert_level.upper()} 告警 - {keyword_group_name or ''}",
                content=(message.text or message.caption or "")[:2000],
                status="success" if success else "failed",
                error_message=error,
                sent_at=now_utc() if success else None,
            ))

            notification_results[channel_key] = {
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

    async def _should_suppress_notification(self, db, alert: Alert) -> bool:
        try:
            from app.api.settings import get_settings_snapshot
            settings_snapshot = await get_settings_snapshot(db)
            enabled = getattr(settings_snapshot, "enable_alert_notification_dedup", True)
            window_minutes = getattr(settings_snapshot, "alert_dedup_window_minutes", 10)
        except Exception:
            enabled = True
            window_minutes = 10

        if not enabled or window_minutes <= 0:
            return False

        cutoff = now_utc().replace(tzinfo=None) - timedelta(minutes=window_minutes)
        result = await db.execute(
            select(Alert.id)
            .where(
                Alert.id != alert.id,
                Alert.conversation_id == alert.conversation_id,
                Alert.sender_id == alert.sender_id,
                Alert.keyword_id == alert.keyword_id,
                Alert.notification_sent == True,
                Alert.created_at >= cutoff,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    def _get_notification_recipient(self, config: NotificationConfig) -> str:
        cfg = config.config or {}
        for key in ("to_emails", "chat_id", "webhook", "webhook_url", "url", "sckey"):
            value = cfg.get(key)
            if value:
                return str(value)[:255]
        return str(config.notification_type)

    async def get_pipeline_health(self, db) -> dict:
        """告警链路健康指标：用于发现“消息正常但告警/通知异常”。"""
        now = now_utc().replace(tzinfo=None)
        last_hour = now - timedelta(hours=1)
        last_day = now - timedelta(days=1)

        latest_message = (await db.execute(select(func.max(Message.date)))).scalar()
        latest_alert = (await db.execute(select(func.max(Alert.created_at)))).scalar()
        matched_without_alert = (await db.execute(
            select(func.count(Message.id)).where(
                Message.created_at >= last_hour,
                Message.matched_keywords.is_not(None),
                Message.alert_id.is_(None),
            )
        )).scalar() or 0
        recent_alerts = (await db.execute(
            select(func.count(Alert.id)).where(Alert.created_at >= last_hour)
        )).scalar() or 0
        notification_failures = (await db.execute(
            select(func.count(NotificationLog.id)).where(
                NotificationLog.created_at >= last_day,
                NotificationLog.status == "failed",
            )
        )).scalar() or 0

        problems = []
        if matched_without_alert:
            problems.append(f"最近1小时有 {matched_without_alert} 条已匹配消息没有关联告警")
        if self._notification_queue.qsize() > 1000:
            problems.append(f"通知队列积压 {self._notification_queue.qsize()} 条")
        if notification_failures > 0:
            problems.append(f"最近24小时通知失败 {notification_failures} 次")

        return {
            "status": "healthy" if not problems else "degraded",
            "latest_message_at": latest_message.isoformat() if latest_message else None,
            "latest_alert_at": latest_alert.isoformat() if latest_alert else None,
            "recent_alerts_1h": recent_alerts,
            "matched_without_alert_1h": matched_without_alert,
            "notification_failures_24h": notification_failures,
            "notification_queue": self.get_queue_stats(),
            "problems": problems,
        }

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
