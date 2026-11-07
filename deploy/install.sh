#!/usr/bin/env bash
# TG Monitor v3 一键安装（Ubuntu 24.04 验证通过）
# 用法: cd <repo>/deploy && sudo bash install.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$REPO_DIR/backend"
FRONTEND="$REPO_DIR/frontend"
DB_NAME="${DB_NAME:-tg_monitor_v2}"
DB_USER="${DB_USER:-tgmonitor}"
DB_PASS="${DB_PASS:-TgMonitor2026Secure}"   # 安装后请自行改强密码并同步 backend/.env
APP_USER="${APP_USER:-$(logname 2>/dev/null || echo test)}"

echo "=== [1/7] 系统依赖 ==="
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip mysql-server redis-server nginx \
    nodejs npm gzip curl >/dev/null
command -v node >/dev/null || { curl -fsSL https://deb.nodesource.com/setup_22.x | bash -; apt-get install -y nodejs; }
systemctl enable --now mysql redis-server nginx

echo "=== [2/7] Python 虚拟环境 ==="
python3 -m venv "$BACKEND/venv"
"$BACKEND/venv/bin/pip" install -q --upgrade pip
"$BACKEND/venv/bin/pip" install -q -r "$BACKEND/requirements.txt"

echo "=== [3/7] MySQL 库与用户 ==="
mysql -e "CREATE DATABASE IF NOT EXISTS $DB_NAME CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -e "CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASS';"
mysql -e "GRANT ALL PRIVILEGES ON $DB_NAME.* TO '$DB_USER'@'localhost'; FLUSH PRIVILEGES;"

echo "=== [4/7] backend/.env ==="
if [ ! -f "$BACKEND/.env" ]; then
    cat > "$BACKEND/.env" <<EOF
DATABASE_TYPE=mysql
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=$DB_USER
MYSQL_PASSWORD=$DB_PASS
MYSQL_DATABASE=$DB_NAME
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
# TELEGRAM_API_ID=你的api_id
# TELEGRAM_API_HASH=你的api_hash
EOF
    echo "已生成 $BACKEND/.env（Telegram API 凭据需自行填写）"
else
    echo "backend/.env 已存在，跳过"
fi

echo "=== [5/7] 目录初始化 ==="
sudo -u "$APP_USER" mkdir -p "$BACKEND/sessions" "$REPO_DIR/logs" "$REPO_DIR/backups" "$REPO_DIR/exports" "$REPO_DIR/uploads"

echo "=== [6/7] 前端构建 ==="
cd "$FRONTEND"
sudo -u "$APP_USER" npm install --no-audit --no-fund
sudo -u "$APP_USER" npm run build

echo "=== [7/7] systemd 服务 ==="
WORKER_DIR="$REPO_DIR/deploy"
sed "s|__REPO_DIR__|$REPO_DIR|g; s|__APP_USER__|$APP_USER|g; s|__VENV__|$BACKEND/venv|g" \
    "$WORKER_DIR/tgmonitor-api-0.service"        > /etc/systemd/system/tgmonitor-api-0.service
sed "s|__REPO_DIR__|$REPO_DIR|g; s|__APP_USER__|$APP_USER|g; s|__VENV__|$BACKEND/venv|g" \
    "$WORKER_DIR/tgmonitor-monitor-0.service"    > /etc/systemd/system/tgmonitor-monitor-0.service
sed "s|__REPO_DIR__|$REPO_DIR|g; s|__APP_USER__|$APP_USER|g" \
    "$WORKER_DIR/tg-watchdog.service"            > /etc/systemd/system/tg-watchdog.service
sed "s|__REPO_DIR__|$REPO_DIR|g; s|__APP_USER__|$APP_USER|g" \
    "$WORKER_DIR/tgmonitor-session-protector.service" > /etc/systemd/system/tgmonitor-session-protector.service

# nginx 站点
cat > /etc/nginx/sites-available/tgmonitor <<'NGINX'
server {
    listen 3000;
    client_max_body_size 200m;
    server_name _;
    root REPLACE_REPO/frontend/dist;
    index index.html;
    location / { try_files $uri $uri/ /index.html; }
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host; proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s; proxy_send_timeout 300s;
    }
    location /health { proxy_pass http://127.0.0.1:8000; proxy_set_header Host $host; }
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade";
    }
}
NGINX
sed -i "s|REPLACE_REPO|$REPO_DIR|g" /etc/nginx/sites-available/tgmonitor
ln -sf /etc/nginx/sites-available/tgmonitor /etc/nginx/sites-enabled/tgmonitor
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

systemctl daemon-reload
systemctl enable tgmonitor-api-0 tgmonitor-monitor-0 tg-watchdog tgmonitor-session-protector

echo ""
echo "✅ 安装完成。后续步骤："
echo "  1. 编辑 $BACKEND/.env 填写 Telegram API 凭据"
echo "  2. cd $REPO_DIR/deploy && sudo bash db_migrate.sh   # 初始化表结构"
echo "  3. sudo systemctl start tgmonitor-api-0 tgmonitor-monitor-0"
echo "  4. 浏览器 http://<ip>:3000 完成 /setup 初始化向导"
