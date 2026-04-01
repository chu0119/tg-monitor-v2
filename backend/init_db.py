#!/usr/bin/env python3
"""数据库初始化脚本"""
import asyncio
import sys
from pathlib import Path

# 添加项目路径到sys.path
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from sqlalchemy import text
from app.core.database import engine, Base, init_db
from app.models import *  # 导入所有模型以确保它们被注册


async def create_database_if_not_exists():
    """创建数据库（如果不存在）"""
    try:
        from app.core.config import settings

        # 连接到MySQL服务器（不指定数据库）
        from sqlalchemy.ext.asyncio import create_async_engine
        server_url = f"mysql+aiomysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}"

        server_engine = create_async_engine(server_url, echo=False)

        async with server_engine.begin() as conn:
            # 检查数据库是否存在
            result = await conn.execute(
                text(f"SHOW DATABASES LIKE '{settings.MYSQL_DATABASE}'")
            )
            exists = result.fetchone()

            if not exists:
                # 创建数据库
                await conn.execute(
                    text(f"CREATE DATABASE {settings.MYSQL_DATABASE} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                )
                logger.info(f"数据库 '{settings.MYSQL_DATABASE}' 已创建")
            else:
                logger.info(f"数据库 '{settings.MYSQL_DATABASE}' 已存在")

        await server_engine.dispose()

    except Exception as e:
        logger.error(f"创建数据库失败: {e}")
        raise


async def create_tables():
    """创建所有表"""
    try:
        await init_db()
        logger.info("数据库表创建完成")
    except Exception as e:
        logger.error(f"创建表失败: {e}")
        raise


async def insert_default_settings():
    """插入默认配置"""
    try:
        from app.core.database import AsyncSessionLocal
        from app.models.settings import Settings
        from sqlalchemy import select

        default_settings = [
            {"key_name": "initialized", "value": "false", "category": "system"},
            {"key_name": "proxy_port", "value": "7897", "category": "proxy"},
            {"key_name": "proxy_enabled", "value": "false", "category": "proxy"},
        ]

        async with AsyncSessionLocal() as db:
            for setting_data in default_settings:
                # 检查是否已存在
                result = await db.execute(
                    select(Settings).where(Settings.key_name == setting_data["key_name"])
                )
                if not result.scalar_one_or_none():
                    setting = Settings(**setting_data)
                    db.add(setting)
                    logger.info(f"插入默认配置: {setting_data['key_name']}")

            await db.commit()

        logger.info("默认配置插入完成")

    except Exception as e:
        logger.error(f"插入默认配置失败: {e}")
        raise


async def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("TG Monitor v2 - 数据库初始化")
    logger.info("=" * 60)

    try:
        # Step 1: 创建数据库
        logger.info("\n[1/3] 检查数据库...")
        await create_database_if_not_exists()

        # Step 2: 创建表
        logger.info("\n[2/3] 创建数据库表...")
        await create_tables()

        # Step 3: 插入默认配置
        logger.info("\n[3/3] 插入默认配置...")
        await insert_default_settings()

        logger.info("\n" + "=" * 60)
        logger.info("✅ 数据库初始化完成！")
        logger.info("=" * 60)

        return True

    except Exception as e:
        logger.error(f"\n❌ 数据库初始化失败: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
