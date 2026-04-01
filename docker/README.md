# TG Monitor Docker 部署

## 快速启动

### 1. 准备配置

```bash
# 复制环境变量模板
cp backend/.env.example backend/.env

# 编辑 backend/.env，修改以下配置：
# - MySQL 连接信息（Docker 内网用 mysql 作为 host）
# - Telegram API 凭证
# - SOCKS5 代理（如果宿主机有代理，用 host.docker.internal 或宿主机IP）
```

**Docker 环境下的 `.env` 配置要点：**

```bash
# MySQL - 使用 Docker 内网地址
DATABASE_TYPE=mysql
MYSQL_HOST=mysql          # Docker 服务名，不是 localhost
MYSQL_PORT=3306
MYSQL_USER=tgmonitor
MYSQL_PASSWORD=TgMonitor2026Secure
MYSQL_DATABASE=tg_monitor

# Telegram API
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash

# 代理 - Docker 内访问宿主机代理
# Linux: 用宿主机内网IP（如 192.168.1.100）
# Mac/Windows: 用 host.docker.internal
SOCKS5_PROXY=socks5://192.168.1.100:7897
```

### 2. 一键启动

```bash
docker compose up -d
```

### 3. 访问

- 前端: http://your-server-ip
- 后端 API: http://your-server-ip/api/
- 健康检查: http://your-server-ip/health

### 4. 查看日志

```bash
# 所有服务
docker compose logs -f

# 单个服务
docker compose logs -f backend
docker compose logs -f mysql
```

### 5. 停止

```bash
docker compose down
# 保留数据
docker compose down

# 清除数据（危险！会删除数据库）
docker compose down -v
```

## 服务架构

```
┌─────────────────────────────────────────┐
│  Nginx (:80)                            │
│  ├── /           → 前端静态文件          │
│  ├── /api/*      → Backend (:8000)       │
│  ├── /ws         → WebSocket → Backend   │
│  └── /health     → Backend               │
└─────────────────────────────────────────┘
         │
┌────────────────┐    ┌────────────────┐
│ Backend (:8000)│───→│ MySQL (:3306)  │
└────────────────┘    └────────────────┘
```

## 数据持久化

Docker 使用命名卷存储数据，容器重建后数据不丢失：

| 卷名 | 用途 |
|------|------|
| `mysql_data` | MySQL 数据库文件 |
| `backend_sessions` | Telegram 登录会话 |
| `backend_logs` | 应用日志 |
| `backend_exports` | 导出文件 |

## 常见问题

### Q: 后端连不上 MySQL？
确保 `MYSQL_HOST=mysql`（不是 localhost），因为 Docker 内网用服务名通信。

### Q: 后端连不上 Telegram？
需要配置 `SOCKS5_PROXY` 指向宿主机的代理地址：
- Linux: `socks5://宿主机内网IP:7897`
- Mac/Windows: `socks5://host.docker.internal:7897`

### Q: 如何备份数据库？
```bash
docker compose exec mysql mysqldump -u root -p tg_monitor > backup.sql
```

### Q: 如何更新？
```bash
git pull
docker compose up -d --build
```
