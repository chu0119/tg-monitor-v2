# 听风追影 – 群组数据预警分析系统 V2

> Telegram 群组实时监控、关键词告警、数据分析平台

## 🚀 一键部署

```bash
bash <(curl -sL https://raw.githubusercontent.com/chu0119/tg-monitor-v2/main/install.sh)
```

> 需要预先安装：Python 3、Node.js、npm、MySQL Server

## ✨ 功能特性

### 🔍 实时监控
- 多账号同时监控数百个 Telegram 群组/频道
- 实时消息采集，支持历史消息回溯
- 自动采集发送者信息（ID、用户名、昵称、手机号）

### 🚨 关键词告警
- 多级告警（低/中/高/严重）
- 关键词分组管理，支持正则匹配
- 告警处理工作流（待处理→处理中→已解决/忽略/误报）
- 告警消息高亮显示

### 📊 数据分析
- Dashboard 实时统计（消息量、活跃度、告警趋势）
- 大屏可视化展示
- 情感分析、词云分析
- 发送者手机号筛选与导出

### 🔔 多渠道通知
- 邮件、钉钉、企业微信、Server酱、Webhook、Telegram Bot
- 自定义通知模板
- 按关键词组/会话过滤通知

### ⚙️ 系统管理
- Web 端账号管理（添加/删除/授权）
- 代理配置（SOCKS5/HTTP）
- 数据库自动备份与恢复
- **一键检查更新**（设置页 → 系统更新 → 检查更新）
- 自动清理过期数据

## 🛠️ 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy / Telethon |
| 前端 | React 18 / TypeScript / TailwindCSS / Recharts |
| 数据库 | MySQL 8.0 |
| 代理 | SOCKS5 / HTTP Proxy |
| 部署 | systemd / Docker Compose |

## 📦 快速部署

### 一键安装（推荐）

```bash
git clone https://github.com/chu0119/tg-monitor-v2.git
cd tg-monitor-v2
chmod +x start.sh
./start.sh
```

脚本会自动：安装依赖 → 初始化数据库 → 配置 systemd 服务 → 启动服务

### 手动部署

```bash
# 1. 克隆项目
git clone https://github.com/chu0119/tg-monitor-v2.git
cd tg-monitor-v2

# 2. 后端配置
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填写数据库和 Telegram API 配置
python init_db.py

# 3. 前端配置
cd ../frontend
npm install

# 4. 启动服务
# 后端（端口 8000）
cd backend && source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 前端（端口 5173）
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

### 环境变量（.env）

```env
# MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=tgmonitor
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=tg_monitor_v2

# Telegram API（从 https://my.telegram.org 获取）
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash

# 代理（可选）
SOCKS5_PROXY=socks5://127.0.0.1:7897
```

## 🔧 配置向导

首次访问 `http://IP:5173` 会进入配置向导：
1. 配置数据库连接
2. 填写 Telegram API 凭证
3. 配置代理（如需要）
4. 添加监控账号（扫码或输入手机号）

## 📱 使用流程

1. **添加账号** — 设置页添加 Telegram 账号，完成授权
2. **添加会话** — 输入群组/频道链接或用户名，开始监控
3. **配置关键词** — 创建关键词组，添加关键词，设置告警级别
4. **查看告警** — 监控页实时查看触发记录，告警页处理告警
5. **数据分析** — Dashboard 查看整体统计，大屏展示

## 🔄 检查更新

系统内置一键更新功能：

1. 进入 **设置** → **系统更新**
2. 点击 **检查更新**
3. 如有新版本，查看更新日志后点击 **立即更新**
4. 系统自动完成：备份数据库 → 拉取代码 → 安装依赖 → 重启服务

也可手动更新：
```bash
cd /path/to/tg-monitor-v2
git pull origin main
cd backend && source venv/bin/activate && pip install -r requirements.txt
cd ../frontend && npm install
sudo systemctl restart tg-monitor-v2-backend tg-monitor-v2-frontend
```

## 📂 项目结构

```
tg-monitor-v2/
├── backend/
│   ├── app/
│   │   ├── api/          # API路由
│   │   ├── core/         # 核心配置
│   │   ├── models/       # 数据模型
│   │   ├── schemas/      # 请求/响应模型
│   │   ├── services/     # 业务逻辑
│   │   ├── telegram/     # Telegram客户端
│   │   └── utils/        # 工具函数
│   ├── sessions/         # Telegram session文件
│   ├── .env              # 环境配置
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/        # 页面组件
│   │   ├── components/   # 通用组件
│   │   ├── hooks/        # 自定义hooks
│   │   ├── lib/          # API/工具库
│   │   └── routes/       # 路由配置
│   └── package.json
├── docker/               # Docker配置
├── start.sh              # 一键启动脚本
└── README.md
```

## 🔒 安全建议

- 修改默认数据库密码
- 不要将 `.env` 文件提交到版本库
- 定期备份数据库（系统已内置自动备份）
- 使用 HTTPS 反向代理（生产环境推荐 Nginx）
- 限制前端端口的外网访问

## 📋 从 V1 迁移数据

如果你之前使用 V1 版本，可以完整迁移数据：

```bash
# 1. 导出V1数据库
mysqldump -u tgmonitor -p tg_monitor > v1_backup.sql

# 2. 部署V2后初始化数据库
cd backend && source venv/bin/activate && python init_db.py

# 3. 导入V1数据
mysql -u tgmonitor -p tg_monitor_v2 < v1_backup.sql

# 4. 重启V2服务
sudo systemctl restart tg-monitor-v2-backend
```

V2 会自动创建新增的用户认证表（users/roles/audit_logs），与 V1 数据完全兼容。

## 📄 许可证

MIT License

## 🙏 致谢

- [Telethon](https://github.com/LonamiWebs/Telethon) — Telegram MTProto 客户端
- [FastAPI](https://fastapi.tiangolo.com/) — 高性能 Python Web 框架
- [React](https://react.dev/) — 前端框架
