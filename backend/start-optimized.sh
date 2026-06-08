#!/bin/bash
# 优化启动脚本

cd "$(dirname "$0")"

# 使用多worker模式提高并发性能
# workers = (2 * CPU核心数) + 1
WORKERS=4

# 每个worker的backlog
BACKLOG=4096

# 启动uvicorn
./venv/bin/python -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers $WORKERS \
  --backlog $BACKLOG \
  --limit-concurrency 1000 \
  --timeout-keep-alive 30 \
  --log-level info \
  > /tmp/tg-monitor.log 2>&1
