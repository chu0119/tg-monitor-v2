# -*- coding: utf-8 -*-
"""手机号归属地/运营商存量回填

用修复后的双引擎解析（phone.dat 号段库 + phonenumbers）重新解析
phone_records 与 senders 表中已存手机号的归属地/运营商/国家。

用法（服务器）:
    cd /home/test/tg-monitor/backend
    python3 scripts/backfill_phone_attribution.py            # 实际执行
    python3 scripts/backfill_phone_attribution.py --dry-run  # 只统计不写入
"""
import asyncio
import sys
import os

# chdir 到 backend（规避 config.py 相对路径副作用）
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.getcwd())

from sqlalchemy import text
from app.core.database import AsyncSessionLocal
from app.services.phone_service import get_full_info

BATCH = 2000
DRY = "--dry-run" in sys.argv


async def backfill_phone_records():
    """回填 phone_records（情报主表）"""
    async with AsyncSessionLocal() as db:
        total = (await db.execute(text("SELECT COUNT(*) FROM phone_records WHERE phone != ''"))).scalar()
        print(f"[phone_records] 待处理 {total} 行")
        offset = 0
        changed = 0
        stats = {"province_city": 0, "country_only": 0, "invalid": 0}
        while True:
            rows = (await db.execute(text(
                "SELECT id, phone FROM phone_records WHERE phone != '' "
                "ORDER BY id LIMIT :b OFFSET :o"
            ), {"b": BATCH, "o": offset})).fetchall()
            if not rows:
                break
            for rid, phone in rows:
                info = get_full_info(phone)
                cc = info.get("country_code", "")
                country = info.get("country", "")
                carrier = info.get("carrier", "")
                loc = info.get("location", "")
                if cc == "CN":
                    # 中国号：省市级归属 或 兜底国家级
                    if loc and loc != "中国":
                        stats["province_city"] += 1
                    else:
                        stats["country_only"] += 1
                if not cc:
                    stats["invalid"] += 1
                if not DRY:
                    await db.execute(text(
                        "UPDATE phone_records SET country_code=:cc, country=:co, "
                        "carrier=:ca, phone_location=:lo WHERE id=:id"
                    ), {"cc": cc, "co": country, "ca": carrier, "lo": loc, "id": rid})
                changed += 1
            offset += len(rows)
            if offset % 20000 == 0 or offset >= total:
                print(f"  进度 {offset}/{total}")
        if not DRY:
            await db.commit()
        print(f"[phone_records] 处理 {changed} 行 | 省市级 {stats['province_city']} | "
              f"国家级兜底 {stats['country_only']} | 无法解析 {stats['invalid']}"
              + ("（dry-run 未写入）" if DRY else " | 已写回"))


async def backfill_senders():
    """回填 senders 的 phone 归属（Telegram 联系人手机号）"""
    async with AsyncSessionLocal() as db:
        total = (await db.execute(text(
            "SELECT COUNT(*) FROM senders WHERE phone IS NOT NULL AND phone != ''"
        ))).scalar()
        print(f"[senders] 待处理 {total} 行")
        offset = 0
        changed = 0
        while True:
            rows = (await db.execute(text(
                "SELECT id, phone FROM senders WHERE phone IS NOT NULL AND phone != '' "
                "ORDER BY id LIMIT :b OFFSET :o"
            ), {"b": BATCH, "o": offset})).fetchall()
            if not rows:
                break
            for rid, phone in rows:
                info = get_full_info(phone)
                if not DRY:
                    await db.execute(text(
                        "UPDATE senders SET country_code=:cc, country=:co, "
                        "phone_location=:lo WHERE id=:id"
                    ), {"cc": info.get("country_code", ""), "co": info.get("country", ""),
                        "lo": info.get("location", ""), "id": rid})
                changed += 1
            offset += len(rows)
            if offset % 20000 == 0 or offset >= total:
                print(f"  进度 {offset}/{total}")
        if not DRY:
            await db.commit()
        print(f"[senders] 处理 {changed} 行" + ("（dry-run 未写入）" if DRY else " | 已写回"))


async def main():
    print(f"=== 手机号归属地回填（dry-run={DRY}）===")
    await backfill_phone_records()
    await backfill_senders()
    print("=== 完成 ===")


if __name__ == "__main__":
    asyncio.run(main())
