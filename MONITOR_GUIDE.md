# 进程守护和自动恢复配置文档

## ✅ 已完成的配置

### 1. Systemd 服务自动重启配置

已更新 `tgjiankong-backend.service` 和 `tgjiankong-frontend.service`：

```ini
# 自动重启策略：无论什么原因退出都自动重启
Restart=always
RestartSec=10         # 重启前等待10秒

# 重启限制：放宽限制以应对频繁卡死
StartLimitBurst=10    # 最多允许10次重启
StartLimitInterval=600 # 10分钟内
StartLimitAction=restart  # 达到限制后继续尝试

# 看门狗定时器：60秒内必须通知存活
WatchdogSec=60

# OOM 保护：降低被系统杀死的优先级
OOMScoreAdjust=-500

# 资源限制
MemoryMax=3G
CPUQuota=300%
```

### 2. 健康监控脚本

创建了 `scripts/health-monitor.sh`，功能包括：

- ✅ 每60秒检查服务健康状态
- ✅ 检测服务卡死（无响应、CPU为0）
- ✅ 检测资源占用异常（内存>500MB、CPU>95%）
- ✅ 自动恢复异常服务
- ✅ 记录监控日志和重启历史

### 3. 监控控制脚本

创建了 `monitorctl.sh` 用于管理监控服务。

---

## 🚀 使用方法

### 启动健康监控

```bash
# 方法1：使用简单启动脚本
./scripts/start-monitor.sh

# 方法2：使用控制脚本（如果systemd服务可用）
./monitorctl.sh start
```

### 停止健康监控

```bash
# 方法1：使用简单停止脚本
./scripts/stop-monitor.sh

# 方法2：使用控制脚本
./monitorctl.sh stop
```

### 查看监控状态

```bash
# 查看监控日志
tail -f logs/health-monitor.log

# 使用控制脚本查看状态
./monitorctl.sh status

# 查看统计信息
./monitorctl.sh stats
```

### 手动测试健康检查

```bash
# 测试服务健康状态
./monitorctl.sh test
```

---

## 📊 监控功能说明

### 健康检查项

| 检查项 | 说明 | 阈值 |
|--------|------|------|
| HTTP响应 | 检查 /health 端点 | 30秒超时 |
| 服务状态 | 检查 JSON 中的 status 字段 | 必须为 "healthy" |
| 内存使用 | 防止内存泄漏 | 500MB |
| CPU使用 | 防止CPU占用过高 | 95% |
| 进程状态 | 检查进程是否卡死 | CPU为0持续15秒 |

### 自动恢复策略

| 异常情况 | 处理方式 |
|----------|----------|
| 健康检查失败 | 重启后端服务 |
| 进程卡死 | 重启后端服务 |
| 资源占用过高 | 记录警告 |
| 前端未运行 | 自动启动前端 |

### 重启限制

- 最多10次自动重启/10分钟
- 5分钟冷却时间
- 退出码100时不重启（用于手动停止）

---

## 📝 日志文件

| 文件 | 说明 |
|------|------|
| `logs/health-monitor.log` | 监控脚本日志 |
| `logs/restart-history.log` | 服务重启历史记录 |
| systemd journal | 使用 `journalctl -u tgjiankong-backend` 查看 |

---

## 🔧 故障排查

### 监控未运行

```bash
# 检查进程
ps aux | grep health-monitor

# 手动启动测试
./scripts/health-monitor.sh
```

### 服务频繁重启

```bash
# 查看重启历史
cat logs/restart-history.log

# 查看后端日志
journalctl -u tgjiankong-backend -f
```

### 健康检查失败

```bash
# 手动测试健康端点
curl http://localhost:8000/health

# 查看详细错误
./monitorctl.sh test
```

---

## 📈 效果验证

### 验证自动重启功能

```bash
# 1. 启动监控
./scripts/start-monitor.sh

# 2. 查看监控日志
tail -f logs/health-monitor.log

# 3. 模拟服务崩溃（在另一个终端）
kill -9 $(pgrep -f "uvicorn app.main:app")

# 4. 观察监控日志，应该看到自动重启
```

### 验证卡死检测

```bash
# 1. 监控会自动检测CPU为0的进程
# 2. 检查日志中的 "进程可能卡死" 警告
tail -f logs/health-monitor.log
```

---

## 🎯 最佳实践

1. **保持监控运行**：使用 `./scripts/start-monitor.sh` 启动
2. **定期检查日志**：`tail -f logs/health-monitor.log`
3. **关注重启历史**：`cat logs/restart-history.log`
4. **资源监控**：使用 `./monitorctl.sh stats`

---

## 📞 需要帮助？

如果监控无法正常工作，请检查：

1. Python 3 是否已安装：`python3 --version`
2. 服务是否在运行：`./service.sh status`
3. 健康端点是否可访问：`curl http://localhost:8000/health`
4. 查看详细错误：`cat logs/health-monitor.log`
