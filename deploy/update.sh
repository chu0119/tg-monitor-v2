#!/usr/bin/env bash
# 日常更新：拉最新代码 → 构建前端 → 数据库迁移 → 滚动重启 → 健康验证
# 用法: cd <repo>/deploy && sudo bash update.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BRANCH="${1:-main}"

echo "=== [1/5] 拉取代码 ($BRANCH) ==="
cd "$REPO_DIR"
git fetch origin "$BRANCH"
OLD=$(git rev-parse --short HEAD)
git reset --hard "origin/$BRANCH"
NEW=$(git rev-parse --short HEAD)
if [ "$OLD" = "$NEW" ]; then echo "已是最新 ($NEW)"; else echo "$OLD -> $NEW"; fi

echo "=== [2/5] 前端构建 ==="
cd "$REPO_DIR/frontend"
npm install --no-audit --no-fund --silent
npm run build

echo "=== [3/5] 数据库迁移（幂等） ==="
cd "$REPO_DIR/backend"
if [ -x venv/bin/python ]; then PY=venv/bin/python; else PY=python3; fi
$PY scripts/migrate_v3.py --skip-optimize | tail -5

echo "=== [4/5] 滚动重启（api → 间隔30s → monitor） ==="
systemctl restart tgmonitor-api-0
sleep 30
systemctl restart tgmonitor-monitor-0
sleep 10

echo "=== [5/5] 健康验证 ==="
for i in 1 2 3 4 5; do
    if curl -sf -m 10 http://localhost:8000/health > /tmp/tg_health.json; then
        python3 -c "import json; d=json.load(open('/tmp/tg_health.json')); print('status:', d['status'], '| monitors:', d['telegram']['active_monitors'], '| pipeline:', d['alert_pipeline']['status'])"
        exit 0
    fi
    echo "等待服务就绪 ($i/5)..."
    sleep 10
done
echo "!! 健康检查未通过，请查看: journalctl -u tgmonitor-api-0 -n 50"
exit 1
