"""通知发送服务 - 优化版"""
import asyncio
import aiohttp
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Tuple, Dict, Any
from datetime import datetime
from loguru import logger
from app.models import NotificationConfig, Alert, Message, Sender
from app.core.config import settings
from app.utils import format_datetime


# 告警级别中文映射
ALERT_LEVEL_LABELS = {
    "low": "低",
    "medium": "中",
    "high": "高",
    "critical": "严重",
}


def get_alert_level_label(level: str) -> str:
    """获取告警级别的中文标签"""
    return ALERT_LEVEL_LABELS.get(level, level)


class NotificationService:
    """通知服务 - 优化版，使用共享的 ClientSession"""

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建共享的 aiohttp 会话"""
        async with self._session_lock:
            if self._session is None or self._session.closed:
                timeout = aiohttp.ClientTimeout(total=30, connect=10)
                self._session = aiohttp.ClientSession(timeout=timeout)
                logger.info("创建新的 aiohttp.ClientSession")
            return self._session

    async def close(self):
        """关闭共享的 aiohttp 会话"""
        async with self._session_lock:
            if self._session and not self._session.closed:
                await self._session.close()
                logger.info("aiohttp.ClientSession 已关闭")
                # 等待连接完全关闭
                await asyncio.sleep(0.25)

    async def send_notification(
        self,
        config: NotificationConfig,
        alert: Alert,
        message: Message,
        sender: Sender
    ) -> Tuple[bool, Optional[str]]:
        """发送通知"""
        try:
            # 提前提取所有需要的属性，避免懒加载
            alert_id = alert.id
            keyword_text = alert.keyword_text
            keyword_group_name = alert.keyword_group_name
            alert_level = alert.alert_level
            message_preview = alert.message_preview

            # 安全地访问 created_at，捕获任何异常
            try:
                created_at = alert.created_at
                if created_at:
                    created_at_str = created_at.strftime('%Y-%m-%d %H:%M:%S')
                    created_at_iso = created_at.isoformat()
                else:
                    created_at_str = ''
                    created_at_iso = ''
            except Exception as e:
                logger.warning(f"无法访问 alert.created_at: {e}")
                created_at_str = ''
                created_at_iso = ''

            # 提取 sender 属性
            try:
                sender_username = sender.username if sender.username else ''
                sender_first_name = sender.first_name if sender.first_name else ''
                sender_name = sender_username or sender_first_name
            except Exception as e:
                logger.warning(f"无法访问 sender 属性: {e}")
                sender_name = 'Unknown'

            # 提取 message 属性
            try:
                message_text = message.text if message.text else ''
                message_date = message.date if message.date else None
                if message_date:
                    message_date_iso = message_date.isoformat()
                else:
                    message_date_iso = ''
            except Exception as e:
                logger.warning(f"无法访问 message 属性: {e}")
                message_text = ''
                message_date_iso = ''

            # 构建简单的数据字典
            alert_data: Dict[str, Any] = {
                'id': alert_id,
                'keyword_text': keyword_text,
                'keyword_group_name': keyword_group_name,
                'alert_level': alert_level,
                'message_preview': message_preview,
                'created_at_str': created_at_str,
                'created_at_iso': created_at_iso,
            }
            sender_data: Dict[str, Any] = {
                'name': sender_name,
            }
            message_data: Dict[str, Any] = {
                'text': message_text,
                'date_iso': message_date_iso,
            }

            if config.notification_type == "email":
                return await self._send_email_with_data(config, alert_data, sender_data)
            elif config.notification_type == "dingtalk":
                return await self._send_dingtalk_with_data(config, alert_data, sender_data)
            elif config.notification_type == "wecom":
                return await self._send_wecom_with_data(config, alert_data, sender_data)
            elif config.notification_type == "serverchan":
                return await self._send_serverchan_with_data(config, alert_data, sender_data)
            elif config.notification_type == "webhook":
                return await self._send_webhook_with_data(config, alert_data, sender_data, message_data)
            elif config.notification_type == "telegram":
                return await self._send_telegram_with_data(config, alert_data, sender_data)
            else:
                return False, f"不支持的通知类型: {config.notification_type}"

        except Exception as e:
            logger.error(f"发送通知失败: {e}")
            return False, str(e)

    async def _send_email_with_data(
        self,
        config: NotificationConfig,
        alert_data: Dict[str, Any],
        sender_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """发送邮件通知"""
        try:
            cfg = config.config
            msg = MIMEMultipart("alternative")
            msg["Subject"] = config.title_template or f"告警通知: {alert_data['keyword_group_name']}"
            msg["From"] = cfg.get("from_email", settings.SMTP_FROM)
            msg["To"] = ", ".join(cfg.get("to_emails", []))

            # 构建邮件内容
            text = f"""
            <html>
            <body>
                <h2>告警通知</h2>
                <p><strong>关键词组:</strong> {alert_data['keyword_group_name']}</p>
                <p><strong>关键词:</strong> {alert_data['keyword_text']}</p>
                <p><strong>级别:</strong> {get_alert_level_label(alert_data['alert_level'])}</p>
                <p><strong>发送者:</strong> {sender_data['name']}</p>
                <p><strong>消息预览:</strong></p>
                <p>{alert_data['message_preview']}</p>
                <p><strong>时间:</strong> {alert_data['created_at_str']}</p>
            </body>
            </html>
            """
            msg.attach(MIMEText(text, "html", "utf-8"))

            # 发送邮件（使用线程池因为smtplib是同步的）
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._send_smtp,
                msg,
                cfg.get("smtp_host", settings.SMTP_HOST),
                cfg.get("smtp_port", settings.SMTP_PORT),
                cfg.get("smtp_user", settings.SMTP_USER),
                cfg.get("smtp_password", settings.SMTP_PASSWORD),
            )

            return True, None

        except Exception as e:
            logger.error(f"发送邮件失败: {e}")
            return False, str(e)

    def _send_smtp(self, msg, host, port, user, password):
        """SMTP发送"""
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)

    async def _send_dingtalk_with_data(
        self,
        config: NotificationConfig,
        alert_data: Dict[str, Any],
        sender_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """发送钉钉通知"""
        cfg = config.config

        text = f"""
