#!/bin/bash
# TG Monitor 多Worker自动化部署脚本
# 用法: bash deploy-auto.sh [api_workers] [monitor_workers]

set -e

# 默认配置
API_WORKERS=${1:-1}
MONITOR_WORKERS=${1:-1}
PROJECT_DIR="/home/test/tg-monitor"
BACKEND_DIR="$PROJECT_DIR/backend"

echo "=========================================="
echo "TG Monitor 多Worker自动化部署"
echo "=========================================="
echo "API Workers: $API_WORKERS"
echo "Monitor Workers: $MONITOR_WORKERS"
echo ""

# 1. 停止现有服务
echo "1. 停止现有服务..."
systemctl stop tgmonitor-backend 2>/dev/null || true
systemctl disable tgmonitor-backend 2>/dev/null || true
sleep 2

# 2. 备份配置
echo "2. 备份配置..."
backup_dir="$PROJECT_DIR/backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$backup_dir"
cp "$BACKEND_DIR/workers/config.json" "$backup_dir/" 2>/dev/null || true
cp "$BACKEND_DIR/.env" "$backup_dir/" 2>/dev/null || true

# 3. 更新配置文件
echo "3. 更新配置文件..."
cat > "$BACKEND_DIR/workers/config.json" << EOF
{
  "api_workers": $API_WORKERS,
  "monitor_workers": $MONITOR_WORKERS,
  "accounts_per_worker": 5,
  "worker_ports": {
    "api": [$(seq -s, 8000 $((8000 + API_WORKERS - 1)))],
    "monitor": [$(seq -s, 8010 $((8010 + MONITOR_WORKERS - 1)))]
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
EOF

# 4. 创建Session目录
echo "4. 创建Session目录..."
for i in $(seq 0 $((MONITOR_WORKERS - 1))); do
    mkdir -p "$PROJECT_DIR/sessions/worker_$i"
done

# 5. 安装Systemd服务
echo "5. 安装Systemd服务..."

# API Workers
for i in $(seq 0 $((API_WORKERS - 1))); do
    cat > "/etc/systemd/system/tgmonitor-api-$i.service" << EOF
[Unit]
Description=TG Monitor API Worker $i
After=network.target mysql.service redis.service

[Service]
Type=simple
User=root
WorkingDirectory=$BACKEND_DIR
ExecStart=/usr/bin/python3 -m app.workers.api_worker
Restart=always
RestartSec=5
MemoryMax=2G
Environment=WORKER_ID=$i
Environment=WORKER_TYPE=api
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
done

# Monitor Workers
for i in $(seq 0 $((MONITOR_WORKERS - 1))); do
    start_id=$((i * 5 + 1))
    end_id=$((start_id + 4))
    cat > "/etc/systemd/system/tgmonitor-monitor-$i.service" << EOF
[Unit]
Description=TG Monitor Worker $i (Accounts $start_id-$end_id)
After=network.target mysql.service redis.service

[Service]
Type=simple
User=root
WorkingDirectory=$BACKEND_DIR
ExecStart=/usr/bin/python3 -m app.workers.monitor_worker
Restart=always
RestartSec=10
MemoryMax=2G
Environment=WORKER_ID=$i
Environment=WORKER_TYPE=monitor
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
done

systemctl daemon-reload

# 6. 启动服务
echo "6. 启动服务..."

# 启动API Workers
for i in $(seq 0 $((API_WORKERS - 1))); do
    systemctl start "tgmonitor-api-$i"
    systemctl enable "tgmonitor-api-$i"
    echo "  API Worker $i 启动成功"
done

# 启动Monitor Workers
for i in $(seq 0 $((MONITOR_WORKERS - 1))); do
    systemctl start "tgmonitor-monitor-$i"
    systemctl enable "tgmonitor-monitor-$i"
    echo "  Monitor Worker $i 启动成功"
done

# 7. 等待启动
echo "7. 等待服务启动..."
sleep 10

# 8. 检查状态
echo "8. 检查服务状态..."
echo ""
echo "API Workers:"
for i in $(seq 0 $((API_WORKERS - 1))); do
    status=$(systemctl is-active "tgmonitor-api-$i" 2>/dev/null || echo "inactive")
    echo "  Worker $i: $status"
done

echo ""
echo "Monitor Workers:"
for i in $(seq 0 $((MONITOR_WORKERS - 1))); do
    status=$(systemctl is-active "tgmonitor-monitor-$i" 2>/dev/null || echo "inactive")
    echo "  Worker $i: $status"
done

# 9. 测试API
echo ""
echo "9. 测试API..."
curl -s http://localhost:8000/ | python3 -m json.tool 2>/dev/null || echo "API测试失败"

echo ""
echo "=========================================="
echo "部署完成！"
echo "=========================================="
echo ""
echo "访问地址: http://$(hostname -I | awk '{print $1}'):3000"
echo "API地址: http://$(hostname -I | awk '{print $1}'):8000"
echo ""
echo "查看日志:"
echo "  tail -f $PROJECT_DIR/logs/api_worker_0.log"
echo "  tail -f $PROJECT_DIR/logs/monitor_worker_0.log"
echo ""
echo "停止服务:"
echo "  systemctl stop tgmonitor-api-* tgmonitor-monitor-*"
echo ""
echo "重启服务:"
echo "  systemctl restart tgmonitor-api-* tgmonitor-monitor-*"
echo ""
