# 听风追影 — 多进程架构补全与性能优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** 在不中断现有业务的前提下，把「听风追影」从半成品多进程架构补全为可用的多进程架构，同时修复已发现的 7 个高严重度 bug、优化慢查询（页面加载 1-3s → <300ms）、补齐前端失效接口。

**Architecture:** 保持 api_worker（HTTP API）+ monitor_worker（Telegram 监控）双进程部署，通过 Redis pub/sub 实现跨进程消息广播与状态同步；把 main.py 中缺失的 `/health`、`/ws` 端点迁回 api_worker；用反范式冗余字段替代 800 万行大表的全表聚合；前端轮询周期与后端缓存 TTL 对齐。

**Tech Stack:** Python 3.12, FastAPI, Telethon 1.40, SQLAlchemy 2.0, aiomysql, Redis 7.x, React 18, Vite

**Spec:** 基于 4 路排查结果（后端架构/前端链路/性能/数据库缓存），共 24 个已验证问题。

## Global Constraints

- 现有业务零中断：当前 tgmonitor-api-0 + tgmonitor-monitor-0 服务持续运行，直到新代码验证通过才切换
- 所有改动在 `fix/telegram-monitor-baseline` 分支上进行，完成后一次性替换
- 数据零丢失：messages/alerts/senders/conversations 表只增不改结构（除冗余字段维护）
- 向后兼容：API 响应字段名、HTTP 状态码、WebSocket 消息格式保持不变
- 每个任务结束时有独立可验证的交付物（curl 实测 / EXPLAIN / 代码审查）
- 提交粒度：每个任务一个 commit，message 格式 `feat/fix(scope): description`

---

## Phase 1: 性能热修复（当前系统直接受益，风险最低）

### Task 1: 修复 messages 列表无条件 COUNT(*) 全表扫描

**背景:** `messages.py:250` 在分页前无条件 `SELECT COUNT(*) FROM messages` 扫描 798 万行，只为算 `total_pages`，实测 1.21s。

**Files:**
- Modify: `backend/app/api/messages.py:249-254, 300-305`

**Interfaces:**
- Consumes: 无
- Produces: `list_messages` 返回结构不变（items/total/pages）

- [ ] **Step 1: 写验证脚本**

创建 `backend/tests/test_messages_perf.py`（如无 tests 目录则建）：

```python
import asyncio, time
from httpx import AsyncClient

async def test_messages_list_under_300ms():
    async with AsyncClient(base_url="http://127.0.0.1:8000") as c:
        t0 = time.perf_counter()
        r = await c.get("/api/v1/messages?limit=50")
        elapsed = (time.perf_counter() - t0) * 1000
        assert r.status_code == 200
        assert elapsed < 300, f"messages list took {elapsed:.0f}ms"
```

- [ ] **Step 2: 运行验证，确认当前 >1000ms**

```bash
cd backend && python -m pytest tests/test_messages_perf.py -v 2>&1 | tail -5
```
Expected: FAIL (耗时 >300ms)

- [ ] **Step 3: 实现修复**

修改 `messages.py:249-254`，无筛选条件时用 information_schema 近似值：

```python
# 替换无条件 COUNT(*)
if not conditions:
    # 大表用 information_schema 近似值（毫秒级），避免全表扫描
    approx = await db.execute(text(
        "SELECT table_rows FROM information_schema.tables "
        "WHERE table_schema = DATABASE() AND table_name = 'messages'"
    ))
    total = approx.scalar() or 0
else:
    count_query = count_query.where(and_(*conditions))
    total = (await db.execute(count_query)).scalar()
```

- [ ] **Step 4: 运行验证，确认 <300ms**

```bash
cd backend && python -m pytest tests/test_messages_perf.py -v 2>&1 | tail -5
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/messages.py backend/tests/test_messages_perf.py
git commit -m "fix(messages): replace full-table COUNT with information_schema estimate when no filters"
```

---

### Task 2: 修复 senders 列表 alerts 全表 GROUP BY

**背景:** `senders.py:51-57` 对 619 万行 alerts 表全量 `GROUP BY sender_id`，但 `senders` 表已有 `alert_count` 冗余字段。实测 1.08s。

**Files:**
- Modify: `backend/app/api/senders.py:45-90`

- [ ] **Step 1: 验证脚本**

