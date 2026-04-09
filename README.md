<div align="center">

# TG Monitor V2
### Telegram 群组/频道智能监控与告警平台

**FastAPI · Telethon · React · MySQL · WebSocket 实时推送**

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?logo=mysql&logoColor=white)

</div>

---

## 1. 项目定位

TG Monitor V2 是一套面向 **Telegram 消息采集、关键词告警、趋势分析与运维可观测** 的全栈系统。

核心目标：
- ✅ 多账号并发接入 Telegram（Telethon）
- ✅ 群组/频道/私聊消息统一采集
- ✅ 关键词匹配 + 告警分级 + 通知分发
- ✅ Web 端统一管理（账号、会话、代理、数据库、备份）
- ✅ 可运维、可回溯、可导出

---

## 2. 技术架构

```text
Browser (React SPA)
        │
        ▼
Nginx (:3000)  ── 静态资源 + /api 反向代理 + /ws
        │
        ▼
FastAPI (:8000)
  ├─ Accounts / Conversations / Messages / Alerts / Settings API
  ├─ Telegram Client Manager (Telethon)
  ├─ Monitoring Pipeline + Keyword Matching
  ├─ Backup / Restore / Diagnostics
  └─ WebSocket Broadcast
        │
        ▼
MySQL 8.0
```

---

## 3. 代理能力（已简化）

> 本项目已移除内置 Clash/Mihomo 节点管理逻辑。

当前代理模型为 **运行时全局代理配置**：
- 协议：`socks5` / `http` / `https`
- 地址：`host`
- 端口：`port`
- 可选鉴权：`username` / `password`

配置后会同步到运行时环境变量（`HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` / `SOCKS5_PROXY`）并应用到主要模块。

---

## 4. 一键部署（推荐）

### 4.1 最简单安装

```bash
git clone https://github.com/chu0119/tg-monitor-v2.git
cd tg-monitor-v2
chmod +x start.sh
./start.sh
```

### 4.2 常用参数

```bash
# 重置部署标记后重装
./start.sh --reset

# 不启用开机自启
./start.sh --no-autostart

# 指定镜像
./start.sh --mirror tsinghua
./start.sh --mirror aliyun
./start.sh --mirror off

# 自定义端口
./start.sh --backend-port 18000 --frontend-port 13000

# 仅部署服务，不重建前端/不重建数据库
./start.sh --skip-frontend-build --skip-db-init
```

### 4.3 支持场景

- Ubuntu 20.04+ / Debian 11+
- root 用户直接执行 或 sudo 用户执行
- 首次全新部署 / 二次升级部署

---

## 5. 初始化流程（Web）

首次打开 `http://<server-ip>:3000`：
1. 配置代理（协议/IP/端口）并测试连通
2. 配置 Telegram API 与账号
3. 可选通知配置
4. 系统标记初始化完成

---

## 6. 数据与运维能力

### 6.1 数据导入导出
- 导出全部配置（系统设置、关键词、通知结构）
- 导出关键词独立备份
- 导入 JSON 配置（增量跳过同名项）

### 6.2 数据库备份与恢复
- 创建备份（可命名）
- 查看备份列表（大小、时间、会话文件数）
- 恢复指定备份（覆盖当前数据库）
- 删除旧备份

### 6.3 诊断与健康检查
- 服务健康探测（`/health`）
- 代理可达性检测
- 数据库连接状态检查

---

## 7. 目录结构

```text
tg-monitor-v2/
├─ backend/
│  ├─ app/
│  │  ├─ api/
│  │  ├─ models/
│  │  ├─ services/
│  │  ├─ telegram/
│  │  └─ main.py
│  ├─ init_db.py
│  └─ requirements.txt
├─ frontend/
│  ├─ src/
│  │  ├─ pages/
│  │  ├─ components/
│  │  └─ lib/api.ts
│  └─ package.json
├─ start.sh
└─ README.md
```

---

## 8. 常用运维命令

```bash
# 后端状态
sudo systemctl status tgmonitor-backend

# 后端日志
journalctl -u tgmonitor-backend -f

# 重启服务
sudo systemctl restart tgmonitor-backend nginx

# 前端可用性
curl -I http://127.0.0.1:3000/

# 后端健康
curl http://127.0.0.1:8000/health
```

---

## 9. 安全建议（生产环境）

- 使用强 MySQL 密码，并限制数据库远程访问
- Nginx 前置 HTTPS（建议 Let’s Encrypt）
- 设置严格 CORS 白名单（不要长期使用 `*`）
- 定期执行备份并做异机存储
- 对高敏感通知渠道使用最小权限 Token

---

## 10. 开发与构建

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

---

## 11. License

MIT
