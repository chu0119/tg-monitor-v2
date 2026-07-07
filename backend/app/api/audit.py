"""审计日志 API"""
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.utils import datetime_to_iso

router = APIRouter(prefix="/audit", tags=["审计日志"])


@router.get("")
async def list_audit_logs(
    operator: str = Query(None, description="操作人筛选"),
    action: str = Query(None, description="操作类型筛选"),
    target_type: str = Query(None, description="目标类型筛选"),
    start_time: str = Query(None, description="开始时间 ISO格式"),
    end_time: str = Query(None, description="结束时间 ISO格式"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """获取审计日志列表"""
    where_clauses = []
    params = {}

    if operator:
        where_clauses.append("a.operator LIKE :op")
        params["op"] = f"%{operator}%"
    if action:
        where_clauses.append("a.action = :act")
        params["act"] = action
    if target_type:
        where_clauses.append("a.target_type = :tt")
        params["tt"] = target_type
    if start_time:
        try:
            start_dt = datetime.fromisoformat(start_time)
            if start_dt.tzinfo is not None:
                start_dt = start_dt.astimezone(None).replace(tzinfo=None)
            where_clauses.append("a.created_at >= :start")
            params["start"] = start_dt
        except ValueError:
            pass
    if end_time:
        try:
            end_dt = datetime.fromisoformat(end_time)
            if end_dt.tzinfo is not None:
                end_dt = end_dt.astimezone(None).replace(tzinfo=None)
            where_clauses.append("a.created_at <= :end")
            params["end"] = end_dt
        except ValueError:
            pass

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    count_result = await db.execute(text(f"SELECT count(*) FROM audit_log a{where_sql}"), params)
    total = count_result.scalar()

    offset = (page - 1) * page_size
    params["lim"] = page_size
    params["off"] = offset

    data_result = await db.execute(text(f"""
        SELECT a.* FROM audit_log a
        {where_sql}
        ORDER BY a.created_at DESC
        LIMIT :lim OFFSET :off
    """), params)
    rows = data_result.fetchall()

    items = []
    for row in rows:
        d = dict(row._mapping)
        if d.get("created_at") and isinstance(d["created_at"], datetime):
            d["created_at"] = datetime_to_iso(d["created_at"])
        if d.get("detail") and isinstance(d["detail"], str):
            import json
            try:
                d["detail"] = json.loads(d["detail"])
            except Exception:
                pass
        items.append(d)

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/stats")
async def get_audit_stats(
    start_time: str = Query(None, description="开始时间 ISO格式"),
    end_time: str = Query(None, description="结束时间 ISO格式"),
    db: AsyncSession = Depends(get_db),
):
    """获取审计统计"""
    where_clauses = []
    params = {}

    if start_time:
        try:
            start_dt = datetime.fromisoformat(start_time)
            if start_dt.tzinfo is not None:
                start_dt = start_dt.astimezone(None).replace(tzinfo=None)
            where_clauses.append("created_at >= :start")
            params["start"] = start_dt
        except ValueError:
            pass
    if end_time:
        try:
            end_dt = datetime.fromisoformat(end_time)
            if end_dt.tzinfo is not None:
                end_dt = end_dt.astimezone(None).replace(tzinfo=None)
            where_clauses.append("created_at <= :end")
            params["end"] = end_dt
        except ValueError:
            pass

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    total_result = await db.execute(text(f"SELECT count(*) FROM audit_log{where_sql}"), params)
    total = total_result.scalar()

    by_action_result = await db.execute(text(f"""
        SELECT action, count(*) as count FROM audit_log
        {where_sql}
        GROUP BY action ORDER BY count DESC
    """), params)
    by_action = [{"action": row[0], "count": row[1]} for row in by_action_result.fetchall()]

    by_operator_result = await db.execute(text(f"""
        SELECT operator, count(*) as count FROM audit_log
        {where_sql}
        GROUP BY operator ORDER BY count DESC
        LIMIT 20
    """), params)
    by_operator = [{"operator": row[0] or "system", "count": row[1]} for row in by_operator_result.fetchall()]

    return {
        "total": total,
        "by_action": by_action,
        "by_operator": by_operator,
    }
