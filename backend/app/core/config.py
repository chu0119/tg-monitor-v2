"""应用配置管理 - 本地开发版"""
import secrets
import warnings
from pathlib import Path
from typing import List, Optional
from zoneinfo import ZoneInfo
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from loguru import logger


class Settings(BaseSettings):
    """应用配置"""

    # 项目信息
    PROJECT_NAME: str = "Telegram 监控告警系统"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"

    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    # 生产环境应通过环境变量设置 DEBUG=False
    DEBUG: bool = False

    # MySQL 数据库配置
    MYSQL_HOST: Optional[str] = None
    MYSQL_PORT: int = 3306
    MYSQL_USER: Optional[str] = None
    MYSQL_PASSWORD: Optional[str] = None
    MYSQL_DATABASE: str = "tg_monitor"

    def get_database_url(self) -> str:
        """获取 MySQL 连接 URL"""
        if not all([self.MYSQL_HOST, self.MYSQL_USER, self.MYSQL_DATABASE]):
            raise ValueError(
                "MySQL 数据库配置不完整。请设置 MYSQL_HOST, MYSQL_USER 和 MYSQL_DATABASE。"
            )

        pwd = f":{self.MYSQL_PASSWORD}" if self.MYSQL_PASSWORD else ""
        return f"mysql+aiomysql://{self.MYSQL_USER}{pwd}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"

    def is_database_configured(self) -> bool:
        """检查数据库是否已配置"""
        return all([self.MYSQL_HOST, self.MYSQL_USER, self.MYSQL_DATABASE])

    # JWT 配置
    JWT_SECRET_KEY: Optional[str] = None
    ALGORITHM: str = "HS256"
    # Token 有效期：4小时 (240分钟) - 生产环境建议使用 refresh token 机制
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 240

    @property
    def SECRET_KEY(self) -> str:
        """获取 JWT 密钥，优先使用环境变量，否则自动生成"""
        if self.JWT_SECRET_KEY:
            return self.JWT_SECRET_KEY
        # 自动生成一个安全的随机密钥
        warnings.warn(
            "JWT_SECRET_KEY 未设置，使用自动生成的临时密钥。"
            "请在生产环境中设置环境变量 JWT_SECRET_KEY！"
        )
        logger.warning(
            "JWT_SECRET_KEY 未设置，使用自动生成的临时密钥。"
            "请在生产环境中设置环境变量 JWT_SECRET_KEY！"
        )
        return secrets.token_urlsafe(32)

    # Telegram 配置
    TELEGRAM_API_ID: Optional[int] = None
    TELEGRAM_API_HASH: Optional[str] = None

    # 代理配置
    HTTP_PROXY: Optional[str] = None
    HTTPS_PROXY: Optional[str] = None
    SOCKS5_PROXY: Optional[str] = None

    # 通知配置
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None

    # PROJECT_DIR 是项目根目录（tgjiankong/）
    PROJECT_DIR: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent.parent)

    # 文件存储（全部基于 PROJECT_DIR 的绝对路径）
    UPLOAD_DIR: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent.parent / "uploads")
    SESSION_DIR: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent.parent / "backend" / "sessions")
    EXPORT_DIR: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent.parent / "exports")
    BACKUP_DIR: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent.parent / "backups")

    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = Field(default_factory=lambda: str(Path(__file__).parent.parent.parent.parent / "logs" / "app.log"))

    # 时区配置
    TIMEZONE: str = "Asia/Shanghai"

    @property
    def tz_info(self) -> ZoneInfo:
        """获取时区信息对象"""
        return ZoneInfo(self.TIMEZONE)

    # CORS 配置
    # 安全警告：允许所有域名访问仅适用于开发/测试环境
    # 生产环境必须配置具体的允许来源列表，例如：
    # CORS_ORIGINS: List[str] = ["https://yourdomain.com", "https://app.yourdomain.com"]
    # 可以通过环境变量 CORS_ORIGINS 覆盖，多个域名用逗号分隔
    CORS_ORIGINS: List[str] = ["*"]  # 默认：允许所有域名访问（仅测试阶段）

    # WebSocket 令牌（可选，用于生产环境）
    # 设置后，WebSocket 连接需要提供此令牌才能连接
    # 通过环境变量 WS_TOKEN 配置
    WS_TOKEN: Optional[str] = None  # None 表示不验证令牌（开发环境）

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()

# 创建必要的目录
settings.UPLOAD_DIR.mkdir(exist_ok=True)
settings.SESSION_DIR.mkdir(exist_ok=True)
settings.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
settings.BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# 创建日志目录
log_file_path = Path(settings.LOG_FILE)
log_file_path.parent.mkdir(parents=True, exist_ok=True)
