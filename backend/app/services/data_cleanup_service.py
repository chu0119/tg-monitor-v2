"""数据清理服务 - 按数据量自动清理告警和消息数据"""
import asyncio
import time
from typing import Dict, Any, Optional
from loguru import logger
from sqlalchemy import select, delete, update, func, text

from app.core.database import AsyncSessionLocal
from app.models.alert import Alert
from app.models.message import Message
from app.models.notification_log import NotificationLog


DEFAULT_MAX_MESSAGE_RECORDS = 200_000_000
DEFAULT_MAX_ALERT_RECORDS = 100_000_000
DEFAULT_MAX_DATABASE_SIZE_GB = 900
DELETE_BATCH_SIZE = 5000
MAX_DELETE_BATCHES = 2000


class DataCleanupService:
    """数据清理服务"""

    def __init__(self):
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        self._stats_cache: Optional[Dict[str, Any]] = None
        self._stats_cache_time: float = 0
        self._stats_cache_ttl: int = 60

    def _invalidate_stats_cache(self):
        self._stats_cache = None
        self._stats_cache_time = 0

    def _normalize_limit(self, value: Optional[int], default: int) -> int:
        try:
            limit = int(value) if value is not None else default
        except (TypeError, ValueError):
            limit = default
        return max(1, limit)

    async def _get_configured_limits(self) -> Dict[str, int]:
        try:
            from app.api.settings import get_settings_snapshot
            async with AsyncSessionLocal() as db:
                settings_snapshot = await get_settings_snapshot(db)
            max_messages = getattr(settings_snapshot, "max_message_records", DEFAULT_MAX_MESSAGE_RECORDS)
            max_alerts = getattr(settings_snapshot, "max_alert_records", DEFAULT_MAX_ALERT_RECORDS)
            max_database_size_gb = getattr(settings_snapshot, "max_database_size_gb", DEFAULT_MAX_DATABASE_SIZE_GB)
        except (ImportError, AttributeError) as e:
            logger.warning(f"获取数据量清理配置失败: {e}，使用默认值")
            max_messages = DEFAULT_MAX_MESSAGE_RECORDS
            max_alerts = DEFAULT_MAX_ALERT_RECORDS
            max_database_size_gb = DEFAULT_MAX_DATABASE_SIZE_GB

        return {
            "max_messages": self._normalize_limit(max_messages, DEFAULT_MAX_MESSAGE_RECORDS),
            "max_alerts": self._normalize_limit(max_alerts, DEFAULT_MAX_ALERT_RECORDS),
            "max_database_size_bytes": self._normalize_limit(
                int(max_database_size_gb * 1024 * 1024 * 1024),
                DEFAULT_MAX_DATABASE_SIZE_GB * 1024 * 1024 * 1024,
            ),
        }

    async def cleanup_expired_alerts(
        self,
        retention_days: Optional[int] = None,
        max_alerts: Optional[int] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """按数量上限清理告警数据。

        retention_days 仅保留为兼容旧接口，当前不再按天清理。
        """
        limits = await self._get_configured_limits()
        max_alerts = self._normalize_limit(max_alerts, limits["max_alerts"])
        logger.info(f"开始按数量清理告警数据（最多保留 {max_alerts} 条）")

        async with AsyncSessionLocal() as db:
            try:
                total_alerts = (await db.execute(select(func.count(Alert.id)))).scalar() or 0
                total_to_delete = max(0, total_alerts - max_alerts)

                if total_to_delete == 0:
                    logger.info("告警数量未超过上限，无需清理")
                    return {
                        "success": True,
                        "cleanup_mode": "count",
                        "max_alerts": max_alerts,
                        "total_alerts": total_alerts,
                        "deleted_count": 0,
                        "dry_run": dry_run,
                    }

                if dry_run:
                    logger.info(f"[演练模式] 将删除最旧的 {total_to_delete} 条告警")
                    return {
                        "success": True,
                        "cleanup_mode": "count",
                        "max_alerts": max_alerts,
                        "total_alerts": total_alerts,
                        "deleted_count": total_to_delete,
                        "dry_run": True,
                        "message": f"将删除最旧的 {total_to_delete} 条告警",
                    }

                total_deleted = 0
                iteration = 0
                while total_deleted < total_to_delete and iteration < MAX_DELETE_BATCHES:
                    iteration += 1
                    limit = min(DELETE_BATCH_SIZE, total_to_delete - total_deleted)
                    batch_ids = (
                        await db.execute(
                            select(Alert.id)
                            .order_by(Alert.created_at.asc(), Alert.id.asc())
                            .limit(limit)
                        )
                    ).scalars().all()

                    if not batch_ids:
                        break

                    await db.execute(delete(NotificationLog).where(NotificationLog.alert_id.in_(batch_ids)))
                    await db.execute(
                        update(Message)
                        .where(Message.alert_id.in_(batch_ids))
                        .values(alert_id=None)
                    )
                    await db.execute(delete(Alert).where(Alert.id.in_(batch_ids)))

                    batch_deleted = len(batch_ids)
                    total_deleted += batch_deleted
                    await db.commit()

                    logger.info(f"已删除最旧告警 {total_deleted}/{total_to_delete} 条...")
                    await asyncio.sleep(0.1)

                if iteration >= MAX_DELETE_BATCHES:
                    logger.warning(f"已达到最大迭代次数 {MAX_DELETE_BATCHES}，停止删除")

                self._invalidate_stats_cache()
                logger.info(f"告警数据清理完成，共删除 {total_deleted} 条记录")
                return {
                    "success": True,
                    "cleanup_mode": "count",
                    "max_alerts": max_alerts,
                    "total_alerts": total_alerts,
                    "deleted_count": total_deleted,
                    "dry_run": False,
                }

            except Exception as e:
                logger.error(f"清理告警数据失败: {e}")
                await db.rollback()
                return {"success": False, "error": str(e), "message": f"清理失败: {str(e)}"}

    async def cleanup_expired_messages(
        self,
        retention_days: Optional[int] = None,
        max_messages: Optional[int] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """按数量上限清理消息数据。

        删除消息时会先删除这些消息关联的告警和通知日志，保证外键一致。
        retention_days 仅保留为兼容旧接口，当前不再按天清理。
        """
        limits = await self._get_configured_limits()
        max_messages = self._normalize_limit(max_messages, limits["max_messages"])
        logger.info(f"开始按数量清理消息数据（最多保留 {max_messages} 条）")

        async with AsyncSessionLocal() as db:
            try:
                total_messages = (await db.execute(select(func.count(Message.id)))).scalar() or 0
                total_to_delete = max(0, total_messages - max_messages)

                if total_to_delete == 0:
                    logger.info("消息数量未超过上限，无需清理")
                    return {
                        "success": True,
                        "cleanup_mode": "count",
                        "max_messages": max_messages,
                        "total_messages": total_messages,
                        "deleted_count": 0,
                        "dry_run": dry_run,
                    }

                if dry_run:
                    logger.info(f"[演练模式] 将删除最旧的 {total_to_delete} 条消息")
                    return {
                        "success": True,
                        "cleanup_mode": "count",
                        "max_messages": max_messages,
                        "total_messages": total_messages,
                        "deleted_count": total_to_delete,
                        "dry_run": True,
                        "message": f"将删除最旧的 {total_to_delete} 条消息",
                    }

                total_deleted = 0
                iteration = 0
                while total_deleted < total_to_delete and iteration < MAX_DELETE_BATCHES:
                    iteration += 1
                    limit = min(DELETE_BATCH_SIZE, total_to_delete - total_deleted)
                    batch_ids = (
                        await db.execute(
                            select(Message.id)
                            .order_by(Message.created_at.asc(), Message.id.asc())
                            .limit(limit)
                        )
                    ).scalars().all()

                    if not batch_ids:
                        break

                    alert_ids = (
                        await db.execute(select(Alert.id).where(Alert.message_id.in_(batch_ids)))
                    ).scalars().all()
                    if alert_ids:
                        await db.execute(delete(NotificationLog).where(NotificationLog.alert_id.in_(alert_ids)))
                        await db.execute(delete(Alert).where(Alert.id.in_(alert_ids)))

                    await db.execute(delete(Message).where(Message.id.in_(batch_ids)))

                    batch_deleted = len(batch_ids)
                    total_deleted += batch_deleted
                    await db.commit()

                    logger.info(f"已删除最旧消息 {total_deleted}/{total_to_delete} 条...")
                    await asyncio.sleep(0.1)

                if iteration >= MAX_DELETE_BATCHES:
                    logger.warning(f"已达到最大迭代次数 {MAX_DELETE_BATCHES}，停止删除")

                self._invalidate_stats_cache()
                logger.info(f"消息数据清理完成，共删除 {total_deleted} 条记录")
                return {
                    "success": True,
                    "cleanup_mode": "count",
                    "max_messages": max_messages,
                    "total_messages": total_messages,
                    "deleted_count": total_deleted,
                    "dry_run": False,
                }

            except Exception as e:
                logger.error(f"清理消息数据失败: {e}")
                await db.rollback()
                return {"success": False, "error": str(e), "message": f"清理失败: {str(e)}"}

    async def cleanup_all(
        self,
        retention_days: Optional[int] = None,
        max_messages: Optional[int] = None,
        max_alerts: Optional[int] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """按数量上限清理所有数据（告警和消息）。"""
        logger.info("开始按数量上限清理所有数据...")

        alert_result = await self.cleanup_expired_alerts(
            retention_days=retention_days,
            max_alerts=max_alerts,
            dry_run=dry_run,
        )
        message_result = await self.cleanup_expired_messages(
            retention_days=retention_days,
            max_messages=max_messages,
            dry_run=dry_run,
        )

        return {
            "success": alert_result.get("success", True) and message_result.get("success", True),
            "cleanup_mode": "count",
            "alerts": alert_result,
            "messages": message_result,
            "total_deleted": alert_result.get("deleted_count", 0) + message_result.get("deleted_count", 0),
        }

    async def get_cleanup_stats(
        self,
        max_messages: Optional[int] = None,
        max_alerts: Optional[int] = None,
    ) -> Dict[str, Any]:
        """获取清理统计信息（不执行清理）"""
        current_time = time.time()
        use_cache = max_messages is None and max_alerts is None
        if use_cache and self._stats_cache is not None and current_time - self._stats_cache_time < self._stats_cache_ttl:
            logger.debug("使用缓存的清理统计数据")
            return self._stats_cache

        limits = await self._get_configured_limits()
        max_messages = self._normalize_limit(max_messages, limits["max_messages"])
        max_alerts = self._normalize_limit(max_alerts, limits["max_alerts"])
        max_database_size_bytes = limits["max_database_size_bytes"]

        async with AsyncSessionLocal() as db:
            try:
                stats_query = text("""
                    SELECT
                        GREATEST((SELECT COUNT(*) FROM alerts) - :max_alerts, 0) AS expired_alerts,
                        GREATEST((SELECT COUNT(*) FROM messages) - :max_messages, 0) AS expired_messages,
                        (SELECT COUNT(*) FROM alerts) AS total_alerts,
                        (SELECT COUNT(*) FROM messages) AS total_messages
                """)
                result = await db.execute(stats_query, {
                    "max_alerts": max_alerts,
                    "max_messages": max_messages,
                })
                row = result.fetchone()

                expired_alerts = row[0] or 0 if row else 0
                expired_messages = row[1] or 0 if row else 0
                total_alerts = row[2] or 0 if row else 0
                total_messages = row[3] or 0 if row else 0

                db_size = await self._get_database_size()
                table_sizes = await self._get_table_sizes()
                message_bytes_per_row = self._estimate_bytes_per_row(table_sizes.get("messages", 0), total_messages)
                alert_bytes_per_row = self._estimate_bytes_per_row(table_sizes.get("alerts", 0), total_alerts)
                estimated_limit_bytes = int(
                    message_bytes_per_row * max_messages +
                    alert_bytes_per_row * max_alerts +
                    sum(size for name, size in table_sizes.items() if name not in {"messages", "alerts"})
                )

                stats = {
                    "cleanup_mode": "count",
                    "retention_days": 0,
                    "cutoff_time": "count-based",
                    "limits": {
                        "max_messages": max_messages,
                        "max_alerts": max_alerts,
                        "max_database_size_bytes": max_database_size_bytes,
                        "max_database_size_gb": round(max_database_size_bytes / 1024 / 1024 / 1024, 1),
                    },
                    "expired": {
                        "alerts": expired_alerts,
                        "messages": expired_messages,
                        "total": expired_alerts + expired_messages,
                    },
                    "total": {
                        "alerts": total_alerts,
                        "messages": total_messages,
                    },
                    "database_size_bytes": int(db_size),
                    "database_size_mb": round(float(db_size) / 1024 / 1024, 1) if db_size else 0.0,
                    "database_size_gb": round(float(db_size) / 1024 / 1024 / 1024, 3) if db_size else 0.0,
                    "estimated_limit_size_bytes": estimated_limit_bytes,
                    "estimated_limit_size_gb": round(estimated_limit_bytes / 1024 / 1024 / 1024, 1),
                    "estimated_bytes_per_row": {
                        "messages": round(message_bytes_per_row, 1),
                        "alerts": round(alert_bytes_per_row, 1),
                    },
                    "within_database_limit": int(db_size) <= max_database_size_bytes,
                }

                if use_cache:
                    self._stats_cache = stats
                    self._stats_cache_time = current_time
                return stats

            except Exception as e:
                logger.error(f"获取清理统计失败: {e}")
                return {"error": str(e)}

    async def _get_database_size(self) -> float:
        """获取数据库大小"""
        try:
            from app.core.config import settings
            db_name = settings.MYSQL_DATABASE if hasattr(settings, "MYSQL_DATABASE") else "tg_monitor"

            async with AsyncSessionLocal() as db:
                size_result = await db.execute(text(
                    "SELECT SUM(data_length + index_length) "
                    "FROM information_schema.TABLES WHERE table_schema = :db"
                ), {"db": db_name})
                return size_result.scalar() or 0
        except Exception as e:
            logger.warning(f"获取数据库大小失败: {e}")
            return 0

    async def _get_table_sizes(self) -> Dict[str, int]:
        """获取当前数据库各表大小"""
        try:
            from app.core.config import settings
            db_name = settings.MYSQL_DATABASE if hasattr(settings, "MYSQL_DATABASE") else "tg_monitor"

            async with AsyncSessionLocal() as db:
                result = await db.execute(text("""
                    SELECT table_name, COALESCE(data_length + index_length, 0) AS bytes
                    FROM information_schema.TABLES
                    WHERE table_schema = :db
                """), {"db": db_name})
                return {row[0]: int(row[1] or 0) for row in result.fetchall()}
        except Exception as e:
            logger.warning(f"获取表大小失败: {e}")
            return {}

    def _estimate_bytes_per_row(self, table_size: int, row_count: int) -> float:
        if row_count <= 0:
            return 0.0
        return float(table_size) / float(row_count)

    async def start_auto_cleanup(self):
        """启动自动清理任务（后台运行）"""
        if self._running:
            logger.warning("自动清理任务已在运行中")
            return

        self._running = True
        logger.info("启动自动清理任务")

        while self._running:
            try:
                from app.api.settings import get_settings_snapshot
                try:
                    async with AsyncSessionLocal() as db:
                        settings_snapshot = await get_settings_snapshot(db)
                    auto_cleanup = getattr(settings_snapshot, "auto_cleanup_expired_data", False)
                except AttributeError:
                    logger.warning("无法获取自动清理配置，默认禁用")
                    auto_cleanup = False

                if not auto_cleanup:
                    await asyncio.sleep(3600)
                    continue

                result = await self.cleanup_all()
                if result.get("success"):
                    deleted = result.get("total_deleted", 0)
                    if deleted > 0:
                        logger.info(f"自动清理完成，删除了 {deleted} 条超限数据")

                await asyncio.sleep(86400)

            except Exception as e:
                logger.error(f"自动清理任务出错: {e}")
                await asyncio.sleep(3600)

    def stop_auto_cleanup(self):
        """停止自动清理任务"""
        self._running = False
        logger.info("自动清理任务已停止")


data_cleanup_service = DataCleanupService()
