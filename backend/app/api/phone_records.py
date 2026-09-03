"""手机号信息 API"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db

router = APIRouter(prefix="/phone-records", tags=["手机号信息"])


@router.get("")
async def list_phone_records(
    phone: Optional[str] = Query(None, description="手机号搜索"),
    source_type: Optional[str] = Query(None, description="来源类型"),
    province: Optional[str] = Query(None, description="省份筛选"),
    city: Optional[str] = Query(None, description="城市筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """获取手机号记录列表"""
    where_clauses = ["1=1"]
    params = {}
    if phone:
        where_clauses.append("(pr.phone LIKE :phone OR pr.phone_display LIKE :phone)")
        params["phone"] = f"%{phone}%"
    if source_type:
        where_clauses.append("pr.source_type = :source_type")
        params["source_type"] = source_type
    if province:
        where_clauses.append("pr.phone_location LIKE :province")
        params["province"] = f"%{province}%"
    if city:
        where_clauses.append("pr.phone_location LIKE :city")
        params["city"] = f"%{city}%"

    where_sql = " AND ".join(where_clauses)

    # count: 无筛选时用 information_schema 近似值，避免全表 COUNT
    if len(where_clauses) <= 1:  # 只有 "1=1"
        count_approx = await db.execute(text(
            "SELECT table_rows FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = 'phone_records'"
        ))
        total = count_approx.scalar() or 0
    else:
        count_result = await db.execute(text(f"SELECT COUNT(*) FROM phone_records pr WHERE {where_sql}"), params)
        total = count_result.scalar() or 0
    offset = (page - 1) * page_size

    # 优化：先获取排序后的 ID，再 JOIN 详情（避免全表 filesort）
    id_sql = f"""SELECT pr.id FROM phone_records pr WHERE {where_sql}
                 ORDER BY pr.occurrence_count DESC, pr.last_seen_at DESC
                 LIMIT :limit OFFSET :offset"""
    id_result = await db.execute(text(id_sql), {**params, "limit": page_size, "offset": offset})
    ids = [row[0] for row in id_result.fetchall()]

    if not ids:
        return {"items": [], "total": total, "page": page, "page_size": page_size, "total_pages": 0}

    # 批量获取详情
    placeholders = ",".join([f":id{i}" for i in range(len(ids))])
    id_params = {f"id{i}": id_val for i, id_val in enumerate(ids)}
    result = await db.execute(text(f"""
        SELECT pr.id, pr.phone, pr.phone_display, pr.country_code, pr.country,
               pr.phone_location, pr.carrier, pr.source_type, pr.source_id,
               pr.source_detail, pr.conversation_id, pr.first_seen_at,
               pr.last_seen_at, pr.occurrence_count,
               s.first_name, s.last_name, s.username, s.user_id
        FROM phone_records pr
        LEFT JOIN senders s ON pr.source_type = 'sender' AND pr.source_id = s.user_id
        WHERE pr.id IN ({placeholders})
        ORDER BY pr.occurrence_count DESC, pr.last_seen_at DESC
    """), id_params)
    rows = result.fetchall()

    items = []
    for r in rows:
        sender_name = ""
        if r[14] or r[15] or r[16]:
            parts = []
            if r[14]: parts.append(r[14])
            if r[15]: parts.append(r[15])
            sender_name = " ".join(parts)
            if r[16]: sender_name += f" (@{r[16]})"
        items.append({
            "id": r[0], "phone": r[1], "phone_display": r[2] or "",
            "country_code": r[3] or "", "country": r[4] or "",
            "phone_location": r[5] or "", "carrier": r[6] or "",
            "source_type": r[7], "source_id": r[8],
            "source_detail": r[9] or "", "conversation_id": r[10],
            "first_seen_at": r[11].isoformat() if r[11] else None,
            "last_seen_at": r[12].isoformat() if r[12] else None,
            "occurrence_count": r[13] or 1,
            "sender_name": sender_name, "sender_user_id": r[17],
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total else 0}


@router.get("/stats")
async def get_phone_stats(db: AsyncSession = Depends(get_db)):
    """获取手机号统计概览（单次查询优化）"""
    # 合并为单次查询，减少 DB 往返
    row = (await db.execute(text("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN country_code = 'CN' THEN 1 ELSE 0 END) as domestic,
            SUM(CASE WHEN source_type = 'sender' THEN 1 ELSE 0 END) as source_sender,
            SUM(CASE WHEN source_type = 'message' THEN 1 ELSE 0 END) as source_message,
            SUM(CASE WHEN source_type = 'alert' THEN 1 ELSE 0 END) as source_alert,
            SUM(CASE WHEN phone_location IS NOT NULL AND phone_location != '' AND phone_location != '中国' THEN 1 ELSE 0 END) as has_location
        FROM phone_records
    """))).fetchone()

    location_result = await db.execute(
        text("""SELECT phone_location, COUNT(*) FROM phone_records
            WHERE country_code='CN' AND phone_location IS NOT NULL AND phone_location != '' AND phone_location != '中国'
            GROUP BY phone_location ORDER BY COUNT(*) DESC LIMIT 10"""))
    top_locations = [{"name": row[0], "count": row[1]} for row in location_result.fetchall()]

    total = row[0] or 0
    domestic = row[1] or 0
    detail_ratio = (row[5] / total * 100) if total > 0 else 0

    return {
        "total": total,
        "domestic": domestic,
        "by_source": {"sender": row[2] or 0, "message": row[3] or 0, "alert": row[4] or 0},
        "top_locations": top_locations,
        "location_detail_ratio": round(detail_ratio, 1),
    }