```python
async def test_senders_list_under_300ms():
    async with AsyncClient(base_url="http://127.0.0.1:8000") as c:
        t0 = time.perf_counter()
        r = await c.get("/api/v1/senders?limit=20")
        elapsed = (time.perf_counter() - t0) * 1000
        assert r.status_code == 200
        assert elapsed < 300
```

- [ ] **Step 2: 确认当前 >1000ms**

```bash
cd backend && python -m pytest tests/test_senders_perf.py -v 2>&1 | tail -3
```
Expected: FAIL

- [ ] **Step 3: 实现修复**

删除 `senders.py:51-68` 的 `alert_counts` 子查询和 `outerjoin`，直接读 `Sender.alert_count`：

```python
# 直接用冗余字段，不再实时聚合
query = select(Sender)
if sort_by == "alerts":
    query = query.order_by(Sender.alert_count.desc())
```

- [ ] **Step 4: 确认 <300ms**

```bash
cd backend && python -m pytest tests/test_senders_perf.py -v 2>&1 | tail -3
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/senders.py
git commit -m "fix(senders): use denormalized alert_count instead of full-table GROUP BY"
```

---

### Task 3: 修复 conversations 列表 messages 全表 GROUP BY

**背景:** `conversations.py:469-482` 对 messages 表按 conversation_id 实时聚合，但 `conversations` 表已有 `total_messages` 冗余字段。实测 2.02s。

**Files:**
- Modify: `backend/app/api/conversations.py:469-482`

- [ ] **Step 1-5: 同 Task 1 模式**

验证 → 确认 >1s → 改为读 `Conversation.total_messages` → 确认 <300ms → commit

```bash
git commit -m "fix(conversations): use denormalized total_messages instead of full-table GROUP BY"
```

---

### Task 4: 修复 dashboard/stats 告警级别全表 GROUP BY

**背景:** `dashboard.py:165-170` 对 alerts 全表 `GROUP BY alert_level`，实测 1.43s。

**Files:**
- Modify: `backend/app/api/dashboard.py:165-170`

- [ ] **Step 1-5: 同模式**

改为从 `senders` 表汇总或直接缓存：

```python
# 用 senders 表的 alert_count 汇总（已有索引）
level_dist = await db.execute(
    select(Sender.alert_level, func.count()).group_by(Sender.alert_level)
)
```

```bash
git commit -m "fix(dashboard): replace alerts full-table GROUP BY with senders aggregation"
```

---

## Phase 2: 多进程架构补全（核心 B 方案）

### Task 5: Redis pub/sub 跨进程广播基础设施

**背景:** monitor_worker 采集到的消息需要广播到 api_worker 的 WebSocket。当前 `monitor.py:908` 的 `from app.main import broadcast_new_message` 跨进程 import 导致广播发到空 manager。

**Files:**
- Create: `backend/app/core/pubsub.py`
- Modify: `backend/app/telegram/monitor.py:905-945`
- Modify: `backend/app/workers/api_worker.py`（订阅端）

- [ ] **Step 1: 创建 pubsub 模块**

```python
# backend/app/core/pubsub.py
import json, asyncio, redis.asyncio as aioredis
from loguru import logger

CHANNEL = "tg_monitor_events"

async def publish(event_type: str, data: dict):
    r = aioredis.Redis()
    await r.publish(CHANNEL, json.dumps({"type": event_type, **data}))
    await r.close()

async def subscribe(handler):
    r = aioredis.Redis()
    async with r.pubsub() as ps:
        await ps.subscribe(CHANNEL)
        async for msg in ps.listen():
            if msg["type"] == "message":
                await handler(json.loads(msg["data"]))
```

- [ ] **Step 2: monitor_worker 发布端**

修改 `monitor.py:905-945` 的 `_broadcast_new_message`：

```python
from app.core.pubsub import publish
# 替换 from app.main import broadcast_new_message
await publish("new_message", message_data)
```

- [ ] **Step 3: api_worker 订阅端**

在 api_worker 的 lifespan 启动订阅，收到消息后调 `broadcast_new_message`：

```python
from app.core.pubsub import subscribe
async def _relay():
    await subscribe(lambda data: broadcast_new_message(data))
asyncio.create_task(_relay())
```

- [ ] **Step 4: 验证**

重启两个 worker，发一条测试消息，确认 api_worker 日志收到 Redis 事件并推送到 WebSocket。

```bash
git add backend/app/core/pubsub.py backend/app/telegram/monitor.py backend/app/workers/api_worker.py
git commit -m "feat(pubsub): Redis pub/sub cross-process message broadcast"
```

---

