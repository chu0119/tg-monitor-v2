<div align="center">

<img src="https://img.shields.io/badge/Telegram-Monitor%20V2-29B6F6?logo=telegram&logoColor=white&style=for-the-badge" alt="TG Monitor V2">

### 🎯 Telegram 群组智能监控预警系统

**全自动部署 · 内置代理引擎 · Web 全局管理 · AI 智能分析**

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)](https://typescriptlang.org)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?logo=mysql&logoColor=white)](https://mysql.com)
[![Mihomo](https://img.shields.io/badge/Mihomo-Clash_Meta-FF6B6B?logo=clash&logoColor=white)](https://github.com/MetaCubeX/mihomo)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

<img src="https://img.shields.io/badge/⭐%20Stars-Welcome!-FFD700?style=flat" alt="Stars">

</div>

---

## 🚀 一键部署（仅需一条命令）

> ⚠️ **重要：请确保在全新安装的操作系统上部署**
>
> 推荐系统：**Ubuntu 25.04 Server**（已测试通过）
>
> 其他支持：Ubuntu 22.04+ / Debian 12+（需 2GB+ 内存）
>
> 不支持在已有 Web 服务（Nginx/Apache/MySQL）的环境上直接安装

```bash
git clone https://github.com/chu0119/tg-monitor-v2.git && cd tg-monitor-v2 && chmod +x start.sh && ./start.sh
```

部署脚本会**全自动**完成以下所有步骤：

| 步骤 | 说明 | 自动化 |
|------|------|--------|
| ① 环境检测 | 操作系统、架构、内存、磁盘、端口占用 | ✅ |
| ② 依赖安装 | Python 3.13、Node.js 24、MySQL 8.0、Nginx | ✅ |
| ③ Python 环境 | 虚拟环境 + pip 依赖安装 | ✅ |
| ④ 前端构建 | npm install + vite build（自动检测国内镜像） | ✅ |
| ⑤ 数据库初始化 | 自动建库建表、索引优化 | ✅ |
| ⑥ 代理内核下载 | mihomo (Clash Meta) 自动下载 | ✅ |
| ⑦ 系统服务配置 | systemd 开机自启（后端 + nginx） | ✅ |
| ⑧ Nginx 配置 | SPA 路由 + API 反代 + WebSocket + 健康检查 | ✅ |
| ⑨ 服务启动 | 后端 + 前端 + 健康检查验证 | ✅ |

### 部署完成后

打开浏览器访问 `http://服务器IP:3000`，跟随**设置向导**完成初始化即可。

### 高级参数

```bash
# 国内服务器自动检测网络，也可手动指定镜像
./start.sh --mirror tsinghua    # 清华镜像
./start.sh --mirror aliyun      # 阿里云镜像
./start.sh --mirror off         # 强制使用官方源

# 其他
./start.sh --reset              # 重置部署状态，重新执行所有步骤
./start.sh --no-autostart       # 不配置开机自启
```

---

## ✨ V2 核心亮点

### 🏗️ 架构级创新

| 特性 | V1 | V2 |
|------|-----|-----|
| 部署方式 | 手动配 .env + systemd | **一条命令全自动** |
| 代理配置 | 手动安装 Clash/Mihomo | **内置 mihomo 内核 + Web 管理** |
| 订阅支持 | 无 | **机场订阅一键导入** |
| 系统配置 | 编辑 .env 文件 | **Web 界面可视化配置** |
| 数据库 | 手动建库建表 | **自动初始化 + 索引优化** |
| 开机自启 | 手动配 systemd | **自动配置 + 依赖检测** |
| TG 连接 | 直连（国内需自备代理） | **自动检测代理，无需手动配置** |
| 适用人群 | 需运维经验 | **零基础用户也能部署** |

### 🔥 代理引擎（V2 独创）

```
┌─────────────────────────────────────────────────┐
│              Web 代理管理面板                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ 订阅解析  │  │ 手动导入  │  │ 节点测试  │       │
│  │ 一键导入  │  │ 粘贴链接  │  │ 延迟检测  │       │
│  └──────────┘  └──────────┘  └──────────┘       │
│                    ↓                             │
│           ┌──────────────┐                       │
│           │  mihomo 内核  │ ← 自动管理生命周期     │
│           │  (Clash Meta) │   启动/停止/重启       │
│           └──────┬───────┘                       │
│                  ↓                               │
│  ┌──────────────────────────────────────┐        │
│  │  自动代理感知                        │        │
│  │  TG 客户端自动走代理 · 无需手动配置   │        │
│  └──────────────────────────────────────┘        │
└─────────────────────────────────────────────────┘
```

- **mihomo (Clash Meta) 内核** — 内置，无需额外安装任何代理软件
- **多格式订阅解析** — Clash YAML / Base64 / SS / VMess / Trojan / VLESS / Hysteria2
- **一键导入** — 粘贴机场订阅链接，自动解析所有节点
- **手动导入** — 粘贴单条或多条节点链接直接导入
- **节点延迟测试** — 一键测试节点延迟，快速找到最优线路
- **30 秒自动刷新** — 代理状态和节点延迟定时更新
- **服务联动** — 系统启动时自动检测并启动代理，TG 客户端自动感知代理配置
- **智能协议适配** — 自动识别节点加密方式（chacha20/aes-256-gcm 等）

---

## 📖 功能全景

### 📡 数据采集

- **多账号管理** — 同时管理多个 Telegram 账号，支持独立配置
- **群组监控** — 实时监听群组消息，支持超级群组
- **频道监控** — 支持只读频道的消息采集（自动重试机制）
- **私聊监控** — 监控指定私聊对话
- **历史消息回溯** — 首次接入自动拉取最近历史消息
- **WebSocket 实时推送** — 新消息毫秒级推送到前端，无需手动刷新
- **会话名称匿名化** — 显示频道真实名称，内部存储使用匿名 ID

### 🧠 智能分析

- **四种匹配模式** — 精确匹配 / 包含匹配 / 正则表达式 / 模糊匹配
- **关键词分组** — 按业务逻辑分组管理关键词（如：金融风险、安全事件、竞品动态）
- **情感分析** — 基于自然语言处理的消息情感倾向分析（积极/消极/中性）
- **词云生成** — 自动生成关键词词云，直观了解话题热点
- **趋势分析** — 消息量趋势 / 告警量趋势 / 关键词频率趋势图表
- **全文搜索** — 支持对历史消息的全文搜索

### 🔔 告警中心

- **四级告警体系** — 🟢 低 / 🟡 中 / 🟠 高 / 🔴 严重
- **告警聚合** — 相似告警自动合并，避免消息轰炸
- **批量处理** — 批量标记已读、批量忽略
- **告警详情** — 关联原始消息上下文，一键查看
- **6 种通知渠道** — 邮件 / 钉钉 / 企业微信 / Server酱 / Webhook / Telegram Bot
- **告警统计** — 按时间/级别/关键词统计告警趋势

### 🌐 代理管理（V2 核心功能）

- **内置 mihomo 内核** — 无需额外安装任何代理软件
- **订阅链接解析** — 支持粘贴机场订阅链接，自动解析节点
- **多协议支持** — SS / SSR / VMess / Trojan / VLESS / Hysteria2 / Clash YAML
- **手动节点导入** — 支持粘贴单条或多条节点链接直接导入
- **节点延迟测试** — 一键测试节点延迟，快速找到最优线路
- **自动状态刷新** — 代理状态和节点延迟每 30 秒自动更新
- **一键切换节点** — Web 界面选择节点，即时生效
- **服务自动联动** — 系统重启时自动启动代理，TG 客户端自动感知

### ⚙️ 系统管理

- **Web 全局配置** — 所有设置在 Web 界面完成，无需 SSH 到服务器
- **首次启动向导** — 引导完成 TG API 配置、数据库连接、代理设置
- **系统诊断大屏** — CPU / 内存 / 磁盘 / 网络 / 连接状态实时监控
- **健康检查** — 后端服务 / 数据库连接 / Telegram 客户端全面状态检测
- **自动数据清理** — 可配置的历史数据保留策略
- **服务自愈** — 代理异常自动重启，TG 连接断开自动重连

### 📊 大屏展示

- **实时消息流** — 所有监控群组的新消息实时滚动展示
- **告警统计面板** — 告警级别分布、趋势图表
- **系统状态监控** — CPU、内存、磁盘、连接数实时可视化
- **群组活跃排行** — 按消息量排名的群组热力图

---

## 🏗️ 系统架构

```
                        ┌─────────────────────────────────┐
                        │         浏览器 (React SPA)        │
                        │         http://IP:3000            │
                        └──────────────┬───────────────────┘
                                       │
                              ┌────────┴────────┐
                              │     Nginx       │
                              │    (:3000)      │
                              │  SPA + API反代   │
                              │  WebSocket + 健康检查 │
                              └──┬──────────┬───┘
                         静态文件  │          │ /api/* /health
                                  │     ┌────┴───────────┐
                                  │     │   FastAPI       │
                                  │     │   (:8000)       │
                                  │     │                │
                                  │     │  ┌──────────┐  │     ┌───────────┐
                                  │     │  │ Telethon │  │     │  mihomo   │
                                  │     │  │TG 客户端  │──┼────→│ 代理内核   │
                                  │     │  │(自动感知   │  │     │ (:7897)   │
                                  │     │  │ 代理配置)  │  │     └─────┬─────┘
                                  │     │  └──────────┘  │           │
                                  │     │  ┌──────────┐  │
                                  │     │  │  MySQL   │  │
                                  │     │  │  数据库   │  │
                                  │     │  └──────────┘  │
                                  │     └───────────────┘
                                  │              │
                                  └──────────────┤
                                                 │
                                          ┌──────┴──────┐
                                          │  Telegram   │
                                          │  服务器      │
                                          └─────────────┘
```

---

## 🛠️ 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **前端** | React 18 + TypeScript 5 | SPA 单页应用 |
| **构建工具** | Vite 6 | 极速热更新 + 生产构建 |
| **UI 框架** | TailwindCSS 4 | 原子化 CSS，深色科技风 |
| **图表** | Recharts | 数据可视化 |
| **后端** | Python 3.13 + FastAPI | 高性能异步 API |
| **数据库 ORM** | SQLAlchemy 2.0 (async) | 异步数据库操作 |
| **数据库** | MySQL 8.0 | 可靠的关系型存储 |
| **TG 客户端** | Telethon (MTProto) | 官方协议，稳定可靠 |
| **代理内核** | Mihomo (Clash Meta) | 高性能代理引擎 |
| **Web 服务器** | Nginx | SPA 路由 + API 反代 + WebSocket |
| **进程管理** | Systemd | 开机自启 + 进程守护 |

---

## 📁 项目结构

```
tg-monitor-v2/
├── start.sh                         # ⭐ 一键部署脚本（全自动）
├── README.md
│
├── backend/                         # 后端服务
│   ├── init_db.py                   # 数据库自动初始化
│   ├── requirements.txt             # Python 依赖
│   └── app/
│       ├── main.py                  # FastAPI 入口 + 生命周期管理
│       ├── api/                     # API 路由层
│       │   ├── settings.py          # 系统设置 API
│       │   ├── proxy.py             # 代理管理 API
│       │   ├── accounts.py          # TG 账号管理 API
│       │   ├── conversations.py     # 会话管理 API
│       │   ├── messages.py          # 消息查询 API
│       │   ├── monitoring.py        # 实时监控 API
│       │   ├── alerts.py            # 告警管理 API
│       │   ├── analysis.py          # 智能分析 API
│       │   ├── notifications.py     # 通知渠道 API
│       │   └── system.py            # 系统信息 API
│       ├── proxy/                   # 代理引擎
│       │   ├── manager.py           # mihomo 进程管理（单例模式）
│       │   ├── subscribe_parser.py  # 多格式订阅解析器
│       │   ├── config_generator.py  # mihomo 配置生成器
│       │   └── proxy/               # 代理内核目录（部署时自动下载）
│       ├── models/                  # 数据模型层
│       ├── services/                # 业务逻辑层
│       └── telegram/                # Telegram 交互层
│           ├── client.py            # Telethon 客户端管理
│           └── monitor.py           # 消息监控引擎
│
└── frontend/                        # 前端应用
    ├── src/
    │   ├── pages/                   # 页面组件
    │   │   ├── SetupPage.tsx        # ⭐ 首次启动设置向导
    │   │   ├── ProxyPage.tsx        # ⭐ 代理管理页
    │   │   ├── AccountsPage.tsx     # 账号管理页
    │   │   ├── MonitoringPage.tsx   # 实时监控页
    │   │   ├── DashboardPage.tsx    # 仪表盘
    │   │   ├── BigScreenPage.tsx    # 大屏展示
    │   │   ├── AlertsPage.tsx       # 告警中心
    │   │   ├── AnalysisPage.tsx     # 智能分析
    │   │   ├── ConversationsPage.tsx # 会话管理
    │   │   └── SettingsPage.tsx     # 系统设置
    │   ├── routes/                  # 路由配置
    │   ├── components/              # 通用组件
    │   └── lib/                     # 工具库
    │       └── api.ts               # API 统一封装
    └── vite.config.ts               # Vite 构建配置
```

---

## ⚙️ 服务管理

```bash
# 查看服务状态
sudo systemctl status tgmonitor-backend nginx

# 重启服务
sudo systemctl restart tgmonitor-backend

# 查看日志
journalctl -u tgmonitor-backend -f

# 停止所有服务
sudo systemctl stop tgmonitor-backend nginx

# 重新部署（保留数据库）
cd tg-monitor-v2 && git pull && ./start.sh --reset
```

| 服务 | 说明 | 端口 |
|------|------|------|
| `tgmonitor-backend` | FastAPI 后端服务 | 8000 |
| `nginx` | 前端托管 + API 反代 + WebSocket | 3000 |
| `mihomo` | 代理内核（由后端自动管理） | 7897 |

---

## ❓ 常见问题

<details>
<summary><b>🖥️ 一键部署失败怎么办？</b></summary>

1. **查看部署日志**：`cat /tmp/tg-monitor-deploy.log`
2. **确认系统版本**：`cat /etc/os-release`（需要 Ubuntu 22.04+ 或 Debian 12+）
3. **确认内存**：至少 2GB（`free -h`）
4. **手动重试**：`./start.sh --reset`
5. **npm 构建失败**：`cd frontend && npm install --legacy-peer-deps && npx vite build`
6. **端口被占用**：确保 3000、8000、3306、7897 端口未被占用

</details>

<details>
<summary><b>🌐 mihomo 代理内核下载失败？</b></summary>

代理内核下载失败不影响核心监控功能（仅代理不可用）。手动下载：

```bash
# Linux x86_64（选一个源）
curl -L https://github.com/MetaCubeX/mihomo/releases/download/v1.19.21/mihomo-linux-amd64-v1.19.21.gz | gunzip > backend/proxy/mihomo
# GitHub 被墙时用镜像
curl -L https://bgithub.xyz/MetaCubeX/mihomo/releases/download/v1.19.21/mihomo-linux-amd64-v1.19.21.gz | gunzip > backend/proxy/mihomo
# 设置权限
chmod +x backend/proxy/mihomo
# 重启后端
sudo systemctl restart tgmonitor-backend
```

</details>

<details>
<summary><b>🔐 如何获取 Telegram API 凭证？</b></summary>

1. 访问 https://my.telegram.org
2. 登录你的 Telegram 账号
3. 进入 **API development tools**
4. 点击 **Create new application**
5. 填写应用名称（随意填写）
6. 获取 `api_id`（数字）和 `api_hash`（字符串）

在设置向导或系统设置页面填入即可。

</details>

<details>
<summary><b>🔄 如何更新到最新版本？</b></summary>

```bash
cd tg-monitor-v2
git pull
./start.sh --reset
```

数据会保留，只更新代码和重新构建前端。

</details>

<details>
<summary><b>📡 TG 账号连接失败（超时）？</b></summary>

- **确认代理已启动**：在代理管理页面检查代理状态
- **国内服务器必须有代理**：Telegram 在中国大陆被封锁，需要通过代理连接
- **系统会自动检测代理**：如果 mihomo 代理正在运行，TG 客户端会自动走代理
- **手动启动代理**：`curl -X POST http://127.0.0.1:8000/api/v1/proxy/start`

</details>

<details>
<summary><b>📊 大屏显示"系统异常"？</b></summary>

- 刷新页面（Ctrl+Shift+R 强制刷新）
- 确认后端服务正常运行：`curl http://127.0.0.1:8000/health`
- 确认 nginx 配置包含 `/health` 代理规则

</details>

<details>
<summary><b>🤖 需要什么硬件配置？</b></summary>

| 资源 | 最低要求 | 推荐配置 |
|------|---------|---------|
| CPU | 1 核 | 2 核+ |
| 内存 | 2 GB | 4 GB+ |
| 磁盘 | 5 GB | 20 GB+（大量消息存储） |
| 网络 | 能连接 Telegram（通过代理） | 稳定的代理连接 |
| 系统 | Ubuntu 22.04+ / Debian 12+ | Ubuntu 25.04 Server |

</details>

---

## 📋 更新日志

### v1.0.0 — 2026-04-02

- 🎉 **初始版本发布**
- ⭐ 一键部署脚本（自动环境检测、依赖安装、服务配置）
- 🌐 内置 mihomo 代理引擎 + Web 代理管理面板
- 📡 多格式订阅解析（Clash YAML / Base64 / SS / VMess / Trojan / VLESS / Hysteria2）
- 🔄 手动节点导入（粘贴节点链接直接导入）
- ⚡ 节点延迟测试 + 30 秒自动刷新
- 🔗 TG 客户端自动感知代理（无需手动配置 SOCKS5）
- 🛡️ 服务联动（系统启动自动启动代理，代理异常自动重连）
- 📊 Web 配置系统（告别 .env 文件编辑）
- 🧭 首次启动设置向导
- 📱 实时消息流 + WebSocket 推送
- 🧠 智能分析（关键词匹配 / 情感分析 / 词云 / 趋势）
- 🔔 四级告警体系 + 6 种通知渠道
- 📺 大屏展示（系统监控 + 消息流 + 告警统计）
- 🗄️ 数据库自动初始化 + 死锁重试
- 🔧 systemd 开机自启 + 服务自愈

---

## 🤝 参与贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建功能分支：`git checkout -b feature/amazing-feature`
3. 提交更改：`git commit -m 'feat: add amazing feature'`
4. 推送分支：`git push origin feature/amazing-feature`
5. 提交 Pull Request

---

## 📄 许可证

[MIT](LICENSE) © 2026 chu0119

---

<div align="center">

**Made with ❤️ by [chu0119](https://github.com/chu0119)**

如果这个项目对你有帮助，请给一个 ⭐ Star！

</div>
