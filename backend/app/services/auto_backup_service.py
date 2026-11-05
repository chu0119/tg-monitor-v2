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
        # 锁文件放项目内（/tmp 在部分环境不可写，且 Windows 无 /tmp）
        from app.core.config import settings
        lock_dir = Path(settings.PROJECT_DIR) / "backend"
        lock_dir.mkdir(parents=True, exist_ok=True)
        self._lock_file = lock_dir / "tg-auto-backup.lock"
        self._lock_fd = None

    async def start_auto_backup(self):
        """启动自动备份"""
        if self._running:
            logger.warning("自动备份已在运行")
            return

        # 使用文件锁确保只有一个进程运行备份服务
        try:
            import fcntl
            self._lock_fd = open(self._lock_file, 'w')
            fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lock_fd.write(str(os.getpid()))
            self._lock_fd.flush()
            logger.info("获取备份服务锁成功")
        except BlockingIOError:
            logger.warning("备份服务已被其他进程启动，跳过")
            if self._lock_fd:
                self._lock_fd.close()
                self._lock_fd = None
            return
        except ImportError:
            # Windows 不支持 fcntl：检查锁文件持有进程是否存活，崩溃残留的锁直接接管
            if self._lock_file.exists():
                stale = True
                try:
                    pid = int(self._lock_file.read_text().strip() or 0)
                    if pid and pid != os.getpid():
                        os.kill(pid, 0)  # 探测进程存活
                        stale = False
                except (ValueError, ProcessLookupError, PermissionError, OSError):
                    stale = True
                if not stale:
                    logger.warning("备份服务锁文件存在且持有进程存活，跳过启动")
                    return
                logger.warning("发现残留的备份锁文件（持有进程已不在），接管并继续")
            try:
                self._lock_fd = open(self._lock_file, 'w')
                self._lock_fd.write(str(os.getpid()))
                self._lock_fd.flush()
            except OSError as e:
                logger.warning(f"创建锁文件失败，跳过启动: {e}")
                return
        except OSError as e:
            # FileNotFoundError 等创建失败不能当成"已被占用"（旧逻辑会让自动备份静默失效）
            logger.warning(f"备份锁获取失败({e})，降级为无锁运行")
            self._lock_fd = None

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
            # 首次立即检查上次备份时间：距上次超过间隔就马上备份。
            # 旧逻辑先睡满 7 天才首次备份，进程重启周期短于间隔时永远不会有备份。
            while self._running:
                try:
                    need_backup = True
                    try:
                        backups = await backup_service.list_backups()
                        if backups:
                            from datetime import timedelta
                            latest = backups[0].get("created_at")
                            if latest:
                                from app.utils import now_utc
                                latest_dt = datetime.fromisoformat(str(latest))
                                if latest_dt.tzinfo is None:
                                    latest_dt = latest_dt.replace(tzinfo=None)
                                age = now_utc().replace(tzinfo=None) - latest_dt
                                if age < timedelta(seconds=self._backup_interval):
                                    need_backup = False
                                    logger.info(
                                        f"距上次自动备份仅 {int(age.total_seconds() // 3600)} 小时，"
                                        f"{self._backup_interval - int(age.total_seconds())} 秒后执行下次备份"
                                    )
                    except Exception as e:
                        logger.warning(f"检查上次备份时间失败，执行兜底备份: {e}")

                    if need_backup:
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
