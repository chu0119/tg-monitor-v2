"""数据备份和恢复服务 - MySQL 版本"""
import asyncio
import aiofiles
import shutil
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from loguru import logger
from app.core.config import settings
import subprocess


class BackupService:
    """数据备份和恢复服务 - MySQL 版本"""

    def __init__(self):
        # 项目根目录
        project_root = settings.PROJECT_DIR
        # backend 目录
        backend_dir = project_root / "backend"

        self.backup_dir = backend_dir / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir = backend_dir / "sessions"
        self.env_file = backend_dir / ".env"

    async def create_backup(self, name: Optional[str] = None) -> dict:
        """创建完整备份

        Args:
            name: 备份名称，如果不指定则使用时间戳

        Returns:
            备份信息字典
        """
        if name is None:
            name = datetime.now().strftime("%Y%m%d_%H%M%S")

        backup_path = self.backup_dir / name
        backup_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"开始创建备份: {name}")

        try:
            # 1. 备份数据库
            await self._backup_database(backup_path)

            # 2. 备份会话文件
            await self._backup_sessions(backup_path)

            # 3. 备份环境配置
            await self._backup_config(backup_path)

            # 4. 创建备份元数据
            await self._create_metadata(backup_path)

            logger.info(f"备份创建成功: {backup_path}")

            return {
                "name": name,
                "path": str(backup_path),
                "created_at": datetime.now().isoformat(),
                "size_mb": self._get_dir_size(backup_path)
            }

        except Exception as e:
            logger.error(f"备份失败: {e}")
            # 清理失败的备份
            if backup_path.exists():
                shutil.rmtree(backup_path)
            raise

    async def _backup_database(self, backup_path: Path):
        """使用 mysqldump 备份 MySQL 数据库并压缩"""
        db_backup = backup_path / "tg_monitor.sql.gz"
        dump_cmd = [
            "mysqldump",
            f"-u{settings.MYSQL_USER}",
            "-h", str(settings.MYSQL_HOST),
            "-P", str(settings.MYSQL_PORT),
            str(settings.MYSQL_DATABASE),
            "--single-transaction",
            "--quick",
            "--lock-tables=false",
        ]
        gzip_cmd = ["gzip", "-c"]

        env = dict(**os.environ)
        env["MYSQL_PWD"] = settings.MYSQL_PASSWORD or ""

        dump_process = await asyncio.create_subprocess_exec(
            *dump_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        gzip_process = await asyncio.create_subprocess_exec(
            *gzip_cmd,
            stdin=dump_process.stdout,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        dump_process.stdout.close()

        gz_data, gzip_stderr = await gzip_process.communicate()
        dump_stdout, dump_stderr = await dump_process.communicate()

        if dump_process.returncode != 0:
            error_msg = dump_stderr.decode() if dump_stderr else "未知错误"
            raise Exception(f"数据库备份失败: {error_msg}")
        if gzip_process.returncode != 0:
            error_msg = gzip_stderr.decode() if gzip_stderr else "未知错误"
            raise Exception(f"备份压缩失败: {error_msg}")

        async with aiofiles.open(db_backup, "wb") as f:
            await f.write(gz_data)

        if not db_backup.exists():
            raise Exception("备份文件未创建")

        file_size_mb = db_backup.stat().st_size / 1024 / 1024
        logger.info(f"数据库备份完成（已压缩）: {file_size_mb:.2f} MB")

    async def _backup_sessions(self, backup_path: Path):
        """备份会话文件"""
        sessions_backup = backup_path / "sessions"
        sessions_backup.mkdir(exist_ok=True)

        if self.sessions_dir.exists():
            for session_file in self.sessions_dir.glob("*.session*"):
                shutil.copy2(session_file, sessions_backup / session_file.name)

            logger.info(f"会话文件备份完成: {len(list(sessions_backup.glob('*')))} 个文件")

    async def _backup_config(self, backup_path: Path):
        """备份配置文件"""
        if self.env_file.exists():
            shutil.copy2(self.env_file, backup_path / ".env")
            logger.info("配置文件备份完成")

    async def _create_metadata(self, backup_path: Path):
        """创建备份元数据"""
        # 检查压缩文件或普通文件
        db_backup_gz = backup_path / "tg_monitor.sql.gz"
        db_backup = backup_path / "tg_monitor.sql"

        if db_backup_gz.exists():
            db_size = db_backup_gz.stat().st_size
        else:
            db_size = db_backup.stat().st_size if db_backup.exists() else 0

        metadata = {
            "created_at": datetime.now().isoformat(),
            "db_size": db_size,
            "compressed": db_backup_gz.exists(),
            "session_count": len(list(self.sessions_dir.glob("*.session"))) if self.sessions_dir.exists() else 0,
        }

        metadata_file = backup_path / "metadata.json"
        async with aiofiles.open(metadata_file, 'w') as f:
            import json
            await f.write(json.dumps(metadata, indent=2, ensure_ascii=False))

    def _get_dir_size(self, path: Path) -> float:
        """获取目录大小（MB）"""
        total = 0
        for item in path.rglob('*'):
            if item.is_file():
                total += item.stat().st_size
        return round(total / 1024 / 1024, 2)

    async def restore_backup(self, name: str) -> dict:
        """恢复备份

        Args:
            name: 备份名称

        Returns:
            恢复结果
        """
        backup_path = self.backup_dir / name

        if not backup_path.exists():
            raise ValueError(f"备份不存在: {name}")

        logger.info(f"开始恢复备份: {name}")

        try:
            # 停止服务（如果需要）
            # 注意：这里需要根据实际情况处理

            # 1. 恢复数据库
            await self._restore_database(backup_path)

            # 2. 恢复会话文件
            await self._restore_sessions(backup_path)

            # 3. 恢复配置文件
            await self._restore_config(backup_path)

            logger.info(f"备份恢复成功: {name}")

            return {
                "name": name,
                "restored_at": datetime.now().isoformat(),
                "status": "success"
            }

        except Exception as e:
            logger.error(f"恢复失败: {e}")
            raise

    async def _restore_database(self, backup_path: Path):
        """使用 mysql 命令恢复数据库（支持压缩文件）"""
        # 优先尝试压缩文件，再尝试普通文件
        db_backup_gz = backup_path / "tg_monitor.sql.gz"
        db_backup = backup_path / "tg_monitor.sql"

        # 确定使用哪个文件
        if db_backup_gz.exists():
            source_file = db_backup_gz
            use_gzip = True
        elif db_backup.exists():
            source_file = db_backup
            use_gzip = False
        else:
            raise FileNotFoundError("备份数据库文件不存在")

        # 使用 mysql 命令恢复
        mysql_cmd = [
            "mysql",
            f"-u{settings.MYSQL_USER}",
            f"-p{settings.MYSQL_PASSWORD}",
            "-h", settings.MYSQL_HOST,
            "-P", str(settings.MYSQL_PORT),
            settings.MYSQL_DATABASE
        ]

        if use_gzip:
            # 解压并恢复
            gzip_cmd = ["gunzip", "-c", str(source_file)]
            process1 = await asyncio.create_subprocess_exec(
                *gzip_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            process2 = await asyncio.create_subprocess_exec(
                *mysql_cmd,
                stdin=process1.stdout,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process2.communicate()
            _, gzip_stderr = await process1.communicate()

            if process1.returncode != 0:
                error_msg = gzip_stderr.decode() if gzip_stderr else "未知错误"
                raise Exception(f"解压失败: {error_msg}")
        else:
            # 直接恢复
            with open(source_file, 'r') as f:
                sql_content = f.read()

            process = await asyncio.create_subprocess_exec(
                *mysql_cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate(input=sql_content.encode())

        if process2.returncode if use_gzip else process.returncode != 0:
            error_msg = stderr.decode() if stderr else "未知错误"
            raise Exception(f"数据库恢复失败: {error_msg}")

        logger.info(f"数据库已恢复")

    async def _restore_sessions(self, backup_path: Path):
        """恢复会话文件"""
        sessions_backup = backup_path / "sessions"

        if not sessions_backup.exists():
            logger.warning("备份中无会话文件，跳过")
            return

        # 备份当前会话
        if self.sessions_dir.exists():
            current_backup = self.sessions_dir.with_suffix('.sessions.bak')
            shutil.copytree(self.sessions_dir, current_backup, dirs_exist_ok=True)
            logger.info(f"当前会话已备份到: {current_backup}")

        # 恢复会话
        self.sessions_dir.mkdir(exist_ok=True)
        for session_file in sessions_backup.glob("*"):
            shutil.copy2(session_file, self.sessions_dir / session_file.name)

        logger.info(f"会话文件已恢复: {len(list(sessions_backup.glob('*')))} 个文件")

    async def _restore_config(self, backup_path: Path):
        """恢复配置文件"""
        env_backup = backup_path / ".env"

        if env_backup.exists():
            shutil.copy2(env_backup, self.env_file)
            logger.info("配置文件已恢复")
        else:
            logger.warning("备份中无配置文件，跳过")

    async def list_backups(self) -> List[dict]:
        """列出所有备份"""
        backups = []

        for backup_path in self.backup_dir.iterdir():
            if backup_path.is_dir():
                metadata_file = backup_path / "metadata.json"

                metadata = {}
                if metadata_file.exists():
                    async with aiofiles.open(metadata_file, 'r') as f:
                        import json
                        metadata = json.loads(await f.read())

                backups.append({
                    "name": backup_path.name,
                    "created_at": metadata.get("created_at"),
                    "size_mb": self._get_dir_size(backup_path),
                    "db_size": metadata.get("db_size", 0),
                    "session_count": metadata.get("session_count", 0)
                })

        # 按创建时间倒序排列（处理 None 值）
        backups.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return backups

    async def delete_backup(self, name: str) -> bool:
        """删除备份"""
        backup_path = self.backup_dir / name

        if not backup_path.exists():
            return False

        shutil.rmtree(backup_path)
        logger.info(f"备份已删除: {name}")
        return True

    async def cleanup_old_backups(self, keep_count: int = 10):
        """清理旧备份，保留最新的 N 个"""
        backups = await self.list_backups()

        if len(backups) <= keep_count:
            return

        to_delete = backups[keep_count:]
        for backup in to_delete:
            await self.delete_backup(backup["name"])

        logger.info(f"已清理 {len(to_delete)} 个旧备份，保留最新 {keep_count} 个")


# 全局备份服务实例
backup_service = BackupService()
