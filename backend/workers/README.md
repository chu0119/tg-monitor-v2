# TG Monitor 多Worker架构

## 架构说明

本架构将系统拆分为多个独立运行的Worker，每个Worker负责不同的任务：

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

## Worker类型

### API Worker
- **职责**: 处理HTTP请求（前端API）
- **端口**: 8000, 8001, ...
- **数量**: 1-4个（根据CPU核心数）
- **特点**: 无状态，可水平扩展

### Monitor Worker
- **职责**: 运行Telegram监控
- **端口**: 8010, 8011, ... (监控) + 9010, 9011, ... (状态API)
- **数量**: 根据账号数量决定
- **每个Worker**: 管理3-5个账号

## 快速部署

### 方式一：自动部署脚本

```bash
cd /home/test/tg-monitor/backend/workers
chmod +x deploy.sh
sudo bash deploy.sh 2 3  # 2个API Worker，3个Monitor Worker
```

### 方式二：手动部署

```bash
# 1. 复制service文件
sudo cp tgmonitor-api-*.service /etc/systemd/system/
sudo cp tgmonitor-monitor-*.service /etc/systemd/system/

# 2. 重新加载systemd
sudo systemctl daemon-reload

# 3. 启动服务
sudo systemctl start tgmonitor-api-0
sudo systemctl start tgmonitor-api-1
sudo systemctl start tgmonitor-monitor-0
sudo systemctl start tgmonitor-monitor-1
sudo systemctl start tgmonitor-monitor-2

# 4. 设置开机自启
sudo systemctl enable tgmonitor-api-* tgmonitor-monitor-*
```

### 方式三：本地测试

```bash
cd /home/test/tg-monitor/backend
python -m app.workers.api_worker  # 启动API Worker
python -m app.workers.monitor_worker  # 启动Monitor Worker
```

## 配置文件

### config.json

```json
{
  "api_workers": 2,
  "monitor_workers": 3,
  "accounts_per_worker": 5,
  "worker_ports": {
    "api": [8000, 8001],
    "monitor": [8010, 8011, 8012]
  },
  "session_dir": "sessions",
  "log_dir": "logs",
  "database": {
    "pool_size": 20,
    "max_overflow": 30
  },
  "monitor": {
    "queue_maxsize": 2000,
    "batch_size": 50,
    "semaphore_limit": 10,
    "heartbeat_interval": 30,
    "startup_timeout": 5.0
  }
}
```

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `WORKER_ID` | Worker编号 | 0 |
| `WORKER_TYPE` | Worker类型 (api/monitor) | api |
| `MYSQL_HOST` | MySQL主机 | localhost |
| `MYSQL_PASSWORD` | MySQL密码 | - |
| `SOCKS5_PROXY` | 代理地址 | - |

## 目录结构

```
workers/
├── config.json              # Worker配置
├── deploy.sh                # 部署脚本
├── nginx.conf               # Nginx配置
├── README.md                # 本文档
├── tgmonitor-api-0.service  # API Worker服务文件
├── tgmonitor-monitor-0.service  # Monitor Worker服务文件
└── start-local.ps1          # 本地测试脚本(Windows)
```

## 监控和日志

### 查看日志

```bash
# API Worker日志
tail -f /home/test/tg-monitor/logs/api_worker_0.log

# Monitor Worker日志
tail -f /home/test/tg-monitor/logs/monitor_worker_0.log
```

### 查看状态

```bash
# 查看所有服务状态
systemctl status tgmonitor-api-* tgmonitor-monitor-*

# 查看Monitor Worker状态API
curl http://localhost:9010/status
```

### 健康检查

```bash
# 通过Nginx检查
curl http://localhost:3000/health

# 直接检查API Worker
curl http://localhost:8000/api/v1/health
```

## 扩展指南

### 添加更多API Worker

1. 修改 `config.json` 中的 `api_workers` 数量
2. 修改 `deploy.sh` 中的端口配置
3. 重新运行部署脚本

### 添加更多Monitor Worker

1. 修改 `config.json` 中的 `monitor_workers` 数量
2. 修改 `accounts_per_worker` 配置
3. 重新运行部署脚本

### 账号分配

账号按顺序分配给Monitor Worker：
- Worker 0: 账号 1-5
- Worker 1: 账号 6-10
- Worker 2: 账号 11-15
- ...

## 故障排除

### 问题：账号未连接

```bash
# 检查Monitor Worker日志
tail -50 /home/test/tg-monitor/logs/monitor_worker_0.log

# 检查账号授权状态
mysql -u tgmonitor -p tg_monitor_v2 -e "SELECT id, phone, is_authorized FROM telegram_accounts;"
```

### 问题：服务启动失败

```bash
# 检查服务状态
systemctl status tgmonitor-monitor-0

# 查看详细错误
journalctl -u tgmonitor-monitor-0 -n 50
```

### 问题：端口冲突

```bash
# 查看端口占用
netstat -tlnp | grep -E "800[0-9]|801[0-9]"

# 修改config.json中的端口配置
```

## 性能优化

### 建议配置

| 服务器配置 | API Workers | Monitor Workers | 每Worker账号数 |
|-----------|-------------|-----------------|---------------|
| 2核4G | 1 | 2 | 5 |
| 4核8G | 2 | 3 | 5 |
| 8核16G | 4 | 6 | 5 |
| 16核32G | 6 | 10 | 5 |

### 监控指标

- API响应时间
- 消息处理速率
- 内存使用率
- CPU使用率
- 数据库连接数

## 注意事项

1. **单Worker限制**: 每个Monitor Worker只能运行在单进程模式
2. **Session隔离**: 每个Worker使用独立的Session目录
3. **数据库共享**: 所有Worker共享同一个MySQL数据库
4. **代理配置**: 所有Worker使用相同的代理配置
5. **重启顺序**: 先启动Monitor Worker，再启动API Worker
