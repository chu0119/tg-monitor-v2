"""数据清理服务 - 自动清理过期的告警和消息数据"""
import asyncio
from datetime import timedelta
from typing import Dict, Any, Optional
from loguru import logger
from sqlalchemy import select, delete, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.alert import Alert
from app.models.message import Message
from app.utils import now_utc


class DataCleanupService:
    """数据清理服务"""

    def __init__(self):
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        # 缓存整个清理统计结果（60秒）
        self._stats_cache: Optional[Dict[str, Any]] = None
        self._stats_cache_time: float = 0
        self._stats_cache_ttl: int = 60  # 缓存60秒

    async def cleanup_expired_alerts(
        self,
        retention_days: Optional[int] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """清理过期的告警数据

        Args:
            retention_days: 保留天数，None 则使用系统配置
            dry_run: 是否为演练模式（不实际删除）

        Returns:
            清理统计信息
            
        清理规则：
        - 已解决（resolved）、已忽略（ignored）、误报（false_positive）的告警超过 30 天后删除
        - 待处理（pending）的告警保留 90 天
        """
        # 计算不同状态的过期时间点
        resolved_cutoff = now_utc() - timedelta(days=30)  # 已解决/忽略/误报保留30天
        pending_cutoff = now_utc() - timedelta(days=90)   # 待处理保留90天

        logger.info(f"开始清理过期告警数据（已解决/忽略/误报: 30天前，待处理: 90天前）")

        async with AsyncSessionLocal() as db:
            try:
                total_to_delete = 0
                stats_by_status = {}
                
                # 统计各状态要删除的数据
                # 1. 已解决/忽略/误报超过30天的
                for status in ['resolved', 'ignored', 'false_positive']:
                    count_query = select(func.count(Alert.id)).where(
                        Alert.status == status,
                        Alert.created_at < resolved_cutoff
                    )
                    count_result = await db.execute(count_query)
                    count = count_result.scalar() or 0
                    stats_by_status[status] = count
                    total_to_delete += count

                # 2. 待处理超过90天的
                count_query = select(func.count(Alert.id)).where(
                    Alert.status == 'pending',
                    Alert.created_at < pending_cutoff
                )
                count_result = await db.execute(count_query)
                count = count_result.scalar() or 0
                stats_by_status['pending'] = count
                total_to_delete += count

                if total_to_delete == 0:
                    logger.info("没有需要清理的过期告警数据")
                    return {
                        "success": True,
                        "cutoff_times": {
                            "resolved_ignored_false_positive": resolved_cutoff.isoformat(),
                            "pending": pending_cutoff.isoformat()
                        },
                        "deleted_count": 0,
                        "stats_by_status": stats_by_status,
                        "dry_run": dry_run
                    }

                if dry_run:
                    logger.info(f"[演练模式] 将删除 {total_to_delete} 条过期告警: {stats_by_status}")
                    return {
                        "success": True,
                        "cutoff_times": {
                            "resolved_ignored_false_positive": resolved_cutoff.isoformat(),
                            "pending": pending_cutoff.isoformat()
                        },
                        "deleted_count": total_to_delete,
                        "stats_by_status": stats_by_status,
                        "dry_run": True,
                        "message": f"将删除 {total_to_delete} 条过期告警"
                    }

                # 实际删除 - 分批删除以避免锁表
                batch_size = 1000
                max_iterations = 200  # 最多删除 20 万条
                total_deleted = 0
                iteration = 0

                # 分状态删除
                # 1. 删除已解决/忽略/误报超过30天的
                for status in ['resolved', 'ignored', 'false_positive']:
                    status_deleted = 0
                    while iteration < max_iterations:
                        iteration += 1
                        batch_ids_query = select(Alert.id).where(
                            Alert.status == status,
                            Alert.created_at < resolved_cutoff
                        ).limit(batch_size)
                        batch_ids = (await db.execute(batch_ids_query)).scalars().all()
                        if not batch_ids:
                            break
                        await db.execute(delete(Alert).where(Alert.id.in_(batch_ids)))
                        batch_deleted = len(batch_ids)
                        total_deleted += batch_deleted
                        status_deleted += batch_deleted

                        await db.commit()

                        if batch_deleted < batch_size:
                            break

                        logger.info(f"已删除 {status} 状态告警 {status_deleted} 条...")
                        await asyncio.sleep(0.1)

                # 2. 删除待处理超过90天的
                pending_deleted = 0
                while iteration < max_iterations:
                    iteration += 1
                    batch_ids_query = select(Alert.id).where(
                        Alert.status == 'pending',
                        Alert.created_at < pending_cutoff
                    ).limit(batch_size)
                    batch_ids = (await db.execute(batch_ids_query)).scalars().all()
                    if not batch_ids:
                        break
                    await db.execute(delete(Alert).where(Alert.id.in_(batch_ids)))
                    batch_deleted = len(batch_ids)
                    total_deleted += batch_deleted
                    pending_deleted += batch_deleted

                    await db.commit()

                    if batch_deleted < batch_size:
                        break

                    logger.info(f"已删除 pending 状态告警 {pending_deleted} 条...")
                    await asyncio.sleep(0.1)

                if iteration >= max_iterations:
                    logger.warning(f"已达到最大迭代次数 {max_iterations}，停止删除")

                logger.info(f"告警数据清理完成，共删除 {total_deleted} 条记录")

                return {
                    "success": True,
                    "cutoff_times": {
                        "resolved_ignored_false_positive": resolved_cutoff.isoformat(),
                        "pending": pending_cutoff.isoformat()
                    },
                    "deleted_count": total_deleted,
                    "stats_by_status": stats_by_status,
                    "dry_run": False
                }

            except Exception as e:
                logger.error(f"清理告警数据失败: {e}")
                await db.rollback()
                return {
                    "success": False,
                    "error": str(e),
                    "message": f"清理失败: {str(e)}"
                }

    async def cleanup_expired_messages(
        self,
        retention_days: Optional[int] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """清理过期的消息数据（仅删除没有关联告警的消息）

        Args:
            retention_days: 保留天数，None 则使用系统配置
            dry_run: 是否为演练模式

        Returns:
            清理统计信息
        """
        if retention_days is None:
            try:
                from app.api.settings import _global_settings
                retention_days = _global_settings.data_retention_days
            except (ImportError, AttributeError) as e:
                logger.warning(f"获取全局数据保留配置失败: {e}，使用默认值 90 天")
                retention_days = 90

        if retention_days is None or retention_days <= 0:
            retention_days = 90

        cutoff_time = now_utc() - timedelta(days=retention_days)

        logger.info(f"开始清理 {retention_days} 天前的消息数据（截止时间: {cutoff_time}）")

        async with AsyncSessionLocal() as db:
            try:
                # 统计要删除的消息（没有关联告警的过期消息）
                from app.models.message import Message as MessageModel

                count_query = select(func.count(MessageModel.id)).where(
                    MessageModel.date < cutoff_time,
                    MessageModel.alert_id == None  # 只删除没有告警的消息
                )
                count_result = await db.execute(count_query)
                total_to_delete = count_result.scalar() or 0

                if total_to_delete == 0:
                    logger.info("没有需要清理的过期消息数据")
                    return {
                        "success": True,
                        "retention_days": retention_days,
                        "cutoff_time": cutoff_time.isoformat(),
                        "deleted_count": 0,
                        "dry_run": dry_run
                    }

                if dry_run:
                    logger.info(f"[演练模式] 将删除 {total_to_delete} 条过期消息")
                    return {
                        "success": True,
                        "retention_days": retention_days,
                        "cutoff_time": cutoff_time.isoformat(),
                        "deleted_count": total_to_delete,
                        "dry_run": True,
                        "message": f"将删除 {total_to_delete} 条过期消息"
                    }

                # 实际删除 - 分批删除
                batch_size = 1000
                max_iterations = 100  # 最多删除 10 万条
                total_deleted = 0
                iteration = 0

                while iteration < max_iterations:
                    iteration += 1
                    # SQLAlchemy 2.x: use subquery for batch delete
                    batch_ids_query = select(MessageModel.id).where(
                        MessageModel.date < cutoff_time,
                        MessageModel.alert_id == None
                    ).limit(batch_size)
                    batch_ids = (await db.execute(batch_ids_query)).scalars().all()

                    if not batch_ids:
                        break

                    await db.execute(
                        delete(MessageModel).where(MessageModel.id.in_(batch_ids))
                    )
                    batch_deleted = len(batch_ids)
                    total_deleted += batch_deleted

                    await db.commit()

                    if batch_deleted < batch_size:
                        break

                    logger.info(f"已删除 {total_deleted}/{total_to_delete} 条消息...")
                    await asyncio.sleep(0.1)

                if iteration >= max_iterations:
                    logger.warning(f"已达到最大迭代次数 {max_iterations}，停止删除")

                logger.info(f"消息数据清理完成，共删除 {total_deleted} 条记录")

                return {
                    "success": True,
                    "retention_days": retention_days,
                    "cutoff_time": cutoff_time.isoformat(),
                    "deleted_count": total_deleted,
                    "dry_run": False
                }

            except Exception as e:
                logger.error(f"清理消息数据失败: {e}")
                await db.rollback()
                return {
                    "success": False,
                    "error": str(e),
                    "message": f"清理失败: {str(e)}"
                }

    async def cleanup_all(
        self,
        retention_days: Optional[int] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """清理所有过期数据（告警和消息）

        Args:
            retention_days: 保留天数
            dry_run: 是否为演练模式

        Returns:
            清理统计信息
        """
        logger.info("开始清理所有过期数据...")

        # 清理告警
        alert_result = await self.cleanup_expired_alerts(
            retention_days=retention_days,
            dry_run=dry_run
        )

        # 清理消息
        message_result = await self.cleanup_expired_messages(
            retention_days=retention_days,
            dry_run=dry_run
        )

        return {
            "success": alert_result.get("success", True) and message_result.get("success", True),
            "alerts": alert_result,
            "messages": message_result,
            "total_deleted": (
                alert_result.get("deleted_count", 0) +
                message_result.get("deleted_count", 0)
            )
        }

    async def get_cleanup_stats(self) -> Dict[str, Any]:
        """获取清理统计信息（不执行清理，只统计）带完整缓存优化"""
        import time
        current_time = time.time()

        # 检查缓存是否有效（60秒内）
        if (self._stats_cache is not None and
            current_time - self._stats_cache_time < self._stats_cache_ttl):
            logger.debug("使用缓存的清理统计数据")
            return self._stats_cache

        # 缓存过期，重新查询
        try:
            from app.api.settings import _global_settings
            retention_days = getattr(_global_settings, 'data_retention_days', None) or 90
        except (ImportError, AttributeError) as e:
            logger.warning(f"获取全局数据保留配置失败: {e}，使用默认值 90 天")
            retention_days = 90
        cutoff_time = now_utc() - timedelta(days=retention_days)

        async with AsyncSessionLocal() as db:
            try:
                from app.models.message import Message as MessageModel
                
                # 优化：使用单个复合查询获取所有统计数据
                # 这样可以减少数据库往返次数，同时避免并发问题
                from sqlalchemy import text
                
                # 使用单个 SQL 查询获取所有统计信息
                stats_query = text("""
                    SELECT 
                        (SELECT COUNT(*) FROM alerts WHERE created_at < :cutoff) as expired_alerts,
                        (SELECT COUNT(*) FROM messages WHERE date < :cutoff AND alert_id IS NULL) as expired_messages,
                        (SELECT COUNT(*) FROM alerts) as total_alerts,
                        (SELECT COUNT(*) FROM messages) as total_messages
                """)
                
                result = await db.execute(stats_query, {"cutoff": cutoff_time})
                row = result.fetchone()
                
                if row:
                    expired_alerts = row[0] or 0
                    expired_messages = row[1] or 0
                    total_alerts = row[2] or 0
                    total_messages = row[3] or 0
                else:
                    expired_alerts = 0
                    expired_messages = 0
                    total_alerts = 0
                    total_messages = 0

                # 获取数据库大小（也缓存）
                db_size = await self._get_database_size()

                stats = {
                    "retention_days": retention_days,
                    "cutoff_time": cutoff_time.isoformat(),
                    "expired": {
                        "alerts": expired_alerts,
                        "messages": expired_messages,
                        "total": expired_alerts + expired_messages
                    },
                    "total": {
                        "alerts": total_alerts,
                        "messages": total_messages
                    },
                    "database_size_bytes": int(db_size),
                    "database_size_mb": round(float(db_size) / 1024 / 1024, 1) if db_size else 0.0,
                }
                
                # 缓存结果
                self._stats_cache = stats
                self._stats_cache_time = current_time
                
                return stats

            except Exception as e:
                logger.error(f"获取清理统计失败: {e}")
                return {
                    "error": str(e)
                }

    async def _get_database_size(self) -> float:
        """获取数据库大小"""
        try:
            from app.core.config import settings
            from sqlalchemy import text

            db_name = settings.MYSQL_DB if hasattr(settings, 'MYSQL_DB') else 'tg_monitor'

            async with AsyncSessionLocal() as db:
                size_result = await db.execute(text(
                    "SELECT SUM(data_length + index_length) FROM information_schema.TABLES WHERE table_schema = :db"
                ), {"db": db_name})
                db_size = size_result.scalar() or 0
                return db_size
        except Exception as e:
            logger.warning(f"获取数据库大小失败: {e}")
            return 0

    async def start_auto_cleanup(self):
        """启动自动清理任务（后台运行）"""
        if self._running:
            logger.warning("自动清理任务已在运行中")
            return

        self._running = True
        logger.info("启动自动清理任务")

        while self._running:
            try:
                from app.api.settings import _global_settings
                # 检查是否启用自动清理
                try:
                    auto_cleanup = getattr(_global_settings, 'auto_cleanup_expired_data', False)
                except AttributeError:
                    logger.warning("无法获取自动清理配置，默认禁用")
                    auto_cleanup = False
                if not auto_cleanup:
                    await asyncio.sleep(3600)  # 每小时检查一次
                    continue

                # 执行清理
                result = await self.cleanup_all()
                if result.get("success"):
                    deleted = result.get("total_deleted", 0)
                    if deleted > 0:
                        logger.info(f"自动清理完成，删除了 {deleted} 条过期数据")

                # 等待 24 小时后再次执行
                await asyncio.sleep(86400)

            except Exception as e:
                logger.error(f"自动清理任务出错: {e}")
                # 出错后等待 1 小时再重试
                await asyncio.sleep(3600)

    def stop_auto_cleanup(self):
        """停止自动清理任务"""
        self._running = False
        logger.info("自动清理任务已停止")


# 全局清理服务实例
data_cleanup_service = DataCleanupService()
