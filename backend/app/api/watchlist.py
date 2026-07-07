"""重点关注名单 API"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.api.deps import get_db
from app.models.watchlist import Watchlist
from app.schemas.watchlist import (
    WatchlistResponse,
    WatchlistCreate,
    WatchlistUpdate,
    WatchlistCheckResult,
)
from app.utils import now_utc, datetime_to_iso

router = APIRouter(prefix="/watchlist", tags=["重点关注名单"])


async def _log_audit(db: AsyncSession, operator: str, action: str, target_type: str, target_id: str, detail: dict = None, ip: str = None):
    """记录审计日志"""
    try:
        await db.execute(text(
            "INSERT INTO audit_log (operator, action, target_type, target_id, detail, ip_address) VALUES (:op, :act, :tt, :tid, :det, :ip)"
        ), {"op": operator, "act": action, "tt": target_type, "tid": target_id, "det": __import__("json").dumps(detail, ensure_ascii=False) if detail else None, "ip": ip})
    except Exception as e:
        logger.warning(f"记录审计日志失败: {e}")


@router.get("")
async def list_watchlist(
    entity_type: str = Query(None, description="实体类型筛选"),
    threat_level: str = Query(None, description="威胁级别筛选"),
    is_active: bool = Query(None, description="是否激活"),
    keyword: str = Query(None, description="关键词搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """获取重点关注名单"""
    where_clauses = []
    params = {}

    if entity_type:
        where_clauses.append("w.entity_type = :et")
        params["et"] = entity_type
    if threat_level:
        where_clauses.append("w.threat_level = :tl")
        params["tl"] = threat_level
    if is_active is not None:
        where_clauses.append("w.is_active = :active")
        params["active"] = is_active
    if keyword:
        where_clauses.append("(w.entity_value LIKE :kw OR w.entity_name LIKE :kw OR w.reason LIKE :kw)")
        params["kw"] = f"%{keyword}%"

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    count_result = await db.execute(text(f"SELECT count(*) FROM watchlist w{where_sql}"), params)
    total = count_result.scalar()

    offset = (page - 1) * page_size
    params["lim"] = page_size
    params["off"] = offset

    data_result = await db.execute(text(f"""
        SELECT w.* FROM watchlist w
        {where_sql}
        ORDER BY w.created_at DESC
        LIMIT :lim OFFSET :off
    """), params)
    rows = data_result.fetchall()

    items = []
    from datetime import datetime
    for row in rows:
        d = dict(row._mapping)
        for k in ["created_at", "updated_at"]:
            if d.get(k) and isinstance(d[k], datetime):
                d[k] = datetime_to_iso(d[k])
        items.append(d)

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/check")
async def check_watchlist(
    sender_id: int = Query(None, description="发送者ID"),
    phone: str = Query(None, description="手机号"),
    db: AsyncSession = Depends(get_db),
):
    """检查是否在重点关注名单中"""
    if not sender_id and not phone:
        raise HTTPException(status_code=400, detail="请提供 sender_id 或 phone 参数")

    where_clauses = ["w.is_active = 1"]
    params = {}

    conditions = []
    if sender_id:
        conditions.append("(w.entity_type = 'sender' AND w.entity_value = :sid)")
        params["sid"] = str(sender_id)
    if phone:
        conditions.append("(w.entity_type = 'phone' AND w.entity_value = :phone)")
        params["phone"] = phone

    if conditions:
        where_clauses.append(f"({' OR '.join(conditions)})")

    where_sql = " WHERE " + " AND ".join(where_clauses)

    from datetime import datetime
    result = await db.execute(text(f"SELECT w.* FROM watchlist w{where_sql}"), params)
    entries = []
    for row in result.fetchall():
        d = dict(row._mapping)
        for k in ["created_at", "updated_at"]:
            if d.get(k) and isinstance(d[k], datetime):
                d[k] = datetime_to_iso(d[k])
        entries.append(d)

    return {"found": len(entries) > 0, "entries": entries}


@router.post("")
async def add_to_watchlist(data: WatchlistCreate, db: AsyncSession = Depends(get_db)):
    """添加到重点关注名单"""
    now = now_utc()

    await db.execute(text("""
        INSERT INTO watchlist (entity_type, entity_value, entity_name, threat_level, reason, case_id, tags, added_by, is_active, created_at, updated_at)
        VALUES (:et, :ev, :en, :tl, :reason, :cid, :tags, :by, 1, :now, :now)
    """), {
        "et": data.entity_type, "ev": data.entity_value, "en": data.entity_name,
        "tl": data.threat_level, "reason": data.reason, "cid": data.case_id,
        "tags": __import__("json").dumps(data.tags, ensure_ascii=False) if data.tags else None,
        "by": data.added_by or "system", "now": now,
    })
    await db.commit()

    result = await db.execute(text("SELECT LAST_INSERT_ID()"))
    new_id = result.scalar()

    await _log_audit(db, data.added_by or "system", "add_watchlist", "watchlist", str(new_id), {
        "entity_type": data.entity_type, "entity_value": data.entity_value, "threat_level": data.threat_level
    })
    await db.commit()

    return {"message": "已添加到重点关注名单", "id": new_id}


@router.put("/{watchlist_id}")
async def update_watchlist(watchlist_id: int, data: WatchlistUpdate, db: AsyncSession = Depends(get_db)):
    """更新名单条目"""
    result = await db.execute(text("SELECT id FROM watchlist WHERE id = :id"), {"id": watchlist_id})
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="名单条目不存在")

    updates = []
    params = {"id": watchlist_id}

    if data.entity_name is not None:
        updates.append("entity_name = :en")
        params["en"] = data.entity_name
    if data.threat_level is not None:
        updates.append("threat_level = :tl")
        params["tl"] = data.threat_level
    if data.reason is not None:
        updates.append("reason = :reason")
        params["reason"] = data.reason
    if data.case_id is not None:
        updates.append("case_id = :cid")
        params["cid"] = data.case_id
    if data.tags is not None:
        updates.append("tags = :tags")
        params["tags"] = __import__("json").dumps(data.tags, ensure_ascii=False)
    if data.is_active is not None:
        updates.append("is_active = :active")
        params["active"] = data.is_active

    if not updates:
        return {"message": "无更新内容"}

    from datetime import datetime
    updates.append("updated_at = :now")
    params["now"] = now_utc()

    await db.execute(text(f"UPDATE watchlist SET {', '.join(updates)} WHERE id = :id"), params)
    await db.commit()

    await _log_audit(db, data.added_by or "system", "update_watchlist", "watchlist", str(watchlist_id), {
        "fields": [u.split(" =")[0] for u in updates if "updated_at" not in u]
    })
    await db.commit()

    return {"message": "名单条目已更新"}


@router.delete("/{watchlist_id}")
async def remove_from_watchlist(watchlist_id: int, db: AsyncSession = Depends(get_db)):
    """从名单移除"""
    result = await db.execute(text("SELECT id FROM watchlist WHERE id = :id"), {"id": watchlist_id})
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="名单条目不存在")

    await db.execute(text("DELETE FROM watchlist WHERE id = :id"), {"id": watchlist_id})
    await db.commit()

    await _log_audit(db, "system", "remove_watchlist", "watchlist", str(watchlist_id))
    await db.commit()

    return {"message": "已从名单移除"}
