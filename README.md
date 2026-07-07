<div align="center">

# 🔥 听风追影
### —— 群组数据预警分析系统 v2.0.0

<p>
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black" />
  <img src="https://img.shields.io/badge/TypeScript-5.7-3178C6?style=for-the-badge&logo=typescript&logoColor=white" />
  <img src="https://img.shields.io/badge/MySQL-8.0-4479A1?style=for-the-badge&logo=mysql&logoColor=white" />
  <img src="https://img.shields.io/badge/Redis-7.x-DC382D?style=for-the-badge&logo=redis&logoColor=white" />
</p>

<p>
  <em>实时监控 · 智能告警 · 数据分析 · 多Worker架构 · 性能优化 · 一键部署</em>
</p>

</div>

---

## 📡 系统简介

**听风追影**是一款面向情报分析、舆情监控、社群管理的 Telegram 群组实时监控与预警平台。支持多账号同时监控数百个群组/频道，通过关键词匹配实时告警，并提供大屏可视化、数据分析、多渠道通知等能力。

> 💡 **设计理念**：部署即用、开箱即监控、数据驱动决策

---

## ✨ 核心功能

<table>
<tr>
<td width="50%">

### 🔍 实时监控
- 多账号并行监控数百个 Telegram 群组/频道
- 实时消息采集 + 历史消息回溯
- 自动采集发送者信息（ID、用户名、手机号）
- 智能排除自身账号消息
- SOCKS5h / HTTP 代理支持（DNS通过代理解析）

</td>
<td width="50%">

### 🚨 关键词告警
- 多级告警：低 / 中 / 高 / 严重
- 关键词分组管理 + 正则匹配
- 告警处理工作流（待处理→处理中→已解决/忽略/误报）
- 告警消息关键词高亮
- 手机号筛选（一键过滤有手机号的告警）
- 显示消息原始发送时间

</td>
</tr>
<tr>
<td width="50%">

### 📊 数据分析
- Dashboard 实时统计（消息量、活跃度、告警趋势）
- 大屏可视化展示（支持全屏）
- 发送者手机号格式化显示（+86 xxxxxxxxxxx）
- 中国手机号用户导出（Excel）
- 手机号筛选：一键找出有手机号的用户

</td>
<td width="50%">

### 🔔 多渠道通知
- 邮件 · 钉钉 · 企业微信 · Server酱
- Webhook · Telegram Bot
- 自定义通知模板
- 按关键词组/会话过滤通知

</td>
</tr>
<tr>
<td width="50%">

### ⚙️ 系统管理
- Web 端账号管理（添加/删除/授权）
- 代理配置 + 连通性测试（Google/Telegram 延迟）
- 数据库自动备份 + 手动备份 + 备份下载/恢复/删除
- 数据上传合并（INSERT IGNORE，不覆盖现有数据）
- **一键检查更新**（设置页 → 系统更新 → 检查更新 → 自动拉取安装）

</td>
<td width="50%">

### 🚀 部署与迁移
- **一键部署脚本**（适配 Ubuntu/Debian/CentOS）
- **多Worker架构**（支持水平扩展）
- **数据迁移**：一键导出/导入（数据库 + Session + 配置）
- 配置导入导出（JSON 格式）
- 关键词单独导入导出
- systemd 服务 + 开机自启
- 自动清理过期数据

</td>
</tr>
</table>

---

## 🛠️ 技术架构

### v2.0 新增：多Worker架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Nginx (反向代理 + 负载均衡)                │
│                      :3000 → :8000-8001                     │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼───────┐     ┌───────▼───────┐     ┌───────▼───────┐
│  API Worker   │     │ Monitor Worker│     │ Monitor Worker│
│  (端口 8000)  │     │   (账号 1-5)  │     │  (账号 6-10)  │
│  处理HTTP请求  │     │   端口 8010   │     │   端口 8011   │
└───────┬───────┘     └───────┬───────┘     └───────┬───────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │     MySQL 8.0     │
                    │   (共享数据库)     │
                    └───────────────────┘
