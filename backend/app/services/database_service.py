"""数据库管理服务 - MySQL 版本"""
import json
from typing import Dict, Any
from datetime import datetime
from loguru import logger
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings
from app.core.database import get_database_info
from app.models import (
    TelegramAccount, Conversation, Message, Sender,
    Keyword, KeywordGroup, Alert
)


class DatabaseManager:
    """数据库管理器 - MySQL 版本"""

    async def test_mysql_connection(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str
    ) -> Dict[str, Any]:
        """测试 MySQL 连接"""
        try:
            mysql_url = f"mysql+aiomysql://{user}:{password}@{host}:{port}/{database}"
            engine = create_async_engine(mysql_url, echo=False)

            # 尝试连接
            async with engine.connect() as conn:
                await conn.execute("SELECT 1")

            await engine.dispose()

            return {
                "success": True,
                "message": "MySQL 连接测试成功"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"MySQL 连接测试失败: {str(e)}"
            }

    async def get_current_stats(self) -> Dict[str, Any]:
        """获取当前数据库统计信息"""
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import select, func

        stats = {
            "type": "mysql",
            "info": get_database_info(),
            "tables": {}
        }

        async with AsyncSessionLocal() as session:
            # 统计各表记录数
            tables = [
                ("telegram_accounts", TelegramAccount),
                ("conversations", Conversation),
                ("messages", Message),
                ("senders", Sender),
                ("keywords", Keyword),
                ("keyword_groups", KeywordGroup),
                ("alerts", Alert),
            ]

            for table_name, model in tables:
                try:
                    result = await session.execute(select(func.count()).select_from(model))
                    count = result.scalar()
                    stats["tables"][table_name] = count
                except Exception as e:
                    logger.warning(f"获取 {table_name} 统计失败: {e}")
                    stats["tables"][table_name] = 0

        return stats


# 全局数据库管理器实例
database_manager = DatabaseManager()
