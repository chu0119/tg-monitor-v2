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
    count_result = await db.execute(text(f"SELECT COUNT(*) FROM phone_records pr WHERE {where_sql}"), params)
    total = count_result.scalar() or 0
    offset = (page - 1) * page_size

    result = await db.execute(
        text(f"""SELECT pr.id, pr.phone, pr.phone_display, pr.country_code, pr.country,
                    pr.phone_location, pr.carrier, pr.source_type, pr.source_id,
                    pr.source_detail, pr.conversation_id, pr.first_seen_at,
                    pr.last_seen_at, pr.occurrence_count,
                    s.first_name, s.last_name, s.username, s.user_id
            FROM phone_records pr
            LEFT JOIN senders s ON pr.source_type = 'sender' AND pr.source_id = s.user_id
            WHERE {where_sql}
            ORDER BY pr.occurrence_count DESC, pr.last_seen_at DESC
            LIMIT :limit OFFSET :offset"""),
        {**params, "limit": page_size, "offset": offset}
    )
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
    """获取手机号统计概览"""
    total = (await db.execute(text("SELECT COUNT(*) FROM phone_records"))).scalar() or 0
    domestic = (await db.execute(text("SELECT COUNT(*) FROM phone_records WHERE country_code = 'CN'"))).scalar() or 0
    source_result = await db.execute(text("SELECT source_type, COUNT(*) FROM phone_records GROUP BY source_type"))
    source_stats = {row[0]: row[1] for row in source_result.fetchall()}
    location_result = await db.execute(
        text("""SELECT phone_location, COUNT(*) FROM phone_records
            WHERE country_code='CN' AND phone_location IS NOT NULL AND phone_location != '' AND phone_location != '中国'
            GROUP BY phone_location ORDER BY COUNT(*) DESC LIMIT 10"""))
    top_locations = [{"name": row[0], "count": row[1]} for row in location_result.fetchall()]
    detail_row = (await db.execute(text(
        """SELECT SUM(CASE WHEN phone_location IS NOT NULL AND phone_location != '' AND phone_location != '中国' THEN 1 ELSE 0 END),
                  COUNT(*) FROM phone_records WHERE country_code='CN'"""))).fetchone()
    detail_ratio = (detail_row[0] / detail_row[1] * 100) if detail_row[1] > 0 else 0

    return {"total": total, "domestic": domestic, "by_source": source_stats,
            "top_locations": top_locations, "location_detail_ratio": round(detail_ratio, 1)}


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
    """获取手机号完整详情"""
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

    senders = []
    sender_ids = set()
    for r in rows:
        if r[7] == 'sender' and r[8] not in sender_ids:
            sender_ids.add(r[8])
            s = (await db.execute(text(
                """SELECT s.id, s.user_id, s.username, s.first_name, s.last_name,
                    s.phone, s.country, s.phone_location, s.is_bot, s.is_verified,
                    s.is_premium, s.message_count, s.created_at
                FROM senders s WHERE s.user_id = :uid"""), {"uid": r[8]})).fetchone()
            if s:
                convs = (await db.execute(text(
                    """SELECT DISTINCT c.id, c.title, c.chat_id FROM conversations c
                    INNER JOIN messages m ON m.conversation_id = c.id
                    WHERE m.sender_id = :sid ORDER BY c.title LIMIT 20"""),
                    {"sid": s[0]})).fetchall()
                senders.append({
                    "id": s[0], "user_id": s[1], "username": s[2] or "",
                    "first_name": s[3] or "", "last_name": s[4] or "",
                    "phone": s[5] or "", "country": s[6] or "",
                    "phone_location": s[7] or "",
                    "is_bot": bool(s[8]), "is_verified": bool(s[9]),
                    "is_premium": bool(s[10]), "message_count": s[11] or 0,
                    "created_at": s[12].isoformat() if s[12] else None,
                    "conversations": [{"id": c[0], "title": c[1] or "", "chat_id": c[2]} for c in convs],
                })

    # 关联发送者：通过 phone_records 表桥接查询（避免全表 LIKE 扫描）
    related_senders = []
    related_sender_ids = set()
    
    # 从 phone_records 获取发送过包含该手机号消息的 sender（需 JOIN messages 获取 sender_id = senders.id）
    mentioned_sender_rows = (await db.execute(text("""
        SELECT m.sender_id as sender_db_id, COUNT(*) as mention_count
        FROM phone_records pr
        JOIN messages m ON pr.source_id = m.id
        WHERE pr.phone = :phone AND pr.source_type = 'message' AND m.sender_id IS NOT NULL
        GROUP BY m.sender_id
    """), {"phone": phone})).fetchall()
    for mr in mentioned_sender_rows:
        if mr[0] not in sender_ids and mr[0] not in related_sender_ids:
            related_sender_ids.add(mr[0])
            # Look up sender details by senders.id (not user_id)
            s = (await db.execute(text("""
                SELECT s.id, s.user_id, s.username, s.first_name, s.last_name,
                       s.phone, s.is_bot, s.is_verified, s.is_premium, s.message_count, s.created_at
                FROM senders s WHERE s.id = :sid
            """), {"sid": mr[0]})).fetchone()
            if s:
                convs = (await db.execute(text(
                    """SELECT DISTINCT c.id, c.title, c.chat_id FROM conversations c
                    INNER JOIN messages m ON m.conversation_id = c.id
                    WHERE m.sender_id = :sid ORDER BY c.title LIMIT 10"""),
                    {"sid": s[0]})).fetchall()
                related_senders.append({
                    "user_id": s[1], "username": s[2] or "",
                    "first_name": s[3] or "", "last_name": s[4] or "",
                    "phone": s[5] or "",
                    "is_bot": bool(s[6]), "is_verified": bool(s[7]),
                    "is_premium": bool(s[8]), "message_count": s[9] or 0,
                    "created_at": s[10].isoformat() if s[10] else None,
                    "source": "mentioned", "mention_count": mr[1],
                    "conversations": [{"id": c[0], "title": c[1] or "", "chat_id": c[2]} for c in convs],
                })
    
    # 同时查找绑定该手机号的发送者（手机号可能带国家代码前缀，用 LIKE 模糊匹配）
    bound_sender_rows = (await db.execute(text("""
        SELECT s.user_id, s.first_name, s.last_name, s.username, s.phone,
               s.is_bot, s.is_verified, s.is_premium, s.message_count, s.created_at
        FROM senders s WHERE s.phone COLLATE utf8mb4_unicode_ci LIKE :phone_pattern
    """), {"phone_pattern": f"%{phone}"})).fetchall()
    
    for bs in bound_sender_rows:
        if bs[0] not in sender_ids and bs[0] not in related_sender_ids:
            related_sender_ids.add(bs[0])
            convs = (await db.execute(text(
                """SELECT DISTINCT c.id, c.title, c.chat_id FROM conversations c
                INNER JOIN messages m ON m.conversation_id = c.id
                WHERE m.sender_id = :sid ORDER BY c.title LIMIT 10"""),
                {"sid": bs[0]})).fetchall()
            related_senders.append({
                "user_id": bs[0], "username": bs[3] or "",
                "first_name": bs[1] or "", "last_name": bs[2] or "",
                "phone": bs[4] or "",
                "is_bot": bool(bs[5]), "is_verified": bool(bs[6]),
                "is_premium": bool(bs[7]), "message_count": bs[8] or 0,
                "created_at": bs[9].isoformat() if bs[9] else None,
                "source": "bound", "mention_count": 0,
                "conversations": [{"id": c[0], "title": c[1] or "", "chat_id": c[2]} for c in convs],
            })

    # 消息上下文：通过 phone_records 桥接获取包含该手机号的消息及前后各3条
    message_contexts = []
    # 从 phone_records 获取消息 ID（避免 LIKE 全表扫描）
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
        
        # 获取前3条消息
        before = (await db.execute(text("""
            SELECT m.id, m.text, m.caption, m.date, m.message_type,
                   s.first_name, s.last_name, s.username
            FROM messages m
            LEFT JOIN senders s ON m.sender_id = s.id
            WHERE m.conversation_id = :cid AND m.date < :dt
            ORDER BY m.date DESC LIMIT 3
        """), {"cid": conv_id, "dt": msg_date})).fetchall()
        before = list(reversed(before))  # 按时间正序
        
        # 获取后3条消息
        after = (await db.execute(text("""
            SELECT m.id, m.text, m.caption, m.date, m.message_type,
                   s.first_name, s.last_name, s.username
            FROM messages m
            LEFT JOIN senders s ON m.sender_id = s.id
            WHERE m.conversation_id = :cid AND m.date > :dt
            ORDER BY m.date ASC LIMIT 3
        """), {"cid": conv_id, "dt": msg_date})).fetchall()
        
        def fmt_msg(m):
            sender_name = ""
            if m[5] or m[6]:
                parts = []
                if m[5]: parts.append(m[5])
                if m[6]: parts.append(m[6])
                sender_name = " ".join(parts)
            if m[7]: sender_name += f" (@{m[7]})"
            text_content = m[1] or m[2] or ""
            return {
                "id": m[0], "text": text_content, "date": m[3].isoformat() if m[3] else None,
                "message_type": m[4], "sender_name": sender_name,
            }
        
        sender_name = ""
        if mm[7] or mm[8]:
            parts = []
            if mm[7]: parts.append(mm[7])
            if mm[8]: parts.append(mm[8])
            sender_name = " ".join(parts)
        if mm[9]: sender_name += f" (@{mm[9]})"
        
        message_contexts.append({
            "match_message": {
                "id": mm[0], "text": mm[1] or mm[2] or "", "date": mm[3].isoformat() if mm[3] else None,
                "message_type": mm[6], "sender_name": sender_name,
                "conversation_title": mm[10] or "",
            },
            "context_before": [fmt_msg(m) for m in before],
            "context_after": [fmt_msg(m) for m in after],
        })

    conversations = []
    conv_ids = set()
    for r in rows:
        if r[10] and r[10] not in conv_ids and r[10] > 0:
            conv_ids.add(r[10])
            c = (await db.execute(text("SELECT id, title, chat_id FROM conversations WHERE id = :cid"),
                                  {"cid": r[10]})).fetchone()
            if c: conversations.append({"id": c[0], "title": c[1] or "", "chat_id": c[2]})

    records = [{"id": r[0], "source_type": r[7], "source_id": r[8], "source_detail": r[9] or "",
                "conversation_id": r[10],
                "first_seen_at": r[11].isoformat() if r[11] else None,
                "last_seen_at": r[12].isoformat() if r[12] else None,
                "occurrence_count": r[13] or 1} for r in rows]

    return {"base_info": base_info, "records": records, "senders": senders,
            "related_senders": related_senders, "message_contexts": message_contexts,
            "conversations": conversations, "total_records": len(records)}
