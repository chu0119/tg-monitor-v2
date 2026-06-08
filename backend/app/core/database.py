"""数据库连接和会话管理 - MySQL 版本"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import select, text
from app.core.config import settings
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

# 使用 MySQL 数据库
DATABASE_TYPE = "mysql"

# 创建 MySQL 引擎
try:
    DATABASE_URL = settings.get_database_url()
    engine = create_async_engine(
        DATABASE_URL,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
        pool_timeout=30,
        pool_use_lifo=True,
    )
    logger.info(f"MySQL 数据库引擎已创建: {settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}")
except Exception as e:
    logger.error(f"创建 MySQL 数据库引擎失败: {e}")
    raise

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """所有模型的基类"""

    @classmethod
    def get_datetime_with_tz(cls):
        """获取带UTC时区的当前时间，用于数据库默认值"""
        return datetime.now(timezone.utc)


async def get_db() -> AsyncSession:
    """获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


class SessionWithTimezone:
    """带时区设置的会话上下文管理器"""

    def __init__(self):
        self._session = None

    async def __aenter__(self):
        self._session = AsyncSessionLocal()
        # MySQL 设置时区
        try:
            await self._session.execute(text("SET time_zone='+08:00'"))
        except Exception as e:
            logger.warning(f"设置数据库时区失败: {e}")
        return self._session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()


def get_session_with_timezone():
    """获取带时区设置的会话"""
    return SessionWithTimezone()


async def init_db():
    """初始化数据库表"""
    try:
        async with engine.begin() as conn:
            # MySQL 设置时区
            await conn.execute(text("SET time_zone='+08:00'"))

            # 创建所有表
            await conn.run_sync(Base.metadata.create_all)
            logger.info("MySQL 数据库表初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise


async def check_database_connection() -> dict:
    """检查数据库连接状态"""
    try:
        async with engine.begin() as conn:
            # 测试查询
            result = await conn.execute(text("SELECT 1 as test"))
            test_value = result.scalar()

            # 获取数据库版本信息
            version_result = await conn.execute(text("SELECT VERSION()"))
            version = version_result.scalar()

            # 获取当前数据库名
            db_result = await conn.execute(text("SELECT DATABASE()"))
            database_name = db_result.scalar()

            # 检查表是否存在
            tables_result = await conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE()"
            ))
            table_count = tables_result.scalar()

            return {
                "connected": True,
                "type": "mysql",
                "database": database_name,
                "version": version,
                "table_count": table_count,
                "url": f"{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
            }
    except Exception as e:
        logger.error(f"数据库连接检查失败: {e}")
        return {
            "connected": False,
            "type": "mysql",
            "error": str(e)
        }


async def get_table_stats() -> dict:
    """获取数据库表统计信息"""
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT table_name, table_rows
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                ORDER BY table_name
            """))
            tables = {row[0]: row[1] for row in result}

            return tables
    except Exception as e:
        logger.error(f"获取表统计失败: {e}")
        return {}


async def drop_all_tables():
    """删除所有表（慎用）"""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            logger.info("所有数据库表已删除")
    except Exception as e:
        logger.error(f"删除表失败: {e}")
        raise


def get_database_info() -> dict:
    """获取数据库信息"""
    try:
        import asyncio

        async def _get_info():
            return await check_database_connection()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            info = loop.run_until_complete(_get_info())
            return {
                "type": "mysql",
                "host": settings.MYSQL_HOST,
                "port": settings.MYSQL_PORT,
                "database": settings.MYSQL_DATABASE,
                "configured": settings.is_database_configured(),
                "connection_info": info
            }
        finally:
            loop.close()
    except Exception as e:
        return {
            "type": "mysql",
            "configured": False,
            "error": str(e)
        }
