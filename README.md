<div align="center">

# 🔭 TG Monitor

### Telegram 群组信息监测预警系统

**实时监控 · 智能分析 · 多维告警 · 全链路追踪**

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)](https://typescriptlang.org)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?logo=mysql&logoColor=white)](https://mysql.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![Telegram](https://img.shields.io/badge/Telethon-1.40-26A5E4?logo=telegram&logoColor=white)](https://github.com/LonamiWebs/Telethon)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[English](README_EN.md) · 简体中文

</div>

---

## 📖 目录

- [项目简介](#-项目简介)
- [功能全景](#-功能全景)
- [系统架构](#-系统架构)
- [技术栈](#-技术栈)
- [界面预览](#-界面预览)
- [快速开始](#-快速开始)
- [Docker 部署](#-docker-部署推荐)
- [Systemd 部署](#-systemd-部署)
- [配置说明](#-配置说明)
- [API 文档](#-api-文档)
- [项目结构](#-项目结构)
- [性能指标](#-性能指标)
- [开发指南](#-开发指南)
- [常见问题](#-常见问题)
- [更新日志](#-更新日志)
- [贡献指南](#-贡献指南)
- [许可证](#-许可证)

---

## 🌟 项目简介

**TG Monitor** 是一款企业级 Telegram 消息监控与分析平台，支持同时监控数百个群组、频道和私聊，实时捕获消息并通过多维度关键词引擎进行智能匹配，触发多渠道告警通知。

### 核心优势

| 特性 | 描述 |
|------|------|
| 🚀 **高性能** | WebSocket 实时推送，单节点支持 500+ 会话并发监控 |
| 🧠 **智能匹配** | 精确 / 包含 / 正则 / 模糊 四种匹配模式 + 关键词分组 |
| 🔔 **多维告警** | 低 / 中 / 高 / 严重 四级告警 + 6种通知渠道 |
| 📊 **深度分析** | 词云、情感分析、趋势图表、大屏可视化 |
| 🔄 **自动恢复** | Systemd 守护 + 健康检查 + 自动重启，7×24 稳定运行 |
| 🐳 **一键部署** | Docker Compose 一条命令启动全部服务 |
| 📱 **全端适配** | 桌面 / 平板 / 手机 完美响应式布局 |
| 🌙 **科技风 UI** | 深色主题 + 玻璃拟态 + 赛博朋克风格 |

---

## 🗺️ 功能全景

```
┌─────────────────────────────────────────────────────────────────────┐
│                        TG Monitor 功能架构                            │
├─────────────┬─────────────┬──────────────┬──────────────┬───────────┤
│  📡 数据采集  │  🔍 智能分析  │  🔔 告警中心   │  📊 数据看板  │  ⚙️ 系统  │
├─────────────┼─────────────┼──────────────┼──────────────┼───────────┤
│ 多账号管理    │ 关键词匹配    │ 多级别告警     │ 实时仪表盘    │ 用户认证   │
│ 群组/频道监控 │ 关键词分组    │ 批量处理       │ 消息趋势图    │ 角色权限   │
│ 私聊监控     │ 正则表达式    │ 告警聚合       │ 关键词热力图  │ 数据备份   │
│ 历史消息拉取  │ 情感分析      │ 已读/忽略      │ 会话活跃度   │ 系统诊断   │
│ 实时推送     │ 词云生成      │ 处理备注       │ 大屏展示     │ 日志管理   │
│ 会话管理     │ 消息搜索      │ 多渠道通知     │ 导出报表     │ 自动清理   │
│ 只读频道采集  │ 趋势分析      │ 通知模板       │ 网络状态     │ 健康检查   │
└─────────────┴─────────────┴──────────────┴──────────────┴───────────┘
```

### 📡 数据采集

- **多账号管理** — 同时管理多个 Telegram 账号，独立配置
- **群组监控** — 实时监听群组消息，支持超级群组
- **频道监控** — 支持公开/私有频道，包含只读频道采集
- **私聊监控** — 监控指定私聊对话
- **历史消息** — 首次接入自动拉取最近 7 天历史消息
- **WebSocket 推送** — 新消息毫秒级推送到前端

### 🔍 智能分析

- **四种匹配模式**
  - `精确匹配` — 完全一致才触发
  - `包含匹配` — 消息中包含关键词即触发
  - `正则匹配` — 支持复杂正则表达式
  - `模糊匹配` — 容错匹配，应对变体和错别字
- **关键词分组** — 按业务逻辑分组管理关键词
- **情感分析** — 基于自然语言处理的情感倾向分析
- **词云生成** — 自动生成消息关键词词云图
- **趋势分析** — 消息量 / 告警量 / 关键词热度 趋势

### 🔔 告警中心

- **四级告警** — 低（🟢） / 中（🟡） / 高（🟠） / 严重（🔴）
- **告警聚合** — 相似告警自动聚合，避免通知轰炸
- **批量处理** — 支持批量标记已读、忽略、升级
- **处理备注** — 每条告警可添加处理记录
- **6种通知渠道**
  - 📧 邮件（SMTP）
  - 💬 钉钉机器人
  - 🏢 企业微信机器人
  - 📲 Server酱
  - 🔗 自定义 Webhook
  - 🤖 Telegram Bot

### 📊 数据看板

- **实时仪表盘** — 消息量、告警数、活跃监控、系统资源 一目了然
- **消息趋势图** — 24小时 / 7天 / 30天 消息量趋势
- **关键词热力图** — Top关键词匹配频次排行
- **会话活跃度** — 各会话消息量排名
- **大屏展示** — 独立大屏页面，适合投屏监控
- **多格式导出** — CSV / JSON / Excel

### ⚙️ 系统管理

- **JWT 认证** — 安全的用户认证机制
- **RBAC 权限** — 基于角色的访问控制
- **自动备份** — 数据库定时自动备份
- **系统诊断** — 一键诊断系统状态（CPU / 内存 / 磁盘 / 连接）
- **健康检查** — 后端 / 数据库 / Telegram / WebSocket 全面健康检查
- **自动清理** — 可配置的历史数据自动清理策略
- **网络状态** — 右上角实时显示 Telegram 连接状态

---

## 🏗️ 系统架构

```
                          ┌──────────────┐
                          │   浏览器客户端  │
                          │  (React SPA)  │
                          └──────┬───────┘
                                 │ HTTP / WebSocket
                          ┌──────┴───────┐
                          │   Nginx      │
                          │  (反向代理)   │
                          └──┬────────┬──┘
                    静态文件 │        │ /api/* /ws/*
                          ┌──┴───┐  ┌──┴──────────┐
                          │ 前端  │  │  FastAPI     │
                          │ 构建  │  │  后端服务     │
                          │ 产物  │  │              │
                          └──────┘  │  ┌─────────┐ │
                                   │  │Telethon │ │
                                   │  │TG 客户端 │ │
                                   │  └────┬────┘ │
                                   │       │      │
                                   │  ┌────┴────┐ │
                                   │  │ MySQL   │ │
                                   │  │ 数据库   │ │
                                   │  └─────────┘ │
                                   └──────────────┘
                                          │
                                   ┌──────┴──────┐
                                   │  SOCKS5 代理  │
                                   │ (Mihomo/Clash)│
                                   └──────┬──────┘
                                          │
                                   ┌──────┴──────┐
                                   │  Telegram   │
                                   │  服务器      │
                                   └─────────────┘
```

### 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                        前端层 (Frontend)                     │
│  React 18 + TypeScript + Vite + TailwindCSS + Recharts      │
│  WebSocket 实时通信 · 响应式布局 · 深色科技风主题              │
├─────────────────────────────────────────────────────────────┤
│                       接口层 (API)                           │
│  FastAPI · RESTful · WebSocket · JWT 认证 · CORS             │
├─────────────────────────────────────────────────────────────┤
│                      业务层 (Services)                        │
│  告警服务 · 关键词匹配引擎 · 情感分析 · 通知调度 · 数据导出     │
├─────────────────────────────────────────────────────────────┤
│                      数据层 (Data)                            │
│  SQLAlchemy 2.0 (Async) · MySQL 8.0 · Alembic 迁移           │
├─────────────────────────────────────────────────────────────┤
│                     基础设施层 (Infra)                        │
│  Telethon (MTProto) · SOCKS5 代理 · Systemd · Docker         │
└─────────────────────────────────────────────────────────────┘
```

---

## 🛠️ 技术栈

### 后端

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.13 | 运行时 |
| FastAPI | 0.115 | Web 框架 |
| Uvicorn | 0.34 | ASGI 服务器 |
| SQLAlchemy | 2.0 | 异步 ORM |
| Alembic | 1.14 | 数据库迁移 |
| Telethon | 1.40 | Telegram MTProto 客户端 |
| MySQL | 8.0 | 关系型数据库 |
| aiomysql | 0.2 | 异步 MySQL 驱动 |
| Loguru | 0.7 | 日志管理 |
| APScheduler | 3.11 | 定时任务调度 |
| Pydantic | 2.10 | 数据校验 |

### 前端

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 18 | UI 框架 |
| TypeScript | 5 | 类型安全 |
| Vite | 6 | 构建工具 |
| TailwindCSS | 3 | 原子化 CSS |
| Recharts | 2 | 数据可视化 |
| React Router | 7 | 路由管理 |
| Lucide React | - | 图标库 |

### 运维

| 技术 | 用途 |
|------|------|
| Docker + Compose | 容器化部署 |
| Nginx | 反向代理 + 静态托管 |
| Systemd | 进程守护 |
| Mihomo (Clash Meta) | SOCKS5 代理 |

---

## 🖥️ 界面预览

> 🌙 深色科技风主题，赛博朋克风格，玻璃拟态设计
> 
> 实时连接状态指示灯 · 霓虹光效 · 渐变色卡片 · 动态数据展示

### 主要页面

| 页面 | 功能 |
|------|------|
| 📊 **仪表盘** | 系统概览、消息趋势、告警统计、关键词热度、系统资源监控 |
| 🔔 **告警中心** | 告警列表、关键词高亮、批量处理、处理备注、导出 |
| 💬 **会话管理** | 群组/频道/私聊管理、监控开关、分类筛选、搜索、分页 |
| 🔑 **关键词管理** | 关键词CRUD、分组管理、匹配模式、正则测试 |
| 📈 **数据分析** | 词云、情感分析、趋势图表、消息统计 |
| 📺 **大屏展示** | 独立全屏页面，实时数据，适合投屏 |
| 👤 **账号管理** | Telegram 账号添加、状态监控、连接管理 |
| ⚙️ **系统设置** | 通知渠道配置、自动清理、备份管理、系统诊断 |

### UI 特色

- 🌈 **霓虹渐变** — 赛博朋克风格配色，高对比度深色主题
- 🪟 **玻璃拟态** — 半透明毛玻璃卡片，层次分明
- 💡 **动态指示** — 连接状态灯、告警脉冲动画、数据加载动效
- 📱 **全端适配** — 桌面多列 → 平板双列 → 手机单列，无缝切换
- 🔔 **实时更新** — WebSocket 推送，新告警即时到达，无需刷新
- 🌍 **国际化** — 内置中英文切换

---

## 🚀 快速开始

### 环境要求

| 依赖 | 最低版本 | 说明 |
|------|---------|------|
| Python | 3.10+ | 推荐 3.13 |
| Node.js | 18+ | 推荐 20 LTS |
| MySQL | 8.0+ | 推荐 8.4 |
| 代理 | - | 国内服务器需要，用于连接 Telegram |

### 获取 Telegram API 凭证

1. 访问 https://my.telegram.org
2. 登录你的 Telegram 账号
3. 进入 **API development tools**
4. 创建应用，获取 `api_id` 和 `api_hash`

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/chu0119/tg-monitor.git
cd tg-monitor

# 2. 后端配置
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入配置（见下方配置说明）

# 3. 前端配置
cd ../frontend
npm install

# 4. 启动后端
cd ../backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 5. 启动前端（新终端）
cd frontend
npm run dev
```

访问 **http://localhost:5173** 即可使用。

---

## 🐳 Docker 部署（推荐）

最简单的部署方式，一条命令启动全部服务。

```bash
# 1. 克隆项目
git clone https://github.com/chu0119/tg-monitor.git
cd tg-monitor

# 2. 配置环境变量
cp backend/.env.example backend/.env
vim backend/.env
# 重要：MYSQL_HOST=mysql（Docker内网地址，不是localhost）
# 重要：SOCKS5_PROXY=socks5://宿主机IP:7897

# 3. 一键启动
docker compose up -d

# 4. 查看状态
docker compose ps
docker compose logs -f
```

访问 **http://your-server-ip** 即可使用。

详细说明见 [docker/README.md](docker/README.md)

### Docker 服务架构

```
┌─────────────────────────────────────────┐
│           Docker Compose                 │
│                                         │
│  ┌───────────┐   ┌──────────────────┐  │
│  │  Nginx    │──→│  FastAPI Backend │  │
│  │  (:80)    │   │  (:8000)         │  │
│  └───────────┘   └────────┬─────────┘  │
│                           │             │
│                  ┌────────┴─────────┐  │
│                  │  MySQL 8.0       │  │
│                  │  (:3306)         │  │
│                  └──────────────────┘  │
│                                         │
│  Volumes: mysql_data / sessions / logs  │
└─────────────────────────────────────────┘
```

---

## ⚙️ Systemd 部署

适用于已有服务器环境的传统部署方式。

### 一键安装

```bash
chmod +x install-services.sh
sudo ./install-services.sh
```

### 服务管理

```bash
# 查看状态
sudo systemctl status tgjiankong-backend tgjiankong-frontend

# 重启
sudo systemctl restart tgjiankong-backend

# 查看日志
journalctl -u tgjiankong-backend -f

# 手动健康检查
./auto-restart.sh
```

### 服务清单

| 服务 | 说明 | 端口 | 自动重启 |
|------|------|------|---------|
| `tgjiankong-backend` | FastAPI 后端 | 8000 | ✅ 5秒 |
| `tgjiankong-frontend` | Vite 前端 | 5173 | ✅ 5秒 |
| `mihomo-proxy` | SOCKS5 代理 | 7897 | ✅ 5秒 |
| `tgjiankong-healthcheck.timer` | 健康检查 | - | 每5分钟 |

---

## 📝 配置说明

### 环境变量 (.env)

```bash
# ============================================
# 数据库配置
# ============================================
DATABASE_TYPE=mysql
MYSQL_HOST=localhost          # Docker 部署填 mysql
MYSQL_PORT=3306
MYSQL_USER=tgmonitor
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=tg_monitor

# ============================================
# Telegram API 配置
# ============================================
TELEGRAM_API_ID=12345678           # 从 my.telegram.org 获取
TELEGRAM_API_HASH=abcdef123456...  # 从 my.telegram.org 获取

# ============================================
# 代理配置（国内服务器必填）
# ============================================
SOCKS5_PROXY=socks5://127.0.0.1:7897
# Docker: socks5://宿主机内网IP:7897
# Mac/Windows: socks5://host.docker.internal:7897

# ============================================
# 可选配置
# ============================================
# JWT 密钥（自动生成，无需手动设置）
# HTTP_PROXY=http://127.0.0.1:7897
# HTTPS_PROXY=http://127.0.0.1:7897
```

### 关键词匹配模式

| 模式 | 说明 | 示例 |
|------|------|------|
| 精确 | 完全匹配 | `崩盘` 只匹配"崩盘" |
| 包含 | 包含即匹配 | `风险` 匹配"有风险提示" |
| 正则 | 正则表达式 | `充值.*元` 匹配"充值100元" |
| 模糊 | 模糊匹配 | `崩盘` 也能匹配"蹦盘" |

---

## 📡 API 文档

启动后端后访问：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 核心 API

| 模块 | 端点 | 说明 |
|------|------|------|
| 认证 | `POST /api/v1/auth/login` | 用户登录 |
| 仪表盘 | `GET /api/v1/dashboard/stats` | 系统概览统计 |
| 会话 | `GET /api/v1/conversations/` | 会话列表 |
| 关键词 | `GET /api/v1/keywords/` | 关键词列表 |
| 告警 | `GET /api/v1/alerts/` | 告警列表 |
| 告警 | `PUT /api/v1/alerts/batch-status` | 批量处理告警 |
| 消息 | `GET /api/v1/messages/` | 消息查询 |
| 分析 | `GET /api/v1/analysis/trends` | 趋势分析 |
| 导出 | `GET /api/v1/alerts/export` | 导出告警 |
| 健康 | `GET /health` | 系统健康检查 |
| WebSocket | `ws://host/ws` | 实时消息推送 |

---

## 📁 项目结构

```
tg-monitor/
├── 📁 backend/                    # 后端服务
│   ├── 📁 app/
│   │   ├── 📁 api/               # API 路由层
│   │   │   ├── accounts.py       #   账号管理 API
│   │   │   ├── alerts.py         #   告警管理 API（聚合/导出/批量）
│   │   │   ├── analysis.py       #   数据分析 API（词云/情感/趋势）
│   │   │   ├── backups.py        #   数据备份 API
│   │   │   ├── conversations.py  #   会话管理 API
│   │   │   ├── dashboard.py      #   仪表盘 API（统计/图表）
│   │   │   ├── database.py       #   数据库管理 API
│   │   │   ├── diagnostics.py    #   系统诊断 API
│   │   │   ├── keywords.py       #   关键词管理 API
│   │   │   ├── messages.py       #   消息查询 API
│   │   │   ├── monitoring.py     #   监控管理 API
│   │   │   ├── notifications.py  #   通知配置 API
│   │   │   └── settings.py       #   系统设置 API
│   │   ├── 📁 core/              # 核心配置
│   │   │   ├── config.py         #   环境配置（Pydantic Settings）
│   │   │   └── database.py       #   数据库连接池
│   │   ├── 📁 models/            # SQLAlchemy 数据模型
│   │   │   ├── account.py        #   账号模型
│   │   │   ├── alert.py          #   告警模型
│   │   │   ├── conversation.py   #   会话模型
│   │   │   ├── keyword.py        #   关键词模型
│   │   │   ├── message.py        #   消息模型
│   │   │   ├── sender.py         #   发送者模型
│   │   │   └── user.py           #   用户模型
│   │   ├── 📁 schemas/           # Pydantic 请求/响应模型
│   │   ├── 📁 services/          # 业务逻辑层
│   │   │   ├── alert_service.py          #   告警处理
│   │   │   ├── alert_aggregation_service.py # 告警聚合
│   │   │   ├── keyword_matcher.py         #   关键词匹配引擎
│   │   │   ├── notification_service.py    #   通知调度
│   │   │   ├── sentiment_service.py       #   情感分析
│   │   │   ├── wordcloud_service.py       #   词云生成
│   │   │   ├── export_service.py          #   数据导出
│   │   │   ├── backup_service.py          #   数据备份
│   │   │   ├── data_cleanup_service.py    #   自动清理
│   │   │   └── database_service.py        #   数据库服务
│   │   ├── 📁 telegram/          # Telegram 集成
│   │   │   ├── client.py         #   Telethon 客户端管理
│   │   │   └── monitor.py        #   消息监控核心
│   │   ├── 📁 utils/             # 工具函数
│   │   │   └── datetime_helper.py #   时区处理
│   │   └── main.py              # FastAPI 应用入口
│   ├── requirements.txt
│   └── .env.example
│
├── 📁 frontend/                   # 前端应用
│   ├── 📁 src/
│   │   ├── 📁 pages/             # 页面组件
│   │   │   ├── DashboardPage.tsx  #   仪表盘
│   │   │   ├── AlertsPage.tsx     #   告警中心
│   │   │   ├── ConversationsPage.tsx # 会话管理
│   │   │   ├── KeywordsPage.tsx   #   关键词管理
│   │   │   ├── AnalysisPage.tsx   #   数据分析
│   │   │   ├── BigScreenPage.tsx  #   大屏展示
│   │   │   ├── AccountsPage.tsx   #   账号管理
│   │   │   ├── MonitoringPage.tsx #   监控管理
│   │   │   ├── NotificationsPage.tsx # 通知配置
│   │   │   └── SettingsPage.tsx   #   系统设置
│   │   ├── 📁 components/        # 通用组件
│   │   │   ├── InternetStatus.tsx #   网络状态指示
│   │   │   ├── layout/           #   布局组件
│   │   │   ├── providers/        #   Context Provider
│   │   │   └── ui/               #   UI 组件库
│   │   ├── 📁 hooks/             # 自定义 Hooks
│   │   │   ├── useWebSocket.ts   #   WebSocket 连接
│   │   │   └── usePolling.ts     #   轮询 Hook
│   │   ├── 📁 routes/            # 路由配置
│   │   ├── 📁 styles/            # 全局样式
│   │   └── 📁 i18n/              # 国际化
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── .env.example
│
├── 📁 docker/                     # Docker 相关
│   ├── nginx.conf                # Nginx 配置
│   └── README.md                 # Docker 部署文档
│
├── Dockerfile                     # 后端镜像
├── Dockerfile.frontend            # 前端镜像
├── docker-compose.yml             # Docker Compose 编排
├── install-services.sh            # Systemd 安装脚本
├── auto-restart.sh                # 健康检查脚本
├── monitorctl.sh                  # 服务管理工具
├── logrotate.conf                 # 日志轮转配置
└── README.md                      # 项目文档
```

---

## 📈 性能指标

| 指标 | 数值 | 说明 |
|------|------|------|
| 并发监控 | 500+ 会话 | 2核4G配置 |
| 消息延迟 | < 500ms | WebSocket 推送 |
| API 响应 | < 50ms | P95 查询接口 |
| Dashboard | 1次 SQL | 原30+次优化 |
| 导出性能 | 流式分批 | 支持百万级数据 |
| 内存占用 | < 300MB | 后端常驻 |
| 自动恢复 | 5秒 | 故障自动重启 |
| 数据保留 | 可配置 | 自动清理策略 |

---

## 🔧 开发指南

### 本地开发

```bash
# 后端热重载
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 前端热更新
cd frontend
npm run dev
```

### 代码规范

- **后端**: PEP 8, type hints, async/await
- **前端**: ESLint, TypeScript strict mode
- **提交**: Conventional Commits

### 技术决策

| 决策 | 选择 | 原因 |
|------|------|------|
| ORM | SQLAlchemy 2.0 Async | 原生异步，性能优秀 |
| TG客户端 | Telethon | MTProto 协议，稳定可靠 |
| 前端构建 | Vite | 极速 HMR，优化构建 |
| CSS方案 | TailwindCSS | 原子化，快速开发 |
| 部署 | Docker Compose | 一键部署，环境一致 |

---

## ❓ 常见问题

<details>
<summary><b>🔧 首次启动需要做什么？</b></summary>

1. 配置 `backend/.env`（数据库 + Telegram API 凭证 + 代理）
2. 启动后端，自动创建数据库表
3. 访问网页，添加 Telegram 账号（输入手机号 + 验证码）
4. 添加要监控的群组/频道
5. 配置关键词和告警规则

</details>

<details>
<summary><b>🌐 连接 Telegram 失败？</b></summary>

- 确保已配置 `SOCKS5_PROXY`（国内服务器必须）
- 确保代理服务正常运行（`curl --proxy socks5://127.0.0.1:7897 https://api.telegram.org`）
- 检查 API ID 和 Hash 是否正确
- 查看后端日志：`journalctl -u tgjiankong-backend -f`

</details>

<details>
<summary><b>🐳 Docker 部署后端连不上 MySQL？</b></summary>

确保 `.env` 中 `MYSQL_HOST=mysql`（Docker 内网服务名），不是 `localhost`。

</details>

<details>
<summary><b>🐳 Docker 部署后端连不上 Telegram？</b></summary>

需要配置 `SOCKS5_PROXY` 指向宿主机代理：
- Linux: `socks5://宿主机内网IP:7897`
- Mac/Windows: `socks5://host.docker.internal:7897`

</details>

<details>
<summary><b>📊 支持多少个群组监控？</b></summary>

理论上无上限。2核4G建议不超过500个，4核8G可支持2000+。

</details>

<details>
<summary><b>💾 如何备份数据？</b></summary>

- **Docker**: `docker compose exec mysql mysqldump -u root -p tg_monitor > backup.sql`
- **Systemd**: 系统设置页面 → 备份管理 → 自动备份（每天）

</details>

<details>
<summary><b>🔄 如何更新？</b></summary>

- **Docker**: `git pull && docker compose up -d --build`
- **Systemd**: `git pull && sudo systemctl restart tgjiankong-backend tgjiankong-frontend`

</details>

---

## 📋 更新日志

### [v1.2.0](https://github.com/chu0119/tg-monitor/releases/tag/v1.2) - 2026-04-01

#### ⚡ 性能优化
- Dashboard N+1 查询优化（24次 SQL → 1次 GROUP BY）
- Alert Stats 趋势查询优化（7次 → 1次）
- Message Trend N+1 查询修复
- 导出 CSV 流式分批处理（支持百万级数据）
- 关键词趋势查询添加 LIMIT

#### 🐛 Bug 修复
- IN 子句语法错误（SQLAlchemy 动态占位符）
- 批量处理改用后端 batch 接口
- WebSocket JSON.parse 异常处理
- commit 后 db session 使用问题
- XSS 防护（sanitizeHtml 转义）
- 会话名称"匿名"修复

#### 🐳 新功能
- Docker Compose 一键部署
- Nginx 反向代理（API + WebSocket + SPA）
- Mihomo 代理 systemd 服务
- 健康检查 timer（每5分钟巡检）

#### 📝 改进
- 会话列表分页（500 → 50 + 分页）
- 时钟组件 memo 隔离
- Dashboard 错误状态 + 重试
- 批量处理支持 handler_note

### [v1.1.0](https://github.com/chu0119/tg-monitor/releases/tag/v1.1) - 2026-03-31

- 只读频道消息采集
- 会话标题 fallback 修复
- 监控状态 API 修复

### [v1.0.0](https://github.com/chu0119/tg-monitor/releases/tag/v1.0) - 2026-03-30

- 初始版本发布
- 核心监控功能
- 告警系统
- 数据分析

---

## 🤝 贡献指南

欢迎贡献！请遵循以下流程：

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: 添加某个功能'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

### 提交规范

```
feat: 新功能
fix: Bug 修复
docs: 文档更新
style: 代码格式
refactor: 重构
perf: 性能优化
test: 测试
chore: 构建/工具
```

---

## 📄 许可证

[MIT](LICENSE) © 2026 chu0119

---

<div align="center">

**Made with ❤️ by [chu0119](https://github.com/chu0119)**

如果这个项目对你有帮助，请给一个 ⭐ Star！

</div>
