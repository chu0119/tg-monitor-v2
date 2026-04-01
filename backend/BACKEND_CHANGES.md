# TG Monitor v2 - 后端改动总结

## 已完成的工作

### 1. 数据库模型（Models）
- ✅ `backend/app/models/settings.py` - 系统配置模型
- ✅ `backend/app/models/proxy_node.py` - 代理节点模型
- ✅ 更新 `backend/app/models/__init__.py` 导入新模型

### 2. 代理模块（Proxy Module）
- ✅ `backend/app/proxy/__init__.py` - 模块初始化
- ✅ `backend/app/proxy/subscribe_parser.py` - 多格式订阅解析器
  - 支持 Clash YAML 格式
  - 支持 Base64 编码格式
  - 支持 SS/SSR/VMess/Trojan/VLESS/Hysteria2 URI
- ✅ `backend/app/proxy/config_generator.py` - Mihomo 配置生成器
- ✅ `backend/app/proxy/manager.py` - 代理管理器（启停、切换节点、测试延迟）

### 3. API 路由（Routers）
- ✅ **Settings API** (`backend/app/api/settings.py`)
  - GET `/api/v1/settings/db` - 获取所有配置
  - PUT `/api/v1/settings/db` - 批量更新配置
  - GET `/api/v1/settings/db/{key}` - 获取单个配置
  - PUT `/api/v1/settings/db/{key}` - 更新单个配置
  - DELETE `/api/v1/settings/db/{key}` - 删除单个配置
  - GET `/api/v1/settings/initialized` - 检查初始化状态

- ✅ **Proxy API** (`backend/app/api/proxy.py`)
  - GET `/api/v1/proxy/status` - 获取代理状态
  - POST `/api/v1/proxy/subscribe` - 解析订阅链接
  - GET `/api/v1/proxy/nodes` - 获取节点列表
  - POST `/api/v1/proxy/nodes/{node_id}/select` - 选择节点
  - POST `/api/v1/proxy/nodes/{node_id}/test` - 测试节点延迟
  - POST `/api/v1/proxy/start` - 启动代理
  - POST `/api/v1/proxy/stop` - 停止代理
  - POST `/api/v1/proxy/restart` - 重启代理
  - DELETE `/api/v1/proxy/nodes` - 清空所有节点
  - DELETE `/api/v1/proxy/nodes/{node_id}` - 删除单个节点

- ✅ **System API** (`backend/app/api/system.py`)
  - GET `/api/v1/system/status` - 获取系统状态
  - POST `/api/v1/system/init-db` - 初始化数据库
  - POST `/api/v1/system/reset` - 重置系统
  - GET `/api/v1/system/health` - 健康检查
  - GET `/api/v1/system/version` - 获取版本信息
  - POST `/api/v1/system/test-db-connection` - 测试数据库连接

### 4. 启动逻辑改造
- ✅ 修改 `backend/app/main.py`
  - 添加初始化检查：启动时检查 `settings.initialized`
  - 未初始化时：仅启动 API，不启动监控
  - 已初始化时：启动完整功能（监控、代理、备份等）
  - 注册新的路由（proxy, system）
  - 创建代理目录

### 5. 数据库初始化脚本
- ✅ `backend/init_db.py` - 独立的数据库初始化脚本
  - 自动创建数据库（如果不存在）
  - 创建所有表
  - 插入默认配置

### 6. 文档
- ✅ `backend/API_DOCUMENTATION.md` - API 使用文档

---

## 文件清单

### 新增文件
```
backend/
├── app/
│   ├── models/
│   │   ├── settings.py              # 系统配置模型
│   │   └── proxy_node.py            # 代理节点模型
│   ├── proxy/                        # 代理模块
│   │   ├── __init__.py
│   │   ├── subscribe_parser.py      # 订阅解析器
│   │   ├── config_generator.py      # 配置生成器
│   │   └── manager.py               # 代理管理器
│   └── api/
│       ├── proxy.py                 # 代理 API
│       └── system.py                # 系统 API
├── init_db.py                       # 数据库初始化脚本
└── API_DOCUMENTATION.md             # API 文档
```

### 修改文件
```
backend/
├── app/
│   ├── models/
│   │   └── __init__.py              # 添加新模型导入
│   ├── api/
│   │   └── settings.py              # 添加数据库配置 API
│   └── main.py                      # 修改启动逻辑、注册新路由
```

---

## 数据库表结构

### settings 表（系统配置）
```sql
CREATE TABLE settings (
    key_name VARCHAR(100) PRIMARY KEY,
    value TEXT,
    category VARCHAR(50) DEFAULT 'general',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### proxy_nodes 表（代理节点）
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

## 使用流程

### 1. 首次部署
```bash
# 进入后端目录
cd backend

# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python3 init_db.py

# 启动后端
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 2. 前端配置
1. 前端访问 `/api/v1/settings/initialized` 检查是否已初始化
2. 如果未初始化，跳转到设置向导页面
3. 用户配置代理（可选）
   - 输入订阅链接
   - 选择节点
   - 测试连接
4. 用户添加 Telegram 账号
5. 用户配置通知（可选）
6. 完成后，前端调用 `/api/v1/settings/db` 设置 `initialized=true`
7. 重启后端服务

### 3. 日常使用
- 后端启动时自动检测初始化状态
- 已初始化：启动完整功能
- 通过 API 管理代理、账号、配置

---

## 重要注意事项

1. **代理内核**
   - 需要将 mihomo 可执行文件放在 `backend/proxy/mihomo`
   - 给予执行权限：`chmod +x backend/proxy/mihomo`
   - 支持自动下载（在 start.sh 中实现）

2. **Python 依赖**
   - 需要安装：`pyyaml`, `aiohttp`
   - 已添加到 requirements.txt

3. **数据库**
   - MySQL 5.7+ 或 MariaDB 10.3+
   - 字符集：utf8mb4

4. **向后兼容**
   - 保留了现有的所有功能
   - 现有的 API 不受影响
   - 现有的数据库表不受影响

---

## 测试建议

### 1. 数据库初始化
```bash
cd backend
python3 init_db.py
```

### 2. API 测试
```bash
# 检查初始化状态
curl http://localhost:8000/api/v1/settings/initialized

# 获取系统状态
curl http://localhost:8000/api/v1/system/status

# 解析订阅（示例）
curl -X POST http://localhost:8000/api/v1/proxy/subscribe \
  -H "Content-Type: application/json" \
  -d '{"url": "YOUR_SUBSCRIPTION_URL", "replace": false}'
```

### 3. 功能测试
- 测试订阅解析
- 测试节点选择
- 测试代理启停
- 测试配置读写

---

## 下一步工作

根据 DEV_SPEC.md，后续需要完成：

1. **前端改动**（P0）
   - 设置向导页
   - 代理管理页
   - 账号管理页改版
   - 系统设置页

2. **部署脚本**（P0）
   - start.sh 一键部署脚本
   - mihomo 内核自动下载

3. **服务配置**（P1）
   - systemd 服务配置
   - 开机自启

---

## 已知问题

1. 订阅解析器可能需要根据实际订阅格式调整
2. 节点延迟测试功能需要实际测试
3. 代理管理器需要与实际的 mihomo 内核配合测试

---

## 联系方式

如有问题，请参考：
- API 文档：`backend/API_DOCUMENTATION.md`
- 开发规格：`DEV_SPEC.md`
