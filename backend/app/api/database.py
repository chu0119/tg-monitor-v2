"""数据库管理 API - MySQL 配置和连接管理"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from loguru import logger

from app.core.database import (
    check_database_connection,
    init_db,
    get_database_info,
    get_table_stats,
    drop_all_tables
)
from app.core.config import settings
from app.models import (
    TelegramAccount, Conversation, Message, Sender,
    Keyword, KeywordGroup, Alert
)
from app.core.database import AsyncSessionLocal
from sqlalchemy import select, func, text

router = APIRouter(prefix="/database", tags=["数据库管理"])


class MySQLConfig(BaseModel):
    """MySQL 配置"""
    host: str = Field(..., description="MySQL 主机地址")
    port: int = Field(3306, description="MySQL 端口")
    user: str = Field(..., description="MySQL 用户名")
    password: str = Field(..., description="MySQL 密码")
    database: str = Field("tg_monitor", description="数据库名称")
    save_config: bool = Field(True, description="是否保存配置到 .env 文件")


class DatabaseStatus(BaseModel):
    """数据库状态"""
    configured: bool = Field(..., description="是否已配置")
    connected: bool = Field(..., description="是否连接成功")
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    error: Optional[str] = None
    connection_info: Optional[dict] = None


class DatabaseStats(BaseModel):
    """数据库统计"""
    tables: dict = Field(default_factory=dict)
    total_messages: int = 0
    total_alerts: int = 0
    total_conversations: int = 0
    total_senders: int = 0
    total_keywords: int = 0


@router.get("/status", response_model=DatabaseStatus)
async def get_database_status():
    """获取数据库连接状态"""
    try:
        # 检查是否配置
        is_configured = settings.is_database_configured()

        if not is_configured:
            return DatabaseStatus(
                configured=False,
                connected=False,
                host=settings.MYSQL_HOST,
                port=settings.MYSQL_PORT,
                database=settings.MYSQL_DATABASE,
                error="数据库未配置"
            )

        # 检查连接
        connection_info = await check_database_connection()

        return DatabaseStatus(
            configured=is_configured,
            connected=connection_info.get("connected", False),
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            database=settings.MYSQL_DATABASE,
            error=connection_info.get("error") if not connection_info.get("connected") else None,
            connection_info=connection_info
        )
    except Exception as e:
        logger.error(f"获取数据库状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-connection")
async def test_database_connection(config: MySQLConfig):
    """测试数据库连接（不保存配置）"""
    try:
        # 临时创建连接测试
        from sqlalchemy.ext.asyncio import create_async_engine

        test_url = f"mysql+aiomysql://{config.user}:{config.password}@{config.host}:{config.port}/{config.database}"
        test_engine = create_async_engine(test_url, echo=False)

        async with test_engine.begin() as conn:
            result = await conn.execute(text("SELECT 1 as test"))
            test_value = result.scalar()

            # 获取表数量
            tables_result = await conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = :db_name"
            ), {"db_name": config.database})
            table_count = tables_result.scalar()

        await test_engine.dispose()

        return {
            "success": True,
            "message": "数据库连接测试成功",
            "details": {
                "host": config.host,
                "port": config.port,
                "database": config.database,
                "table_count": table_count
            }
        }
    except Exception as e:
        logger.error(f"数据库连接测试失败: {e}")
        return {
            "success": False,
            "message": f"数据库连接测试失败: {str(e)}"
        }


@router.post("/configure")
async def configure_database(config: MySQLConfig):
    """配置数据库连接"""
    try:
        # 1. 先测试连接
        test_result = await test_database_connection(config)
        if not test_result["success"]:
            return {
                "success": False,
                "message": f"数据库连接测试失败: {test_result['message']}"
            }

        # 2. 如果要求保存配置，更新 .env 文件
        if config.save_config:
            from pathlib import Path
            import os

            env_path = settings.PROJECT_DIR / "backend" / ".env"
            env_content = ""

            if env_path.exists():
                with open(env_path, "r", encoding="utf-8") as f:
                    env_content = f.read()

            # 更新或添加配置
            lines = env_content.split("\n")
            new_lines = []
            config_vars = {
                "MYSQL_HOST": config.host,
                "MYSQL_PORT": str(config.port),
                "MYSQL_USER": config.user,
                "MYSQL_PASSWORD": config.password,
                "MYSQL_DATABASE": config.database,
            }

            existing_vars = set()

            for line in lines:
                if "=" in line and not line.strip().startswith("#"):
                    var_name = line.split("=")[0].strip()
                    existing_vars.add(var_name)
                    if var_name in config_vars:
                        new_lines.append(f"{var_name}={config_vars[var_name]}")
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)

            # 添加新配置
            for var_name, var_value in config_vars.items():
                if var_name not in existing_vars:
                    new_lines.append(f"{var_name}={var_value}")

            # 写入文件
            with open(env_path, "w", encoding="utf-8") as f:
                f.write("\n".join(new_lines))

            logger.info(f"数据库配置已保存到 {env_path}")

            # 重新加载配置
            # 注意：这需要重启服务才能生效
            return {
                "success": True,
                "message": "数据库配置已保存，请重启服务以应用新配置",
                "need_restart": True,
                "config": {
                    "host": config.host,
                    "port": config.port,
                    "database": config.database
                }
            }
        else:
            return {
                "success": True,
                "message": "数据库连接测试成功（未保存配置）",
                "need_restart": False,
                "test_result": test_result["details"]
            }

    except Exception as e:
        logger.error(f"配置数据库失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/init")
async def initialize_database():
    """初始化数据库表结构"""
    try:
        await init_db()

        # 获取初始化后的表统计
        stats = await get_table_stats()

        return {
            "success": True,
            "message": "数据库初始化成功",
            "tables": stats
        }
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=DatabaseStats)
async def get_database_statistics():
    """获取数据库统计信息"""
    try:
        # 获取表统计
        tables = await get_table_stats()

        # 获取详细统计
        async with AsyncSessionLocal() as db:
            # 消息总数
            msg_result = await db.execute(select(func.count()).select_from(Message))
            total_messages = msg_result.scalar() or 0

            # 告警总数
            alert_result = await db.execute(select(func.count()).select_from(Alert))
            total_alerts = alert_result.scalar() or 0

            # 会话总数
            conv_result = await db.execute(select(func.count()).select_from(Conversation))
            total_conversations = conv_result.scalar() or 0

            # 发送者总数
            sender_result = await db.execute(select(func.count()).select_from(Sender))
            total_senders = sender_result.scalar() or 0

            # 关键词总数
            kw_result = await db.execute(select(func.count()).select_from(Keyword))
            total_keywords = kw_result.scalar() or 0

        return DatabaseStats(
            tables=tables,
            total_messages=total_messages,
            total_alerts=total_alerts,
            total_conversations=total_conversations,
            total_senders=total_senders,
            total_keywords=total_keywords
        )
    except Exception as e:
        logger.error(f"获取数据库统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear")
async def clear_database(confirm: bool = False):
    """清空数据库（删除所有表）"""
    if not confirm:
        return {
            "success": False,
            "message": "请确认操作（设置 confirm=true）"
        }

    try:
        await drop_all_tables()
        return {
            "success": True,
            "message": "数据库已清空，所有表已删除"
        }
    except Exception as e:
        logger.error(f"清空数据库失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reload-config")
async def reload_config():
    """重新加载配置并重启服务"""
    try:
        import os
        import signal
        from pathlib import Path

        # 发送重启信号给当前进程
        os.kill(os.getpid(), signal.SIGHUP)

        return {
            "success": True,
            "message": "配置重载请求已发送"
        }
    except Exception as e:
        logger.error(f"重载配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
