#!/usr/bin/env python3
"""
回填手机号记录 - 从 senders 和 messages 表中提取手机号导入 phone_records
"""
import sys
sys.path.insert(0, "/home/test/tg-monitor/backend")

import pymysql
from app.services.phone_service import get_full_info, extract_phones_from_text

conn = pymysql.connect(
    host='localhost', user='tgmonitor', password='TgMonitor2026Secure',
    database='tg_monitor_v2', charset='utf8mb4'
)
cur = conn.cursor()

# ========================================
# Phase 1: 从 senders 表导入发送者手机号
# ========================================
print("=== Phase 1: 导入发送者手机号 ===")
cur.execute("""
    SELECT id, user_id, phone, country_code, country, phone_location,
           first_name, last_name, username
    FROM senders
    WHERE phone IS NOT NULL AND phone != '' AND country_code = 'CN'
""")
senders = cur.fetchall()
print(f"找到 {len(senders)} 个中国发送者")

sender_inserted = 0
for row in senders:
    sender_id, user_id, phone, cc, country, loc, first, last, uname = row
    # 标准化手机号（去掉可能的+号和86前缀）
    clean_phone = phone.replace('+', '')
    if clean_phone.startswith('86') and len(clean_phone) > 11:
        clean_phone = clean_phone[2:]
    if len(clean_phone) != 11 or not clean_phone.isdigit():
        continue

    detail = f"sender: {first or ''} {last or ''} (@{uname or ''})".strip()
    phone_info = get_full_info(clean_phone)

    try:
        cur.execute("""
            INSERT INTO phone_records (
                phone, phone_display, country_code, country, phone_location, carrier,
                source_type, source_id, source_detail, conversation_id,
                first_seen_at, last_seen_at, occurrence_count
            ) VALUES (%s, %s, %s, %s, %s, %s, 'sender', %s, %s, 0, NOW(), NOW(), 1)
            ON DUPLICATE KEY UPDATE
                last_seen_at = NOW(),
                occurrence_count = occurrence_count + 1
        """, (
            clean_phone, phone, phone_info.get("country_code", cc or ""),
            phone_info.get("country", country or ""),
            phone_info.get("location", loc or ""),
            phone_info.get("carrier", ""),
            user_id, detail[:500]
        ))
        sender_inserted += 1
    except Exception as e:
        if sender_inserted < 5:
            print(f"  Error: {clean_phone} - {e}")

conn.commit()
print(f"发送者手机号导入完成: {sender_inserted} 条")

# ========================================
# Phase 2: 从 messages 表提取正文中的手机号
# ========================================
print("\n=== Phase 2: 从消息正文提取手机号 ===")

# 先统计有多少消息需要处理
cur.execute("""
    SELECT COUNT(*) FROM messages
    WHERE (text IS NOT NULL AND text != '') OR (caption IS NOT NULL AND caption != '')
""")
total_messages = cur.fetchone()[0]
print(f"共 {total_messages} 条消息需要扫描")

# 分批处理
BATCH_SIZE = 10000
message_inserted = 0
messages_scanned = 0

cur.execute("""
    SELECT id, text, caption, conversation_id, sender_id
    FROM messages
    WHERE (text IS NOT NULL AND text != '') OR (caption IS NOT NULL AND caption != '')
    ORDER BY id
""")
rows = cur.fetchall()
total = len(rows)

for idx, row in enumerate(rows):
    msg_id, text, caption, conv_id, sender_id = row

    # 合并文本
    full_text = ""
    if text:
        full_text += text + " "
    if caption:
        full_text += caption

    if not full_text.strip():
        continue

    # 提取手机号
    phones = extract_phones_from_text(full_text)
    if not phones:
        continue

    for p in phones:
        phone_num = p["phone"]
        phone_detail = get_full_info(phone_num)

        try:
            cur.execute("""
                INSERT INTO phone_records (
                    phone, phone_display, country_code, country, phone_location, carrier,
                    source_type, source_id, source_detail, conversation_id,
                    first_seen_at, last_seen_at, occurrence_count
                ) VALUES (%s, %s, %s, %s, %s, %s, 'message', %s, %s, %s, NOW(), NOW(), 1)
                ON DUPLICATE KEY UPDATE
                    last_seen_at = NOW(),
                    occurrence_count = occurrence_count + 1,
                    source_detail = IF(LENGTH(COALESCE(%s, '')) > LENGTH(COALESCE(source_detail, '')), %s, source_detail)
            """, (
                phone_num, p.get("display", phone_num),
                phone_detail.get("country_code", ""),
                phone_detail.get("country", ""),
                phone_detail.get("location", ""),
                phone_detail.get("carrier", ""),
                msg_id, p.get("context", "")[:500] if p.get("context") else "",
                conv_id or 0,
                p.get("context", "")[:500] if p.get("context") else "",
                p.get("context", "")[:500] if p.get("context") else "",
            ))
            message_inserted += 1
        except Exception as e:
            if message_inserted < 5:
                print(f"  Error: {phone_num} - {e}")

    messages_scanned += 1
    if messages_scanned % 5000 == 0:
        conn.commit()
        print(f"  进度: {messages_scanned}/{total} ({messages_scanned*100//total}%), 已插入 {message_inserted} 条")

