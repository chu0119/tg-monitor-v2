#!/bin/bash
# 使用 gunicorn + uvicorn workers 的生产级启动脚本

cd "$(dirname "$0")"

# 配置
WORKERS=4
WORKER_CLASS="uvicorn.workers.UvicornWorker"
BIND="0.0.0.0:8000"
BACKLOG=4096
TIMEOUT=120
KEEPALIVE=30

# 启动 gunicorn
exec ./venv/bin/gunicorn app.main:app \
  --bind $BIND \
  --workers $WORKERS \
  --worker-class $WORKER_CLASS \
  --backlog $BACKLOG \
  --timeout $TIMEOUT \
  --keep-alive $KEEPALIVE \
  --access-logfile /tmp/tg-monitor-access.log \
  --error-logfile /tmp/tg-monitor-error.log \
  --log-level info \
  --worker-connections 1000 \
  --max-requests 10000 \
  --max-requests-jitter 1000 \
  --preload-app