### Task 6: 迁移 /health 详细端点到 api_worker

**背景:** 前端 `fetch("/health")` 期望返回 resources/telegram/websocket/alert_pipeline 结构，但 api_worker 没有此端点（只有简单探活）。

**Files:**
- Create: `backend/app/api/health_detailed.py`
- Modify: `backend/app/workers/api_worker.py`（注册路由）

- [ ] **Step 1: 创建 health_detailed 模块**

从 `main.py:466-574` 提取健康检查逻辑，改为读取 monitor_worker 的状态（通过 Redis 或共享状态）：

```python
@router.get("/health/detailed")
async def detailed_health():
    return {
        "status": "ok",
        "database": await check_database(),
        "system": get_system_stats(),
        "telegram": await get_telegram_status(),  # 从 Redis 或 monitor_worker 9010 获取
        "websocket": {"connections": ws_manager.count()},
    }
```

- [ ] **Step 2: 注册到 api_worker**

```python
from app.api.health_detailed import router as health_detailed_router
app.include_router(health_detailed_router)  # 无前缀，直接 /health/detailed
```

- [ ] **Step 3: 验证**

```bash
curl -s http://localhost:8000/health/detailed | python3 -m json.tool
```
Expected: 返回完整 resources/telegram 结构

```bash
git add backend/app/api/health_detailed.py backend/app/workers/api_worker.py
git commit -m "feat(health): migrate detailed health endpoint to api_worker"
```

---

### Task 7: 迁移 WebSocket /ws 到 api_worker

**背景:** 前端 `useWebSocket("/ws")` 需要后端有 `/ws` 端点。当前只在 main.py 中。

**Files:**
- Create: `backend/app/core/websocket_manager.py`（从 main.py 提取）
- Modify: `backend/app/workers/api_worker.py`

- [ ] **Step 1: 提取 ConnectionManager**

把 `main.py:55-173` 的 ConnectionManager 和 broadcast 函数移到 `backend/app/core/websocket_manager.py`。

- [ ] **Step 2: api_worker 注册 /ws**

```python
from app.core.websocket_manager import manager, websocket_endpoint
app.add_websocket_route("/ws", websocket_endpoint)
```

- [ ] **Step 3: 验证 WebSocket 连接**

```bash
python3 -c "
import asyncio, websockets, json
async def test():
    async with websockets.connect('ws://localhost:8000/ws') as ws:
        await ws.send(json.dumps({'type':'ping'}))
        resp = await asyncio.wait_for(ws.recv(), timeout=5)
        assert json.loads(resp)['type'] == 'pong'
        print('WebSocket OK')
asyncio.run(test())
```

```bash
git add backend/app/core/websocket_manager.py backend/app/workers/api_worker.py
git commit -m "feat(websocket): migrate /ws endpoint to api_worker"
```

---

### Task 8: 修复 monitoring/status 跨进程状态

**背景:** api_worker 的 `monitoring/status` 查的是本进程空 client_manager。需要改为查 monitor_worker 的真实状态。

**Files:**
- Modify: `backend/app/api/monitoring.py:54-82`

- [ ] **Step 1: 改为查 monitor_worker 9010 状态**

```python
import httpx
@router.get("/status")
async def get_status():
    async with httpx.AsyncClient() as c:
        monitor_status = await c.get("http://127.0.0.1:9010/status")
        return monitor_status.json()
```

- [ ] **Step 2: 验证**

```bash
curl -s http://localhost:8000/api/v1/monitoring/status | python3 -m json.tool
```
Expected: active_monitors=291, connected_clients=1

```bash
git add backend/app/api/monitoring.py
git commit -m "fix(monitoring): query real monitor_worker status via HTTP"
```

---

### Task 9: 修复 worker_config 账号分配逻辑

**背景:** `worker_config.py:89` 用硬编码 `range(1,6)` 连续 ID 区间分配账号，账号 ID >5 后永远不被监控。

**Files:**
- Modify: `backend/app/core/worker_config.py:85-95`

- [ ] **Step 1: 改为按实际授权账号列表轮询切分**

```python
async def get_account_ids(db, worker_id, num_workers):
    result = await db.execute(
        select(TelegramAccount.id).where(
            TelegramAccount.is_authorized == True,
            TelegramAccount.is_active == True
        ).order_by(TelegramAccount.id)
    )
    all_ids = [r[0] for r in result.fetchall()]
    # 轮询分配
    return [aid for i, aid in enumerate(all_ids) if i % num_workers == worker_id]
```

