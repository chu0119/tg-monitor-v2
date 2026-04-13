"""Telegram 消息监控服务 - MySQL 版本"""
import asyncio
from typing import List, Set, Optional, Dict, Any
from datetime import datetime, timedelta
from telethon import events
from telethon.tl.types import Message, PeerChannel
from loguru import logger
from sqlalchemy import select, update, func
from app.core.database import AsyncSessionLocal
from app.models import (
    Conversation, Message as MessageModel, Sender,
    Keyword, KeywordGroup, Alert, TelegramAccount
)
from app.telegram.client import client_manager
from app.services.keyword_matcher import KeywordMatcher
from app.services.alert_service import AlertService
from app.utils import now_utc


class MessageMonitor:
    """消息监控器 - MySQL 版本"""

    def __init__(self):
        self.active_monitors: Set[int] = set()  # 正在监控的会话ID
        self.keyword_matcher = KeywordMatcher()
        self.alert_service = AlertService()
        self._running = False
        # 存储事件处理器引用,用于重新注册
        self.event_handlers: Dict[int, List[Dict]] = {}  # {account_id: [{'conversation_id': x, 'handler': y, 'chat_id': z, 'type': str}]}
        # 心跳检测任务
        self._heartbeat_task: Optional[asyncio.Task] = None
        # 追踪所有后台任务,确保它们被正确清理
        self._background_tasks: Set[asyncio.Task] = set()
        # 并发控制:限制同时处理的消息数量(防止数据库连接池耗尽)
        self._process_semaphore = asyncio.Semaphore(10)
        # 消息处理队列(设置最大大小防止内存溢出)
        self._message_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        # 队列处理任务
        self._queue_processor_task: Optional[asyncio.Task] = None
        # 队列统计
        self._queue_stats = {"enqueued": 0, "processed": 0, "dropped": 0}
        # 追踪每个会话的最后收到消息时间(用于检测僵尸会话)
        self._session_last_message_time: Dict[int, datetime] = {}

    @staticmethod
    def _get_telethon_entity_id(chat_id: int) -> int:
        """将数据库chat_id转换为Telethon PeerChannel可用的正数ID

        Telethon的PeerChannel要求正数channel_id：
        - 数据库channel: -998518730431 → abs = 998518730431（12位，正确）
        - Bot API格式: -1001234567890 → 去掉-100前缀 → 1234567890（10位）
        - 普通group负数（非channel）：保持原样
        """
        if chat_id < -1000000000000:
            # -100前缀格式（13位，如-1001234567890）
            return abs(chat_id + 1000000000000)
        elif chat_id < 0:
            # 负数channel/group ID → 取绝对值作为PeerChannel ID
            return abs(chat_id)
        return chat_id

    async def start_monitor(self, conversation_id: int):
        """开始监控会话"""
        if conversation_id in self.active_monitors:
            logger.debug(f"会话 {conversation_id} 已在监控中")
            return

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )
            conversation = result.scalar_one_or_none()

            if not conversation:
                logger.error(f"会话 {conversation_id} 不存在")
                return

            if not conversation.enable_realtime or conversation.status != "active":
                logger.debug(f"会话 {conversation_id} 未启用实时监控")
                return

        # 注册消息处理器
        await self._register_event_handler(conversation)
        self.active_monitors.add(conversation_id)
        logger.info(f"开始监控会话: {conversation.title} ({conversation.chat_id})")

    async def _register_event_handler(self, conversation: Conversation):
        """注册事件处理器 - 优化版,支持频道重试和统一 chat_id 处理"""
        logger.debug(f"正在为会话 {conversation.id} (账号 {conversation.account_id}) 注册事件处理器...")
        client = await client_manager.get_client(conversation.account_id)
        if not client:
            logger.error(f"账号 {conversation.account_id} 客户端未连接,跳过会话 {conversation.id}")
            return

        logger.debug(f"账号 {conversation.account_id} 客户端已就绪,正在注册 {conversation.chat_id} 的事件...")


        # 对于频道,需要使用实体对象来确保正确监听(增加重试次数和延迟)
        chats = conversation.chat_id

        if conversation.chat_type == 'channel':
            entity = None
            max_attempts = 2  # 减少重试次数，加速启动
            for attempt in range(max_attempts):
                try:
                    # 优先使用 username 获取实体（加超时）
                    if conversation.username:
                        entity = await asyncio.wait_for(
                            client.get_entity(conversation.username),
                            timeout=3.0
                        )
                        logger.debug(f"使用 username 获取频道实体: {conversation.username}")
                    else:
                        # 对频道 chat_id 使用 PeerChannel 构造实体
                        entity_id = self._get_telethon_entity_id(conversation.chat_id)
                        try:
                            entity = await asyncio.wait_for(
                                client.get_entity(PeerChannel(entity_id)),
                                timeout=3.0
                            )
                            logger.debug(f"使用 PeerChannel 获取频道实体: entity_id={entity_id}")
                        except Exception:
                            # PeerChannel失败，尝试get_input_entity
                            try:
                                entity = await asyncio.wait_for(
                                    client.get_input_entity(PeerChannel(entity_id)),
                                    timeout=3.0
                                )
                                logger.debug(f"使用 get_input_entity 获取频道实体: entity_id={entity_id}")
                            except Exception:
                                # 最终fallback: 用PeerChannel直接监听
                                entity = PeerChannel(entity_id)
                                logger.warning(f"所有方式均失败，使用PeerChannel({entity_id})直接监听")

                    chats = entity
                    logger.info(f"频道实体获取成功: {conversation.title} (尝试 {attempt + 1}/{max_attempts})")
                    break
                except Exception as e:
                    logger.warning(f"获取频道实体失败 (尝试 {attempt + 1}/{max_attempts}): {conversation.title} - {e}")
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(1)  # 短延迟
                    else:
                        # 最后一次尝试失败,使用channel_id直接监听
                        channel_id = self._get_telethon_entity_id(conversation.chat_id)
                        chats = channel_id
                        logger.warning(f"频道实体获取最终失败,使用channel_id({channel_id})继续监听: {conversation.title}")

        # 创建事件处理器
        async def handle_new_message(event):
            # 将消息放入队列,由队列处理器统一处理(限制并发)
            try:
                # 使用 put_nowait 避免阻塞,如果队列满则记录警告
                self._message_queue.put_nowait((event.message, conversation.id))
                self._queue_stats["enqueued"] += 1
            except asyncio.QueueFull:
                self._queue_stats["dropped"] += 1
                logger.warning(f"消息队列已满,消息 {event.message.id} 暂时无法入队(队列大小: {self._message_queue.qsize()})")
                # 队列满时,尝试同步处理(降级策略)
                try:
                    async with asyncio.timeout(30):
                        await self.process_message(event.message, conversation.id)
                except Exception as e:
                    logger.error(f"同步处理消息失败: {e}")

        # 注册 NewMessage 处理器
        new_msg_handler = client.on(events.NewMessage(chats=chats))(handle_new_message)

        # 注册 EditedMessage 处理器(监听编辑的消息)
        async def handle_edited_message(event):
            """处理编辑的消息"""
            try:
                # 编辑的消息也需要检查关键词
                logger.debug(f"收到编辑消息: {event.message.id}")
                self._message_queue.put_nowait((event.message, conversation.id))
                self._queue_stats["enqueued"] += 1
            except asyncio.QueueFull:
                self._queue_stats["dropped"] += 1
                logger.warning(f"消息队列已满,编辑消息 {event.message.id} 无法入队")

        edited_msg_handler = client.on(events.MessageEdited(chats=chats))(handle_edited_message)

        # 保存处理器引用以便后续移除
        if conversation.account_id not in self.event_handlers:
            self.event_handlers[conversation.account_id] = []

        # 保存两个处理器
        self.event_handlers[conversation.account_id].extend([
            {
                'conversation_id': conversation.id,
                'handler': new_msg_handler,
                'chat_id': conversation.chat_id,
                'type': 'new_message'
            },
            {
                'conversation_id': conversation.id,
                'handler': edited_msg_handler,
                'chat_id': conversation.chat_id,
                'type': 'edited_message'
            }
        ])

        logger.info(f"会话 {conversation.id} ({conversation.title}) 事件处理器注册成功(新消息+编辑消息)")

    async def _remove_event_handlers(self, account_id: int):
        """移除指定账号的所有事件处理器"""
        if account_id not in self.event_handlers:
            return

        client = client_manager.clients.get(account_id)
        if not client:
            logger.warning(f"无法找到账号 {account_id} 的客户端")
            return

        for handler_info in self.event_handlers[account_id]:
            try:
                client.remove_event_handler(handler_info['handler'])
                logger.debug(f"移除会话 {handler_info['conversation_id']} 的事件处理器")
            except Exception as e:
                logger.error(f"移除事件处理器失败: {e}")

        del self.event_handlers[account_id]

    async def restart_monitors_for_account(self, account_id: int):
        """重新启动指定账号的所有监控"""
        logger.info(f"重新启动账号 {account_id} 的监控...")

        # 移除旧的事件处理器
        await self._remove_event_handlers(account_id)

        # 从活跃监控中移除该账号的所有会话
        to_remove = []
        for conv_id in self.active_monitors:
            # 需要查询会话的account_id
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Conversation.account_id).where(Conversation.id == conv_id)
                )
                acc_id = result.scalar_one_or_none()
                if acc_id == account_id:
                    to_remove.append(conv_id)

        for conv_id in to_remove:
            self.active_monitors.discard(conv_id)

        # 获取该账号下所有启用的会话
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Conversation).where(
                    Conversation.account_id == account_id,
                    Conversation.status == "active",
                    Conversation.enable_realtime == True
                )
            )
            conversations = result.scalars().all()

        # 重新注册事件处理器
        for conversation in conversations:
            await self.start_monitor(conversation.id)

        logger.info(f"账号 {account_id} 的 {len(conversations)} 个监控已重启")

    async def _heartbeat_check(self):
        """心跳检测 - 定期检查客户端连接状态和监控活跃度(优化版)"""
        while self._running:
            try:
                await asyncio.sleep(30)  # 每30秒检查一次(从60秒缩短)

                # 检查所有账号的客户端状态
                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(TelegramAccount).where(
                            TelegramAccount.is_authorized == True,
                            TelegramAccount.is_active == True
                        )
                    )
                    accounts = result.scalars().all()

                    # 在会话内处理所有账号,避免会话泄漏
                    for account in accounts:
                        client = client_manager.clients.get(account.id)
                        if not client:
                            # 客户端不存在,尝试重新创建
                            logger.warning(f"账号 {account.phone} 的客户端不存在,尝试重新连接...")
                            new_client = await client_manager.get_client(account.id)
                            if new_client:
                                # 重启该账号的监控
                                await self.restart_monitors_for_account(account.id)
                            continue

                        if not client.is_connected():
                            # 客户端断开,尝试重连
                            logger.warning(f"账号 {account.phone} 的客户端已断开,尝试重连...")
                            try:
                                await client.connect()
                                logger.info(f"账号 {account.phone} 重连成功")
                                # 重启该账号的监控
                                await self.restart_monitors_for_account(account.id)
                            except Exception as e:
                                logger.error(f"账号 {account.phone} 重连失败: {e}")

                        # 检查每个活跃监控的会话是否有消息(检测僵尸会话)
                        for conv_id in list(self.active_monitors):
                            if conv_id in self._session_last_message_time:
                                last_msg_time = self._session_last_message_time[conv_id]
                                time_since_last_msg = (datetime.now() - last_msg_time).total_seconds()

                                # 如果超过10分钟没有消息,记录警告
                                if time_since_last_msg > 600:  # 10分钟
                                    logger.warning(f"会话 {conv_id} 超过 {int(time_since_last_msg/60)} 分钟没有收到消息,可能监控失效")
                                    # 可以在这里添加通知机制(如发送到前端)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"心跳检测出错: {e}")
                await asyncio.sleep(30)

    async def start_heartbeat(self):
        """启动心跳检测"""
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._running = True
            self._heartbeat_task = asyncio.create_task(self._heartbeat_check())
            logger.info("心跳检测已启动")

    async def stop_heartbeat(self):
        """停止心跳检测"""
        self._running = False
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        logger.info("心跳检测已停止")

    async def stop_monitor(self, conversation_id: int):
        """停止监控会话"""
        if conversation_id not in self.active_monitors:
            return

        # 获取会话信息以便移除事件处理器
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )
            conversation = result.scalar_one_or_none()
            if conversation:
                # 从事件处理器中移除
                if conversation.account_id in self.event_handlers:
                    client = client_manager.clients.get(conversation.account_id)
                    if client:
                        to_remove = []
                        for handler_info in self.event_handlers[conversation.account_id]:
                            if handler_info['conversation_id'] == conversation_id:
                                try:
                                    client.remove_event_handler(handler_info['handler'])
                                except Exception as e:
                                    logger.error(f"移除事件处理器失败: {e}")
                                to_remove.append(handler_info)
                        for item in to_remove:
                            self.event_handlers[conversation.account_id].remove(item)

        self.active_monitors.discard(conversation_id)
        logger.info(f"停止监控会话: {conversation_id}")

    # 需要排除的自身账号 user_id 集合（不存储自己的消息）
    _self_user_ids: Set[int] = set()

    async def _load_self_user_ids(self):
        """加载所有监控账号的 user_id，用于排除自身消息"""
        if self._self_user_ids:
            return
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(TelegramAccount.user_id).where(TelegramAccount.is_active == True)
                )
                self._self_user_ids = {row[0] for row in result.fetchall() if row[0]}
                logger.info(f"已加载 {len(self._self_user_ids)} 个自身账号 user_id，将排除其消息")
        except Exception as e:
            logger.warning(f"加载自身账号 user_id 失败: {e}")

    async def process_message(self, message: Message, conversation_id: int) -> bool:
        """处理新消息(带重试机制,处理数据库锁)

        Returns:
            bool: 如果是新消息返回 True,如果是重复消息返回 False
        """
        # 排除自身账号的消息
        await self._load_self_user_ids()
        if message.sender_id and message.sender_id in self._self_user_ids:
            return False

        max_retries = 5
        base_delay = 0.5  # 基础延迟 500ms

        for attempt in range(max_retries):
            db = None
            try:
                db = AsyncSessionLocal()
                # 获取会话标题（用于 WebSocket 广播）
                conv_result = await db.execute(
                    select(Conversation).where(Conversation.id == conversation_id)
                )
                conversation = conv_result.scalar_one_or_none()
                conv_title = conversation.title if conversation else "Unknown"

                # 获取或创建发送者
                sender = await self._get_or_create_sender(db, message)
                if not sender:
                    await db.rollback()
                    return False

                # 保存消息
                db_message = await self._save_message(db, message, conversation_id, sender.id)

                # 如果消息已存在(重复消息),不重复处理
                if not db_message:
                    await db.rollback()
                    return False

                # 关键词匹配
                matched_keywords = await self.keyword_matcher.match_message(
                    db, message, conversation_id
                )

                if matched_keywords:
                    # 创建告警（由下方统一 commit）
                    await self.alert_service.create_alerts(
                        db, db_message, sender, matched_keywords
                    )

                # 通过 WebSocket 广播新消息到前端（在 commit 前，可能需要 session 数据）
                conv_title = await self._get_conversation_title(db, conversation_id)
                await self._broadcast_new_message(db, db_message, sender, conversation_id, conv_title)

                # 更新会话统计
                await self._update_conversation_stats(db, conversation_id, message.id)

                # 更新会话的最后消息时间（用于心跳检测）
                self._session_last_message_time[conversation_id] = datetime.now()

                # 最终提交（如果 create_alerts 没有触发告警，这里需要 commit）
                try:
                    await db.commit()
                except Exception as e:
                    # 如果事务已经提交，这里会出错，可以忽略
                    if "already committed" not in str(e).lower():
                        logger.warning(f"Commit failed: {e}")

                logger.info(
                    f"处理消息: {message.id} from {sender.username}, "
                    f"匹配关键词: {len(matched_keywords)}"
                )

                return True

            except Exception as e:
                # 确保任何异常都回滚事务
                if db:
                    try:
                        await db.rollback()
                    except Exception:
                        pass

                error_str = str(e).lower()
                import traceback

                # 检查是否是数据库死锁错误(MySQL)
                is_database_locked = (
                    "deadlock" in error_str or
                    "1213" in error_str or  # MySQL Deadlock 错误码
                    "lock wait timeout" in error_str or
                    "locking" in error_str
                )

                # 如果是数据库锁定/死锁且还有重试次数
                if is_database_locked and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # 指数退避
                    logger.warning(
                        f"数据库锁定,消息 {message.id} 处理失败,"
                        f"{delay:.1f}秒后重试 {attempt + 1}/{max_retries}"
                    )
                    await asyncio.sleep(delay)
                    continue

                # 其他错误或最后一次重试失败
                logger.error(f"处理消息失败(消息ID={message.id}, 尝试={attempt + 1}/{max_retries}): {e}\n{traceback.format_exc()}")
                return False
            finally:
                # 确保会话被正确关闭
                if db:
                    try:
                        await db.close()
                    except Exception:
                        pass

        return False

    async def _get_or_create_sender(self, db, message: Message) -> Optional[Sender]:
        """获取或创建发送者(使用 MySQL 原生 SQL 避免死锁)

        使用 INSERT ... ON DUPLICATE KEY UPDATE 确保原子性操作,
        避免"检查-插入"之间的竞态条件
        """
        if not message.sender:
            return None

        sender_id = message.sender_id
        new_username = getattr(message.sender, "username", None)
        new_first_name = getattr(message.sender, "first_name", None)
        new_last_name = getattr(message.sender, "last_name", None)
        new_phone = getattr(message.sender, "phone", None)

        # 使用 MySQL 原生 SQL 进行原子操作(参数化查询防止 SQL 注入)
        from sqlalchemy import text

        # 使用参数化查询
        sql = text("""
            INSERT INTO senders (
                user_id, username, first_name, last_name, phone,
                is_bot, is_verified, is_premium, message_count
            ) VALUES (
                :user_id, :username, :first_name, :last_name, :phone,
                :is_bot, :is_verified, :is_premium, 1
            )
            ON DUPLICATE KEY UPDATE
                message_count = message_count + 1,
                updated_at = NOW(),
                username = COALESCE(NULLIF(username, ''), :username),
                first_name = COALESCE(NULLIF(first_name, ''), :first_name),
                last_name = COALESCE(NULLIF(last_name, ''), :last_name),
                phone = COALESCE(NULLIF(phone, ''), :phone)
        """)

        try:
            await db.execute(sql, {
                "user_id": sender_id,
                "username": new_username or "",
                "first_name": new_first_name or "",
                "last_name": new_last_name or "",
                "phone": new_phone or "",
                "is_bot": 1 if getattr(message.sender, 'bot', False) else 0,
                "is_verified": 1 if getattr(message.sender, 'verified', False) else 0,
                "is_premium": 1 if getattr(message.sender, 'premium', False) else 0,
            })
            await db.flush()

            # 查询并返回 Sender 对象
            result = await db.execute(
                select(Sender).where(Sender.user_id == sender_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"获取或创建发送者失败(user_id={sender_id}): {e}")
            # 回退到原始方法
            return await self._get_or_create_sender_fallback(db, message, sender_id)

    async def _get_or_create_sender_fallback(self, db, message: Message, sender_id: int) -> Optional[Sender]:
        """回退方法:使用 ORM 方式获取或创建发送者"""
        max_retries = 2
        for attempt in range(max_retries):
            try:
                result = await db.execute(
                    select(Sender).where(Sender.user_id == sender_id)
                )
                sender = result.scalar_one_or_none()

                if sender:
                    sender.message_count = (sender.message_count or 0) + 1
                    return sender

                sender = Sender(
                    user_id=sender_id,
                    username=getattr(message.sender, "username", None),
                    first_name=getattr(message.sender, "first_name", None),
                    last_name=getattr(message.sender, "last_name", None),
                    phone=getattr(message.sender, "phone", None),
                    is_bot=getattr(message.sender, "bot", False),
                    is_verified=getattr(message.sender, "verified", False),
                    is_premium=getattr(message.sender, "premium", False),
                    message_count=1,
                )
                db.add(sender)
                await db.flush()
                return sender

            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.1 * (attempt + 1))
                    continue
                logger.error(f"回退方法失败(user_id={sender_id}): {e}")
                return None

    async def _save_message(
        self,
        db,
        message: Message,
        conversation_id: int,
        sender_id: int
    ) -> Optional[MessageModel]:
        """保存消息到数据库(幂等性处理)

        先查询后插入，避免 Duplicate entry 错误
        """
        # 处理Telegram消息时间:转换为UTC naive datetime存储
        msg_date = message.date
        if msg_date.tzinfo is not None:
            # 转换为UTC并去掉时区信息
            from app.utils import to_utc
            msg_date = to_utc(msg_date).replace(tzinfo=None)
        else:
            # 如果没有时区信息,假定为UTC(Telegram API默认返回UTC)
            pass

        # 先查询消息是否已存在（快速路径，避免不必要的 INSERT）
        result = await db.execute(
            select(MessageModel.id).where(MessageModel.id == message.id)
        )
        if result.scalar_one_or_none():
            # 消息已存在，返回 None 表示重复
            return None

        # 尝试插入，如果因并发导致主键冲突则返回 None
        try:
            # 创建新消息
            db_message = MessageModel(
                id=message.id,
                conversation_id=conversation_id,
                sender_id=sender_id,
                message_type=self._get_message_type(message),
                text=message.text,
                caption=getattr(message, "caption", None),
                date=msg_date,  # 存储为UTC naive datetime
                views=getattr(message, "views", None),
                forwards=getattr(message, "forwards", None),
                has_media=message.media is not None,
                is_reply=message.reply_to is not None,
                reply_to_msg_id=message.reply_to_msg_id if message.reply_to else None,
            )
            db.add(db_message)
            await db.flush()
            return db_message
        except Exception as e:
            # 如果插入失败(可能是主键冲突),说明消息已存在
            logger.debug(f"消息 {message.id} 已存在，跳过: {e}")
            return None

    def _get_message_type(self, message: Message) -> str:
        """获取消息类型"""
        if message.media:
            media_type = type(message.media).__name__
            if "Photo" in media_type:
                return "photo"
            elif "Video" in media_type:
                return "video"
            elif "Document" in media_type:
                return "document"
            elif "Audio" in media_type:
                return "audio"
            elif "Sticker" in media_type:
                return "sticker"
            else:
                return "media"
        elif message.text:
            return "text"
        else:
            return "unknown"

    async def _update_conversation_stats(self, db, conversation_id: int, message_id: int):
        """更新会话统计(使用 MySQL 原生 SQL 避免死锁)"""
        from sqlalchemy import text

        # 使用单条 SQL 更新会话和账号统计,减少锁竞争(参数化查询)
        sql = text("""
            UPDATE conversations c
            INNER JOIN telegram_accounts a ON c.account_id = a.id
            SET
                c.total_messages = c.total_messages + 1,
                c.last_message_id = :message_id,
                c.last_message_at = NOW(),
                c.updated_at = NOW(),
                a.total_messages = a.total_messages + 1,
                a.updated_at = NOW()
            WHERE c.id = :conversation_id
        """)

        try:
            await db.execute(sql, {"message_id": message_id, "conversation_id": conversation_id})
        except Exception as e:
            # 如果更新失败,回退到分离的更新语句
            logger.warning(f"联合更新失败,回退到分离更新: {e}")
            await self._update_conversation_stats_fallback(db, conversation_id, message_id)

    async def _update_conversation_stats_fallback(self, db, conversation_id: int, message_id: int):
        """回退方法:分离更新会话和账号统计"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # 先获取会话的 account_id
                result = await db.execute(
                    select(Conversation.account_id).where(Conversation.id == conversation_id)
                )
                account_id = result.scalar_one_or_none()
                if not account_id:
                    return

                # 更新会话统计
                await db.execute(
                    update(Conversation)
                    .where(Conversation.id == conversation_id)
                    .values(
                        total_messages=Conversation.total_messages + 1,
                        last_message_id=message_id,
                        last_message_at=now_utc(),
                        updated_at=now_utc()
                    )
                )

                # 更新账号统计
                await db.execute(
                    update(TelegramAccount)
                    .where(TelegramAccount.id == account_id)
                    .values(
                        total_messages=TelegramAccount.total_messages + 1,
                        updated_at=now_utc()
                    )
                )
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.1 * (attempt + 1))
                    continue
                logger.error(f"更新会话统计失败(conversation_id={conversation_id}): {e}")

    async def _get_conversation_title(self, db, conversation_id: int) -> str:
        """获取会话标题（使用缓存减少数据库查询，支持Telethon fallback）"""
        if not hasattr(self, '_conv_title_cache'):
            self._conv_title_cache = {}
        if conversation_id in self._conv_title_cache:
            return self._conv_title_cache[conversation_id]
        try:
            result = await db.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )
            conv = result.scalar_one_or_none()
            title = conv.title if conv else "Unknown"

            # 如果title为空，尝试从Telethon实时获取
            if not title and conv:
                try:
                    client = await client_manager.get_client(conv.account_id)
                    if client:
                        entity_id = self._get_telethon_entity_id(conv.chat_id)
                        entity = await client.get_entity(entity_id)
                        if hasattr(entity, 'first_name'):
                            title = entity.first_name or ""
                            if hasattr(entity, 'last_name') and entity.last_name:
                                title += f" {entity.last_name}"
                        if not title and hasattr(entity, 'title'):
                            title = entity.title
                        if title:
                            conv.title = title
                            await db.commit()
                except Exception:
                    pass

            if not title:
                title = f"用户#{conv.chat_id}" if conv and conv.chat_type == 'private' else f"会话#{conversation_id}"

            self._conv_title_cache[conversation_id] = title
            return title
        except Exception:
            return "Unknown"

    async def _broadcast_new_message(self, db, db_message: MessageModel, sender: Sender, conversation_id: int, conversation_title: str = "Unknown"):
        """通过 WebSocket 广播新消息到前端"""
        try:
            from app.main import broadcast_new_message

            # 格式化日期时间
            date_str = db_message.date.isoformat() if hasattr(db_message.date, 'isoformat') else str(db_message.date)

            # 构建广播数据
            message_data: Dict[str, Any] = {
                "id": db_message.id,
                "conversation_id": conversation_id,
                "conversation_title": conversation_title,
                "sender_id": sender.id,
                "sender_username": sender.username or sender.first_name or "Unknown",
                "message_type": db_message.message_type,
                "text": db_message.text,
                "caption": db_message.caption,
                "date": date_str,
                "has_media": db_message.has_media,
                "is_reply": db_message.is_reply,
                "alert_id": db_message.alert_id,
            }

            # 创建后台任务并追踪,确保任务被正确清理
            async def _broadcast_with_timeout():
                try:
                    async with asyncio.timeout(5):
                        await broadcast_new_message(message_data)
                except asyncio.TimeoutError:
                    logger.warning("WebSocket 广播超时")
                except Exception as e:
                    logger.error(f"广播新消息失败: {e}")

            task = asyncio.create_task(_broadcast_with_timeout())
            self._background_tasks.add(task)
            # 任务完成后自动从集合中移除
            task.add_done_callback(self._background_tasks.discard)
        except Exception as e:
            logger.error(f"广播新消息失败: {e}")

    async def pull_history(self, conversation_id: int, days: int = 7, limit: int = 1000, offset_date: Optional[datetime] = None):
        """拉取历史消息(支持断点续传)

        Args:
            conversation_id: 会话 ID
            days: 回溯天数(当没有最后消息时间时使用)
            limit: 最大拉取消息数
            offset_date: 从哪个时间点开始拉取(用于断点续传)
        """
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )
            conversation = result.scalar_one_or_none()
            if not conversation:
                logger.error(f"会话 {conversation_id} 不存在")
                return

        client = await client_manager.get_client(conversation.account_id)
        if not client:
            logger.error(f"账号 {conversation.account_id} 客户端未连接")
            return

        try:
            # 确定起始日期
            if offset_date:
                start_date = offset_date
            else:
                start_date = datetime.now() - timedelta(days=days)

            # 确定聊天实体（channel类型需要特殊处理）
            entity = conversation.chat_id
            if conversation.chat_type == 'channel':
                channel_id = self._get_telethon_entity_id(conversation.chat_id)
                entity = None
                # 依次尝试多种方式获取实体
                try_methods = []
                if conversation.username:
                    try_methods.append(lambda: client.get_entity(conversation.username))
                try_methods.append(lambda: client.get_entity(PeerChannel(channel_id)))
                try_methods.append(lambda: client.get_input_entity(PeerChannel(channel_id)))
                
                for method in try_methods:
                    try:
                        entity = await asyncio.wait_for(method(), timeout=5.0)
                        logger.info(f"pull_history: 频道实体获取成功 (chat_id={conversation.chat_id}, entity_id={channel_id})")
                        break
                    except Exception:
                        continue
                
                if entity is None:
                    logger.warning(f"pull_history: 所有方式均无法获取频道实体 {channel_id}, 尝试使用chat_id直接拉取")
                    entity = channel_id

            # 拉取历史消息
            messages = await client.get_messages(
                entity,
                limit=limit,
                offset_date=start_date
            )

            processed = 0
            for message in messages:
                if message.id:
                    await self.process_message(message, conversation_id)
                    processed += 1

            logger.info(f"历史消息拉取完成: 会话 {conversation_id}, 处理了 {processed}/{len(messages)} 条消息")
        except Exception as e:
            logger.error(f"拉取历史消息失败(conversation_id={conversation_id}): {e}")

    async def start_all_monitors(self):
        """启动所有会话的监控"""
        # 先启动队列处理器(如果还没启动)
        if self._queue_processor_task is None or self._queue_processor_task.done():
            self._queue_processor_task = asyncio.create_task(self._process_queue_loop())
            logger.info("消息队列处理器已启动")

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Conversation).where(
                    Conversation.status == "active",
                    Conversation.enable_realtime == True
                )
            )
            conversations = result.scalars().all()

        logger.info(f"启动 {len(conversations)} 个监控任务(实时监控)")

        # 并发启动监控（信号量控制并发数，避免 API 限流）
        sem = asyncio.Semaphore(10)
        startup_timeout = 5.0

        async def start_one(conv):
            async with sem:
                try:
                    await asyncio.wait_for(
                        self.start_monitor(conv.id),
                        timeout=startup_timeout
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"启动监控超时,跳过会话: {conv.id} ({conv.title})")
                    self.active_monitors.add(conv.id)
                except Exception as e:
                    logger.warning(f"启动监控异常,跳过会话: {conv.id}: {e}")

        await asyncio.gather(*[start_one(c) for c in conversations])

        # 启动历史消息拉取任务(后台运行)
        asyncio.create_task(self._fetch_history_background())

    async def _fetch_history_background(self):
        """后台任务:拉取启用历史消息的会话"""
        import asyncio
        await asyncio.sleep(5)  # 等待实时监控启动完成

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Conversation).where(
                    Conversation.status == "active",
                    Conversation.enable_history == True,
                    Conversation.total_messages == 0  # 只拉取没有消息的会话
                )
            )
            conversations = result.scalars().all()

        if not conversations:
            logger.info("没有需要拉取历史消息的会话")
            return

        logger.info(f"开始后台拉取 {len(conversations)} 个会话的历史消息...")

        success_count = 0
        for i, conv in enumerate(conversations):
            try:
                # 使用会话配置的天数
                days = conv.history_days if conv.history_days else 7
                await self.pull_history(conv.id, days=days, limit=100)
                success_count += 1

                # 每拉取10个会话记录一次进度
                if (i + 1) % 10 == 0:
                    logger.info(f"历史消息拉取进度: {i + 1}/{len(conversations)}")

                # 避免请求过快被Telegram限制
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"拉取会话 {conv.id} ({conv.title}) 历史消息失败: {e}")

        logger.info(f"历史消息拉取完成: 成功 {success_count}/{len(conversations)}")

    async def _process_queue_loop(self):
        """队列处理器循环 - 批量处理消息以提高性能"""
        logger.info("队列处理器循环已启动（批量模式）")
        try:
            while True:
                try:
                    # 批量从队列获取消息（最多50条）
                    batch_messages = []
                    batch_size = 50
                    
                    try:
                        # 获取第一条消息（阻塞等待）
                        message, conversation_id = await asyncio.wait_for(
                            self._message_queue.get(),
                            timeout=1.0
                        )
                        batch_messages.append((message, conversation_id))
                        
                        # 尝试获取更多消息（非阻塞）
                        while len(batch_messages) < batch_size:
                            try:
                                message, conversation_id = self._message_queue.get_nowait()
                                batch_messages.append((message, conversation_id))
                            except asyncio.QueueEmpty:
                                break
                    except asyncio.TimeoutError:
                        # 队列为空，继续等待
                        continue
                    
                    # 批量处理消息
                    if batch_messages:
                        await self._process_batch(batch_messages)
                        
                    # 队列积压监控和告警
                    queue_size = self._message_queue.qsize()
                    if queue_size > 100:  # 队列积压超过100条消息
                        logger.warning(f"消息队列积压严重: {queue_size} 条消息待处理")

                    if queue_size > 500:  # 严重积压
                        logger.error(f"消息队列严重积压: {queue_size} 条消息,可能导致消息丢失")

                except asyncio.TimeoutError:
                    # 超时是正常的,继续循环
                    continue
                except Exception as e:
                    logger.error(f"队列处理器异常: {e}")
                    await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.info("队列处理器循环已取消")
        except Exception as e:
            logger.error(f"队列处理器循环异常退出: {e}")
            # 异常退出后自动重启(延迟5秒)
            logger.info("5秒后自动重启队列处理器...")
            await asyncio.sleep(5)
            if self._running:
                self._queue_processor_task = asyncio.create_task(self._process_queue_loop())
                logger.info("队列处理器已自动重启")

    async def _process_batch(self, batch_messages: List[tuple]):
        """批量处理消息
        
        Args:
            batch_messages: 消息列表 [(message, conversation_id), ...]
        """
        if not batch_messages:
            return
            
        # 使用 semaphore 限制并发
        async with self._process_semaphore:
            # 按会话分组
            messages_by_conv = {}
            for message, conversation_id in batch_messages:
                if conversation_id not in messages_by_conv:
                    messages_by_conv[conversation_id] = []
                messages_by_conv[conversation_id].append(message)
            
            # 批量处理每个会话的消息
            for conversation_id, messages in messages_by_conv.items():
                try:
                    await self._process_batch_for_conversation(conversation_id, messages)
                except Exception as e:
                    logger.error(f"批量处理会话 {conversation_id} 失败: {e}")
                    # 批量失败时，逐条处理
                    for message in messages:
                        try:
                            await self.process_message(message, conversation_id)
                        except Exception as msg_error:
                            logger.error(f"单条处理消息 {message.id} 失败: {msg_error}")
                        finally:
                            self._queue_stats["processed"] += 1
                else:
                    self._queue_stats["processed"] += len(messages)

    async def _process_batch_for_conversation(self, conversation_id: int, messages: List[Message]):
        """批量处理单个会话的消息"""
        db = None
        try:
            db = AsyncSessionLocal()

            # 批量创建发送者和消息
            db_messages = []
            senders_cache = {}
            skipped_count = 0
            # 批内去重：记录已处理的消息ID
            processed_ids = set()

            # 加载自身账号ID用于过滤
            await self._load_self_user_ids()

            for message in messages:
                # 排除自身账号的消息
                if message.sender_id and message.sender_id in self._self_user_ids:
                    skipped_count += 1
                    continue

                # 批内去重检查
                if message.id in processed_ids:
                    skipped_count += 1
                    continue
                    
                # 获取或创建发送者
                sender = None
                if message.sender:
                    sender_id = message.sender_id
                    if sender_id in senders_cache:
                        sender = senders_cache[sender_id]
                    else:
                        sender = await self._get_or_create_sender(db, message)
                        if sender:
                            senders_cache[sender_id] = sender

                if not sender:
                    continue

                # 检查消息是否已存在（数据库去重）
                result = await db.execute(
                    select(MessageModel.id).where(MessageModel.id == message.id)
                )
                if result.scalar_one_or_none():
                    # 消息已存在，跳过
                    skipped_count += 1
                    processed_ids.add(message.id)  # 记录已存在
                    continue

                # 创建消息对象（但不立即flush）
                msg_date = message.date
                if msg_date.tzinfo is not None:
                    from app.utils import to_utc
                    msg_date = to_utc(msg_date).replace(tzinfo=None)

                db_message = MessageModel(
                    id=message.id,
                    conversation_id=conversation_id,
                    sender_id=sender.id,
                    message_type=self._get_message_type(message),
                    text=message.text,
                    caption=getattr(message, "caption", None),
                    date=msg_date,
                    views=getattr(message, "views", None),
                    forwards=getattr(message, "forwards", None),
                    has_media=message.media is not None,
                    is_reply=message.reply_to is not None,
                    reply_to_msg_id=message.reply_to_msg_id if message.reply_to else None,
                )
                db_messages.append(db_message)
                db.add(db_message)
                processed_ids.add(message.id)  # 记录已处理

            if skipped_count > 0:
                logger.debug(f"批量处理跳过 {skipped_count} 条重复消息")

            if db_messages:
                # 批量 flush（捕获主键冲突）
                try:
                    await db.flush()
                except Exception as flush_error:
                    # 如果 flush 失败（可能是主键冲突），逐条处理
                    logger.warning(f"批量 flush 失败，降级为逐条处理: {flush_error}")
                    await db.rollback()
                    await self._process_messages_individually(db, conversation_id, messages, senders_cache)
                    return

                # 批量处理关键词匹配
                for db_message in db_messages:
                    try:
                        # 创建一个简单的对象，有 text 和 date 属性供 match_message 使用
                        class _Msg:
                            pass
                        m = _Msg()
                        m.text = db_message.text
                        m.caption = None
                        m.date = db_message.date  # 添加 date 属性
                        matched_keywords = await self.keyword_matcher.match_message(
                            db, m, conversation_id
                        )

                        if matched_keywords:
                            # 获取发送者
                            sender = senders_cache.get(db_message.sender_id)
                            if sender:
                                await self.alert_service.create_alerts(
                                    db, db_message, sender, matched_keywords
                                )
                    except Exception as e:
                        logger.error(f"消息 {db_message.id} 关键词匹配失败: {e}")

                # 更新会话统计
                await self._update_conversation_stats(
                    db, conversation_id, db_messages[-1].id
                )

                # 更新最后消息时间
                self._session_last_message_time[conversation_id] = datetime.now()

            # 提交事务
            await db.commit()

            logger.info(f"批量处理完成: 会话 {conversation_id}, {len(db_messages)} 条消息, 跳过 {skipped_count} 条重复")

        except Exception as e:
            if db:
                try:
                    await db.rollback()
                except Exception:
                    pass
            logger.error(f"批量处理会话 {conversation_id} 失败: {e}")
            raise
        finally:
            if db:
                try:
                    await db.close()
                except Exception:
                    pass

    async def _process_messages_individually(self, db, conversation_id: int, messages: List[Message], senders_cache: Dict):
        """逐条处理消息（降级方案，用于批量处理失败时）"""
        for message in messages:
            try:
                # 获取发送者
                sender = senders_cache.get(message.sender_id) if message.sender else None
                if not sender and message.sender:
                    sender = await self._get_or_create_sender(db, message)
                    if sender:
                        senders_cache[message.sender_id] = sender

                if not sender:
                    continue

                # 检查消息是否已存在
                result = await db.execute(
                    select(MessageModel.id).where(MessageModel.id == message.id)
                )
                if result.scalar_one_or_none():
                    continue

                # 创建消息
                msg_date = message.date
                if msg_date.tzinfo is not None:
                    from app.utils import to_utc
                    msg_date = to_utc(msg_date).replace(tzinfo=None)

                db_message = MessageModel(
                    id=message.id,
                    conversation_id=conversation_id,
                    sender_id=sender.id,
                    message_type=self._get_message_type(message),
                    text=message.text,
                    caption=getattr(message, "caption", None),
                    date=msg_date,
                    views=getattr(message, "views", None),
                    forwards=getattr(message, "forwards", None),
                    has_media=message.media is not None,
                    is_reply=message.reply_to is not None,
                    reply_to_msg_id=message.reply_to_msg_id if message.reply_to else None,
                )
                db.add(db_message)
                await db.flush()

                # 关键词匹配
                class _Msg:
                    pass
                m = _Msg()
                m.text = db_message.text
                m.caption = None
                m.date = db_message.date

                matched_keywords = await self.keyword_matcher.match_message(
                    db, m, conversation_id
                )

                if matched_keywords:
                    await self.alert_service.create_alerts(
                        db, db_message, sender, matched_keywords
                    )

            except Exception as e:
                logger.error(f"逐条处理消息 {message.id} 失败: {e}")
                continue

        # 更新会话统计
        if messages:
            await self._update_conversation_stats(
                db, conversation_id, messages[-1].id
            )

    async def stop_all_monitors(self):
        """停止所有监控"""
        # 停止队列处理器
        if self._queue_processor_task and not self._queue_processor_task.done():
            self._queue_processor_task.cancel()
            try:
                await self._queue_processor_task
            except asyncio.CancelledError:
                pass
            self._queue_processor_task = None
            logger.info("队列处理器已停止")

        # 停止所有监控会话
        for conversation_id in list(self.active_monitors):
            await self.stop_monitor(conversation_id)
        logger.info("所有监控已停止")


# 全局消息监控器实例
message_monitor = MessageMonitor()
