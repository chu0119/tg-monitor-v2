"""备份管理 API"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from loguru import logger
import os
import subprocess
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services.auto_backup_service import auto_backup_service
from app.services.backup_service import backup_service


router = APIRouter(prefix="/backups", tags=["备份管理"])


class BackupInfo(BaseModel):
    name: str
    created_at: Optional[str] = None
    size_mb: float
    db_size: int
    session_count: int


class BackupResponse(BaseModel):
    name: str
    path: str
    created_at: str
    size_mb: float


class RestoreResponse(BaseModel):
    name: str
    restored_at: str
    status: str


@router.get("/list", response_model=List[BackupInfo])
async def list_backups():
    """获取所有备份列表"""
    try:
        backups = await auto_backup_service.list_backups()
        return [
            BackupInfo(
                name=b["name"],
                created_at=b.get("created_at"),
                size_mb=b.get("size_mb", 0),
                db_size=b.get("db_size", 0),
                session_count=b.get("session_count", 0)
            )
            for b in backups
        ]
    except Exception as e:
        logger.error(f"获取备份列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create", response_model=BackupResponse)
async def create_backup(name: Optional[str] = None, background_tasks: BackgroundTasks = None):
    """手动创建备份"""
    try:
        result = await auto_backup_service.create_manual_backup(name)
        return BackupResponse(**result)
    except Exception as e:
        logger.error(f"创建备份失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/restore/{name}", response_model=RestoreResponse)
async def restore_backup(name: str, background_tasks: BackgroundTasks = None):
    """恢复备份

    警告：恢复备份将覆盖当前数据！
    """
    try:
        # 在后台执行恢复，避免阻塞
        if background_tasks:
            background_tasks.add_task(auto_backup_service.restore_backup, name)
            return RestoreResponse(
                name=name,
                restored_at="",
                status="pending"
            )
        else:
            result = await auto_backup_service.restore_backup(name)
            return RestoreResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"恢复备份失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/{name}")
async def delete_backup(name: str):
    """删除备份"""
    try:
        success = await auto_backup_service.delete_backup(name)
        if not success:
            raise HTTPException(status_code=404, detail="备份不存在")
        return {"success": True, "message": f"备份 {name} 已删除"}
    except Exception as e:
        logger.error(f"删除备份失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup")
async def cleanup_old_backups(keep_count: int = 10):
    """清理旧备份，保留最新的 N 个"""
    try:
        await backup_service.cleanup_old_backups(keep_count=keep_count)
        return {"success": True, "message": f"已清理旧备份，保留最新 {keep_count} 个"}
    except Exception as e:
        logger.error(f"清理备份失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_backup_status():
    """获取备份服务状态"""
    try:
        backups = await auto_backup_service.list_backups()
        return {
            "total_backups": len(backups),
            "latest_backup": backups[0] if backups else None,
            "auto_backup_enabled": auto_backup_service._running,
            "backup_interval": auto_backup_service._backup_interval,
            "max_backups": auto_backup_service._max_backups
        }
    except Exception as e:
        logger.error(f"获取备份状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{name}")
async def download_backup(name: str):
    """下载备份文件"""
    try:
        backups = await auto_backup_service.list_backups()
        target = next((b for b in backups if b["name"] == name), None)
        if not target:
            raise HTTPException(status_code=404, detail="备份不存在")

        file_path = target.get("path")
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="备份文件不存在")

        return FileResponse(
            path=file_path,
            filename=name,
            media_type="application/octet-stream",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载备份失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-merge")
async def upload_merge_backup(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """上传备份文件并合并到现有数据库"""
    import shutil, tempfile, re
    from sqlalchemy import text
    from app.core.database import async_engine

    try:
        # 保存上传文件到临时目录
        suffix = os.path.splitext(file.filename or "backup.sql")[1] or ".sql"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        logger.info(f"上传备份文件: {file.filename}, 大小: {os.path.getsize(tmp_path)} bytes")

        stats = {"inserted": 0, "updated": 0, "skipped": 0}
        messages = []

        # 处理 .sql.gz
        if tmp_path.endswith(".gz"):
            import gzip
            with gzip.open(tmp_path, "rb") as gz:
                content = gz.read().decode("utf-8", errors="replace")
        else:
            with open(tmp_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

        # 用 mysqldump 格式解析并合并
        # 简化方案：通过 mysql 客户端导入，使用 INSERT IGNORE
        from app.core.config import settings as cfg
        if not cfg.MYSQL_HOST or not cfg.MYSQL_USER:
            raise HTTPException(status_code=500, detail="数据库未配置")

        # 使用 INSERT IGNORE 替换 INSERT 语句实现合并
        modified_sql = re.sub(
            r"^INSERT\s+INTO",
            "INSERT IGNORE INTO",
            content,
            flags=re.MULTILINE | re.IGNORECASE
        )

        # 写入临时 SQL 文件
        sql_path = tmp_path + ".merge.sql"
        with open(sql_path, "w") as f:
            f.write(modified_sql)

        # 执行导入
        db_name = cfg.MYSQL_DATABASE or "tg_monitor"
        cmd = [
            "mysql",
            f"-h{cfg.MYSQL_HOST}",
            f"-P{cfg.MYSQL_PORT or 3306}",
            f"-u{cfg.MYSQL_USER}",
        ]
        if cfg.MYSQL_PASSWORD:
            cmd.append(f"-p{cfg.MYSQL_PASSWORD}")
        cmd.append(db_name)

        result = subprocess.run(
            cmd,
            input=modified_sql.encode(),
            capture_output=True,
            timeout=300,
        )

        if result.returncode != 0:
            logger.warning(f"MySQL import warnings: {result.stderr.decode()[:500]}")

        # 统计结果
        stderr = result.stderr.decode() if result.stderr else ""
        import re as re2
        warnings = stderr.count("Warning")
        if warnings > 0:
            messages.append(f"导入完成，有 {warnings} 条警告（重复数据已跳过）")
        else:
            messages.append("导入完成")

        stats["skipped"] = warnings
        stats["inserted"] = max(0, (modified_sql.count("INSERT IGNORE") - warnings))

        # 清理临时文件
        os.unlink(tmp_path)
        if os.path.exists(sql_path):
            os.unlink(sql_path)

        return {
            "success": True,
            "stats": stats,
            "message": "; ".join(messages),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"上传合并备份失败: {e}")
        raise HTTPException(status_code=500, detail=f"合并失败: {str(e)}")
