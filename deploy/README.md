# TG Monitor v3 部署套件

生产验证过的部署方式（与 100.110.75.96 实际运行架构一致）。

## 架构

```
nginx(3000) ──静态── frontend/dist
     └──/api /ws──▶ api_worker(8000) ◀──Redis pub/sub── monitor_worker(8010/status:9010)
                          │                                    │
                          └────────── MySQL 8 (tg_monitor_v2) ──┘
                                     sessions/ 文件归 monitor 进程独占
```

## 全新部署（一台 Ubuntu 24.04 裸机）

```bash
git clone https://github.com/chu0119/tg-monitor-v2.git /home/test/tg-monitor
cd /home/test/tg-monitor/deploy
sudo bash install.sh          # 装依赖、建库、构建前端、装 systemd 服务
sudo bash db_migrate.sh       # 建表 + 索引/约束治理（幂等）
sudo systemctl start tgmonitor-api-0 tgmonitor-monitor-0
curl http://localhost:8000/health
# 浏览器打开 http://<ip>:3000 → 跳 /setup 完成初始化向导
```

## 日常更新（已有部署）

```bash
cd /home/test/tg-monitor/deploy
sudo bash update.sh           # git pull → 前端构建 → 跑迁移 → 滚动重启 api/monitor → 健康检查
```

## 文件说明

| 文件 | 用途 |
|---|---|
| install.sh | 一键安装：系统依赖 + Python/Node 环境 + MySQL 库 + 前端构建 + systemd 服务 |
| update.sh | 日常更新：拉代码 → 构建 → 迁移 → 滚动重启 → 健康验证 |
| db_migrate.sh | 数据库迁移包装（backend/scripts/migrate_v3.py，幂等可重跑） |
| tgmonitor-api-0.service | API Worker 单元（含真实参数，替代旧空文件） |
| tgmonitor-monitor-0.service | Monitor Worker 单元 |
| tg-watchdog.service | 看门狗单元 |
| tgmonitor-session-protector.service | Session 保护器单元 |

## 关键约定（务必遵守）

1. **session 文件归 monitor 进程独占**：API 进程不得为已监控账号创建 Telethon 客户端（监控控制走 HTTP 转发 9010）。新增机器扩到多个 monitor worker 时，账号轮询分配自动生效，勿手动同时在两个进程连同一账号
2. **时区口径**：连接级已锚定 +08:00；`created_at` 系列列 = DB NOW() 口径，`messages.date` = UTC，见 REFACTOR_PLAN.md
3. **大表操作**：OPTIMIZE/DDL 必须独占窗口，先跑 `backend/scripts/safe_optimize.sh`（内含长查询与备份检查）
4. **数据库迁移**：全部走 `backend/scripts/migrate_v3.py`（幂等），禁止手工直接 ALTER 后不回写脚本
5. **密钥**：`backend/.env` 永不入库；GitHub 推送用 PAT（建议改用 fine-grained token 并定期轮换）
