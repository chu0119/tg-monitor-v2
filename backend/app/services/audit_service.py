"""统一审计日志服务"""
import json
import functools
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger


async def log_audit(
    db: AsyncSession,
    action: str,
    target_type: str,
    target_id: str = None,
    detail: dict = None,
    operator: str = "system",
    ip_address: str = None,
):
    """记录审计日志（统一入口）

    注意：审计写入使用独立会话并立即提交。原先复用调用方会话会中途 commit，
    把调用方尚未完成的业务变更一并提交（提前可见/部分提交）。
    """
    try:
        from app.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as audit_db:
            await audit_db.execute(
                text(
                    "INSERT INTO audit_log (operator, action, target_type, target_id, detail, ip_address, created_at) "
                    "VALUES (:operator, :action, :target_type, :target_id, :detail, :ip_address, NOW())"
                ),
                {
                    "operator": operator,
                    "action": action,
                    "target_type": target_type,
                    "target_id": str(target_id) if target_id else None,
                    "detail": json.dumps(detail, ensure_ascii=False, default=str) if detail else None,
                    "ip_address": ip_address,
                },
            )
            await audit_db.commit()
    except Exception as e:
        logger.error(f"写入审计日志失败: {e}")


async def list_audit_logs(
    db: AsyncSession,
    operator: str = None,
    action: str = None,
    target_type: str = None,
    start_time: str = None,
    end_time: str = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """获取审计日志列表（统一接口）"""
    where_clauses = []
    params = {}

    if operator:
        where_clauses.append("operator LIKE :op")
        params["op"] = f"%{operator}%"
    if action:
        where_clauses.append("action = :act")
        params["act"] = action
    if target_type:
        where_clauses.append("target_type = :tt")
        params["tt"] = target_type
    if start_time:
        where_clauses.append("created_at >= :start")
        params["start"] = start_time
    if end_time:
        where_clauses.append("created_at <= :end")
        params["end"] = end_time

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    # 总数
    count_result = await db.execute(text(f"SELECT count(*) FROM audit_log{where_sql}"), params)
    total = count_result.scalar() or 0

    # 分页数据
    offset = (page - 1) * page_size
    params["lim"] = page_size
    params["off"] = offset

    data_result = await db.execute(text(f"""
        SELECT id, operator, action, target_type, target_id, detail, ip_address, created_at
        FROM audit_log
        {where_sql}
        ORDER BY created_at DESC
        LIMIT :lim OFFSET :off
    """), params)
    rows = data_result.fetchall()

    items = []
    for row in rows:
        d = dict(row._mapping)
        # 解析 detail JSON
        if d.get("detail") and isinstance(d["detail"], str):
            try:
                d["detail"] = json.loads(d["detail"])
            except Exception:
                pass
        # 统一字段名（前端期望 details 和 action_type）
        d["action_type"] = d.pop("action", "")
        d["details"] = d.pop("detail", None)
        items.append(d)

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total else 0,
    }


async def get_audit_stats(
    db: AsyncSession,
    start_time: str = None,
    end_time: str = None,
) -> dict:
    """获取审计统计"""
    where_clauses = []
    params = {}

    if start_time:
        where_clauses.append("created_at >= :start")
        params["start"] = start_time
    if end_time:
        where_clauses.append("created_at <= :end")
        params["end"] = end_time

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    # 总数
    total_result = await db.execute(text(f"SELECT count(*) FROM audit_log{where_sql}"), params)
    total = total_result.scalar() or 0

    # 按操作类型统计
    by_action_result = await db.execute(text(f"""
        SELECT action, count(*) as count FROM audit_log
        {where_sql}
        GROUP BY action ORDER BY count DESC
    """), params)
    by_action = [{"action": row[0], "count": row[1]} for row in by_action_result.fetchall()]

    # 按操作人统计
    by_operator_result = await db.execute(text(f"""
        SELECT operator, count(*) as count FROM audit_log
        {where_sql}
        GROUP BY operator ORDER BY count DESC LIMIT 20
    """), params)
    by_operator = [{"operator": row[0] or "system", "count": row[1]} for row in by_operator_result.fetchall()]

    # 按日期统计（最近 30 天）
    by_date_result = await db.execute(text(f"""
        SELECT DATE(created_at) as date, count(*) as count FROM audit_log
        {where_sql}
        GROUP BY DATE(created_at) ORDER BY date DESC LIMIT 30
    """), params)
    by_date = [{"date": str(row[0]), "count": row[1]} for row in by_date_result.fetchall()]

    return {
        "total": total,
        "by_action": by_action,
        "by_operator": by_operator,
        "by_date": list(reversed(by_date)),
    }
