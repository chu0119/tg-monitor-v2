"""
Monitor Worker入口
运行Telegram监控，管理独立的账号组
"""
import os
import sys
import asyncio
import signal
from contextlib import asynccontextmanager

import uvicorn
from loguru import logger
from sqlalchemy import select

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.core.config import settings
from app.core.worker_config import worker_manager, get_account_ids
from app.core.database import init_db, AsyncSessionLocal
from app.models.account import TelegramAccount
from app.models.conversation import Conversation
from app.telegram.client import client_manager
from app.telegram.monitor import message_monitor


def setup_logging(worker_id: int):
    """配置日志"""
    log_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, f'monitor_worker_{worker_id}.log')

    logger.remove()
    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | Monitor Worker | {function}:{line} - {message}"
    )
    logger.add(
        log_file,
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        encoding="utf-8",
        level=settings.LOG_LEVEL,
        enqueue=True,
        backtrace=True,
        diagnose=True
    )


def setup_session_dir(worker_id: int):
    """设置Session目录

    与 api_worker 保持一致，直接使用 backend/sessions/（不按 worker_id 拆分子目录），
    否则 monitor 会读 worker_N/ 下的空桩文件，而账号真实 session 在 backend/sessions/ 下。
    """
    session_base = os.path.join(os.path.dirname(__file__), '..', '..', 'sessions')
    session_dir = session_base
    os.makedirs(session_dir, exist_ok=True)

    # 更新settings的SESSION_DIR
    settings.SESSION_DIR = type(settings.SESSION_DIR)(session_dir)
    logger.info(f"Session目录: {session_dir}")


async def connect_accounts(worker_id: int, account_ids: list):
    """连接分配给该Worker的账号"""
    logger.info(f"开始连接账号，Worker ID: {worker_id}, 账号ID: {account_ids}")

    async with AsyncSessionLocal() as db:
        # 只连接分配给当前Worker的账号
        result = await db.execute(
            select(TelegramAccount).where(
                TelegramAccount.id.in_(account_ids),
                TelegramAccount.is_authorized == True,
                TelegramAccount.is_active == True
            )
        )
        accounts = result.scalars().all()

    if not accounts:
        logger.warning(f"Worker {worker_id} 没有找到需要连接的账号")
        return

    logger.info(f"Worker {worker_id} 找到 {len(accounts)} 个账号需要连接")

    # 并行连接账号（限制并发数，避免Telegram限流）
    sem = asyncio.Semaphore(5)

    async def connect_one(account):
        async with sem:
            try:
                client = await asyncio.wait_for(
                    client_manager.get_client(account.id),
                    timeout=30
                )
                if client:
                    logger.info(f"Worker {worker_id} 账号已连接: {account.phone}")
                else:
                    logger.warning(f"Worker {worker_id} 账号连接失败: {account.phone}")
            except asyncio.TimeoutError:
                logger.warning(f"Worker {worker_id} 账号连接超时: {account.phone}")
            except Exception as e:
                logger.error(f"Worker {worker_id} 账号连接异常: {account.phone} - {e}")

    tasks = [connect_one(acc) for acc in accounts]
    await asyncio.gather(*tasks)


async def start_monitors(worker_id: int, account_ids: list):
    """启动分配给该Worker的监控"""
    logger.info(f"Worker {worker_id} 开始启动监控")

    async with AsyncSessionLocal() as db:
        # 查询分配给当前Worker账号的会话
        result = await db.execute(
            select(Conversation).where(
                Conversation.account_id.in_(account_ids),
                Conversation.status == "active",
                Conversation.enable_realtime == True
            )
        )
        conversations = result.scalars().all()

    if not conversations:
        logger.warning(f"Worker {worker_id} 没有需要监控的会话")
        return

    logger.info(f"Worker {worker_id} 找到 {len(conversations)} 个会话需要监控")

    # 启动监控
    success_count = 0
    failed_count = 0

    for conv in conversations:
        try:
            await asyncio.wait_for(
                message_monitor.start_monitor(conv.id),
                timeout=10
            )
            success_count += 1
        except asyncio.TimeoutError:
            failed_count += 1
            logger.warning(f"Worker {worker_id} 会话监控启动超时: {conv.id}")
        except Exception as e:
            failed_count += 1
            logger.error(f"Worker {worker_id} 会话监控启动失败: {conv.id} - {e}")

    logger.info(f"Worker {worker_id} 监控启动完成: 成功 {success_count}, 失败 {failed_count}, 共 {len(conversations)}")


