#!/usr/bin/env bash
# 数据库迁移包装（幂等可重跑）
# 用法: cd <repo>/deploy && bash db_migrate.sh [--skip-optimize]
set -euo pipefail
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR/backend"
if [ -x venv/bin/python ]; then PY=venv/bin/python; else PY=python3; fi
$PY scripts/migrate_v3.py "$@"