- [ ] **Step 2: 验证**

```bash
cd backend && python3 -c "
import asyncio
from app.core.worker_config import get_account_ids
from app.core.database import AsyncSessionLocal
async def test():
    async with AsyncSessionLocal() as db:
        print('worker 0:', await get_account_ids(db, 0, 1))
asyncio.run(test())
"
```
Expected: [3]（当前只有 1 个账号）

```bash
git add backend/app/core/worker_config.py
git commit -m "fix(worker): assign accounts by round-robin instead of hardcoded ID range"
```

---

## Phase 3: 前端接口补全

### Task 10: 补全 accounts.toggle 接口

**Files:**
- Modify: `backend/app/api/accounts.py`（新增路由）

```python
@router.post("/{account_id}/toggle")
async def toggle_account(account_id: int, db=Depends(get_db)):
    account = await db.get(TelegramAccount, account_id)
    account.is_active = not account.is_active
    await db.commit()
    return {"id": account_id, "is_active": account.is_active}
```

验证 → commit

---

### Task 11: 补全 cases.getAlerts 接口

**Files:**
- Modify: `backend/app/api/cases.py`

```python
@router.get("/{case_id}/alerts")
async def get_case_alerts(case_id: int, db=Depends(get_db)):
    result = await db.execute(
        select(Alert).join(case_alerts).where(case_alerts.c.case_id == case_id)
    )
    return result.scalars().all()
```

---

### Task 12: 修复审计/重点名单筛选参数名

**Files:**
- Modify: `backend/app/api/audit.py:14-21`
- Modify: `backend/app/api/watchlist.py:30-39`

为前端参数名加 Pydantic alias：

```python
action: Optional[str] = Field(None, alias="action_type")
start_time: Optional[datetime] = Field(None, alias="start_date")
```

---

### Task 13: 前端轮询周期与后端缓存对齐

**Files:**
- Modify: `frontend/src/pages/DashboardPage.tsx:319`（30s → 5min）
- Modify: `frontend/src/pages/MonitoringPage.tsx:181-184`（5s 轮询在 WebSocket 正常时禁用）
- Modify: `frontend/src/lib/api.ts`（加 AbortController 10s 超时）

---

## Phase 4: 数据冗余维护

### Task 14: 维护 conversations.total_messages

**Files:**
- Modify: `backend/app/telegram/monitor.py`（写消息同事务内 UPDATE）

```python
# 在 _save_message 同事务内
await db.execute(
    text("UPDATE conversations SET total_messages = total_messages + 1 WHERE id = :cid"),
    {"cid": conversation_id}
)
```

### Task 15: 维护 senders.alert_count

**Files:**
- Modify: `backend/app/services/alert_service.py`（创建告警时 +1）

```python
await db.execute(
    text("UPDATE senders SET alert_count = alert_count + 1 WHERE id = :sid"),
    {"sid": sender_id}
)
```

### Task 16: 历史数据回填脚本

**Files:**
- Create: `backend/scripts/backfill_denormalized.py`

```sql
UPDATE conversations c SET total_messages = (
    SELECT COUNT(*) FROM messages WHERE conversation_id = c.id
);
UPDATE senders s SET alert_count = (
    SELECT COUNT(*) FROM alerts WHERE sender_id = s.id
);
```

---

## Phase 5: 切换与验证

### Task 17: 部署验证清单

- [ ] 所有接口 curl 验证通过
- [ ] WebSocket 实时推送正常
- [ ] Dashboard 机器信息/监控状态显示正确
- [ ] messages/senders/conversations 列表 <300ms
- [ ] 账号启用/禁用、案件关联告警、筛选功能正常
- [ ] monitor_worker 日志不再落错目录
- [ ] 回滚预案验证（切回旧 service 文件可在 30s 内恢复）

### Task 18: 切换到新代码

```bash
# 停止旧服务
sudo systemctl stop tgmonitor-api-0 tgmonitor-monitor-0
# 启动新代码（部署脚本或手动）
# 验证 → 完成
```

---

## 风险与回滚

| 风险 | 缓解 |
|------|------|
| Redis pub/sub 消息丢失 | 保留 DB 轮询作为 fallback；消息不持久化但实时性优先 |
| 冗余字段不同步 | 写路径同事务维护 + 月度回填脚本 |
| 新代码启动失败 | 旧 service 文件保留，30s 内回滚 |
| 性能回滚 | 每个任务独立 commit，可 `git revert` 单任务 |
