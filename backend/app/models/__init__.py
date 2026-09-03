"""数据库模型导入"""
# Case 必须在 Alert 之前导入，否则 Alert 的 case_id 外键无法解析
from app.models.case import Case, CaseAlert, CasePerson
from app.models.account import TelegramAccount
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.sender import Sender
from app.models.keyword import KeywordGroup, Keyword
from app.models.alert import Alert
from app.models.notification_config import NotificationConfig
from app.models.notification_log import NotificationLog
from app.models.settings import Settings
from app.models.proxy_node import ProxyNode
from app.models.phone_record import PhoneRecord
from app.models.audit import AuditLog
from app.models.watchlist import Watchlist

__all__ = [
    "TelegramAccount",
    "Conversation",
    "Message",
    "Sender",
    "KeywordGroup",
    "Keyword",
    "Alert",
    "NotificationConfig",
    "NotificationLog",
    "Settings",
    "ProxyNode",
    "Case",
    "CaseAlert",
    "CasePerson",
    "AuditLog",
    "Watchlist",
]
