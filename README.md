# 听风追影 - Telegram 群组数据预警分析系统

`tg-monitor-v2` 是一套面向 Telegram 群组、频道和公开会话的实时监控、关键词告警、数据分析和可视化大屏系统。当前仓库已同步生产环境稳定版本，代码中不包含数据库、日志、Telegram session、导出包、备份包和任何真实密钥。

## 当前能力

- Telegram 多账号实时监听，支持新消息与编辑消息处理。
- 会话管理、历史消息拉取、发送者画像和消息检索。
- 关键词组、关键词规则、告警等级、告警处理状态和通知降噪。
- 告警链路健康检查、诊断接口、通知队列和系统资源监控。
- 仪表盘：消息趋势、告警分布、关键词热度、词云、高风险对象、会话活跃度、最新告警流。
- 监控大屏：面向展示屏的态势指标、告警结构、关键词热度、重点对象和实时告警流。
- 数据保留策略：按消息/告警记录数量上限清理，默认不超过 900GB 数据库容量预算。
- 备份、导出、导入、系统设置持久化和一键部署脚本。

## 技术栈

| 模块 | 技术 |
| --- | --- |
| 前端 | React 19, TypeScript, Vite, Tailwind CSS, Recharts |
| 后端 | FastAPI, SQLAlchemy 2.x, Telethon, Pydantic |
| 数据库 | MySQL 8.x |
| 部署 | systemd, shell scripts, optional Nginx/reverse proxy |

## 仓库结构

```text
.
├── backend/                  # FastAPI 后端、Telegram 监听和业务服务
├── frontend/                 # React 前端
├── install.sh                # 一键安装脚本
├── install-services.sh       # systemd 服务安装
├── monitorctl.sh             # 运维控制脚本
├── start.sh                  # 启动与环境初始化脚本
├── tg-monitor-*.service      # systemd 服务模板
├── .env.example              # 根环境变量模板
├── DEPLOYMENT.md             # 部署与迁移说明
├── CONTRIBUTING.md           # 协作和提交规范
└── SECURITY.md               # 安全说明
```

## 快速部署

推荐在 Ubuntu 22.04/24.04 或 Debian 12 上部署。

```bash
git clone https://github.com/chu0119/tg-monitor-v2.git
cd tg-monitor-v2
cp .env.example .env
vim .env
bash install.sh
```

安装完成后通常访问：

- 前端：`http://服务器IP:3000`
- 后端 API：`http://服务器IP:8000/api/v1`
- 健康检查：`http://服务器IP:8000/health`

更详细的安装、升级、迁移和回退流程见 [DEPLOYMENT.md](./DEPLOYMENT.md)。

## 手动开发

后端：

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python init_db.py
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

前端：

```bash
cd frontend
npm ci
npm run dev -- --host 0.0.0.0 --port 5173
```

生产构建：

```bash
cd frontend
npm ci
npm run build
```

## 必填配置

复制 `.env.example` 为 `.env` 后至少填写：

```env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=tgmonitor
MYSQL_PASSWORD=change_me
MYSQL_DATABASE=tg_monitor

TELEGRAM_API_ID=123456
TELEGRAM_API_HASH=change_me

JWT_SECRET_KEY=change_me_to_a_long_random_value
```

Telegram API 凭证从 <https://my.telegram.org/apps> 获取。

## 数据与密钥

以下内容不应提交到仓库：

- `.env`、真实 API ID/API Hash、JWT 密钥、SMTP 密码、Webhook Token。
- `backend/sessions/`、`*.session`、Telegram 登录态。
- `logs/`、`exports/`、`backups/`、数据库文件、上传文件。
- `frontend/dist/`、`node_modules/`、Python `venv/`。

仓库已经通过 `.gitignore` 排除这些路径。提交前建议运行：

```bash
git status --short
git diff --cached --name-only
```

## 常用运维命令

```bash
# 查看状态
./monitorctl.sh status

# 启动/停止/重启
./monitorctl.sh start
./monitorctl.sh stop
./monitorctl.sh restart

# 查看日志
./monitorctl.sh logs

# 健康检查
./health-check.sh
```

## 近期重点更新

- 修复实时消息能入库但告警统计/排行不准确的问题。
- 大屏重点对象排行改为按真实告警数聚合。
- 仪表盘增加词云、关键词热度、系统健康、对象排行和告警流。
- 大屏改为 3 秒刷新，数字随数据变化滚动，支持全屏比例缩放。
- 数据清理策略从按天改为按记录数量和数据库容量预算控制。
- 增加告警链路诊断、通知队列健康状态和敏感配置脱敏。

## 协作规则

`main` 分支用于稳定版本。后续提交应通过 Pull Request 合并，并由仓库所有者审核。详细规则见 [CONTRIBUTING.md](./CONTRIBUTING.md)。

## 许可

当前仓库未声明开源许可证。未经仓库所有者明确授权，不得用于二次分发或商业化再发布。
