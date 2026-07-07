"""案件管理 API"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, update, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from datetime import datetime

from app.api.deps import get_db
from app.models.case import Case, CaseAlert, CasePerson
from app.schemas.case import (
    CaseResponse,
    CaseDetailResponse,
    CaseCreate,
    CaseUpdate,
    CaseAlertAdd,
    CasePersonAdd,
)
from app.utils import now_utc, datetime_to_iso

router = APIRouter(prefix="/cases", tags=["案件管理"])


async def _log_audit(db: AsyncSession, operator: str, action: str, target_type: str, target_id: str, detail: dict = None, ip: str = None):
    """记录审计日志"""
    try:
        await db.execute(text(
            "INSERT INTO audit_log (operator, action, target_type, target_id, detail, ip_address) VALUES (:op, :act, :tt, :tid, :det, :ip)"
        ), {"op": operator, "act": action, "tt": target_type, "tid": target_id, "det": __import__("json").dumps(detail, ensure_ascii=False) if detail else None, "ip": ip})
    except Exception as e:
        logger.warning(f"记录审计日志失败: {e}")


async def _generate_case_number(db: AsyncSession) -> str:
    """生成案件编号 CASE-YYYYMMDD-NNN"""
    today = now_utc().strftime("%Y%m%d")
    prefix = f"CASE-{today}-"
    result = await db.execute(
        select(Case.case_number)
        .where(Case.case_number.like(f"{prefix}%"))
        .order_by(Case.case_number.desc())
        .limit(1)
    )
    last = result.scalar_one_or_none()
    if last:
        try:
            seq = int(last.split("-")[-1]) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:03d}"


@router.get("")
async def list_cases(
    status_filter: str = Query(None, alias="status", description="状态筛选"),
    case_type: str = Query(None, description="案件类型"),
    priority: str = Query(None, description="优先级"),
    investigator: str = Query(None, description="主办人"),
    keyword: str = Query(None, description="关键词搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """获取案件列表"""
    where_clauses = []
    params = {}

    if status_filter:
        where_clauses.append("c.status = :status")
        params["status"] = status_filter
    if case_type:
        where_clauses.append("c.case_type = :case_type")
        params["case_type"] = case_type
    if priority:
        where_clauses.append("c.priority = :priority")
        params["priority"] = priority
    if investigator:
        where_clauses.append("c.lead_investigator LIKE :investigator")
        params["investigator"] = f"%{investigator}%"
    if keyword:
        where_clauses.append("(c.case_name LIKE :kw OR c.case_number LIKE :kw OR c.description LIKE :kw)")
        params["kw"] = f"%{keyword}%"

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    count_result = await db.execute(text(f"SELECT count(*) FROM cases c{where_sql}"), params)
    total = count_result.scalar()

    offset = (page - 1) * page_size
    params["lim"] = page_size
    params["off"] = offset

    data_result = await db.execute(text(f"""
        SELECT c.* FROM cases c
        {where_sql}
        ORDER BY c.created_at DESC
        LIMIT :lim OFFSET :off
    """), params)
    rows = data_result.fetchall()

    items = []
    for row in rows:
        d = dict(row._mapping)
        for k in ["created_at", "updated_at", "closed_at"]:
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


@router.get("/{case_id}")
async def get_case(case_id: int, db: AsyncSession = Depends(get_db)):
    """获取案件详情（含关联告警和人员）"""
    result = await db.execute(text("SELECT * FROM cases WHERE id = :id"), {"id": case_id})
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="案件不存在")

    case_data = dict(row._mapping)
    for k in ["created_at", "updated_at", "closed_at"]:
        if case_data.get(k) and isinstance(case_data[k], datetime):
            case_data[k] = datetime_to_iso(case_data[k])

    # 关联告警
    alerts_result = await db.execute(text("""
        SELECT ca.id, ca.alert_id, ca.added_by, ca.created_at,
               a.alert_level, a.status, a.keyword_text, a.matched_text, a.message_preview
        FROM case_alerts ca
        LEFT JOIN alerts a ON ca.alert_id = a.id
        WHERE ca.case_id = :cid
        ORDER BY ca.created_at DESC
    """), {"cid": case_id})
    alerts = []
    for r in alerts_result.fetchall():
        ad = dict(r._mapping)
        if ad.get("created_at") and isinstance(ad["created_at"], datetime):
            ad["created_at"] = datetime_to_iso(ad["created_at"])
        alerts.append(ad)

    # 关联人员
    persons_result = await db.execute(text("""
        SELECT cp.id, cp.sender_id, cp.role, cp.added_by, cp.created_at,
               s.user_id AS sender_tg_id,
               COALESCE(s.username, COALESCE(s.first_name, CONCAT('User_', s.user_id))) AS sender_name,
               s.phone AS sender_phone
        FROM case_persons cp
        LEFT JOIN senders s ON cp.sender_id = s.id
        WHERE cp.case_id = :cid
        ORDER BY cp.created_at DESC
    """), {"cid": case_id})
    persons = []
    for r in persons_result.fetchall():
        pd = dict(r._mapping)
        if pd.get("created_at") and isinstance(pd["created_at"], datetime):
            pd["created_at"] = datetime_to_iso(pd["created_at"])
        persons.append(pd)

    case_data["alerts"] = alerts
    case_data["persons"] = persons
    return case_data


@router.post("")
async def create_case(data: CaseCreate, db: AsyncSession = Depends(get_db)):
    """创建案件"""
    case_number = await _generate_case_number(db)
    now = now_utc()

    await db.execute(text("""
        INSERT INTO cases (case_number, case_name, case_type, status, description, lead_investigator, priority, created_by, created_at, updated_at)
        VALUES (:cn, :name, :type, 'open', :desc, :invest, :prio, :creator, :now, :now)
    """), {
        "cn": case_number, "name": data.case_name, "type": data.case_type,
        "desc": data.description, "invest": data.lead_investigator,
        "prio": data.priority, "creator": data.created_by or "system", "now": now,
    })
    await db.commit()

    result = await db.execute(text("SELECT * FROM cases WHERE case_number = :cn"), {"cn": case_number})
    row = result.fetchone()
    case_data = dict(row._mapping)
    for k in ["created_at", "updated_at", "closed_at"]:
        if case_data.get(k) and isinstance(case_data[k], datetime):
            case_data[k] = datetime_to_iso(case_data[k])

    await _log_audit(db, data.created_by or "system", "create_case", "case", str(case_data["id"]), {"case_number": case_number, "case_name": data.case_name})
    await db.commit()

    return case_data


@router.put("/{case_id}")
async def update_case(case_id: int, data: CaseUpdate, db: AsyncSession = Depends(get_db)):
    """更新案件"""
    result = await db.execute(text("SELECT * FROM cases WHERE id = :id"), {"id": case_id})
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="案件不存在")

    updates = []
    params = {"id": case_id}
    if data.case_name is not None:
        updates.append("case_name = :name")
        params["name"] = data.case_name
    if data.case_type is not None:
        updates.append("case_type = :type")
        params["type"] = data.case_type
    if data.status is not None:
        updates.append("status = :status")
        params["status"] = data.status
        if data.status == "closed":
            updates.append("closed_at = :now")
            params["now"] = now_utc()
    if data.description is not None:
        updates.append("description = :desc")
        params["desc"] = data.description
    if data.lead_investigator is not None:
        updates.append("lead_investigator = :invest")
        params["invest"] = data.lead_investigator
    if data.priority is not None:
        updates.append("priority = :prio")
        params["prio"] = data.priority

    if not updates:
        return {"message": "无更新内容"}

    updates.append("updated_at = :now2")
    params["now2"] = now_utc()

    await db.execute(text(f"UPDATE cases SET {', '.join(updates)} WHERE id = :id"), params)
    await db.commit()

    await _log_audit(db, "system", "update_case", "case", str(case_id), {"fields": [u.split(" =")[0] for u in updates if "updated_at" not in u]})
    await db.commit()

    return {"message": "案件已更新"}


@router.delete("/{case_id}")
async def delete_case(case_id: int, db: AsyncSession = Depends(get_db)):
    """删除案件"""
    result = await db.execute(text("SELECT * FROM cases WHERE id = :id"), {"id": case_id})
    case = result.fetchone()
    if not case:
        raise HTTPException(status_code=404, detail="案件不存在")

    await db.execute(text("DELETE FROM case_alerts WHERE case_id = :id"), {"id": case_id})
    await db.execute(text("DELETE FROM case_persons WHERE case_id = :id"), {"id": case_id})
    await db.execute(text("DELETE FROM cases WHERE id = :id"), {"id": case_id})
    await db.commit()

    await _log_audit(db, "system", "delete_case", "case", str(case_id), {"case_number": dict(case._mapping).get("case_number")})
    await db.commit()

    return {"message": "案件已删除"}


@router.post("/{case_id}/alerts")
async def add_alert_to_case(case_id: int, data: CaseAlertAdd, db: AsyncSession = Depends(get_db)):
    """添加告警到案件"""
    result = await db.execute(text("SELECT id FROM cases WHERE id = :id"), {"id": case_id})
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="案件不存在")

    existing = await db.execute(text(
        "SELECT id FROM case_alerts WHERE case_id = :cid AND alert_id = :aid"
    ), {"cid": case_id, "aid": data.alert_id})
    if existing.fetchone():
        raise HTTPException(status_code=400, detail="该告警已关联到此案件")

    await db.execute(text("""
        INSERT INTO case_alerts (case_id, alert_id, added_by) VALUES (:cid, :aid, :by)
    """), {"cid": case_id, "aid": data.alert_id, "by": data.added_by})

    await db.execute(text("UPDATE cases SET alert_count = alert_count + 1, updated_at = :now WHERE id = :id"), {"id": case_id, "now": now_utc()})
    await db.commit()

    await _log_audit(db, data.added_by or "system", "add_alert_to_case", "case", str(case_id), {"alert_id": data.alert_id})
    await db.commit()

    return {"message": "告警已添加到案件"}


@router.delete("/{case_id}/alerts/{alert_id}")
async def remove_alert_from_case(case_id: int, alert_id: int, db: AsyncSession = Depends(get_db)):
    """从案件移除告警"""
    result = await db.execute(text(
        "SELECT id FROM case_alerts WHERE case_id = :cid AND alert_id = :aid"
    ), {"cid": case_id, "aid": alert_id})
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="关联关系不存在")

    await db.execute(text("DELETE FROM case_alerts WHERE case_id = :cid AND alert_id = :aid"), {"cid": case_id, "aid": alert_id})
    await db.execute(text("UPDATE cases SET alert_count = GREATEST(alert_count - 1, 0), updated_at = :now WHERE id = :id"), {"id": case_id, "now": now_utc()})
    await db.commit()

    await _log_audit(db, "system", "remove_alert_from_case", "case", str(case_id), {"alert_id": alert_id})
    await db.commit()

    return {"message": "告警已从案件移除"}


@router.post("/{case_id}/persons")
async def add_person_to_case(case_id: int, data: CasePersonAdd, db: AsyncSession = Depends(get_db)):
    """添加人员到案件"""
    result = await db.execute(text("SELECT id FROM cases WHERE id = :id"), {"id": case_id})
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="案件不存在")

    existing = await db.execute(text(
        "SELECT id FROM case_persons WHERE case_id = :cid AND sender_id = :sid"
    ), {"cid": case_id, "sid": data.sender_id})
    if existing.fetchone():
        raise HTTPException(status_code=400, detail="该人员已关联到此案件")

    await db.execute(text("""
        INSERT INTO case_persons (case_id, sender_id, role, added_by) VALUES (:cid, :sid, :role, :by)
    """), {"cid": case_id, "sid": data.sender_id, "role": data.role or "related", "by": data.added_by})

    await db.execute(text("UPDATE cases SET person_count = person_count + 1, updated_at = :now WHERE id = :id"), {"id": case_id, "now": now_utc()})
    await db.commit()

    await _log_audit(db, data.added_by or "system", "add_person_to_case", "case", str(case_id), {"sender_id": data.sender_id, "role": data.role})
    await db.commit()

    return {"message": "人员已添加到案件"}


@router.delete("/{case_id}/persons/{sender_id}")
async def remove_person_from_case(case_id: int, sender_id: int, db: AsyncSession = Depends(get_db)):
    """从案件移除人员"""
    result = await db.execute(text(
        "SELECT id FROM case_persons WHERE case_id = :cid AND sender_id = :sid"
    ), {"cid": case_id, "sid": sender_id})
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="关联关系不存在")

    await db.execute(text("DELETE FROM case_persons WHERE case_id = :cid AND sender_id = :sid"), {"cid": case_id, "sid": sender_id})
    await db.execute(text("UPDATE cases SET person_count = GREATEST(person_count - 1, 0), updated_at = :now WHERE id = :id"), {"id": case_id, "now": now_utc()})
    await db.commit()

    await _log_audit(db, "system", "remove_person_from_case", "case", str(case_id), {"sender_id": sender_id})
    await db.commit()

    return {"message": "人员已从案件移除"}
