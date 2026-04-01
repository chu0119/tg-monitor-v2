<div align="center">

# 🔭 TG Monitor v2

### Telegram 群组监控预警系统 — Web 配置版

**一键部署 · 内置代理 · Web 管理 · 开箱即用**

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)](https://typescriptlang.org)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?logo=mysql&logoColor=white)](https://mysql.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

## ✨ V2 新特性

相比 V1，V2 是完全重新设计的部署体验：

| 特性 | V1 | V2 |
|------|-----|-----|
| 部署方式 | 手动配置 .env + systemd | **一条命令全自动** |
| 代理配置 | 手动安装 Clash/Mihomo | **内置代理内核 + Web 配置** |
| 订阅支持 | 无 | **Clash/Base64/SS/VMess/Trojan/VLESS/Hysteria2** |
| 系统设置 | 编辑 .env 文件 | **Web 界面配置** |
| 数据库 | 手动建库建表 | **自动初始化** |
| 开机自启 | 手动配 systemd | **自动配置** |
| 适用环境 | 需要一定运维经验 | **全新系统直接跑** |

---

## 🚀 一键部署

> 支持 Ubuntu 20.04+ / Debian 11+，从全新系统开始

```bash
git clone https://github.com/chu0119/tg-monitor-v2.git
cd tg-monitor-v2
chmod +x start.sh
./start.sh
```

部署脚本会自动完成：

1. ✅ 检测系统环境（操作系统、架构、内存、磁盘）
2. ✅ 安装所有依赖（Python、Node.js、MySQL）
3. ✅ 创建 Python 虚拟环境并安装依赖
4. ✅ 安装前端依赖并构建
5. ✅ 初始化数据库
6. ✅ 下载代理内核（mihomo）
7. ✅ 配置 systemd 服务（开机自启）
8. ✅ 启动所有服务

### 国内服务器

脚本自动检测网络环境，国内服务器会使用清华/阿里云镜像加速。

手动指定镜像：
```bash
./start.sh --mirror tsinghua    # 清华镜像
./start.sh --mirror aliyun      # 阿里云镜像
./start.sh --mirror off         # 强制使用官方源
```

### 其他参数

```bash
./start.sh --reset              # 重置部署状态，重新执行所有步骤
./start.sh --no-autostart       # 不配置开机自启
```

### 部署完成后

打开浏览器访问 `http://服务器IP:3000`，跟随设置向导完成初始化配置。

---

## 📖 功能介绍

### 📡 数据采集

- **多账号管理** — 同时管理多个 Telegram 账号
- **群组/频道监控** — 实时监听，支持超级群组和只读频道
- **私聊监控** — 监控指定私聊对话
- **历史消息** — 首次接入自动拉取最近历史消息
- **WebSocket 推送** — 新消息实时推送到前端

### 🔍 智能分析

- **四种匹配模式** — 精确 / 包含 / 正则 / 模糊
- **关键词分组** — 按业务逻辑分组管理
- **情感分析** — 基于自然语言处理的情感倾向分析
- **词云生成** — 自动生成关键词词云
- **趋势分析** — 消息量 / 告警量趋势图表

### 🔔 告警中心

- **四级告警** — 低（🟢）/ 中（🟡）/ 高（🟠）/ 严重（🔴）
- **告警聚合** — 相似告警自动合并，避免轰炸
- **批量处理** — 批量标记已读、忽略
- **6种通知渠道** — 邮件 / 钉钉 / 企业微信 / Server酱 / Webhook / Telegram Bot

### 🌐 内置代理（V2 新增）

- **mihomo 内核** — 内置 Clash Meta 内核，无需额外安装
- **订阅链接** — 支持粘贴订阅链接，自动解析节点
- **多格式解析** — Clash / Base64 / SS / VMess / Trojan / VLESS / Hysteria2
- **手动配置** — 支持手动添加代理节点
- **一键切换** — Web 界面选择节点，即时生效

### ⚙️ 系统管理

- **Web 配置** — 所有设置在 Web 界面完成，无需编辑配置文件
- **设置向导** — 首次启动引导完成基本配置
- **系统诊断** — CPU / 内存 / 磁盘 / 连接状态
- **健康检查** — 后端 / 数据库 / Telegram 全面检查
- **自动清理** — 可配置的历史数据清理策略

---

## 🏗️ 系统架构

```
┌──────────────────────────────────────────────────┐
│                  浏览器 (React SPA)                │
│              http://IP:3000                      │
└──────────────────────┬───────────────────────────┘
                       │
              ┌────────┴────────┐
              │   Nginx        │
              │  (:3000)       │
              │  SPA + API代理  │
              └──┬─────────┬───┘
        静态文件  │         │ /api/*
                 │    ┌────┴──────────┐
                 │    │  FastAPI      │
                 │    │  (:8000)      │
                 │    │               │
                 │    │  ┌─────────┐  │     ┌──────────┐
                 │    │  │Telethon │  │     │  mihomo  │
                 │    │  │TG 客户端 │──┼────→│  代理内核 │
                 │    │  └─────────┘  │     │  (:7897) │
                 │    │               │     └────┬─────┘
                 │    │  ┌─────────┐  │          │
                 │    │  │ MySQL   │  │          │
                 │    │  │ 数据库   │  │          │
                 │    │  └─────────┘  │          │
                 │    └──────────────┘          │
                 │                              │
                 └──────────────────────────────┘
                        │
                 ┌──────┴──────┐
                 │  Telegram   │
                 └─────────────┘
```

---

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18 + TypeScript + Vite + TailwindCSS + Recharts |
| 后端 | Python 3.13 + FastAPI + Uvicorn + SQLAlchemy 2.0 |
| 数据库 | MySQL 8.0 + aiomysql |
| TG 客户端 | Telethon (MTProto) |
| 代理内核 | Mihomo (Clash Meta) |
| Web 服务器 | Nginx |
| 进程管理 | Systemd |

---

## 📁 项目结构

```
tg-monitor-v2/
├── start.sh                    # ⭐ 一键部署脚本
├── README.md
│
├── backend/                    # 后端服务
│   ├── init_db.py              # 数据库初始化
│   ├── requirements.txt
│   └── app/
│       ├── main.py             # FastAPI 入口
│       ├── api/
│       │   ├── settings.py     # 系统设置 API（Web配置）
│       │   ├── proxy.py        # 代理管理 API（订阅/节点/切换）
│       │   ├── accounts.py     # 账号管理 API
│       │   ├── system.py       # 系统信息 API
│       │   └── ...             # 其他 API
│       ├── proxy/
│       │   ├── manager.py      # mihomo 进程管理（单例模式）
│       │   ├── subscribe_parser.py  # 多格式订阅解析
│       │   ├── config_generator.py  # mihomo 配置生成
│       │   └── mihomo          # 代理内核二进制
│       ├── models/
│       ├── services/
│       └── telegram/
│
└── frontend/                   # 前端应用
    ├── src/
    │   ├── pages/
    │   │   ├── SetupPage.tsx    # ⭐ 设置向导（首次启动）
    │   │   ├── ProxyPage.tsx    # ⭐ 代理管理页
    │   │   ├── AccountsPage.tsx # ⭐ 账号管理页（改版）
    │   │   ├── DashboardPage.tsx
    │   │   ├── AlertsPage.tsx
    │   │   └── ...
    │   ├── routes/
    │   └── components/
    └── vite.config.ts
```

---

## ⚙️ 服务管理

部署完成后，通过 systemd 管理服务：

```bash
# 查看状态
sudo systemctl status tgmonitor-backend

# 重启服务
sudo systemctl restart tgmonitor-backend

# 查看日志
journalctl -u tgmonitor-backend -f

# 停止服务
sudo systemctl stop tgmonitor-backend nginx

# 重新部署
./start.sh --reset
```

### 服务列表

| 服务 | 说明 | 端口 |
|------|------|------|
| `tgmonitor-backend` | FastAPI 后端 | 8000 |
| `nginx` | 前端托管 + API 反向代理 | 3000 |

---

## ❓ 常见问题

<details>
<summary><b>一键部署失败怎么办？</b></summary>

1. 查看部署日志：`cat /tmp/tg-monitor-deploy.log`
2. 确认系统版本：`cat /etc/os-release`（需要 Ubuntu 20.04+ 或 Debian 11+）
3. 手动重试：`./start.sh --reset`
4. 如果 npm install 失败：`cd frontend && npm install --legacy-peer-deps`

</details>

<details>
<summary><b>mihomo 下载失败？</b></summary>

代理内核下载失败不影响核心功能（仅代理不可用）。手动下载：

```bash
# 下载（选一个源）
curl -L https://github.com/MetaCubeX/mihomo/releases/download/v1.19.21/mihomo-linux-amd64-v1.19.21.gz -o /tmp/mihomo.gz
# 或镜像
curl -L https://bgithub.xyz/MetaCubeX/mihomo/releases/download/v1.19.21/mihomo-linux-amd64-v1.19.21.gz -o /tmp/mihomo.gz

# 解压并放置
gunzip /tmp/mihomo.gz
chmod +x /tmp/mihomo
mv /tmp/mihomo backend/app/proxy/mihomo
```

</details>

<details>
<summary><b>如何更新？</b></summary>

```bash
cd tg-monitor-v2
git pull
./start.sh --reset
```

</details>

<details>
<summary><b>需要什么环境？</b></summary>

| 依赖 | 最低要求 |
|------|---------|
| 系统 | Ubuntu 20.04+ / Debian 11+ |
| 内存 | 512MB+ |
| 磁盘 | 2GB+ |
| 网络 | 需要能连接 Telegram（通过代理） |

脚本会自动安装 Python、Node.js、MySQL，无需提前准备。

</details>

<details>
<summary><b>如何获取 Telegram API 凭证？</b></summary>

1. 访问 https://my.telegram.org
2. 登录 Telegram 账号
3. 进入 **API development tools**
4. 创建应用，获取 `api_id` 和 `api_hash`

在设置向导中填入即可。

</details>

---

## 📋 更新日志

### v1.0.0 — 2026-04-02

- 🎉 初始版本发布
- 一键部署脚本（自动环境检测、依赖安装、服务配置）
- 内置 mihomo 代理内核 + Web 代理管理
- 多格式订阅解析（Clash/Base64/SS/VMess/Trojan/VLESS/Hysteria2）
- Web 配置系统（告别 .env 文件）
- 首次启动设置向导
- 基于 V1 的完整功能（监控、告警、分析、大屏）

---

## 📄 许可证

[MIT](LICENSE) © 2026 chu0119

---

<div align="center">

**Made with ❤️ by [chu0119](https://github.com/chu0119)**

如果这个项目对你有帮助，请给一个 ⭐ Star！

</div>