@router.get("/provinces")
async def list_provinces(db: AsyncSession = Depends(get_db)):
    """获取省份列表（按记录数排序）"""
    result = await db.execute(
        text("""SELECT
            CASE
                WHEN phone_location LIKE '%省%' THEN SUBSTRING_INDEX(phone_location, '省', 1)
                WHEN phone_location IN ('北京市','上海市','天津市','重庆市') THEN LEFT(phone_location, 2)
                WHEN phone_location LIKE '%自治区%' THEN SUBSTRING_INDEX(phone_location, '自治区', 1)
                ELSE phone_location
            END as province,
            COUNT(*) as cnt
        FROM phone_records
        WHERE country_code = 'CN' AND phone_location IS NOT NULL AND phone_location != '' AND phone_location != '中国'
        GROUP BY province
        ORDER BY cnt DESC""")
    )
    return [{"name": row[0], "count": row[1]} for row in result.fetchall() if row[0]]


@router.get("/cities")
async def list_cities(
    province: str = Query(..., description="省份名称"),
    db: AsyncSession = Depends(get_db),
):
    """获取某省份下的城市列表"""
    result = await db.execute(
        text("""SELECT phone_location, COUNT(*) as cnt
        FROM phone_records
        WHERE country_code = 'CN' AND phone_location LIKE :province
        GROUP BY phone_location
        ORDER BY cnt DESC"""),
        {"province": f"%{province}%"}
    )
    return [{"name": row[0], "count": row[1]} for row in result.fetchall()]