【告警通知】
关键词组: {alert_data['keyword_group_name']}
关键词: {alert_data['keyword_text']}
级别: {get_alert_level_label(alert_data['alert_level'])}
发送者: {sender_data['name']}
消息: {alert_data['message_preview']}
时间: {alert_data['created_at_str']}
        """

        payload = {
            "msgtype": "text",
            "text": {"content": text}
        }

        # 获取 webhook URL
        webhook_url = cfg.get("webhook_url") or cfg.get("webhook")

        # 如果有加签密钥，添加签名
        if cfg.get("secret"):
            import time
            import hmac
            import hashlib
            import base64
            import urllib.parse

            timestamp = str(int(time.time() * 1000))
            secret_enc = cfg["secret"].encode('utf-8')
            string_to_sign = f'{timestamp}\n{cfg["secret"]}'
            string_to_sign_enc = string_to_sign.encode('utf-8')
            hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
            sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
            webhook_url = f"{webhook_url}&timestamp={timestamp}&sign={sign}"

        session = await self._get_session()
        try:
            async with session.post(webhook_url, json=payload) as resp:
                result = await resp.json()
                if result.get("errcode") == 0:
                    return True, None
                return False, result.get("errmsg")
        except asyncio.TimeoutError:
            return False, "请求超时"
        except Exception as e:
            return False, str(e)

    async def _send_wecom_with_data(
        self,
        config: NotificationConfig,
        alert_data: Dict[str, Any],
        sender_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """发送企业微信通知"""
        cfg = config.config

        text = f"""
【告警通知】
关键词组: {alert_data['keyword_group_name']}
关键词: {alert_data['keyword_text']}
级别: {get_alert_level_label(alert_data['alert_level'])}
发送者: {sender_data['name']}
消息: {alert_data['message_preview']}
时间: {alert_data['created_at_str']}
        """

        payload = {
            "msgtype": "text",
            "text": {"content": text}
        }

        webhook_url = cfg.get("webhook_url") or cfg.get("webhook")

        session = await self._get_session()
        try:
            async with session.post(webhook_url, json=payload) as resp:
                result = await resp.json()
                if result.get("errcode") == 0:
                    return True, None
                return False, result.get("errmsg")
        except asyncio.TimeoutError:
            return False, "请求超时"
        except Exception as e:
            return False, str(e)

    async def _send_serverchan_with_data(
        self,
        config: NotificationConfig,
        alert_data: Dict[str, Any],
        sender_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """发送Server酱通知"""
        cfg = config.config

        url = f"https://sctapi.ftqq.com/{cfg['sckey']}.send"
        payload = {
            "title": f"告警: {alert_data['keyword_group_name']} - {alert_data['keyword_text']}",
            "desp": f"""
