"""系统管理 API"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import platform
import sys
import subprocess

from app.api.deps import get_db
from app.models.settings import Settings
from app.core.database import check_database_connection, init_db
from app.services.runtime_proxy_service import get_proxy_config, apply_proxy_config

router = APIRouter(prefix="/system", tags=["system"])


def _mask_password(pwd: str) -> str:
    """密码脱敏：保留前2后2，中间星号"""
    if len(pwd) <= 4:
        return "****"
    return pwd[:2] + "****" + pwd[-2:]


@router.get("/status")
async def system_status(db: AsyncSession = Depends(get_db)):
    """
    获取系统状态

    返回：
    - Python版本
    - Node版本（如果安装）
    - MySQL状态
    - 代理状态
    - 账号数量
    - 是否已初始化
    """
    try:
        # 检查数据库连接
        db_info = await check_database_connection()

        # 检查是否已初始化
        result = await db.execute(
            select(Settings).where(Settings.key_name == "initialized")
        )
        init_setting = result.scalar_one_or_none()
        is_initialized = bool(init_setting and init_setting.value == "true")

        # 获取账号数量
        from app.models.account import TelegramAccount
        result = await db.execute(select(TelegramAccount))
        account_count = len(result.scalars().all())

        # 检查代理状态（简化代理配置）
        proxy_config = await get_proxy_config(db)
        runtime_result = apply_proxy_config(proxy_config)
        proxy_status = {
            "enabled": proxy_config.get("enabled"),
            "protocol": proxy_config.get("protocol"),
            "host": proxy_config.get("host"),
            "port": proxy_config.get("port"),
            "applied": runtime_result.get("applied", False),
        }

        # 获取系统信息
        system_info = {
            "python_version": sys.version,
            "platform": platform.platform(),
            "architecture": platform.architecture()[0],
        }

        # 检查Node.js（可选）
        try:
            node_version = subprocess.check_output(
                ["node", "--version"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
            system_info["node_version"] = node_version
        except Exception:
            system_info["node_version"] = None

        return {
            "success": True,
            "initialized": is_initialized,
            "database": db_info,
            "proxy": proxy_status,
            "account_count": account_count,
            "system": system_info,
        }

    except Exception as e:
        logger.error(f"获取系统状态失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "initialized": False,
        }


@router.post("/init-db")
async def initialize_database(db: AsyncSession = Depends(get_db)):
    """
    初始化/重置数据库表

    创建所有必需的表（如果不存在）
    """
    try:
        # 初始化数据库表
        await init_db()
        logger.info("数据库表初始化完成")

        # 设置初始化标记
        result = await db.execute(
            select(Settings).where(Settings.key_name == "initialized")
        )
        setting = result.scalar_one_or_none()

        if setting:
            setting.value = "true"
        else:
            setting = Settings(
                key_name="initialized",
                value="true",
                category="system"
            )
            db.add(setting)

        await db.commit()

        return {
            "success": True,
            "message": "数据库初始化成功",
            "initialized": True
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"初始化数据库失败: {e}")
        raise HTTPException(status_code=500, detail=f"初始化失败: {str(e)}")


@router.post("/reset")
async def reset_system(
    confirm: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    重置系统（危险操作）

    清空所有配置和数据，恢复到初始状态
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="需要确认参数 confirm=true"
        )

    try:
        # 删除所有设置
        from sqlalchemy import delete
        await db.execute(delete(Settings))

        # 删除所有代理节点
        from app.models.proxy_node import ProxyNode
        await db.execute(delete(ProxyNode))

        # 不删除账号和消息数据（用户需要手动删除）

        await db.commit()
        logger.warning("系统已重置")

        return {
            "success": True,
            "message": "系统已重置，请重新配置"
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"重置系统失败: {e}")
        raise HTTPException(status_code=500, detail=f"重置失败: {str(e)}")


@router.get("/health")
async def health_check():
    """
    健康检查（轻量级）

    仅检查服务是否运行
    """
    return {
        "status": "healthy",
        "service": "TG Monitor Backend"
    }


@router.get("/version")
async def get_version():
    """
    获取版本信息
    """
    from app.core.config import settings

    return {
        "version": settings.VERSION,
        "project_name": settings.PROJECT_NAME,
    }


@router.get("/info")
async def get_system_info():
    """获取系统基本信息"""
    import time
    import psutil
    process = psutil.Process()
    uptime = int(time.time() - process.create_time())
    hours, remainder = divmod(uptime, 3600)
    minutes, seconds = divmod(remainder, 60)
    return {
        "version": settings.VERSION,
        "project_name": settings.PROJECT_NAME,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "uptime_seconds": uptime,
        "uptime_human": f"{hours}h {minutes}m {seconds}s",
        "pid": process.pid,
    }


@router.post("/test-db-connection")
async def test_database_connection():
    """
    测试数据库连接

    不依赖依赖注入，直接测试连接
    """
    try:
        db_info = await check_database_connection()

        if db_info.get("connected"):
            return {
                "success": True,
                "message": "数据库连接成功",
                "info": db_info
            }
        else:
            return {
                "success": False,
                "message": "数据库连接失败",
                "error": db_info.get("error")
            }

    except Exception as e:
        logger.error(f"测试数据库连接失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/db-config")
async def get_db_config():
    """获取数据库配置信息（密码脱敏）"""
    from app.core.config import settings as cfg
    return {
        "success": True,
        "host": cfg.MYSQL_HOST or "localhost",
        "port": cfg.MYSQL_PORT or 3306,
        "user": cfg.MYSQL_USER or "",
        "database": cfg.MYSQL_DATABASE or "tg_monitor",
        "password": _mask_password(cfg.MYSQL_PASSWORD or ""),
    }