```

### 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **前端** | React 19 + TypeScript | SPA 单页应用，响应式设计 |
| **UI** | TailwindCSS + Lucide Icons | 深色科技风，玻璃拟态效果 |
| **图表** | Recharts | Dashboard + 大屏数据可视化 |
| **虚拟滚动** | React Virtuoso | 大列表性能优化 |
| **后端** | FastAPI (Python 3.12+) | 异步高性能 API |
| **ORM** | SQLAlchemy 2.0 + aiomysql | 异步数据库操作 |
| **Telegram** | Telethon 1.44 | MTProto 客户端，实时消息采集 |
| **数据库** | MySQL 8.0 | 消息存储 + 索引优化 |
| **缓存** | Redis 7.x | Dashboard API 缓存，减少数据库压力 |
| **代理** | SOCKS5h Proxy | DNS通过代理解析，突破网络限制 |

---

## 🚀 快速部署

### 一键安装（推荐）

```bash
bash <(curl -sL https://raw.githubusercontent.com/chu0119/tg-monitor-v2/main/install.sh)
```

### 手动部署

```bash
# 1. 克隆项目
git clone https://github.com/chu0119/tg-monitor-v2.git
cd tg-monitor-v2

# 2. 后端
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填写数据库和 Telegram API 配置
python init_db.py

# 3. 前端
cd ../frontend
npm install
npm run build

# 4. 启动（单Worker模式）
cd backend
python -m app.main
```

### 多Worker部署

```bash
# 自动部署（推荐）
cd backend/workers
sudo bash deploy-auto.sh 2 3  # 2个API Worker，3个Monitor Worker

# 手动部署
# 编辑 workers/config.json 配置Worker数量
# 运行 deploy.sh
```

### 环境变量 (.env)

```env
# MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=tgmonitor
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=tg_monitor_v2

# Telegram API (从 https://my.telegram.org 获取)
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash

# 代理 (推荐使用 socks5h 协议，DNS通过代理解析)
SOCKS5_PROXY=socks5h://192.168.1.120:7897
```

> ⚠️ **重要**：代理地址请使用 `socks5h://` 而非 `socks5://`，前者通过代理解析DNS，后者本地解析DNS可能导致连接失败。

---

## 📱 使用流程

```
配置向导 → 添加账号 → 扫码授权 → 添加监控群组 → 配置关键词 → 实时监控 → 处理告警
    ↑                                                              ↓
    └──────────── 设置页（代理/通知/备份/更新/迁移）←──────────────────┘
```

### 首次使用
1. 访问 `http://IP:3000` 进入配置向导
2. 填写 Telegram API 凭证 + 代理配置
3. 添加监控账号（扫码或输入手机号）
4. 添加群组/频道（输入链接或用户名）
5. 创建关键词组 → 添加关键词 → 设置告警级别
6. 开始监控！

### 日常使用
- **Dashboard** — 查看整体统计、消息趋势、系统状态
- **实时监控** — 查看消息流、点击查看详情（含手机号）
- **告警中心** — 处理告警、筛选有手机号的告警
- **大屏展示** — 全屏可视化，适合投屏
- **设置** — 数据库配置、备份恢复、系统更新、数据迁移

---

## 🏥 健康检查

系统内置健康检查API，用于监控系统状态：

```bash
# 基础探活
curl http://localhost:8000/api/v1/health/

# 详细状态（数据库、Redis、系统资源、Telegram监控）
curl http://localhost:8000/api/v1/health/detailed

# 性能指标
curl http://localhost:8000/api/v1/health/metrics
```

### 响应示例

```json
{
  "status": "healthy",
  "uptime_seconds": 3600,
  "checks": {
    "database": {"status": "healthy", "latency_ms": 1.55},
    "redis": {"status": "healthy", "latency_ms": 0.51, "keys": 2},
    "system": {"cpu_percent": 4.5, "memory": {"percent": 33.5}},
    "telegram": {"active_monitors": 291, "connected_clients": 1}
  }
}
```

---

## 📊 性能优化

### v2.0 性能提升

| API | v1.0 | v2.0 | 提升 |
|-----|------|------|------|
| **Dashboard统计** | 3.4秒 | 0.17ms | **20,000倍** |
| **发送者排行** | 11秒 | 0.2ms | **55,000倍** |
| **会话活跃度** | 9秒 | 20ms | **450倍** |
| **串行加载** | 15秒 | 0.24秒 | **62倍** |

### 优化技术

1. **预计算字段**：添加 `sender_count` 字段，避免实时计算
2. **子查询优化**：使用子查询替代大表JOIN
3. **近似计数**：使用 `information_schema` 获取大表行数
4. **Redis缓存**：所有API结果缓存60秒
5. **索引优化**：确保关键查询使用索引

### 前端优化

- **React Virtuoso**：大列表虚拟滚动
- **搜索防抖**：400ms防抖，减少API请求
- **代码分割**：按路由懒加载

---

## 🔧 生产环境部署

### Nginx 反向代理配置

```nginx
# /etc/nginx/sites-available/tgmonitor.conf
upstream api_backend {
    least_conn;
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    keepalive 32;
}

server {
    listen 3000;
    server_name _;

    # 前端静态文件
    location / {
        root /home/test/tg-monitor/frontend/dist;
        try_files $uri $uri/ /index.html;
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
            expires 7d;
            add_header Cache-Control "public, no-transform";
        }
    }

    # API 反向代理
    location /api/ {
        proxy_pass http://api_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }

    # WebSocket 代理
    location ~ ^/ws/? {
        proxy_pass http://api_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

### Systemd 服务配置

```ini
# /etc/systemd/system/tgmonitor-api-0.service
[Unit]
Description=TG Monitor API Worker 0
After=network.target mysql.service redis.service

[Service]
Type=simple
User=root
WorkingDirectory=/home/test/tg-monitor/backend
ExecStart=/usr/bin/python3 -m app.workers.api_worker
Restart=always
RestartSec=5
MemoryMax=2G
Environment=WORKER_ID=0
Environment=WORKER_TYPE=api

[Install]
WantedBy=multi-user.target
```

> ⚠️ **重要**：Monitor Worker 必须使用 `--workers 1`（单worker模式），因为Telegram Session文件（SQLite）不支持多进程并发访问。

---

## 🔄 更新日志

### v2.0.0 (2026-07-07)

#### 🚀 新增功能
- **多Worker架构**：支持API Worker和Monitor Worker分离部署
- **自动化部署脚本**：一键部署多Worker架构
- **健康检查API**：`/health`、`/health/detailed`、`/health/metrics`
- **输入验证模块**：统一的Pydantic验证器
- **统一错误处理**：标准化的错误响应格式

#### ⚡ 性能优化
- **Dashboard统计API**：从3.4秒优化到0.17ms（20,000倍提升）
- **发送者排行API**：从11秒优化到0.2ms（55,000倍提升）
- **会话活跃度API**：从9秒优化到20ms（450倍提升）
- **Redis缓存**：添加缓存穿透防护、空值缓存
- **预计算字段**：添加 `sender_count` 字段避免实时计算
- **虚拟滚动**：使用 React Virtuoso 优化大列表

#### 🐛 Bug修复
- **修复 `database is locked` 错误**：使用文件锁保护SQLite session
- **修复分页重置问题**：筛选条件改变时自动重置到第1页
- **修复代理配置问题**：socks5 → socks5h（DNS通过代理解析）
- **修复Redis连接失败返回False**：改为返回None避免TypeError
- **修复worker_id=0被忽略**：使用 `if worker_id is not None`
- **修复端口冲突Bug**：使用 `ports[wid % len(ports)]`

#### 🔒 安全改进
- **添加APIKeyAuth中间件**：支持API密钥认证
- **统一异常处理**：避免暴露内部错误信息
- **输入验证**：防止SQL注入和XSS攻击

#### 📝 代码优化
- **代码审查**：修复15个代码质量问题
- **错误处理**：统一的AppException异常体系
- **日志优化**：添加Worker ID到日志格式

---

### v1.1.0 (2026-06-25)

#### ⚡ 性能优化
- **Redis缓存**：Dashboard API添加Redis缓存
- **数据库索引**：添加组合索引优化查询
- **连接池优化**：调整MySQL连接池参数

#### 🐛 Bug修复
- **修复消息不更新**：Telegram客户端重连逻辑优化
- **修复Session文件损坏**：添加asyncio.Lock保护

#### 📝 功能改进
- **告警中心**：支持手机号筛选
- **大屏展示**：优化可视化效果
- **数据导出**：支持CSV导出

---

### v1.0.0 (2026-04-15)

#### 🎉 首次发布
- **实时监控**：多账号并行监控Telegram群组
- **关键词告警**：多级告警 + 正则匹配
- **数据分析**：Dashboard + 大屏可视化
- **多渠道通知**：邮件/钉钉/企业微信/Webhook
- **系统管理**：账号管理/代理配置/备份恢复
- **一键部署**：自动化部署脚本

---

## 📂 项目结构

```
tg-monitor-v2/
├── backend/
│   ├── app/
│   │   ├── api/                  # API 路由层
│   │   │   ├── accounts.py       # 账号管理
│   │   │   ├── alerts.py         # 告警管理
│   │   │   ├── dashboard.py      # 仪表盘（性能优化）
│   │   │   ├── health.py         # 健康检查API
│   │   │   ├── keywords.py       # 关键词管理
│   │   │   └── ...
│   │   ├── core/
│   │   │   ├── config.py         # 配置管理
│   │   │   ├── database.py       # 数据库连接池
│   │   │   ├── error_handler.py  # 统一错误处理
│   │   │   ├── validators.py     # 输入验证
│   │   │   └── worker_config.py  # Worker配置管理
│   │   ├── models/               # 数据模型
│   │   ├── services/             # 业务逻辑层
│   │   ├── telegram/             # Telegram客户端
│   │   ├── utils/
│   │   │   └── redis_cache.py    # Redis缓存（防穿透）
│   │   └── workers/              # 多Worker架构
│   │       ├── api_worker.py     # API Worker入口
│   │       └── monitor_worker.py # Monitor Worker入口
│   ├── workers/
│   │   ├── config.json           # Worker配置
│   │   ├── deploy.sh             # 部署脚本
│   │   ├── deploy-auto.sh        # 自动化部署脚本
│   │   ├── nginx.conf            # Nginx配置
│   │   └── README.md             # 架构文档
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── pages/                # 页面组件
│   │   │   ├── DashboardPage.tsx  # 仪表盘（性能优化）
│   │   │   ├── AlertsPage.tsx     # 告警中心（虚拟滚动）
│   │   │   └── ...
│   │   ├── hooks/
│   │   │   └── useDebounce.ts    # 搜索防抖
│   │   └── ...
│   └── package.json
├── README.md
└── CHANGELOG.md
```

---

## 🛡️ 已知问题与解决方案

### 1. `database is locked` 错误

**原因**：Telegram Session文件（SQLite）不支持多进程并发访问

**解决方案**：
- 使用 `--workers 1`（单worker模式）
- 或使用多Worker架构，每个Worker独立Session目录

### 2. 消息不更新 / 连接断开

**排查步骤**：
```bash
# 1. 检查日志
tail -50 /home/test/tg-monitor/logs/app.log | grep ERROR

# 2. 检查代理连通性
curl -x socks5h://192.168.1.120:7897 -s https://api.telegram.org/

# 3. 重启服务
systemctl restart tgmonitor-backend
```

### 3. Dashboard加载慢

**解决方案**：
```bash
# 清除Redis缓存
redis-cli FLUSHALL

# 重启服务
systemctl restart tgmonitor-api-0
```

---

## 📋 系统要求

| 组件 | 最低版本 | 推荐 |
|------|---------|------|
| Python | 3.12+ | 3.12 |
| Node.js | 18+ | 20 LTS |
| MySQL | 8.0+ | 8.4 |
| Redis | 6.0+ | 7.x |
| RAM | 4GB | 8GB+ |
| Disk | 20GB | 100GB+ |

---

## 🔒 安全建议

- ⚡ 修改默认数据库密码
- 🔐 不要将 `.env` 文件提交到版本库
- 💾 定期备份数据库（系统已内置自动备份）
- 🌐 使用 HTTPS 反向代理（生产环境推荐 Nginx）
- 🚫 限制前端端口的外网访问
- 🔄 定期检查系统更新
- 🔒 确保 `sessions/` 目录权限为 `700`

---

## 📄 许可证

[MIT License](LICENSE)

---

## 🙏 致谢

- [Telethon](https://github.com/LonamiWebs/Telethon) — Telegram MTProto 客户端
- [FastAPI](https://fastapi.tiangolo.com/) — 高性能 Python Web 框架
- [React](https://react.dev/) — 前端框架
- [Recharts](https://recharts.org/) — 数据可视化
- [TailwindCSS](https://tailwindcss.com/) — 原子化 CSS
- [React Virtuoso](https://virtuoso.dev/) — 虚拟滚动

---

<div align="center">

**⭐ 如果这个项目对你有帮助，请给一个 Star ⭐**

<p>
  <em>Made with 🔥 by 听风追影 Team</em>
</p>

</div>
