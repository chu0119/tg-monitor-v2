"""代理管理 API"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from loguru import logger
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import json

from app.api.deps import get_db
from app.models.proxy_node import ProxyNode as ProxyNodeModel
from app.models.settings import Settings
from app.proxy.manager import ProxyManager
from app.proxy.subscribe_parser import ProxyNode

router = APIRouter(prefix="/proxy", tags=["proxy"])

# 代理管理器实例（延迟初始化）
_proxy_manager_instance = None


async def get_proxy_manager():
    """获取代理管理器单例实例"""
    global _proxy_manager_instance
    if _proxy_manager_instance is None:
        _proxy_manager_instance = await ProxyManager.get_instance()
    return _proxy_manager_instance


class SubscribeRequest(BaseModel):
    """订阅请求"""
    url: str = Field(..., description="订阅链接URL")
    replace: bool = Field(default=True, description="是否替换现有节点")


class ImportNodesRequest(BaseModel):
    """手动导入节点请求"""
    nodes_text: str = Field(..., description="节点链接文本，每行一个，支持 ss:// ssr:// vmess:// trojan:// vless:// hysteria2:// hysteria2://")


class NodeSelectRequest(BaseModel):
    """节点选择请求"""
    proxy_port: int = Field(default=7897, description="代理端口")


@router.get("/status")
async def proxy_status():
    """获取代理状态"""
    try:
        proxy_manager = await get_proxy_manager()
        status = await proxy_manager.get_status()
        return {
            "success": True,
            "status": status
        }
    except Exception as e:
        logger.error(f"获取代理状态失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/subscribe")
async def parse_subscribe(
    request: SubscribeRequest,
    db: AsyncSession = Depends(get_db)
):
    """解析订阅链接并保存节点到数据库"""
    try:
        proxy_manager = await get_proxy_manager()
        # 解析订阅链接
        nodes = await proxy_manager.parse_subscription(request.url)

        if not nodes:
            raise HTTPException(status_code=400, detail="未解析到任何节点")

        # 如果要替换，先删除旧节点
        if request.replace:
            await db.execute(delete(ProxyNodeModel))
            logger.info("已清空旧节点")

        # 保存节点到数据库
        saved_nodes = []
        for node in nodes:
            # 检查是否已存在相同名称的节点
            existing = await db.execute(
                select(ProxyNodeModel).where(ProxyNodeModel.name == node.name)
            )
            if existing.scalar_one_or_none() and not request.replace:
                continue  # 跳过已存在的节点

            # 创建节点记录
            node_model = ProxyNodeModel(
                name=node.name,
                type=node.type,
                server=node.server,
                port=node.port,
                config_json=json.dumps(node.to_dict(), ensure_ascii=False),
                subscription_url=request.url,
                is_selected=False,
                latency_ms=None
            )
            db.add(node_model)
            saved_nodes.append(node.name)

        await db.commit()
        logger.info(f"保存了 {len(saved_nodes)} 个节点")

        # 保存订阅URL到settings
        result = await db.execute(
            select(Settings).where(Settings.key_name == "subscription_url")
        )
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = request.url
        else:
            setting = Settings(
                key_name="subscription_url",
                value=request.url,
                category="proxy"
            )
            db.add(setting)
        await db.commit()

        return {
            "success": True,
            "total_nodes": len(nodes),
            "saved_nodes": len(saved_nodes),
            "nodes": [{"name": n.name, "type": n.type, "server": n.server} for n in nodes[:10]]  # 只返回前10个预览
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"解析订阅失败: {e}")
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")


@router.post("/import")
async def import_nodes(
    request: ImportNodesRequest,
    db: AsyncSession = Depends(get_db)
):
    """手动导入节点（支持粘贴单条或多条节点URI）"""
    try:
        from app.proxy.subscribe_parser import SubscribeParser
        nodes = await SubscribeParser._parse_uri_lines(request.nodes_text)

        if not nodes:
            raise HTTPException(status_code=400, detail="未解析到任何节点，请检查格式（支持 ss:// ssr:// vmess:// trojan:// vless:// hysteria2://）")

        saved_nodes = []
        for node in nodes:
            existing = await db.execute(
                select(ProxyNodeModel).where(ProxyNodeModel.name == node.name)
            )
            if existing.scalar_one_or_none():
                continue

            node_model = ProxyNodeModel(
                name=node.name,
                type=node.type,
                server=node.server,
                port=node.port,
                config_json=json.dumps(node.to_dict(), ensure_ascii=False),
                subscription_url="manual",
                is_selected=False,
                latency_ms=None
            )
            db.add(node_model)
            saved_nodes.append(node.name)

        await db.commit()

        return {
            "success": True,
            "total_nodes": len(nodes),
            "saved_nodes": len(saved_nodes),
            "nodes": [{"name": n.name, "type": n.type, "server": n.server} for n in nodes]
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"导入节点失败: {e}")
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


@router.get("/nodes")
async def list_nodes(
    db: AsyncSession = Depends(get_db)
):
    """获取节点列表（从数据库读取）"""
    try:
        result = await db.execute(
            select(ProxyNodeModel).order_by(ProxyNodeModel.created_at.desc())
        )
        nodes = result.scalars().all()

        return {
            "success": True,
            "total": len(nodes),
            "nodes": [
                {
                    "id": node.id,
                    "name": node.name,
                    "type": node.type,
                    "server": node.server,
                    "port": node.port,
                    "is_selected": node.is_selected,
                    "latency_ms": node.latency_ms,
                    "created_at": node.created_at.isoformat() if node.created_at else None
                }
                for node in nodes
            ]
        }

    except Exception as e:
        logger.error(f"获取节点列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.post("/nodes/{node_id}/select")
async def select_node(
    node_id: int,
    request: NodeSelectRequest = None,
    db: AsyncSession = Depends(get_db)
):
    """选择节点，生成配置，重启mihomo"""
    try:
        proxy_manager = await get_proxy_manager()
        # 获取节点
        result = await db.execute(
            select(ProxyNodeModel).where(ProxyNodeModel.id == node_id)
        )
        node_model = result.scalar_one_or_none()

        if not node_model:
            raise HTTPException(status_code=404, detail="节点不存在")

        # 解析节点配置
        node_dict = json.loads(node_model.config_json)
        node = ProxyNode(
            name=node_dict["name"],
            type=node_dict["type"],
            server=node_dict["server"],
            port=node_dict["port"],
            params=node_dict.get("params", {})
        )

        # 获取代理端口
        proxy_port = request.proxy_port if request else 7897

        # 选择节点（生成配置并重启mihomo）
        success = await proxy_manager.select_node(node, proxy_port)

        if not success:
            raise HTTPException(status_code=500, detail="选择节点失败")

        # 更新数据库中的选中状态
        await db.execute(
            ProxyNodeModel.__table__.update().values(is_selected=False)
        )
        node_model.is_selected = True

        # 保存当前选中的节点ID到settings
        result = await db.execute(
            select(Settings).where(Settings.key_name == "selected_node_id")
        )
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = str(node_id)
        else:
            setting = Settings(
                key_name="selected_node_id",
                value=str(node_id),
                category="proxy"
            )
            db.add(setting)

        # 合并为一次commit（问题10修复）
        await db.commit()

        logger.info(f"已选择节点: {node.name}")

        return {
            "success": True,
            "node_id": node_id,
            "node_name": node.name,
            "proxy_port": proxy_port,
            "message": f"已选择节点 {node.name}"
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"选择节点失败: {e}")
        raise HTTPException(status_code=500, detail=f"选择失败: {str(e)}")


@router.post("/nodes/{node_id}/test")
async def test_node(
    node_id: int,
    db: AsyncSession = Depends(get_db)
):
    """测试节点延迟"""
    try:
        proxy_manager = await get_proxy_manager()
        # 获取节点
        result = await db.execute(
            select(ProxyNodeModel).where(ProxyNodeModel.id == node_id)
        )
        node_model = result.scalar_one_or_none()

        if not node_model:
            raise HTTPException(status_code=404, detail="节点不存在")

        # 解析节点配置
        node_dict = json.loads(node_model.config_json)
        node = ProxyNode(
            name=node_dict["name"],
            type=node_dict["type"],
            server=node_dict["server"],
            port=node_dict["port"],
            params=node_dict.get("params", {})
        )

        # 测试节点延迟
        latency_ms = await proxy_manager.test_node(node)

        # 更新数据库中的延迟
        node_model.latency_ms = latency_ms if latency_ms > 0 else None
        await db.commit()

        if latency_ms > 0:
            return {
                "success": True,
                "node_id": node_id,
                "node_name": node.name,
                "latency_ms": latency_ms,
                "message": f"节点延迟: {latency_ms}ms"
            }
        else:
            return {
                "success": False,
                "node_id": node_id,
                "node_name": node.name,
                "latency_ms": None,
                "message": "节点连接失败"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"测试节点失败: {e}")
        raise HTTPException(status_code=500, detail=f"测试失败: {str(e)}")


@router.get("/latency")
async def test_proxy_latency():
    """测试当前代理到 Telegram API 的延迟"""
    import subprocess
    import time

    try:
        proxy_mgr = await get_proxy_manager()
        status = await proxy_mgr.get_status()

        if not status.get("running"):
            return {"success": False, "latency_ms": None, "message": "代理未运行"}

        proxy_port = status.get("proxy_port", 7897)

        start = time.time()
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
             "-m", "10", "-x", f"http://127.0.0.1:{proxy_port}",
             "https://api.telegram.org"],
            capture_output=True, text=True, timeout=15
        )
        elapsed_ms = int((time.time() - start) * 1000)
        http_code = result.stdout.strip()

        if http_code in ("200", "301", "302", "401", "403", "404"):
            return {"success": True, "latency_ms": elapsed_ms, "message": f"延迟: {elapsed_ms}ms"}
        else:
            return {"success": False, "latency_ms": None, "message": f"连接失败 (HTTP {http_code})"}

    except Exception as e:
        return {"success": False, "latency_ms": None, "message": f"测试失败: {str(e)}"}


@router.post("/start")
async def start_proxy():
    """启动代理"""
    try:
        proxy_manager = await get_proxy_manager()
        result = await proxy_manager.start()

        if result.get("success"):
            return {
                "success": True,
                "pid": result.get("pid"),
                "message": "代理已启动"
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "启动失败")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动代理失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动失败: {str(e)}")


@router.post("/stop")
async def stop_proxy():
    """停止代理"""
    try:
        proxy_manager = await get_proxy_manager()
        result = await proxy_manager.stop()

        if result.get("success"):
            return {
                "success": True,
                "message": "代理已停止"
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "停止失败")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"停止代理失败: {e}")
        raise HTTPException(status_code=500, detail=f"停止失败: {str(e)}")


@router.post("/restart")
async def restart_proxy():
    """重启代理"""
    try:
        proxy_manager = await get_proxy_manager()
        result = await proxy_manager.restart()

        if result.get("success"):
            return {
                "success": True,
                "pid": result.get("pid"),
                "message": "代理已重启"
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "重启失败")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重启代理失败: {e}")
        raise HTTPException(status_code=500, detail=f"重启失败: {str(e)}")


@router.delete("/nodes")
async def clear_nodes(db: AsyncSession = Depends(get_db)):
    """清空所有节点"""
    try:
        result = await db.execute(delete(ProxyNodeModel))
        await db.commit()

        deleted_count = result.rowcount

        logger.info(f"已清空 {deleted_count} 个节点")

        return {
            "success": True,
            "deleted_count": deleted_count,
            "message": f"已清空 {deleted_count} 个节点"
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"清空节点失败: {e}")
        raise HTTPException(status_code=500, detail=f"清空失败: {str(e)}")


@router.delete("/nodes/{node_id}")
async def delete_node(
    node_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除单个节点"""
    try:
        result = await db.execute(
            delete(ProxyNodeModel).where(ProxyNodeModel.id == node_id)
        )
        await db.commit()

        deleted_count = result.rowcount

        if deleted_count == 0:
            raise HTTPException(status_code=404, detail="节点不存在")

        logger.info(f"已删除节点: {node_id}")

        return {
            "success": True,
            "node_id": node_id,
            "message": "节点已删除"
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"删除节点失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
