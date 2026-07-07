# TG Monitor 多Worker架构 - 代码审查报告

## 审查时间
2026-07-07 09:50

## 审查范围
- `backend/app/core/worker_config.py`
- `backend/app/workers/api_worker.py`
- `backend/app/workers/monitor_worker.py`
- `backend/app/api/dashboard.py`
- `backend/app/api/health.py`
- `backend/app/utils/redis_cache.py`

---

## 发现汇总

| 严重程度 | 数量 | 说明 |
|----------|------|------|
| **🔴 严重** | 5 | 需要立即修复 |
| **🟠 重要** | 6 | 需要尽快修复 |
| **🟡 轻微** | 4 | 建议修复 |
| **总计** | 15 | - |

---

## 🔴 严重问题

### 1. 端口冲突Bug
**文件**: `worker_config.py:79,83`
**问题**: 当 `worker_id >= len(ports)` 时，回退到硬编码默认端口，导致与Worker 0端口冲突
**修复**: 使用 `ports[wid % len(ports)]` 替代条件表达式

### 2. worker_id=0 被错误忽略
**文件**: `worker_config.py:74`
**问题**: `wid = worker_id or self.worker_id` 当 worker_id=0 时被当作 falsy 值
**修复**: 使用 `wid = worker_id if worker_id is not None else self.worker_id`

### 3. WORKER_ID环境变量解析无错误处理
**文件**: `worker_config.py:32`
**问题**: 非整数环境变量会导致模块导入时崩溃
**修复**: 添加 try/except 包装

### 4. Redis连接失败返回False导致崩溃
**文件**: `redis_cache.py:60`
**问题**: `get()` 在 ConnectionError 时返回 `False` 而非 `None`，导致 TypeError
**修复**: 将 `return False` 改为 `return None`

### 5. api_worker缺少异常处理器
**文件**: `api_worker.py:create_app()`
**问题**: 未注册 AppException 和 general_exception 处理器
**修复**: 添加异常处理器注册

---

## 🟠 重要问题

### 6. api_worker缺少APIKeyAuth中间件
**文件**: `api_worker.py:create_app()`
**问题**: 未添加 APIKeyAuthMiddleware，API密钥认证不生效

### 7. api_worker缺少数据库初始化
**文件**: `api_worker.py:lifespan`
**问题**: 未调用 `init_db()` 创建表

### 8. api_worker缺少兼容路由
**文件**: `api_worker.py:create_app()`
**问题**: 缺少 `/api/v1/keyword-groups` 兼容路由

### 9. api_worker缺少代理配置加载
**文件**: `api_worker.py:lifespan`
**问题**: 未加载运行时代理配置

### 10. monitor_worker未停止心跳任务
**文件**: `monitor_worker.py:172-176`
**问题**: 关闭时未调用 `stop_heartbeat()`

### 11. monitor_worker无信号处理
**文件**: `monitor_worker.py`
**问题**: 未注册 SIGTERM/SIGINT 处理器

---

## 🟡 轻微问题

### 12. monitor_worker Uvicorn服务器未管理生命周期
**文件**: `monitor_worker.py:225`

### 13. connect_accounts无并发控制
**文件**: `monitor_worker.py:101-102`

### 14. dashboard.py使用废弃的.dict()方法
**文件**: `dashboard.py:66,435,485`

---

## 修复计划

1. 修复 worker_config.py 的端口冲突和worker_id问题
2. 修复 redis_cache.py 的返回值问题
3. 修复 api_worker.py 的异常处理器和中间件
4. 修复 monitor_worker.py 的关闭逻辑