async def run_monitor_worker(worker_id: int, account_ids: list):
    """运行Monitor Worker"""
    global current_account_ids
    current_account_ids = list(account_ids)
    logger.info(f"Monitor Worker {worker_id} 开始运行，账号: {account_ids}")

    # 初始化数据库
    await init_db()
    logger.info(f"Worker {worker_id} 数据库初始化完成")

    # 注入账号归属：心跳/对账只处理本 worker 的账号，避免跨进程抢连同一 session 文件
    message_monitor.set_assigned_accounts(account_ids)

    # 连接账号
    await connect_accounts(worker_id, account_ids)

    # 启动监控
    await start_monitors(worker_id, account_ids)

    # 启动消息处理队列
    message_monitor._queue_processor_task = asyncio.create_task(
        message_monitor._process_queue_loop()
    )
    logger.info(f"Worker {worker_id} 消息队列处理器已启动")

    # 启动心跳检测
    await message_monitor.start_heartbeat()
    logger.info(f"Worker {worker_id} 心跳检测已启动")

    logger.info(f"Monitor Worker {worker_id} 启动完成")

    # 保持运行，等待停止信号
    stop_event = asyncio.Event()

    def _signal_handler():
        logger.info(f"Worker {worker_id} 收到停止信号")
        stop_event.set()

    # 注册信号处理器（仅Linux/macOS）
    try:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, _signal_handler)
    except (NotImplementedError, AttributeError):
        # Windows不支持add_signal_handler
        pass

    try:
        await stop_event.wait()
    except asyncio.CancelledError:
        logger.info(f"Worker {worker_id} 任务被取消")
    finally:
        # 清理资源
        await message_monitor.stop_heartbeat()
        await message_monitor.stop_all_monitors()
        await client_manager.disconnect_all()
        logger.info(f"Worker {worker_id} 已停止")


# 本 worker 实际分配到的账号ID（run_monitor_worker 启动时写入，控制端点使用）
current_account_ids: list = []


def create_status_app():
    """创建状态查询API"""
    from fastapi import FastAPI, HTTPException

    app = FastAPI(title=f"Monitor Worker {worker_manager.worker_id} Status")

    @app.get("/status")
    async def status():
        return {
            "worker_id": worker_manager.worker_id,
            "worker_type": "monitor",
            "account_ids": current_account_ids or worker_manager.get_worker_config().account_ids,
            "active_monitors": len(message_monitor.active_monitors),
            "connected_clients": len(client_manager.clients)
        }

    @app.get("/health")
    async def health():
        return {"status": "ok", "worker_id": worker_manager.worker_id}

    # ===== 控制端点：监控操作只能在本进程执行（session 文件由本进程持有），
    # api_worker 通过 HTTP 转发到这里，避免在 API 进程创建 Telethon 客户端 =====

    @app.post("/control/restart")
    async def control_restart():
        await message_monitor.stop_all_monitors()
        connected = 0
        for aid in current_account_ids:
            try:
                client = await client_manager.get_client(aid)
                if client and client.is_connected():
                    connected += 1
            except Exception as e:
                logger.warning(f"重连账号 {aid} 失败: {e}")
        await start_monitors(worker_manager.worker_id, current_account_ids)
        await message_monitor.start_heartbeat()
        return {
            "message": "监控已重启",
            "connected_accounts": connected,
            "active_monitors": len(message_monitor.active_monitors),
        }

    @app.post("/control/start/{conversation_id}")
    async def control_start(conversation_id: int):
        # 校验会话归属：不是本 worker 的账号则拒绝，避免抢连
        from sqlalchemy import select as sa_select
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                sa_select(Conversation.account_id).where(Conversation.id == conversation_id)
            )
            account_id = result.scalar_one_or_none()
        if account_id is None:
            raise HTTPException(status_code=404, detail=f"会话 {conversation_id} 不存在")
        if account_id not in current_account_ids:
            raise HTTPException(
                status_code=409,
                detail=f"会话 {conversation_id} 属于账号 {account_id}，不由本 Worker 管理"
            )
        await message_monitor.start_monitor(conversation_id)
        return {"message": f"会话 {conversation_id} 监控已启动"}

    @app.post("/control/stop/{conversation_id}")
    async def control_stop(conversation_id: int):
        await message_monitor.stop_monitor(conversation_id)
        return {"message": f"会话 {conversation_id} 监控已停止"}

    return app


def main():
    """主函数"""
    config = worker_manager.get_worker_config()

    setup_logging(config.worker_id)
    setup_session_dir(config.worker_id)

    logger.info(f"启动 Monitor Worker {config.worker_id}")

    # 创建状态查询应用
    status_app = create_status_app()

    # 启动监控任务
    async def run():
        # 从数据库查询实际授权的账号，按轮询分配给当前worker
        async with AsyncSessionLocal() as db:
            num_workers = worker_manager.config.get('monitor_workers', 1)
            account_ids = await get_account_ids(db, config.worker_id, num_workers)
        logger.info(f"管理账号: {account_ids}")

        # 启动状态API
        uvicorn_config = uvicorn.Config(
            status_app,
            host="0.0.0.0",
            port=config.port + 1000,  # 状态API端口 = 监控端口 + 1000
            log_level="warning"
        )
        server = uvicorn.Server(uvicorn_config)
        server_task = asyncio.create_task(server.serve())

        try:
            # 运行监控
            await run_monitor_worker(config.worker_id, account_ids)
        finally:
            # 优雅关闭状态API服务器
            server.should_exit = True
            await server_task

    asyncio.run(run())


if __name__ == "__main__":
    main()
