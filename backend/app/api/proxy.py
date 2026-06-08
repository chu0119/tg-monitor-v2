"""代理管理 API（简化版，不依赖内置 Clash/Mihomo）。"""
from __future__ import annotations


import time
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services.runtime_proxy_service import (
    apply_proxy_config,
    get_proxy_config,
    save_proxy_config,
)

router = APIRouter(prefix="/proxy", tags=["proxy"])


class ProxyConfigRequest(BaseModel):
    enabled: bool = True
    protocol: Literal["http", "https", "socks5"] = "socks5"
    host: str = Field(..., min_length=1, max_length=255)
    port: int = Field(..., ge=1, le=65535)
    username: Optional[str] = Field(default=None, max_length=128)
    password: Optional[str] = Field(default=None, max_length=256)


class ProxyTestRequest(BaseModel):
    protocol: Literal["http", "https", "socks5"]
    host: str = Field(..., min_length=1, max_length=255)
    port: int = Field(..., ge=1, le=65535)
    timeout_sec: int = Field(default=5, ge=1, le=30)


@router.get("/status")
async def proxy_status(db: AsyncSession = Depends(get_db)):
    config = await get_proxy_config(db)
    runtime = apply_proxy_config(config)
    return {
        "success": True,
        "status": {
            "enabled": config["enabled"],
            "protocol": config["protocol"],
            "host": config["host"],
            "port": config["port"],
            "username": config.get("username"),
            "configured": bool(config["host"] and config["port"]),
            "applied": runtime["applied"],
            "proxy_url": runtime["proxy_url"],
        },
    }


@router.post("/config")
async def set_proxy_config(request: ProxyConfigRequest, db: AsyncSession = Depends(get_db)):
    config = request.model_dump()
    await save_proxy_config(db, config)
    runtime = apply_proxy_config(config)
    return {
        "success": True,
        "message": "代理配置已保存并应用",
        "config": {
            **config,
            "password": "***" if config.get("password") else None,
            "applied": runtime["applied"],
        },
    }


@router.post("/disable")
async def disable_proxy(db: AsyncSession = Depends(get_db)):
    current = await get_proxy_config(db)
    current["enabled"] = False
    await save_proxy_config(db, current)
    apply_proxy_config(current)
    return {"success": True, "message": "代理已禁用"}


@router.post("/enable")
async def enable_proxy(db: AsyncSession = Depends(get_db)):
    current = await get_proxy_config(db)
    if not current.get("host"):
        raise HTTPException(status_code=400, detail="请先配置代理主机和端口")
    current["enabled"] = True
    await save_proxy_config(db, current)
    apply_proxy_config(current)
    return {"success": True, "message": "代理已启用"}


@router.post("/test")
async def test_proxy_connectivity(request: ProxyTestRequest):
    import urllib.request
    import urllib.error

    target = "https://www.google.com"
    proxy_url = f"{request.protocol}://{request.host}:{request.port}"
    proxy_handler = urllib.request.ProxyHandler({"https": proxy_url, "http": proxy_url})
    opener = urllib.request.build_opener(proxy_handler)

    start = time.perf_counter()
    try:
        req = urllib.request.Request(target, headers={"User-Agent": "Mozilla/5.0"})
        resp = opener.open(req, timeout=request.timeout_sec)
        resp.read()
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return {
            "success": True,
            "latency_ms": elapsed_ms,
            "message": f"通过代理访问 {target} 成功 ({elapsed_ms}ms)",
            "target": target,
        }
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return {
            "success": False,
            "latency_ms": elapsed_ms,
            "message": f"通过代理访问 {target} 失败: {e}",
            "target": target,
        }


@router.get("/latency")
async def test_current_proxy_latency(db: AsyncSession = Depends(get_db)):
    config = await get_proxy_config(db)
    if not config.get("enabled"):
        return {"success": False, "latency_ms": None, "message": "代理未启用"}

    req = ProxyTestRequest(
        protocol=config["protocol"],
        host=config["host"],
        port=config["port"],
    )
    return await test_proxy_connectivity(req)


# 兼容旧前端调用：start/stop/restart
@router.post("/start")
async def start_proxy(db: AsyncSession = Depends(get_db)):
    return await enable_proxy(db)


@router.post("/stop")
async def stop_proxy(db: AsyncSession = Depends(get_db)):
    return await disable_proxy(db)


@router.post("/restart")
async def restart_proxy(db: AsyncSession = Depends(get_db)):
    await disable_proxy(db)
    return await enable_proxy(db)


# 下列旧节点接口保留为兼容响应，明确告知已下线
@router.post("/subscribe")
async def deprecated_subscribe():
    raise HTTPException(status_code=410, detail="订阅节点功能已下线，请使用代理主机/端口配置")


@router.post("/import")
async def deprecated_import():
    raise HTTPException(status_code=410, detail="节点导入功能已下线，请使用代理主机/端口配置")


@router.get("/nodes")
async def deprecated_nodes():
    return {"success": True, "total": 0, "nodes": [], "message": "节点功能已下线"}


@router.post("/nodes/{node_id}/select")
async def deprecated_select_node(node_id: int):
    raise HTTPException(status_code=410, detail=f"节点选择功能已下线（node_id={node_id}）")


@router.post("/nodes/{node_id}/test")
async def deprecated_test_node(node_id: int):
    raise HTTPException(status_code=410, detail=f"节点测试功能已下线（node_id={node_id}）")


@router.delete("/nodes")
async def deprecated_clear_nodes():
    return {"success": True, "deleted_count": 0, "message": "节点功能已下线"}


@router.delete("/nodes/{node_id}")
async def deprecated_delete_node(node_id: int):
    return {"success": True, "node_id": node_id, "message": "节点功能已下线"}
