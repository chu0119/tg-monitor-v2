import sys, re
sys.path.insert(0, "/home/test/tg-monitor/backend")
import pymysql
from app.services.phone_service import get_full_info, extract_phones_from_text

conn = pymysql.connect(host="localhost", user="tgmonitor", password="TgMonitor2026Secure", database="tg_monitor_v2", charset="utf8mb4")
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM phone_records WHERE source_type = 'sender'")
sender_count = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM phone_records WHERE source_type = 'message'")
msg_count = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM phone_records WHERE source_type = 'alert'")
alert_count = cur.fetchone()[0]
print("Current: sender=%d, message=%d, alert=%d" % (sender_count, msg_count, alert_count))

if msg_count == 0:
    print("Phase 2: Messages")
    cur.execute("SELECT id, text, caption, conversation_id, sender_id FROM messages WHERE (text IS NOT NULL AND text != '') OR (caption IS NOT NULL AND caption != '') ORDER BY id")
    rows = cur.fetchall()
    total = len(rows)
    print("Messages to scan: %d" % total)
    inserted = 0
    for idx, row in enumerate(rows):
        msg_id, text, caption, conv_id, sender_id = row
        full_text = (text or "") + " " + (caption or "")
        if not full_text.strip(): continue
        phones = extract_phones_from_text(full_text)
        for p in phones:
            phone_num = p["phone"]
            pd = get_full_info(phone_num)
            try:
                cur.execute("INSERT INTO phone_records (phone, phone_display, country_code, country, phone_location, carrier, source_type, source_id, source_detail, conversation_id, first_seen_at, last_seen_at, occurrence_count) VALUES (%s, %s, %s, %s, %s, %s, 'message', %s, %s, %s, NOW(), NOW(), 1) ON DUPLICATE KEY UPDATE last_seen_at=NOW(), occurrence_count=occurrence_count+1",
                    (phone_num, p.get("display", phone_num), pd.get("country_code",""), pd.get("country",""), pd.get("location",""), pd.get("carrier",""), msg_id, (p.get("context","") or "")[:500], conv_id or 0))
                inserted += 1
            except: pass
        if (idx+1) % 5000 == 0:
            conn.commit()
            print("  %d/%d (%d%%), inserted=%d" % (idx+1, total, (idx+1)*100//total, inserted))
    conn.commit()
    print("Phase 2 done: %d inserted" % inserted)
else:
    print("Phase 2 skipped")

if alert_count == 0:
    print("Phase 3: Alerts")
    cur.execute("SELECT id, message_preview, highlighted_message, sender_id, conversation_id FROM alerts WHERE message_preview IS NOT NULL AND message_preview != '' ORDER BY id")
    rows = cur.fetchall()
    total = len(rows)
    print("Alerts to scan: %d" % total)
    inserted = 0
    for idx, row in enumerate(rows):
        alert_id, preview, highlighted, sender_id, conv_id = row
        full_text = (preview or "") + " " + re.sub(r"<[^>]+>", "", highlighted or "")
        if not full_text.strip(): continue
        phones = extract_phones_from_text(full_text)
        for p in phones:
            phone_num = p["phone"]
            pd = get_full_info(phone_num)
            try:
                cur.execute("INSERT INTO phone_records (phone, phone_display, country_code, country, phone_location, carrier, source_type, source_id, source_detail, conversation_id, first_seen_at, last_seen_at, occurrence_count) VALUES (%s, %s, %s, %s, %s, %s, 'alert', %s, %s, %s, NOW(), NOW(), 1) ON DUPLICATE KEY UPDATE last_seen_at=NOW(), occurrence_count=occurrence_count+1",
                    (phone_num, p.get("display", phone_num), pd.get("country_code",""), pd.get("country",""), pd.get("location",""), pd.get("carrier",""), alert_id, (p.get("context","") or "")[:500], conv_id or 0))
                inserted += 1
            except: pass
        if (idx+1) % 5000 == 0:
            conn.commit()
            print("  %d/%d (%d%%), inserted=%d" % (idx+1, total, (idx+1)*100//total, inserted))
    conn.commit()
    print("Phase 3 done: %d inserted" % inserted)
else:
    print("Phase 3 skipped")

print("Summary:")
cur.execute("SELECT source_type, COUNT(*) FROM phone_records GROUP BY source_type ORDER BY COUNT(*) DESC")
for row in cur.fetchall():
    print("  %s: %d" % (row[0], row[1]))
cur.execute("SELECT COUNT(*) FROM phone_records")
print("  Total: %d" % cur.fetchone()[0])
conn.close()
