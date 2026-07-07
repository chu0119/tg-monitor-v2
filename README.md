<div align="center">

# 🔥 听风追影
### —— 群组数据预警分析系统 v1.1.0

<p>
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black" />
  <img src="https://img.shields.io/badge/TypeScript-5.7-3178C6?style=for-the-badge&logo=typescript&logoColor=white" />
  <img src="https://img.shields.io/badge/MySQL-8.0-4479A1?style=for-the-badge&logo=mysql&logoColor=white" />
  <img src="https://img.shields.io/badge/Redis-7.x-DC382D?style=for-the-badge&logo=redis&logoColor=white" />
</p>

<p>
  <em>实时监控 · 智能告警 · 数据分析 · 性能优化 · 一键部署</em>
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

```
┌─────────────────────────────────────────────────┐
│                   Frontend                       │
│  React 19 · TypeScript · TailwindCSS · Recharts │
│  React Virtuoso(虚拟滚动) · TanStack Router     │
│              Nginx :3000                         │
└────────────────────┬────────────────────────────┘
                     │ API Proxy
┌────────────────────▼────────────────────────────┐
│                   Backend                        │
│   FastAPI · SQLAlchemy · Telethon · aiomysql     │
│          Gunicorn + Uvicorn (1 worker) :8000      │
├─────────────────────────────────────────────────┤
│  ┌─────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ Monitor │ │  Alert   │ │   Notification   │ │
│  │ Engine  │ │  Engine  │ │     Service      │ │
│  └────┬────┘ └──────────┘ └──────────────────┘ │
│       │     MySQL 8.0 + Redis 7.x (缓存)        │
└───────┼─────────────────────────────────────────┘
        │
   ┌────▼────┐
   │  Proxy  │
   │ SOCKS5h │
   └─────────┘
```

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

脚本自动完成：系统检测 → 依赖安装 → 项目克隆 → 数据库初始化 → 配置向导 → 服务启动

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

# 4. 启动
# 后端 (端口 8000)
cd backend && source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 前端 (端口 5173)
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
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

## 🔧 生产环境部署

### Nginx 反向代理配置

```nginx
# /etc/nginx/sites-available/tgmonitor.conf
server {
    listen 3000;
    server_name _;

    # 前端静态文件
    location / {
        root /home/test/tg-monitor/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # API 反向代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    # WebSocket 代理
    location ~ ^/ws/? {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

### Systemd 服务配置

```ini
# /etc/systemd/system/tgmonitor-backend.service
[Unit]
Description=TG Monitor Backend
After=network.target mysql.service redis.service

[Service]
Type=simple
User=root
WorkingDirectory=/home/test/tg-monitor/backend
ExecStart=/usr/bin/python3 -m gunicorn app.main:app \
    --bind 0.0.0.0:8000 \
    --workers 1 \
    --worker-class uvicorn.workers.UvicornWorker \
    --timeout 120 \
    --keep-alive 30
Restart=always
RestartSec=5
MemoryMax=8G

[Install]
WantedBy=multi-user.target
```

> ⚠️ **重要**：`--workers 1` 是必须的！因为Telegram Session文件（SQLite）不支持多进程并发访问。多个worker会导致 `database is locked` 错误。

---

## 🔄 检查更新

系统内置一键更新：

1. 进入 **设置** → **系统更新**
2. 点击 **检查更新**
3. 如有新版本，查看更新日志后点击 **立即更新**
4. 系统自动：备份数据库 → git pull → 安装依赖 → 重启服务

手动更新：
```bash
cd /path/to/tg-monitor-v2
git pull origin main
cd backend && source venv/bin/activate && pip install -r requirements.txt
cd ../frontend && npm install
sudo systemctl restart tgmonitor-backend
```

---

## 📦 数据迁移

在新服务器上完整恢复所有数据：

### 方式一：设置页迁移（推荐）
1. 旧服务器：**设置** → **数据迁移** → **导出数据** → 下载 .tar.gz
2. 新服务器：部署完成后 → **设置** → **数据迁移** → **导入数据** → 上传 .tar.gz
3. 自动合并：数据库（INSERT IGNORE）+ Session文件 + 配置文件

### 方式二：手动迁移
```bash
# 旧服务器导出
mysqldump -u tgmonitor -p tg_monitor_v2 > backup.sql
tar czf migrate.tar.gz backup.sql backend/sessions/ backend/.env

