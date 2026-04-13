#!/bin/bash
set -e

# tg-monitor-v2 一键部署脚本
# 用法: bash <(curl -sL https://raw.githubusercontent.com/chu0119/tg-monitor-v2/main/install.sh)

REPO_URL="https://github.com/chu0119/tg-monitor-v2.git"
APP_DIR="/opt/tg-monitor-v2"
SERVICE_USER="tgmonitor"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# 1. 检查系统依赖
check_deps() {
    info "检查系统依赖..."
    for cmd in python3 node npm mysql; do
        if ! command -v $cmd &>/dev/null; then
            error "$cmd 未安装，请先安装: sudo apt install python3 python3-pip nodejs npm mysql-server"
        fi
    done
    info "所有依赖已满足"
}

# 2. 克隆/更新仓库
clone_repo() {
    if [ -d "$APP_DIR" ]; then
        warn "目录 $APP_DIR 已存在，跳过克隆"
        cd "$APP_DIR"
    else
        info "克隆仓库到 $APP_DIR ..."
        sudo git clone "$REPO_URL" "$APP_DIR"
        cd "$APP_DIR"
    fi
}

# 3. 安装后端依赖
install_backend() {
    info "安装后端依赖..."
    cd "$APP_DIR/backend"
    sudo python3 -m pip install -r requirements.txt -q
}

# 4. 安装前端依赖 & 构建
install_frontend() {
    info "安装前端依赖..."
    cd "$APP_DIR/frontend"
    sudo npm install --silent
    info "构建前端..."
    sudo npm run build
}

# 5. 配置 .env
configure_env() {
    cd "$APP_DIR/backend"
    if [ -f .env ]; then
        warn ".env 已存在，跳过配置"
        return
    fi

    info "配置 .env（按回车使用默认值）..."
    read -p "MySQL 密码 [TgMonitor2026Secure]: " DB_PASS
    DB_PASS=${DB_PASS:-TgMonitor2026Secure}
    read -p "MySQL 数据库名 [tg_monitor_v2]: " DB_NAME
    DB_NAME=${DB_NAME:-tg_monitor_v2}
    read -p "服务端口 [8000]: " PORT
    PORT=${PORT:-8000}

    sudo tee .env > /dev/null <<EOF
# Database
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=tgmonitor
MYSQL_PASSWORD=${DB_PASS}
MYSQL_DATABASE=${DB_NAME}

# App
APP_HOST=0.0.0.0
APP_PORT=${PORT}

# Telegram API
TELEGRAM_API_ID=
TELEGRAM_API_HASH=

# Proxy (optional)
PROXY_HOST=
PROXY_PORT=7897
PROXY_ENABLED=false
EOF
    info ".env 配置完成"
}

# 6. 初始化数据库
init_database() {
    info "创建 MySQL 用户和数据库..."
    cd "$APP_DIR/backend"
    source .env 2>/dev/null || true
    DB_PASS=${MYSQL_PASSWORD:-TgMonitor2026Secure}
    DB_NAME=${MYSQL_DATABASE:-tg_monitor_v2}

    sudo mysql -u root <<EOF
CREATE USER IF NOT EXISTS 'tgmonitor'@'localhost' IDENTIFIED BY '${DB_PASS}';
CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO 'tgmonitor'@'localhost';
FLUSH PRIVILEGES;
EOF

    info "初始化数据库表..."
    sudo python3 init_db.py
}

# 7. 配置 systemd 服务
configure_systemd() {
    info "配置 systemd 服务..."

    sudo tee /etc/systemd/system/tg-monitor.service > /dev/null <<EOF
[Unit]
Description=TG Monitor v2 Backend
After=network.target mysql.service

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR/backend
ExecStart=$(which python3) -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable tg-monitor
    info "systemd 服务配置完成"
}

# 8. 启动服务
start_service() {
    info "启动服务..."
    sudo systemctl start tg-monitor
    sleep 2
    if sudo systemctl is-active --quiet tg-monitor; then
        info "服务启动成功！"
    else
        error "服务启动失败，请检查: journalctl -u tg-monitor -n 50"
    fi
}

# 9. 显示访问地址
show_info() {
    IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  TG Monitor v2 部署完成！${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "  访问地址: ${YELLOW}http://${IP}:8000${NC}"
    echo -e "  API文档:  ${YELLOW}http://${IP}:8000/docs${NC}"
    echo -e "  服务管理: ${YELLOW}sudo systemctl start/stop/restart tg-monitor${NC}"
    echo -e "  查看日志: ${YELLOW}sudo journalctl -u tg-monitor -f${NC}"
    echo ""
}

# 主流程
main() {
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  TG Monitor v2 一键部署脚本${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""

    check_deps
    clone_repo
    install_backend
    install_frontend
    configure_env
    init_database
    configure_systemd
    start_service
    show_info
}

main "$@"
