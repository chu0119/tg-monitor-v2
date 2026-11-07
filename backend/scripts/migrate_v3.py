"""v3.0 数据库治理迁移脚本（幂等，可重复执行）

用途（配合商用化重构，见 REFACTOR_PLAN.md 阶段2）：
1. 补齐大表缺失索引（alerts/messages/notification_logs/phone_records）
2. 删除线上重复索引（senders.idx_user_id 等）
3. 补唯一约束前先做数据去重（phone_records / case_alerts / watchlist / conversations）
4. alerts 表 OPTIMIZE 回收已删除行占用的空间（线上 ~10.5GB 中约 8GB 为空洞）

使用（服务器上执行）:
    cd /home/test/tg-monitor/backend
    python3 scripts/migrate_v3.py            # 全部步骤
    python3 scripts/migrate_v3.py --skip-optimize   # 跳过 OPTIMIZE（低峰再单独跑）

安全：只做加索引/删冗余索引/去重，不改列、不删数据行；
     phone_records 去重保留 occurrence_count 最大的一行并合并计数。
"""
import asyncio
import sys
import os

# 切到 backend 目录再导入 app：config.py 在 import 时会用相对路径创建
# sessions/exports 等目录，依赖 CWD（必须先 chdir，否则在 scripts/ 下运行会 FileNotFoundError）
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.getcwd())

from sqlalchemy import text
from app.core.database import AsyncSessionLocal, engine


# (索引名, 表名, 列定义)
INDEXES_TO_ADD = [
    ("idx_alerts_status_created", "alerts", "(status, created_at)"),
    ("idx_alerts_conv_created", "alerts", "(conversation_id, created_at)"),
    ("idx_alerts_sender_created", "alerts", "(sender_id, created_at)"),
    ("idx_messages_created_at", "messages", "(created_at)"),
    ("idx_notif_logs_status_created", "notification_logs", "(status, created_at)"),
    ("idx_phone_records_source", "phone_records", "(source_type, source_id)"),
    ("idx_phone_records_occ", "phone_records", "(occurrence_count, last_seen_at)"),
]

# (索引名, 表名) 线上重复/无用索引
INDEXES_TO_DROP = [
    ("idx_user_id", "senders"),          # 与 unique 的 ix_senders_user_id 重复
    ("idx_senders_message_alert", "senders"),  # 与 ix_senders_user_message_count 前缀重复
    ("ix_messages_telegram_id", "messages"),   # telegram_id 已废弃列的索引（列保留）
]

# 唯一约束：(表, 约束索引名, 列) —— 添加前先去重
UNIQUE_CONSTRAINTS = [
    ("phone_records", "uq_phone_records_phone", "phone"),
    ("case_alerts", "uq_case_alerts", "case_id, alert_id"),
    ("watchlist", "uq_watchlist_entity", "entity_type, entity_value"),
    ("conversations", "uq_conversations_account_chat", "account_id, chat_id"),
]


async def index_exists(conn, table: str, name: str) -> bool:
    result = await conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.statistics "
        "WHERE table_schema = DATABASE() AND table_name = :t AND index_name = :n"
    ), {"t": table, "n": name})
    return (result.scalar() or 0) > 0


async def add_indexes(conn) -> list:
    done = []
    for name, table, cols in INDEXES_TO_ADD:
        if await index_exists(conn, table, name):
            print(f"  = 跳过（已存在）: {table}.{name}")
            continue
        print(f"  + 添加索引: {table}.{name} {cols}")
        await conn.execute(text(f"CREATE INDEX {name} ON {table} {cols}"))
        done.append(f"{table}.{name}")
    return done


async def drop_indexes(conn) -> list:
    done = []
    for name, table in INDEXES_TO_DROP:
        if not await index_exists(conn, table, name):
            print(f"  = 跳过（不存在）: {table}.{name}")
            continue
        # 唯一键保护：确认不是 PRIMARY/UNIQUE 再删
        kind = await conn.execute(text(
            "SELECT NON_UNIQUE FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() AND table_name = :t AND index_name = :n LIMIT 1"
        ), {"t": table, "n": name})
        if (kind.scalar() or 1) == 0:
            print(f"  ! 跳过（是唯一索引，需人工确认）: {table}.{name}")
            continue
        print(f"  - 删除冗余索引: {table}.{name}")
        await conn.execute(text(f"DROP INDEX {name} ON {table}"))
        done.append(f"{table}.{name}")
    return done