# 新服务器导入
tar xzf migrate.tar.gz
mysql -u tgmonitor -p tg_monitor_v2 < backup.sql
cp sessions/* backend/sessions/
```

---

## 📂 项目结构

```
tg-monitor-v2/
├── backend/
│   ├── app/
│   │   ├── api/                  # API 路由层
│   │   │   ├── accounts.py       # 账号管理
│   │   │   ├── alerts.py         # 告警（支持手机号筛选、消息原始时间）
│   │   │   ├── backups.py        # 备份（创建/恢复/下载/删除/上传合并）
│   │   │   ├── conversations.py  # 会话管理
│   │   │   ├── dashboard.py      # 仪表盘统计（Redis缓存优化）
│   │   │   ├── health.py         # 健康检查API
│   │   │   ├── keywords.py       # 关键词（支持导入导出）
│   │   │   ├── messages.py       # 消息查询
│   │   │   ├── migration.py      # 数据迁移（导出/导入）
│   │   │   ├── monitoring.py     # 实时监控
│   │   │   ├── notifications.py  # 通知配置
│   │   │   ├── proxy.py          # 代理管理（含连通性测试）
│   │   │   ├── senders.py        # 发送者查询（手机号筛选）
│   │   │   ├── settings.py       # 系统设置
│   │   │   ├── system.py         # 系统信息（数据库配置、版本）
│   │   │   └── update.py         # 一键更新
│   │   ├── core/                 # 核心配置
│   │   │   ├── config.py         # 环境变量 + 版本号
│   │   │   ├── database.py       # 数据库连接池（优化配置）
│   │   │   └── error_handler.py  # 统一错误处理
│   │   ├── models/               # 数据模型
│   │   │   ├── account.py        # Telegram 账号
│   │   │   ├── alert.py          # 告警记录（含组合索引）
│   │   │   ├── conversation.py   # 监控会话
│   │   │   ├── keyword.py        # 关键词 + 关键词组
│   │   │   ├── message.py        # 消息记录（含组合索引）
│   │   │   ├── sender.py         # 发送者（含手机号）
│   │   │   ├── settings.py       # 系统设置
│   │   │   └── user.py           # 用户认证（RBAC）
│   │   ├── schemas/              # 请求/响应模型
│   │   ├── services/             # 业务逻辑层
│   │   │   ├── alert_service.py         # 告警匹配
│   │   │   ├── auto_backup_service.py   # 自动备份
│   │   │   ├── backup_service.py        # 备份核心
│   │   │   ├── data_cleanup_service.py  # 数据清理
│   │   │   ├── keyword_matcher.py       # 关键词匹配引擎
│   │   │   ├── notification_service.py  # 多渠道通知
│   │   │   └── runtime_proxy_service.py # 运行时代理配置
│   │   ├── telegram/             # Telegram 客户端
│   │   │   ├── client.py         # 多账号管理（文件锁保护）
│   │   │   └── monitor.py        # 消息采集引擎
│   │   └── utils/                # 工具函数
│   │       ├── redis_cache.py    # Redis缓存（防穿透/防雪崩）
│   │       └── validators.py     # 输入验证
│   ├── sessions/                 # Telegram Session 文件
│   ├── .env                      # 环境配置
│   ├── init_db.py                # 数据库初始化（含自动迁移）
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/                # 页面组件
│   │   │   ├── DashboardPage.tsx   # 仪表盘
│   │   │   ├── MonitoringPage.tsx  # 实时监控
│   │   │   ├── AlertsPage.tsx      # 告警中心（虚拟滚动）
│   │   │   ├── BigScreenPage.tsx   # 大屏展示
│   │   │   ├── SettingsPage.tsx    # 系统设置（备份/迁移/更新）
│   │   │   ├── KeywordsPage.tsx    # 关键词管理（导入导出）
│   │   │   ├── ProxyPage.tsx       # 代理管理
│   │   │   └── ...
│   │   ├── components/           # UI 组件
│   │   ├── hooks/                # React Hooks
│   │   │   ├── useDebounce.ts    # 搜索防抖
│   │   │   ├── usePolling.ts     # 轮询
│   │   │   └── useWebSocket.ts   # WebSocket
│   │   ├── lib/
│   │   │   ├── api.ts            # API 客户端
│   │   │   └── utils.ts          # 工具（手机号格式化等）
│   │   └── routes/               # TanStack Router 路由
│   └── package.json
├── tg-monitor-backend.service    # 后端 systemd 服务
├── tg-monitor-frontend.service   # 前端 systemd 服务
├── logrotate.conf                # 日志轮转配置
├── tg_watchdog.py                # 看门狗脚本
└── README.md
```

---

## 🛡️ 已知问题与解决方案

### 1. `database is locked` 错误

**原因**：Telegram Session文件（SQLite）不支持多进程并发访问

**解决方案**：
- 后端使用 `--workers 1`（单worker模式）
- 如需更高性能，可考虑多账号分散到不同进程

### 2. 消息不更新 / 连接断开

**排查步骤**：
```bash
# 1. 检查日志
tail -50 /home/test/tg-monitor/logs/app.log | grep ERROR

# 2. 检查代理连通性
curl -x socks5h://192.168.1.120:7897 -s https://api.telegram.org/

# 3. 检查服务状态
systemctl status tgmonitor-backend

# 4. 重启服务
systemctl restart tgmonitor-backend
```

### 3. Session文件损坏

**症状**：`file is not a database` 或 `database is locked`

**解决方案**：
```bash
# 停止服务
systemctl stop tgmonitor-backend

# 删除损坏的session文件
rm -f /home/test/tg-monitor/backend/sessions/*.session*

# 重启服务（需要重新登录）
systemctl start tgmonitor-backend

# 在前端重新登录Telegram账号
```

### 4. 代理连接失败

**症状**：`FloodWaitError` 或连接超时

**解决方案**：
- 确保使用 `socks5h://` 协议（DNS通过代理解析）
- 检查代理服务器是否正常运行
- 在前端代理管理页面测试连通性

---

## 🔒 安全建议

- ⚡ 修改默认数据库密码
- 🔐 不要将 `.env` 文件提交到版本库
- 💾 定期备份数据库（系统已内置自动备份）
- 🌐 使用 HTTPS 反向代理（生产环境推荐 Nginx）
- 🚫 限制前端端口的外网访问
- 🔄 定期检查系统更新
- 🔒 确保 `sessions/` 目录权限为 `700`（仅owner可访问）

---

## 📋 系统要求

| 组件 | 最低版本 | 推荐 |
|------|---------|------|
| Python | 3.12+ | 3.12 |
| Node.js | 18+ | 20 LTS |
| MySQL | 8.0+ | 8.4 |
| Redis | 6.0+ | 7.x |
| RAM | 4GB | 8GB+ |
| Disk | 20GB | 100GB+（取决于监控量） |

---

## 📊 性能优化

### Redis 缓存
- Dashboard统计：30秒缓存
- 发送者排名：60秒缓存
- 会话活跃度：60秒缓存
- 缓存穿透防护：空值缓存30秒
- 缓存雪崩防护：TTL随机偏移

### 数据库索引
- alerts表：15+索引，覆盖主要查询场景
- messages表：组合索引优化时间范围查询
- conversations表：状态+实时监控组合索引

### 前端优化
- React Virtuoso：大列表虚拟滚动
- 搜索防抖：400ms防抖，减少API请求
- 代码分割：按路由懒加载

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