关键词组: {alert_data['keyword_group_name']}
关键词: {alert_data['keyword_text']}
级别: {get_alert_level_label(alert_data['alert_level'])}
发送者: {sender_data['name']}
消息: {alert_data['message_preview']}
            """
        }

        session = await self._get_session()
        try:
            async with session.post(url, data=payload) as resp:
                result = await resp.json()
                if result.get("code") == 0:
                    return True, None
                return False, result.get("message")
        except asyncio.TimeoutError:
            return False, "请求超时"
        except Exception as e:
            return False, str(e)

    async def _send_webhook_with_data(
        self,
        config: NotificationConfig,
        alert_data: Dict[str, Any],
        sender_data: Dict[str, Any],
        message_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """发送自定义Webhook通知"""
        cfg = config.config

        payload = {
            "alert": {
                "id": alert_data['id'],
                "keyword": alert_data['keyword_text'],
                "keyword_group": alert_data['keyword_group_name'],
                "level": get_alert_level_label(alert_data['alert_level']),
                "message_preview": alert_data['message_preview'],
                "created_at": alert_data['created_at_iso'],
            },
            "sender": sender_data,
            "message": message_data,
        }

        headers = cfg.get("headers", {})

        session = await self._get_session()
        method = cfg.get("method", "POST").upper()
        try:
            http_method = getattr(session, method.lower(), session.post)
            async with http_method(
                cfg["url"],
                json=payload,
                headers=headers,
            ) as resp:
                if resp.status < 400:
                    return True, None
                return False, f"HTTP {resp.status}"
        except asyncio.TimeoutError:
            return False, "请求超时"
        except Exception as e:
            return False, str(e)

    async def _send_telegram_with_data(
        self,
        config: NotificationConfig,
        alert_data: Dict[str, Any],
        sender_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """发送Telegram通知"""
        cfg = config.config

        text = f"""
🚨 <b>告警通知</b>

<b>关键词组:</b> {alert_data['keyword_group_name']}
<b>关键词:</b> {alert_data['keyword_text']}
<b>级别:</b> {alert_data['alert_level']}
<b>发送者:</b> {sender_data['name']}

<b>消息预览:</b>
{alert_data['message_preview']}

<b>时间:</b> {alert_data['created_at_str']}
        """

        url = f"https://api.telegram.org/bot{cfg['bot_token']}/sendMessage"
        payload = {
            "chat_id": cfg["chat_id"],
            "text": text.strip(),
            "parse_mode": "HTML"
        }

        session = await self._get_session()
        try:
            # Telegram API 需要走代理（国内无法直连）
            telegram_proxy = settings.HTTP_PROXY or settings.HTTPS_PROXY
            if telegram_proxy:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as proxy_session:
                    async with proxy_session.post(url, json=payload, proxy=telegram_proxy) as resp:
                        result = await resp.json()
                        if result.get("ok"):
                            return True, None
                        return False, result.get("description")
            else:
                async with session.post(url, json=payload) as resp:
                    result = await resp.json()
                if result.get("ok"):
                    return True, None
                return False, result.get("description")
        except asyncio.TimeoutError:
            return False, "请求超时"
        except Exception as e:
            return False, str(e)

    async def test_notification(self, config: NotificationConfig, test_message: str) -> bool:
        """测试通知配置"""
        logger.info(f"开始测试通知: config_id={config.id}, type={config.notification_type}, message={test_message}")

        # 创建测试告警对象
        class TestAlert:
            id = 0
            keyword_text = "测试关键词"
            keyword_group_name = "测试组"
            alert_level = "medium"
            message_preview = test_message
            created_at = datetime.now()

        class TestSender:
            username = "test_user"
            first_name = "测试用户"

        class TestMessage:
            id = 0
            text = test_message
            date = datetime.now()

        success, error = await self.send_notification(
            config,
            TestAlert(),
            TestMessage(),
            TestSender()
        )

        if success:
            logger.info(f"测试通知发送成功: config_id={config.id}")
        else:
            logger.error(f"测试通知发送失败: config_id={config.id}, error={error}")

        return success


# 全局通知服务实例
notification_service = NotificationService()
