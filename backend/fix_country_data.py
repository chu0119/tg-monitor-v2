#!/usr/bin/env python3
import sys
sys.path.insert(0, "/home/test/tg-monitor/backend")

import pymysql
from app.services.phone_service import get_full_info

conn = pymysql.connect(
    host='localhost', user='tgmonitor', password='TgMonitor2026Secure',
    database='tg_monitor_v2', charset='utf8mb4'
)
cur = conn.cursor()

cur.execute("SELECT id, user_id, phone, country_code, country, phone_location FROM senders WHERE phone IS NOT NULL AND phone != ''")
rows = cur.fetchall()
total = len(rows)
print("Total senders with phone: %d" % total)

updated = 0
unchanged = 0
errors = 0

for row in rows:
    sender_id, user_id, phone, old_cc, old_country, old_loc = row
    try:
        info = get_full_info(phone)
        new_cc = info.get("country_code", "")
        new_country = info.get("country", "")
        new_loc = info.get("location", "")

        if phone.startswith("8880"):
            if old_cc or old_country or old_loc:
                cur.execute("UPDATE senders SET country_code='', country='', phone_location='' WHERE id=%s", (sender_id,))
                updated += 1
            else:
                unchanged += 1
            continue

        if new_cc == (old_cc or "") and new_country == (old_country or "") and new_loc == (old_loc or ""):
            unchanged += 1
            continue

        cur.execute("UPDATE senders SET country_code=%s, country=%s, phone_location=%s WHERE id=%s",
                     (new_cc, new_country, new_loc, sender_id))
        updated += 1

        if updated % 500 == 0:
            print("  Processed %d/%d (updated: %d)" % (updated + unchanged, total, updated))

    except Exception as e:
        errors += 1
        if errors <= 5:
            print("  Error: phone=%s, error=%s" % (phone, str(e)))

conn.commit()

print("")
print("=== DONE ===")
print("  Total: %d" % total)
print("  Updated: %d" % updated)
print("  Unchanged: %d" % unchanged)
print("  Errors: %d" % errors)

print("")
print("=== Country Distribution ===")
cur.execute("SELECT country_code, country, COUNT(*) as cnt FROM senders WHERE phone IS NOT NULL AND phone != '' GROUP BY country_code, country ORDER BY cnt DESC LIMIT 20")
for r in cur.fetchall():
    print("  %s %s %d" % (str(r[0] or '?'), str(r[1] or '?'), r[2]))

print("")
print("=== Cuba numbers (535xxx) ===")
cur.execute("SELECT phone, country_code, country, phone_location FROM senders WHERE phone LIKE '535%%' LIMIT 5")
for r in cur.fetchall():
    print("  phone=%s, cc=%s, country=%s, loc=%s" % (r[0], r[1], r[2], r[3]))

conn.close()
