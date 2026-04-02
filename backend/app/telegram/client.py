"""Telegram 客户端管理"""
import asyncio
import time
from datetime import datetime
from typing import Dict, Optional, List
from telethon import TelegramClient, events
from telethon.tl.types import Message, User, Chat, Channel
from telethon.errors import SessionPasswordNeededError
from loguru import logger
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models import TelegramAccount, Conversation, Sender, Message as MessageModel
from sqlalchemy import select, update


class TelegramClientManager:
    """Telegram 客户端管理器"""

    def __init__(self):
        self.clients: Dict[int, TelegramClient] = {}
        self.login_sessions: Dict[str, dict] = {}  # 存储登录会话状态
        # 缓存账号信息以减少数据库访问
        self._account_cache: Dict[int, dict] = {}  # {account_id: {phone, api_id, api_hash, proxy_config}}
        # 追踪事件处理器用于清理
        self.event_handlers: Dict[int, List[dict]] = {}  # {account_id: [{'handler': handler, ...}]}
        self._unauthorized_accounts: set = set()  # 已知未授权的账号ID，跳过重复连接

    def _get_default_proxy(self) -> Optional[tuple]:
        """从配置获取默认代理，返回 Telethon 可用的元组"""
        socks5_url = getattr(settings, 'SOCKS5_PROXY', None)
        logger.info(f"_get_default_proxy called: SOCKS5_PROXY={socks5_url}")

        # 如果没有配置SOCKS5_PROXY，尝试检测mihomo代理
        if not socks5_url:
            try:
                from app.proxy.manager import ProxyManager
                import asyncio
                proxy_mgr = ProxyManager()
                config = proxy_mgr.generator.read_config()
                if config and config.get("mixed-port"):
                    port = config["mixed-port"]
                    logger.info(f"_get_default_proxy: detected mihomo on port {port}, using as SOCKS5 proxy")
                    import socks as socklib
                    return (socklib.SOCKS5, "127.0.0.1", port, None, None)
            except Exception as e:
                logger.warning(f"_get_default_proxy: failed to detect mihomo: {e}")

        if socks5_url and socks5_url.startswith('socks5://'):
            # socks5://user:pass@host:port
            import re
            import socks as socklib
            m = re.match(r'socks5://(?:([^:]+):([^@]+)@)?([^:]+):(\d+)', socks5_url)
            if m:
                result = (socklib.SOCKS5, m.group(3), int(m.group(4)), m.group(1) or None, m.group(2) or None)
                logger.info(f"_get_default_proxy returning: {result}")
                return result
        logger.warning(f"_get_default_proxy returning None")
        return None

    def _cache_account_info(self, account_id: int, phone: str, api_id: int, api_hash: str, proxy_config):
        """缓存账号信息"""
        self._account_cache[account_id] = {
            "phone": phone,
            "api_id": api_id,
            "api_hash": api_hash,
            "proxy_config": proxy_config
        }

    def _get_cached_account_info(self, account_id: int) -> Optional[dict]:
        """获取缓存的账号信息"""
        return self._account_cache.get(account_id)

    def _clear_account_cache(self, account_id: int):
        """清除账号缓存"""
        self._account_cache.pop(account_id, None)

    def get_session_path(self, phone: str) -> str:
        """获取会话文件路径"""
        return str(settings.SESSION_DIR / f"{phone}")

    def _normalize_proxy_config(self, proxy_config) -> Optional[dict]:
        """规范化代理配置，处理各种可能的格式"""
        if proxy_config is None:
            return None

        # 如果是字符串 "null"，返回 None
        if isinstance(proxy_config, str):
            if proxy_config.lower() == "null" or proxy_config.strip() == "":
                return None
            try:
                import json
                proxy_config = json.loads(proxy_config)
            except:
                return None

        # 如果已经是字典，验证其格式
        if isinstance(proxy_config, dict):
            # 检查是否有有效的代理配置
            if proxy_config.get("proxy_type") and proxy_config.get("addr"):
                # Telethon 代理格式
                return {
                    "proxy_type": proxy_config["proxy_type"],
                    "addr": proxy_config["addr"],
                    "port": proxy_config.get("port", 1080),
                    "username": proxy_config.get("username"),
                    "password": proxy_config.get("password"),
                    "rdns": True,
                }

        return None

    async def create_client(
        self,
        phone: str,
        api_id: int,
        api_hash: str,
        proxy: Optional[dict] = None
    ) -> tuple:
        """创建Telegram客户端，返回 (client, authorized)"""
        session_path = self.get_session_path(phone)

        # 检查session文件是否损坏，损坏则删除
        import os
        session_db = session_path + ".session"
        if os.path.exists(session_db):
            try:
                import sqlite3
                conn = sqlite3.connect(session_db)
                conn.execute("SELECT count(*) FROM sqlite_master")
                conn.close()
            except Exception:
                logger.warning(f"Session文件损坏，自动删除: {session_db}")
                os.remove(session_db)
                # 同时删除可能的journal/wal文件
                for suffix in [".session-journal", ".session-wal", ".session-shm"]:
                    p = session_path + suffix
                    if os.path.exists(p):
                        os.remove(p)

        # 规范化代理配置，如果没有传入则尝试从环境变量/配置获取
        if proxy is None:
            proxy = self._get_default_proxy()
        if proxy is not None and isinstance(proxy, dict):
            proxy = self._normalize_proxy_config(proxy)

        logger.info(f"create_client: final proxy={proxy}, phone={phone}")

        client = TelegramClient(
            session_path,
            api_id,
            api_hash,
            proxy=proxy,
            timeout=10,
        )
        await client.connect()

        if not client.is_connected():
            raise ConnectionError("Telethon connect failed")

        # Debug: 检查 Telethon 内部状态
        try:
            sender = getattr(client, '_sender', None)
            user_id = getattr(client, '_user_id', None)
            dc_id = getattr(client, '_dc_id', None)
            logger.info(f"create_client: _user_id={user_id}, _dc_id={dc_id}, _sender type={type(sender).__name__ if sender else None}")
        except Exception as dbg:
            logger.info(f"create_client debug: {dbg}")

        auth = await client.is_user_authorized()
        logger.info(f"create_client: connected=True, authorized={auth}, proxy={'yes' if proxy else 'no'}")

        return client, auth

    async def request_login_code(
        self,
        phone: str,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        proxy: Optional[dict] = None
    ) -> dict:
        """请求发送登录验证码"""
        # 优先级：传入参数 > 数据库已有账号 > 全局配置
        if api_id is None or api_hash is None or api_hash == "":
            # 尝试从数据库获取该账号已有的凭据
            try:
                async with AsyncSessionLocal() as db:
                    from sqlalchemy import select
                    from app.models import TelegramAccount
                    result = await db.execute(
                        select(TelegramAccount).where(TelegramAccount.phone == phone)
                    )
                    existing = result.scalar_one_or_none()
                    if existing:
                        if api_id is None:
                            api_id = existing.api_id or settings.TELEGRAM_API_ID
                        if not api_hash or api_hash == "":
                            api_hash = existing.api_hash or settings.TELEGRAM_API_HASH
            except Exception:
                pass

            # 最后回退到全局配置
            if api_id is None:
                api_id = settings.TELEGRAM_API_ID
            if not api_hash or api_hash == "":
                api_hash = settings.TELEGRAM_API_HASH

        if not api_id or not api_hash:
            raise ValueError("请先配置 API ID 和 API Hash（可在添加账号时输入，或在设置中配置全局 API）")

        client, auth = await self.create_client(phone, api_id, api_hash, proxy)

        # 发送验证码
        result = await client.send_code_request(phone)

        # 保存会话状态
        self.login_sessions[phone] = {
            "client": client,
            "phone": phone,
            "phone_code_hash": result.phone_code_hash,
            "proxy": proxy,
            "api_id": api_id,
            "api_hash": api_hash,
            "created_at": time.time(),  # 记录创建时间
        }

        return {
            "phone": phone,
            "phone_code_hash": result.phone_code_hash,
            "next_step": "code" if not result.next_type else "password"
        }

    async def sign_in_with_code(
        self,
        phone: str,
        code: str,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        password: Optional[str] = None
    ) -> TelegramAccount:
        """使用验证码登录"""
        if phone not in self.login_sessions:
            raise ValueError("登录会话不存在，请重新请求验证码")

        session = self.login_sessions[phone]
        client = session["client"]

        try:
            # 使用验证码登录
            await client.sign_in(
                phone,
                code,
                phone_code_hash=session["phone_code_hash"]
            )
        except SessionPasswordNeededError:
            # 需要两步验证密码
            if not password:
                raise ValueError("需要两步验证密码")
            await client.sign_in(password=password)

        # 获取用户信息
        me = await client.get_me()

        # 保存或更新到数据库
        async with AsyncSessionLocal() as db:
            # 检查账号是否已存在
            result = await db.execute(
                select(TelegramAccount).where(TelegramAccount.phone == phone)
            )
            account = result.scalar_one_or_none()

            if account:
                # 更新现有账号
                account.user_id = me.id
                account.username = me.username
                account.first_name = me.first_name
                account.last_name = me.last_name
                account.is_premium = me.premium
                account.is_bot = me.bot
                account.session_file = self.get_session_path(phone)
                account.is_authorized = True
                account.is_active = True
                account.last_used_at = datetime.now()
                if session.get("proxy"):
                    account.proxy_config = session.get("proxy")
                if session.get("api_id"):
                    account.api_id = session.get("api_id")
                if session.get("api_hash"):
                    account.api_hash = session.get("api_hash")
            else:
                # 创建新账号
                account = TelegramAccount(
                    phone=phone,
                    user_id=me.id,
                    username=me.username,
                    first_name=me.first_name,
                    last_name=me.last_name,
                    is_premium=me.premium,
                    is_bot=me.bot,
                    session_file=self.get_session_path(phone),
                    is_authorized=True,
                    is_active=True,
                    proxy_config=session.get("proxy"),
                    api_id=session.get("api_id"),
                    api_hash=session.get("api_hash"),
                )
                db.add(account)

            await db.commit()
            await db.refresh(account)

            # 登录成功，清除未授权标记
            self._unauthorized_accounts.discard(account.id)

        # 添加到活跃客户端
        self.clients[account.id] = client

        # 确保 session 持久化到磁盘
        try:
            await client.session.save()
            logger.info(f"账号 {phone} session 已保存到磁盘")
        except Exception as e:
            logger.warning(f"保存 session 失败: {e}")

        # 清理登录会话
        del self.login_sessions[phone]

        logger.info(f"Telegram 账号登录成功: {phone} ({me.username})")
        return account

    async def get_client(self, account_id: int) -> Optional[TelegramClient]:
        """获取账号的客户端，确保已连接"""
        # 快速跳过已知未授权的账号（避免重复连接尝试）
        if account_id in self._unauthorized_accounts:
            return None

        if account_id in self.clients:
            client = self.clients[account_id]
            # 检查客户端是否仍连接
            if client.is_connected():
                self._start_client_loop(account_id, client)
                return client
            else:
                # 客户端已断开，移除并重新创建
                logger.warning(f"客户端 {account_id} 已断开，将重新连接")
                del self.clients[account_id]

        # 先检查缓存
        cached_info = self._get_cached_account_info(account_id)

        if cached_info:
            # 使用缓存的信息创建客户端
            phone = cached_info["phone"]
            api_id = cached_info["api_id"]
            api_hash = cached_info["api_hash"]
            proxy_config = cached_info["proxy_config"]

            try:
                client, auth = await self.create_client(phone, api_id, api_hash, proxy_config)

                if auth:
                    self.clients[account_id] = client
                    # 在后台启动Telethon事件循环，使事件处理器生效
                    self._start_client_loop(account_id, client)
                    logger.info(f"账号 {account_id} 客户端已就绪（使用缓存）")
                    return client
                else:
                    logger.error(f"账号 {account_id} 未授权")
                    self._unauthorized_accounts.add(account_id)
                    return None
            except Exception as e:
                logger.warning(f"使用缓存创建客户端失败（账号 {account_id}）: {e}，尝试从数据库重新加载")
                self._clear_account_cache(account_id)

        # 从数据库加载会话（缓存未命中或使用缓存失败）
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(TelegramAccount).where(TelegramAccount.id == account_id)
            )
            account = result.scalar_one_or_none()

            if not account or not account.is_authorized:
                logger.error(f"账号 {account_id} 不存在或未授权")
                self._unauthorized_accounts.add(account_id)
                return None

            # 优先使用数据库存储的凭据，否则使用全局配置
            api_id = account.api_id or settings.TELEGRAM_API_ID
            api_hash = account.api_hash or settings.TELEGRAM_API_HASH

            if not api_id or not api_hash:
                logger.error(f"账号 {account_id} 缺少 API 凭据")
                return None

            # 缓存账号信息
            self._cache_account_info(account_id, account.phone, api_id, api_hash, account.proxy_config)

            try:
                # 如果账号没有单独配置代理，传 None 让 create_client 使用全局默认代理
                proxy = account.proxy_config
                if proxy is None or (isinstance(proxy, str) and proxy.lower() in ('null', '', '{}')) or (isinstance(proxy, dict) and not proxy.get('addr')):
                    proxy = None

                client, auth = await self.create_client(
                    account.phone,
                    api_id,
                    api_hash,
                    proxy
                )

                logger.info(f"账号 {account_id} create_client 完成, authorized={auth}")

                if auth:
                    self.clients[account_id] = client
                    # 在后台启动Telethon事件循环，使事件处理器生效
                    self._start_client_loop(account_id, client)
                    logger.info(f"账号 {account_id} 客户端已就绪")
                    return client
                else:
                    logger.error(f"账号 {account_id} 未授权")
                    self._unauthorized_accounts.add(account_id)
                    return None
            except Exception as e:
                logger.error(f"创建账号 {account_id} 客户端失败: {type(e).__name__}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return None

        return None

    async def get_dialogs(self, account_id: int) -> List[dict]:
        """获取对话列表"""
        client = await self.get_client(account_id)
        if not client:
            raise ValueError(f"无法获取账号 {account_id} 的客户端")

        if not client.is_connected():
            raise ValueError(f"账号 {account_id} 的客户端未连接")

        dialogs = []
        try:
            async for dialog in client.iter_dialogs():
                entity = dialog.entity

                # 标准化chat_id格式（特别是频道）
                chat_id = entity.id
                chat_type = self._get_chat_type(entity)

                # 对于频道，转换为-100前缀格式
                if chat_type == 'channel' and chat_id > 0:
                    chat_id = -1000000000000 + chat_id

                dialogs.append({
                    "chat_id": chat_id,  # 使用标准化后的chat_id
                    "title": dialog.title,
                    "username": getattr(entity, "username", None),
                    "type": chat_type,
                    "is_verified": getattr(entity, "verified", False),
                    "is_scam": getattr(entity, "scam", False),
                    "participants_count": getattr(entity, "participants_count", None),
                    "description": getattr(entity, "about", None),
                })
        except Exception as e:
            logger.error(f"获取账号 {account_id} 对话列表失败: {e}")
            raise

        return dialogs

    def _get_chat_type(self, entity) -> str:
        """获取聊天类型"""
        if isinstance(entity, User):
            return "private"
        elif isinstance(entity, Chat):
            return "group"
        elif isinstance(entity, Channel):
            return "channel" if entity.broadcast else "supergroup"
        return "unknown"

    async def get_history_messages(
        self,
        account_id: int,
        chat_id: int,
        limit: int = 1000
    ) -> List[Message]:
        """获取历史消息"""
        client = await self.get_client(account_id)
        if not client:
            raise ValueError("客户端未连接")

        messages = []
        async for message in client.iter_messages(chat_id, limit=limit):
            messages.append(message)

        return messages

    def _start_client_loop(self, account_id: int, client: TelegramClient):
        """在后台启动Telethon事件循环，使注册的事件处理器开始工作"""
        if hasattr(client, '_event_loop_task') and not client._event_loop_task.done():
            return  # 已在运行
        client._event_loop_task = asyncio.create_task(
            self._run_client_loop(account_id, client)
        )

    async def _run_client_loop(self, account_id: int, client: TelegramClient):
        """后台运行Telethon事件循环"""
        try:
            await client.run_until_disconnected()
        except asyncio.CancelledError:
            logger.info(f"账号 {account_id} 事件循环已取消")
        except Exception as e:
            logger.error(f"账号 {account_id} 事件循环异常: {e}")

    async def disconnect_all(self):
        """断开所有客户端并清理事件处理器"""
        for account_id, client in list(self.clients.items()):
            # 清理事件处理器
            if account_id in self.event_handlers:
                for handler_info in self.event_handlers[account_id]:
                    try:
                        client.remove_event_handler(handler_info['handler'])
                    except Exception:
                        pass
                del self.event_handlers[account_id]

            try:
                await client.disconnect()
            except Exception:
                pass

        self.clients.clear()
        self.event_handlers.clear()

    async def cleanup_expired_login_sessions(self, timeout_seconds: int = 300):
        """清理超时的登录会话（默认5分钟）"""
        current_time = time.time()
        expired_phones = []

        for phone, session_data in self.login_sessions.items():
            created_at = session_data.get('created_at', current_time)
            if current_time - created_at > timeout_seconds:
                expired_phones.append(phone)

        for phone in expired_phones:
            session = self.login_sessions[phone]
            try:
                if 'client' in session:
                    await session['client'].disconnect()
            except Exception as e:
                logger.warning(f"清理登录会话失败: {e}")
            del self.login_sessions[phone]

        if expired_phones:
            logger.info(f"清理了 {len(expired_phones)} 个过期登录会话")


# 全局客户端管理器实例
client_manager = TelegramClientManager()