conn.commit()
print(f"消息手机号提取完成: 扫描 {messages_scanned} 条消息, 插入 {message_inserted} 条记录")

# ========================================
# Phase 3: 从 alerts 表提取告警中的手机号
# ========================================
print("\n=== Phase 3: 从告警内容提取手机号 ===")

cur.execute("""
    SELECT COUNT(*) FROM alerts
    WHERE message_preview IS NOT NULL AND message_preview != ''
""")
total_alerts = cur.fetchone()[0]
print(f"共 {total_alerts} 条告警需要扫描")

ALERT_BATCH = 10000
alert_inserted = 0
alerts_scanned = 0

cur.execute("""
    SELECT id, message_preview, highlighted_message, sender_id, conversation_id
    FROM alerts
    WHERE message_preview IS NOT NULL AND message_preview != ''
    ORDER BY id
""")
alert_rows = cur.fetchall()
total_a = len(alert_rows)

for idx, row in enumerate(alert_rows):
    alert_id, preview, highlighted, sender_id, conv_id = row

    full_text = ""
    if preview:
        full_text += preview + " "
    if highlighted:
        # Strip HTML tags for phone extraction
        import re
        clean = re.sub(r'<[^>]+>', '', highlighted)
        full_text += clean

    if not full_text.strip():
        continue

    phones = extract_phones_from_text(full_text)
    if not phones:
        continue

    for p in phones:
        phone_num = p["phone"]
        phone_detail = get_full_info(phone_num)

        try:
            cur.execute("""
                INSERT INTO phone_records (
                    phone, phone_display, country_code, country, phone_location, carrier,
                    source_type, source_id, source_detail, conversation_id,
                    first_seen_at, last_seen_at, occurrence_count
                ) VALUES (%s, %s, %s, %s, %s, %s, 'alert', %s, %s, %s, NOW(), NOW(), 1)
                ON DUPLICATE KEY UPDATE
                    last_seen_at = NOW(),
                    occurrence_count = occurrence_count + 1
            """, (
                phone_num, p.get("display", phone_num),
                phone_detail.get("country_code", ""),
                phone_detail.get("country", ""),
                phone_detail.get("location", ""),
                phone_detail.get("carrier", ""),
                alert_id, p.get("context", "")[:500] if p.get("context") else "",
                conv_id or 0,
            ))
            alert_inserted += 1
        except Exception as e:
            if alert_inserted < 5:
                print(f"  Error: {phone_num} - {e}")

    alerts_scanned += 1
    if alerts_scanned % 5000 == 0:
        conn.commit()
        print(f"  进度: {alerts_scanned}/{total_a} ({alerts_scanned*100//total_a}%), 已插入 {alert_inserted} 条")

conn.commit()
print(f"告警手机号提取完成: 扫描 {alerts_scanned} 条告警, 插入 {alert_inserted} 条记录")

# ========================================
# Summary
# ========================================
print("\n=== 回填完成 ===")
cur.execute("SELECT COUNT(*) FROM phone_records")
total_records = cur.fetchone()[0]
cur.execute("SELECT source_type, COUNT(*) FROM phone_records GROUP BY source_type")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")
print(f"  总计: {total_records}")

# 国内号码统计
cur.execute("SELECT COUNT(*) FROM phone_records WHERE country_code = 'CN'")
print(f"  国内号码: {cur.fetchone()[0]}")

conn.close()
