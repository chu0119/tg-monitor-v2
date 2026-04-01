# TG 监控告警系统 - 系统文档

## 系统概述

本项目是一个基于 FastAPI + React 的 Telegram 监控告警系统，用于监控 Telegram 群组/频道消息并进行关键词匹配告警。

## 系统架构

- **后端**: Python 3.12+ / FastAPI / SQLAlchemy / MySQL
- **前端**: React 19 / TypeScript / Vite / Tailwind CSS
- **数据库**: MySQL 8.0+

## 服务配置

### 后端服务 (systemd)

后端使用 systemd 管理，已配置开机自启。

**服务文件**: `/etc/systemd/system/tgjiankong-backend.service`

**管理命令**:
```bash
# 启动服务
sudo systemctl start tgjiankong-backend

# 停止服务
sudo systemctl stop tgjiankong-backend

# 重启服务
sudo systemctl restart tgjiankong-backend

# 查看状态
sudo systemctl status tgjiankong-backend

# 查看日志
tail -f /home/xingchuan/桌面/tgjiankong/logs/backend_service.log
```

### 前端服务 (crontab)

前端使用 crontab @reboot 实现开机自启（systemd 在中文路径下有兼容性问题）。

**管理命令**:
```bash
# 查看自启任务
crontab -l

# 手动启动前端
cd /home/xingchuan/桌面/tgjiankong/frontend
nohup npm run dev > /home/xingchuan/桌面/tgjiankong/logs/frontend_startup.log 2>&1 &

# 停止前端
pkill -f "vite"

# 查看日志
tail -f /home/xingchuan/桌面/tgjiankong/logs/frontend_startup.log
```

## 快速启动脚本

项目根目录提供了快速启动脚本 `start-all.sh`:

```bash
/home/xingchuan/桌面/tgjiankong/start-all.sh
```

此脚本会：
1. 停止所有现有进程
2. 启动后端服务 (端口 8000)
3. 启动前端服务 (端口 5173)

## 访问地址

- **本地访问**: http://localhost:5173
- **外网访问**: http://nas.xiaomuxi.cn (通过雷池反向代理)

## 重要端口

- **后端 API**: 8000
- **前端界面**: 5173
- **MySQL**: 3306

## 日志位置

所有日志存放在 `/home/xingchuan/桌面/tgjiankong/logs/` 目录:

- `backend_service.log` - 后端服务日志 (systemd)
- `backend_service_error.log` - 后端错误日志
- `frontend_startup.log` - 前端启动日志 (手动启动)
- `app.log` - 应用运行日志 (按日期轮转)

## 故障排除

### 后端无法启动

1. 检查服务状态: `sudo systemctl status tgjiankong-backend`
2. 查看错误日志: `tail -f /home/xingchuan/桌面/tgjiankong/logs/backend_service_error.log`
3. 检查 MySQL 连接: `systemctl status mysql`

### 前端无法启动

1. 检查端口占用: `lsof -i :5173`
2. 查看启动日志: `tail -f /home/xingchuan/桌面/tgjiankong/logs/frontend_startup.log`
3. 手动启动测试: `cd /home/xingchuan/桌面/tgjiankong/frontend && npm run dev`

### 重启后服务未自动启动

1. 检查后端: `sudo systemctl status tgjiankong-backend`
   - 如未启用: `sudo systemctl enable tgjiankong-backend`

2. 检查前端: `crontab -l`
   - 应该看到 `@reboot` 条目
   - 如没有，重新运行安装脚本

## 重新安装服务

如果需要重新配置服务，运行:

```bash
sudo bash /home/xingchuan/桌面/tgjiankong/install-services.sh
```

## 系统要求

- Linux 系统 (Ubuntu 20.04+ 推荐)
- Python 3.12+
- Node.js 18+
- MySQL 8.0+
- 至少 2GB 可用内存
- 至少 10GB 可用磁盘空间

## 维护建议

1. **定期清理日志**: 日志文件会自动轮转，但建议定期检查磁盘空间
2. **数据库备份**: 定期备份 MySQL 数据库
3. **监控资源**: 使用 `htop` 或 `systemctl status` 检查服务状态

## 更新记录

- 2026-02-05: 配置 systemd 服务和开机自启
- 2026-02-05: 修复批量操作路由冲突
- 2026-02-05: 添加仪表盘缓存优化

---

**系统版本**: 1.0.0  
**最后更新**: 2026-02-05