async def dedupe_then_add_unique(conn) -> list:
    done = []
    # phone_records：按 phone 去重，保留 id 最小的一行，合并 occurrence_count 总和与最近时间
    result = await conn.execute(text(
        "SELECT COUNT(*) FROM (SELECT phone FROM phone_records GROUP BY phone HAVING COUNT(*) > 1) x"
    ))
    dup_phones = result.scalar() or 0
    if dup_phones:
        print(f"  ~ phone_records 发现 {dup_phones} 个重复号码，合并中...")
        # 1) 把每组的总次数与最近时间合并到 keeper（MIN(id)）
        await conn.execute(text("""
            UPDATE phone_records p
            JOIN (
                SELECT phone,
                       MIN(id) AS keep_id,
                       SUM(occurrence_count) AS total_cnt,
                       MAX(last_seen_at) AS last_seen
                FROM phone_records GROUP BY phone HAVING COUNT(*) > 1
            ) g ON p.id = g.keep_id
            SET p.occurrence_count = g.total_cnt,
                p.last_seen_at = g.last_seen
        """))
        # 2) 删除每组中未被保留的行
        await conn.execute(text("""
            DELETE p FROM phone_records p
            JOIN (
                SELECT phone, MIN(id) AS keep_id
                FROM phone_records GROUP BY phone HAVING COUNT(*) > 1
            ) g ON p.phone = g.phone AND p.id != g.keep_id
        """))
        print(f"  ✔ 已合并 {dup_phones} 组重复号码")
    else:
        print("  = phone_records 无重复号码")

    for table, name, cols in UNIQUE_CONSTRAINTS:
        if await index_exists(conn, table, name):
            print(f"  = 跳过（已存在）: {table}.{name}")
            continue
        dup = await conn.execute(text(
            f"SELECT COUNT(*) FROM (SELECT {cols} FROM {table} GROUP BY {cols} HAVING COUNT(*) > 1) x"
        ))
        n = dup.scalar() or 0
        if n:
            print(f"  ! {table} 存在 {n} 组重复 ({cols})，跳过唯一约束，请人工处理")
            continue
        print(f"  + 添加唯一约束: {table}.{name} ({cols})")
        await conn.execute(text(f"CREATE UNIQUE INDEX {name} ON {table} ({cols})"))
        done.append(f"{table}.{name}")
    return done


async def optimize_alerts() -> None:
    print("  ~ OPTIMIZE TABLE alerts（回收已删行空间，线上预计回收 ~8GB，耗时数分钟）...")
    async with engine.connect() as conn:
        await conn.execute(text("OPTIMIZE TABLE alerts"))
    print("  ✔ alerts 表空间回收完成")


async def widen_last_message_id(conn) -> None:
    """conversations.last_message_id 从 INT 扩到 BIGINT（替代消息ID ~10^14 超 INT 范围）"""
    result = await conn.execute(text(
        "SELECT DATA_TYPE FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name='conversations' AND column_name='last_message_id'"
    ))
    dtype = (result.scalar() or "").lower()
    if dtype == "bigint":
        print("  = conversations.last_message_id 已是 BIGINT")
        return
    print(f"  ~ conversations.last_message_id: {dtype} -> BIGINT ...")
    await conn.execute(text(
        "ALTER TABLE conversations MODIFY last_message_id BIGINT NULL"
    ))
    print("  ✔ conversations.last_message_id 已扩为 BIGINT")


async def add_occurrence_count(conn) -> None:
    """alerts 加 occurrence_count 列（窗口聚合功能）"""
    result = await conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name='alerts' AND column_name='occurrence_count'"
    ))
    if (result.scalar() or 0) > 0:
        print("  = alerts.occurrence_count 已存在")
        return
    print("  ~ alerts 加 occurrence_count 列 ...")
    await conn.execute(text(
        "ALTER TABLE alerts ADD COLUMN occurrence_count INT NOT NULL DEFAULT 1 "
        "COMMENT '聚合命中次数' AFTER merged_into_id"
    ))
    print("  ✔ alerts.occurrence_count 已添加")


async def main():
    skip_optimize = "--skip-optimize" in sys.argv
    print("=== TG Monitor v3 数据库治理迁移 ===")
    async with engine.begin() as conn:
        print("[0/3] 列类型修正:")
        await widen_last_message_id(conn)
        await add_occurrence_count(conn)
        print("[1/3] 补缺失索引:")
        await add_indexes(conn)
        print("[2/3] 删冗余索引:")
        await drop_indexes(conn)
        print("[3/3] 去重 + 唯一约束:")
        await dedupe_then_add_unique(conn)
    if skip_optimize:
        print("已跳过 OPTIMIZE（--skip-optimize）")
    else:
        await optimize_alerts()
    print("=== 迁移完成 ===")


if __name__ == "__main__":
    asyncio.run(main())
