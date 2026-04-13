<div align="center">

# 🔥 听风追影
### —— 群组数据预警分析系统

<p>
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black" />
  <img src="https://img.shields.io/badge/TypeScript-5-3178C6?style=for-the-badge&logo=typescript&logoColor=white" />
  <img src="https://img.shields.io/badge/MySQL-8.0-4479A1?style=for-the-badge&logo=mysql&logoColor=white" />
</p>

<p>
  <em>实时监控 · 智能告警 · 数据分析 · 一键部署</em>
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
- SOCKS5 / HTTP 代理支持

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
│   React 18 · TypeScript · TailwindCSS · Recharts │
│              Vite DevServer :5173                │
└────────────────────┬────────────────────────────┘
                     │ API Proxy
┌────────────────────▼────────────────────────────┐
│                   Backend                        │
│   FastAPI · SQLAlchemy · Telethon · aiomysql     │
│                Uvicorn :8000                      │
├─────────────────────────────────────────────────┤
│  ┌─────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ Monitor │ │  Alert   │ │   Notification   │ │
│  │ Engine  │ │  Engine  │ │     Service      │ │
│  └────┬────┘ └──────────┘ └──────────────────┘ │
│       │         MySQL 8.0                        │
└───────┼─────────────────────────────────────────┘
        │
   ┌────▼────┐
   │  Proxy  │
   │ SOCKS5  │
   └─────────┘
```

| 层级 | 技术 | 说明 |
|------|------|------|
| **前端** | React 18 + TypeScript | SPA 单页应用，响应式设计 |
| **UI** | TailwindCSS + Lucide Icons | 深色科技风，玻璃拟态效果 |
| **图表** | Recharts | Dashboard + 大屏数据可视化 |
| **后端** | FastAPI (Python 3.11+) | 异步高性能 API |
| **ORM** | SQLAlchemy 2.0 + aiomysql | 异步数据库操作 |
| **Telegram** | Telethon | MTProto 客户端，实时消息采集 |
| **数据库** | MySQL 8.0 | 消息存储 + 索引优化 |
| **部署** | systemd + Docker Compose | 双模式部署 |
| **代理** | SOCKS5 / HTTP Proxy | 突破网络限制 |

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

# 代理 (可选)
SOCKS5_PROXY=socks5://127.0.0.1:7897
```

---

## 📱 使用流程

```
配置向导 → 添加账号 → 扫码授权 → 添加监控群组 → 配置关键词 → 实时监控 → 处理告警
    ↑                                                              ↓
    └──────────── 设置页（代理/通知/备份/更新/迁移）←──────────────────┘
```

### 首次使用
1. 访问 `http://IP:5173` 进入配置向导
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
sudo systemctl restart tg-monitor-v2-backend tg-monitor-v2-frontend
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
│   │   │   ├── dashboard.py      # 仪表盘统计
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
│   │   │   └── database.py       # 数据库连接池
│   │   ├── models/               # 数据模型
│   │   │   ├── account.py        # Telegram 账号
│   │   │   ├── alert.py          # 告警记录
│   │   │   ├── conversation.py   # 监控会话
│   │   │   ├── keyword.py        # 关键词 + 关键词组
│   │   │   ├── message.py        # 消息记录
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
│   │   │   └── notification_service.py  # 多渠道通知
│   │   ├── telegram/             # Telegram 客户端
│   │   │   ├── client.py         # 多账号管理
│   │   │   └── monitor.py        # 消息采集引擎
│   │   └── utils/                # 工具函数
│   ├── sessions/                 # Telegram Session 文件
│   ├── .env                      # 环境配置
│   ├── init_db.py                # 数据库初始化（含自动迁移）
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/                # 页面组件
│   │   │   ├── DashboardPage.tsx   # 仪表盘
│   │   │   ├── MonitoringPage.tsx  # 实时监控
│   │   │   ├── AlertsPage.tsx      # 告警中心
│   │   │   ├── BigScreenPage.tsx   # 大屏展示
│   │   │   ├── SettingsPage.tsx    # 系统设置（备份/迁移/更新）
│   │   │   ├── KeywordsPage.tsx    # 关键词管理（导入导出）
│   │   │   ├── ProxyPage.tsx       # 代理管理
│   │   │   └── ...
│   │   ├── components/           # UI 组件
│   │   ├── hooks/                # React Hooks
│   │   ├── lib/
│   │   │   ├── api.ts            # API 客户端
│   │   │   └── utils.ts          # 工具（手机号格式化等）
│   │   └── routes/               # TanStack Router 路由
│   └── package.json
├── docker/                       # Docker 配置
│   ├── docker-compose.yml
│   └── nginx.conf
├── install.sh                    # 一键部署脚本
├── start.sh                      # 快速启动脚本
└── README.md
```

---

## 🔒 安全建议

- ⚡ 修改默认数据库密码
- 🔐 不要将 `.env` 文件提交到版本库
- 💾 定期备份数据库（系统已内置自动备份）
- 🌐 使用 HTTPS 反向代理（生产环境推荐 Nginx）
- 🚫 限制前端端口的外网访问
- 🔄 定期检查系统更新

---

## 📋 系统要求

| 组件 | 最低版本 | 推荐 |
|------|---------|------|
| Python | 3.11+ | 3.12 |
| Node.js | 18+ | 20 LTS |
| MySQL | 8.0+ | 8.4 |
| RAM | 2GB | 4GB+ |
| Disk | 10GB | 50GB+（取决于监控量） |

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

---

<div align="center">

**⭐ 如果这个项目对你有帮助，请给一个 Star ⭐**

<p>
  <em>Made with 🔥 by 听风追影 Team</em>
</p>

</div>
