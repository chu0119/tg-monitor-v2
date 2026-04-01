"""备份管理 API"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
from loguru import logger

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
