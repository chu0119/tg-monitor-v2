"""运行时代理配置服务（不依赖内置 Clash/Mihomo）。"""
from __future__ import annotations

import os
from typing import Optional
from urllib.parse import quote

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.settings import Settings

PROXY_KEYS = {
    "enabled": "proxy_enabled",
    "protocol": "proxy_protocol",
    "host": "proxy_host",
    "port": "proxy_port",
    "username": "proxy_username",
    "password": "proxy_password",
}


def _to_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


async def get_proxy_config(db: AsyncSession) -> dict:
    """从 settings 表读取代理配置。"""
    rows = await db.execute(
        select(Settings).where(Settings.key_name.in_(list(PROXY_KEYS.values())))
    )
    mapping = {row.key_name: row.value for row in rows.scalars().all()}

    enabled = _to_bool(mapping.get(PROXY_KEYS["enabled"]), default=False)
    protocol = (mapping.get(PROXY_KEYS["protocol"]) or "socks5").lower()
    host = (mapping.get(PROXY_KEYS["host"]) or "").strip()
    port_raw = mapping.get(PROXY_KEYS["port"]) or "1080"

    try:
        port = int(port_raw)
    except ValueError:
        port = 1080

    return {
        "enabled": enabled,
        "protocol": protocol,
        "host": host,
        "port": port,
        "username": (mapping.get(PROXY_KEYS["username"]) or "").strip() or None,
        "password": (mapping.get(PROXY_KEYS["password"]) or "").strip() or None,
    }


async def save_proxy_config(db: AsyncSession, config: dict) -> dict:
    """保存代理配置到 settings 表。"""
    values = {
        PROXY_KEYS["enabled"]: "true" if config.get("enabled") else "false",
        PROXY_KEYS["protocol"]: config.get("protocol", "socks5"),
        PROXY_KEYS["host"]: config.get("host", ""),
        PROXY_KEYS["port"]: str(config.get("port", 1080)),
        PROXY_KEYS["username"]: config.get("username") or "",
        PROXY_KEYS["password"]: config.get("password") or "",
    }

    for key_name, value in values.items():
        result = await db.execute(select(Settings).where(Settings.key_name == key_name))
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = value
            setting.category = "proxy"
        else:
            db.add(Settings(key_name=key_name, value=value, category="proxy"))

    await db.commit()
    return config


def build_proxy_url(config: dict) -> Optional[str]:
    """将代理配置转换为 URL。"""
    if not config.get("enabled"):
        return None

    protocol = (config.get("protocol") or "").lower()
    host = (config.get("host") or "").strip()
    port = config.get("port")

    if protocol not in {"http", "https", "socks5"}:
        return None
    if not host or not isinstance(port, int):
        return None

    username = config.get("username")
    password = config.get("password")

    auth = ""
    if username:
        safe_user = quote(username, safe="")
        safe_pass = quote(password or "", safe="")
        auth = f"{safe_user}:{safe_pass}@"

    return f"{protocol}://{auth}{host}:{port}"


def apply_proxy_config(config: dict) -> dict:
    """将代理配置应用到当前进程环境变量与全局 settings。"""
    proxy_url = build_proxy_url(config)

    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "SOCKS5_PROXY"):
        os.environ.pop(key, None)

    settings.HTTP_PROXY = None
    settings.HTTPS_PROXY = None
    settings.SOCKS5_PROXY = None

    if not proxy_url:
        logger.info("代理已禁用或配置不完整，已清空运行时代理环境变量")
        return {"applied": False, "proxy_url": None}

    protocol = config.get("protocol")
    if protocol in {"http", "https"}:
        os.environ["HTTP_PROXY"] = proxy_url
        os.environ["HTTPS_PROXY"] = proxy_url
        settings.HTTP_PROXY = proxy_url
        settings.HTTPS_PROXY = proxy_url
    elif protocol == "socks5":
        os.environ["ALL_PROXY"] = proxy_url
        os.environ["SOCKS5_PROXY"] = proxy_url
        settings.SOCKS5_PROXY = proxy_url

    logger.info(f"已应用运行时代理配置: {protocol}://{config.get('host')}:{config.get('port')}")
    return {"applied": True, "proxy_url": proxy_url}