@router.get("/phone/{phone}")
async def get_phone_detail(phone: str, db: AsyncSession = Depends(get_db)):
    """获取手机号完整详情（批量查询优化，避免 N+1）"""
    result = await db.execute(
        text("""SELECT id, phone, phone_display, country_code, country, phone_location,
                    carrier, source_type, source_id, source_detail, conversation_id,
                    first_seen_at, last_seen_at, occurrence_count
            FROM phone_records WHERE phone = :phone ORDER BY source_type, last_seen_at DESC"""),
        {"phone": phone})
    rows = result.fetchall()

    base_info = {}
    if rows:
        r = rows[0]
        base_info = {"phone": r[1], "phone_display": r[2] or "", "country_code": r[3] or "",
                     "country": r[4] or "", "phone_location": r[5] or "", "carrier": r[6] or ""}

    # 第一步：收集所有 sender_db_id（去重）
    sender_user_ids = set()
    for r in rows:
        if r[7] == 'sender':
            sender_user_ids.add(r[8])

    # 关联发送者：通过 phone_records 桥接查询
    mentioned_sender_rows = (await db.execute(text("""
        SELECT m.sender_id as sender_db_id, COUNT(*) as mention_count
        FROM phone_records pr
        JOIN messages m ON pr.source_id = m.id
        WHERE pr.phone = :phone AND pr.source_type = 'message' AND m.sender_id IS NOT NULL
        GROUP BY m.sender_id
    """), {"phone": phone})).fetchall()
    mentioned_map = {mr[0]: mr[1] for mr in mentioned_sender_rows}

    # 绑定该手机号的发送者
    bound_sender_rows = (await db.execute(text("""
        SELECT s.id FROM senders s
        WHERE s.phone COLLATE utf8mb4_unicode_ci LIKE :phone_pattern
    """), {"phone_pattern": f"%{phone}"})).fetchall()
    bound_ids = {bs[0] for bs in bound_sender_rows}

    # 收集所有需要查询的 sender_db_id
    all_sender_db_ids = set(mentioned_map.keys()) | bound_ids
    sender_id_map = {}
    if sender_user_ids:
        uid_rows = (await db.execute(text(
            "SELECT id, user_id FROM senders WHERE user_id = ANY(:uids)"),
            {"uids": list(sender_user_ids)})).fetchall()
        sender_id_map = {u: s for s, u in uid_rows}
        all_sender_db_ids.update(sender_id_map.values())

    # 第二步：批量查询所有 sender 详情（1 次查询替代 N 次）
    sender_details = {}
    if all_sender_db_ids:
        sid_list = list(all_sender_db_ids)
        sid_rows = (await db.execute(text(
            """SELECT s.id, s.user_id, s.username, s.first_name, s.last_name,
                      s.phone, s.country, s.phone_location, s.is_bot, s.is_verified,
                      s.is_premium, s.message_count, s.created_at
               FROM senders s WHERE s.id = ANY(:sids)"""),
            {"sids": sid_list})).fetchall()
        for s in sid_rows:
            sender_details[s[0]] = {
                "id": s[0], "user_id": s[1], "username": s[2] or "",
                "first_name": s[3] or "", "last_name": s[4] or "",
                "phone": s[5] or "", "country": s[6] or "",
                "phone_location": s[7] or "",
                "is_bot": bool(s[8]), "is_verified": bool(s[9]),
                "is_premium": bool(s[10]), "message_count": s[11] or 0,
                "created_at": s[12].isoformat() if s[12] else None,
            }

    # 第三步：批量查询所有 sender 的会话（1 次查询替代 N 次）
    sender_convs = {}
    if all_sender_db_ids:
        conv_rows = (await db.execute(text(
            """SELECT m.sender_id as sid, c.id, c.title, c.chat_id
               FROM conversations c
               INNER JOIN messages m ON m.conversation_id = c.id
               WHERE m.sender_id = ANY(:sids)
               ORDER BY m.sender_id, c.title"""),
            {"sids": list(all_sender_db_ids)})).fetchall()
        for cr in conv_rows:
            sid = cr[0]
            if sid not in sender_convs:
                sender_convs[sid] = []
            if len(sender_convs[sid]) < 20:
                sender_convs[sid].append({"id": cr[1], "title": cr[2] or "", "chat_id": cr[3]})

    # 第四步：组装结果
    senders = []
    seen_user_ids = set()
    for r in rows:
        if r[7] == 'sender' and r[8] not in seen_user_ids:
            seen_user_ids.add(r[8])
            sid = sender_id_map.get(r[8])
            if sid and sid in sender_details:
                d = sender_details[sid]
                d["conversations"] = sender_convs.get(sid, [])
                senders.append(d)

    related_senders = []
    for sid, mention_count in mentioned_map.items():
        if sid in sender_details:
            d = dict(sender_details[sid])
            d["source"] = "mentioned"
            d["mention_count"] = mention_count
            d["conversations"] = sender_convs.get(sid, [])[:10]
            related_senders.append(d)
    for sid in bound_ids:
        if sid in sender_details and sid not in mentioned_map:
            d = dict(sender_details[sid])
            d["source"] = "bound"
            d["mention_count"] = 0
            d["conversations"] = sender_convs.get(sid, [])[:10]
            related_senders.append(d)

    # 消息上下文
    message_contexts = []
    match_msg_rows = (await db.execute(text("""
        SELECT pr.source_id as msg_id, pr.conversation_id
        FROM phone_records pr
        WHERE pr.phone = :phone AND pr.source_type = 'message'
        ORDER BY pr.last_seen_at DESC
        LIMIT 30
    """), {"phone": phone})).fetchall()

    if match_msg_rows:
        msg_ids = [mmr[0] for mmr in match_msg_rows]
        placeholders = ",".join([f":id{i}" for i in range(len(msg_ids))])
        msg_params = {f"id{i}": mid for i, mid in enumerate(msg_ids)}
        batch_result = await db.execute(text(f"""
            SELECT m.id, m.text, m.caption, m.date, m.sender_id, m.conversation_id, m.message_type,
                   s.first_name, s.last_name, s.username, c.title as conv_title
            FROM messages m
            LEFT JOIN senders s ON m.sender_id = s.id
            LEFT JOIN conversations c ON m.conversation_id = c.id
            WHERE m.id IN ({placeholders})
        """), msg_params)
        match_messages = batch_result.fetchall()
    else:
        match_messages = []

    for mm in match_messages:
        msg_id = mm[0]
        conv_id = mm[5]
        msg_date = mm[3]
        sender_info = {"id": mm[4], "name": mm[7] or mm[8] or mm[9] or f"User_{mm[4]}", "username": mm[9]}
        message_contexts.append({
            "id": msg_id, "text": mm[1] or mm[2] or "", "date": msg_date.isoformat() if msg_date else None,
            "sender": sender_info, "conversation_id": conv_id, "conversation_title": mm[10] or "",
            "message_type": mm[6],
        })

    return {
        "base_info": base_info,
        "records": [{"id": r[0], "phone": r[1], "phone_display": r[2], "country_code": r[3],
                     "country": r[4], "phone_location": r[5], "carrier": r[6], "source_type": r[7],
                     "source_id": r[8], "source_detail": r[9], "conversation_id": r[10],
                     "first_seen_at": r[11].isoformat() if r[11] else None,
                     "last_seen_at": r[12].isoformat() if r[12] else None,
                     "occurrence_count": r[13] or 1} for r in rows],
        "senders": senders,
        "related_senders": related_senders,
        "message_contexts": message_contexts,
    }

