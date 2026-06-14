# TG Monitor v2 - 后端 API 文档

## 新增功能 API

### 1. Settings API（配置管理）

#### 获取所有配置（从数据库）
```
GET /api/v1/settings/db
Query参数：
  - category (可选): 配置分类（general/proxy/notification/account）

响应示例：
{
  "success": true,
  "settings": {
    "initialized": {
      "value": "true",
      "category": "system",
      "updated_at": "2024-01-01T00:00:00"
    }
  }
}
```

#### 批量更新配置
```
PUT /api/v1/settings/db
Body: {
  "settings": {
    "proxy_port": "7897",
    "proxy_enabled": "true"
  }
}
```

#### 获取单个配置
```
GET /api/v1/settings/db/{key}
```

#### 更新单个配置
```
PUT /api/v1/settings/db/{key}?value=xxx&category=proxy
```

#### 删除单个配置
```
DELETE /api/v1/settings/db/{key}
```

#### 检查是否已初始化
```
GET /api/v1/settings/initialized
响应：{
  "initialized": true
}
```

---

### 2. Proxy API（代理管理）

#### 获取代理状态
```
GET /api/v1/proxy/status
响应示例：
{
  "success": true,
  "status": {
    "running": true,
    "pid": 12345,
    "current_node": "HK-Node-01",
    "proxy_port": 7897,
    "config_exists": true
  }
}
```

#### 解析订阅链接
```
POST /api/v1/proxy/subscribe
Body: {
  "url": "https://example.com/subscribe",
  "replace": false  // 是否替换现有节点
}

响应示例：
{
  "success": true,
  "total_nodes": 50,
  "saved_nodes": 45,
  "nodes": [...]  // 前10个节点预览
}
```

#### 获取节点列表
```
GET /api/v1/proxy/nodes
响应示例：
{
  "success": true,
  "total": 50,
  "nodes": [
    {
      "id": 1,
      "name": "HK-Node-01",
      "type": "vmess",
      "server": "hk1.example.com",
      "port": 443,
      "is_selected": true,
      "latency_ms": 120,
      "created_at": "2024-01-01T00:00:00"
    }
  ]
}
```

#### 选择节点
```
POST /api/v1/proxy/nodes/{node_id}/select
Body (可选): {
  "proxy_port": 7897
}

响应示例：
{
  "success": true,
  "node_id": 1,
  "node_name": "HK-Node-01",
  "proxy_port": 7897,
  "message": "已选择节点 HK-Node-01"
}
```

#### 测试节点延迟
```
POST /api/v1/proxy/nodes/{node_id}/test
响应示例：
{
  "success": true,
  "node_id": 1,
  "node_name": "HK-Node-01",
  "latency_ms": 120,
  "message": "节点延迟: 120ms"
}
```

#### 启动代理
```
POST /api/v1/proxy/start
```

#### 停止代理
```
POST /api/v1/proxy/stop
```

#### 重启代理
```
POST /api/v1/proxy/restart
```

#### 清空所有节点
```
DELETE /api/v1/proxy/nodes
```

#### 删除单个节点
```
DELETE /api/v1/proxy/nodes/{node_id}
```

---

### 3. System API（系统管理）

#### 获取系统状态
```
GET /api/v1/system/status
响应示例：
{
  "success": true,
  "initialized": true,
  "database": {
    "connected": true,
    "type": "mysql",
    "version": "8.0.26",
    "database": "tg_monitor"
  },
  "proxy": {
    "running": true,
    "current_node": "HK-Node-01"
  },
  "account_count": 2,
  "system": {
    "python_version": "3.11.0",
    "node_version": "18.0.0",
    "platform": "Linux-5.15.0",
    "architecture": "x86_64"
  }
}
```

#### 初始化数据库
```
POST /api/v1/system/init-db
响应示例：
{
  "success": true,
  "message": "数据库初始化成功",
  "initialized": true
}
```

#### 重置系统
```
POST /api/v1/system/reset
警告：此操作会清空所有数据！
```

#### 健康检查
```
GET /api/v1/system/health
响应示例：
{
  "status": "healthy",
  "service": "TG Monitor Backend"
}
```

#### 获取版本信息
```
GET /api/v1/system/version
```

#### 测试数据库连接
```
POST /api/v1/system/test-db-connection
```

---

### 4. Accounts API（账号管理）

现有的账号 API 已经支持完整的增删改查功能，无需修改。

---

## 数据库模型

### Settings 表
```sql
CREATE TABLE settings (
    key_name VARCHAR(100) PRIMARY KEY,
    value TEXT,
    category VARCHAR(50) DEFAULT 'general',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### ProxyNodes 表
```sql
CREATE TABLE proxy_nodes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    type VARCHAR(20) NOT NULL,
    server VARCHAR(200),
    port INT,
    config_json TEXT,
    is_selected BOOLEAN DEFAULT FALSE,
    latency_ms INT,
    subscription_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

---

## 初始化流程

### 首次部署
```bash
# 1. 运行数据库初始化脚本
cd backend
python init_db.py

# 2. 启动后端
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 3. 访问前端进行配置
# 前端会自动检测未初始化状态，跳转到设置向导页面
```

### 配置流程
1. 前端检测到 `initialized = false`
2. 跳转到设置向导页面
3. 用户配置代理（可选）
4. 用户添加 Telegram 账号
5. 用户配置通知（可选）
6. 完成后设置 `initialized = true`
7. 重启后端服务，启动完整功能

---

## 启动逻辑

后端启动时会检查 `settings` 表中的 `initialized` 配置项：

- **如果 `initialized = false` 或不存在**：
  - 仅启动 API 服务
  - 不启动 Telegram 监控
  - 不启动代理
  - 允许前端访问设置向导

- **如果 `initialized = true`**：
  - 启动完整功能
  - 连接 Telegram 账号
  - 启动消息监控
  - 启动代理（如果配置了）
  - 启动后台任务（清理、备份等）

---

## 错误处理

所有 API 都遵循统一的错误响应格式：

```json
{
  "detail": "错误描述信息"
}
```

HTTP 状态码：
- 200: 成功
- 400: 请求参数错误
- 404: 资源不存在
- 500: 服务器内部错误

---

## 注意事项

1. **代理模块依赖**：
   - 需要安装 `pyyaml` 和 `aiohttp`
   - mihomo 可执行文件需要放在 `backend/proxy/mihomo`

2. **数据库要求**：
   - MySQL 5.7+ 或 MariaDB 10.3+
   - 字符集：utf8mb4
   - 排序规则：utf8mb4_unicode_ci

3. **首次使用**：
   - 必须先运行 `init_db.py` 初始化数据库
   - 前端会自动检测并引导配置

4. **代理配置**：
   - 支持多种订阅格式（Clash YAML、Base64、URI）
   - 支持多种协议（SS、SSR、VMess、Trojan、VLESS、Hysteria2）
   - 自动解析并保存节点到数据库
