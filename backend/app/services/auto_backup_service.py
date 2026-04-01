"""自动备份服务 - 定期备份数据"""
import asyncio
import os
from datetime import datetime
from pathlib import Path
from loguru import logger
from app.services.backup_service import backup_service


class AutoBackupService:
    """自动备份服务"""

    def __init__(self):
        self._running = False
        self._backup_task: asyncio.Task | None = None
        self._backup_interval = 604800  # 7天备份一次
        self._max_backups = 4  # 保留4个备份（28天 = 约1个月数据）
        self._lock_file = Path("/tmp/tg-auto-backup.lock")
        self._lock_fd = None

    async def start_auto_backup(self):
        """启动自动备份"""
        if self._running:
            logger.warning("自动备份已在运行")
            return

        # 使用文件锁确保只有一个进程运行备份服务
        # 这解决了 Gunicorn 多 Worker 模式下重复启动的问题
        try:
            import fcntl
            self._lock_fd = open(self._lock_file, 'w')
            fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lock_fd.write(str(os.getpid()))
            self._lock_fd.flush()
            logger.info("获取备份服务锁成功")
        except (IOError, BlockingIOError):
            logger.warning("备份服务已被其他进程启动，跳过")
            if self._lock_fd:
                self._lock_fd.close()
                self._lock_fd = None
            return
        except ImportError:
            # Windows 不支持 fcntl，降级到简单检查
            if self._lock_file.exists():
                logger.warning("备份服务锁文件存在，跳过启动")
                return

        self._running = True
        self._backup_task = asyncio.create_task(self._backup_loop())
        logger.info(f"自动备份已启动 (间隔: {self._backup_interval}s, 保留: {self._max_backups}个)")

    async def stop_auto_backup(self):
        """停止自动备份"""
        self._running = False
        if self._backup_task and not self._backup_task.done():
            self._backup_task.cancel()
            try:
                await self._backup_task
            except asyncio.CancelledError:
                logger.debug("备份任务已取消")
            except Exception as e:
                logger.error(f"停止备份任务时发生错误: {e}")

        # 释放锁文件
        if self._lock_fd:
            try:
                self._lock_fd.close()
            except Exception as e:
                logger.error(f"关闭锁文件失败: {e}")
            self._lock_fd = None

        try:
            if self._lock_file.exists():
                self._lock_file.unlink()
        except Exception as e:
            logger.error(f"删除锁文件失败: {e}")

        logger.info("自动备份已停止")

    async def _backup_loop(self):
        """备份循环"""
        try:
            # 先等待一个完整的间隔，避免启动时立即备份
            # 这解决了 Gunicorn 多 Worker 模式下重复启动的问题
            logger.info(f"首次备份将在 {self._backup_interval} 秒后执行（{self._backup_interval // 86400} 天）")
            await asyncio.sleep(self._backup_interval)

            while self._running:
                try:
                    # 执行备份
                    backup_name = datetime.now().strftime("%Y%m%d_%H%M%S")
                    result = await backup_service.create_backup(backup_name)
                    logger.info(f"自动备份完成: {result['name']} ({result['size_mb']} MB)")

                    # 清理旧备份
                    await backup_service.cleanup_old_backups(keep_count=self._max_backups)

                except Exception as e:
                    logger.error(f"自动备份失败: {e}")

                # 等待下次备份
                await asyncio.sleep(self._backup_interval)

        except asyncio.CancelledError:
            logger.info("备份循环已取消")
        except Exception as e:
            logger.error(f"备份循环异常: {e}")

    async def create_manual_backup(self, name: str = None) -> dict:
        """手动创建备份"""
        if name is None:
            name = datetime.now().strftime("%Y%m%d_%H%M%S") + "_manual"
        return await backup_service.create_backup(name)

    async def list_backups(self):
        """列出所有备份"""
        return await backup_service.list_backups()

    async def restore_backup(self, name: str):
        """恢复备份"""
        return await backup_service.restore_backup(name)

    async def delete_backup(self, name: str):
        """删除备份"""
        return await backup_service.delete_backup(name)


# 全局自动备份服务实例
auto_backup_service = AutoBackupService()
