#!/bin/bash
# ============================================
# 听风追影 (TG Monitor v2) - 一键部署脚本
# 支持 Ubuntu 20.04+ / Debian 11+ / CentOS 8+
# ============================================
set -e

REPO_URL="https://github.com/chu0119/tg-monitor-v2.git"
APP_DIR="/opt/tg-monitor-v2"
SERVICE_USER="tgmonitor"
STATE_FILE="/tmp/tg_monitor_install_state"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }
step()  { echo -e "\n${BLUE}==== $* ====${NC}"; }
fail()  { error "$*"; echo -e "${RED}建议: $1${NC}"; exit 1; }

mark_done() { echo "$1" >> "$STATE_FILE"; }
is_done()   { grep -qx "$1" "$STATE_FILE" 2>/dev/null; }

# ==================== 步骤0: 系统检测 ====================
detect_system() {
    if is_done "system_check"; then
        info "系统检测已完成，跳过"
        return
    fi
    step "系统检测"

    # 检测root
    if [ "$EUID" -ne 0 ]; then
        warn "非root用户运行，将尝试使用sudo"
        if ! command -v sudo &>/dev/null; then
            fail "未安装sudo" "请使用root用户运行，或先安装sudo: apt install sudo / yum install sudo"
        fi
        SUDO="sudo"
    else
        SUDO=""
    fi

    # 检测OS
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS_ID="$ID"
        OS_VERSION="$VERSION_ID"
        case "$OS_ID" in
            ubuntu|debian) PKG_MANAGER="apt" ;;
            centos|rhel|rocky|almalinux) PKG_MANAGER="yum" ;;
            *) fail "不支持的系统: $OS_ID" "目前仅支持 Ubuntu/Debian/CentOS/Rocky/AlmaLinux" ;;
        esac
    else
        fail "无法检测操作系统" "需要 /etc/os-release，请确认系统版本"
    fi

    # 检测架构
    ARCH=$(uname -m)
    case "$ARCH" in
        x86_64|amd64) ARCH="x86_64" ;;
        aarch64|arm64) ARCH="arm64" ;;
        *) fail "不支持的架构: $ARCH" "仅支持 x86_64 和 arm64" ;;
    esac

    info "系统: $OS_ID $OS_VERSION ($ARCH) | 包管理器: $PKG_MANAGER"
    mark_done "system_check"
}

# ==================== 步骤1: 依赖安装 ====================
install_dependencies() {
    if is_done "dependencies"; then
        info "依赖安装已完成，跳过"
        return
    fi
    step "安装系统依赖"

    if [ "$PKG_MANAGER" = "apt" ]; then
        $SUDO apt-get update -qq
        $SUDO apt-get install -y -qq git curl wget build-essential libffi-dev libssl-dev
    else
        $SUDO yum install -y -q git curl wget gcc make openssl-devel
    fi

    # Python 3.11+
    info "检查 Python..."
    PYTHON_CMD=""
    for py in python3.12 python3.11 python3; do
        if command -v $py &>/dev/null; then
            PY_VER=$($py -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
            PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
            PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
            if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 11 ]; then
                PYTHON_CMD=$py
                break
            fi
        fi
    done

    if [ -z "$PYTHON_CMD" ]; then
        warn "未找到 Python 3.11+，尝试安装..."
        if [ "$PKG_MANAGER" = "apt" ]; then
            $SUDO apt-get install -y -qq software-properties-common
            $SUDO add-apt-repository -y ppa:deadsnakes/ppa
            $SUDO apt-get update -qq
            $SUDO apt-get install -y -qq python3.11 python3.11-venv python3.11-dev python3-pip
            PYTHON_CMD=python3.11
        else
            warn "CentOS/RHEL 请手动安装 Python 3.11+:"
            warn "  yum install -y gcc openssl-devel bzip2-devel libffi-devel zlib-devel"
            warn "  curl -sS https://www.python.org/ftp/python/3.11.9/Python-3.11.9.tgz | tar xz"
            warn "  cd Python-3.11.9 && ./configure --enable-optimizations && make altinstall"
            fail "需要 Python 3.11+" "请按上述提示手动安装后重新运行本脚本"
        fi
    fi
    info "Python: $($PYTHON_CMD --version)"

    # Node.js 18+
    info "检查 Node.js..."
    NODE_VERSION=""
    if command -v node &>/dev/null; then
        NODE_VERSION=$(node -v | sed 's/^v//' | cut -d. -f1)
    fi

    if [ -z "$NODE_VERSION" ] || [ "$NODE_VERSION" -lt 18 ]; then
        warn "未找到 Node.js 18+，通过nvm安装..."
        export NVM_DIR="$HOME/.nvm"
        if [ ! -s "$NVM_DIR/nvm.sh" ]; then
            curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
        fi
        . "$NVM_DIR/nvm.sh"
        nvm install --lts
        nvm use --lts
    fi
    info "Node.js: $(node --version) | npm: $(npm --version)"

    # MySQL/MariaDB
    info "检查 MySQL/MariaDB..."
    if ! command -v mysql &>/dev/null && ! command -v mysqld &>/dev/null && ! command -v mariadb &>/dev/null; then
        warn "未安装 MySQL/MariaDB，正在安装..."
        if [ "$PKG_MANAGER" = "apt" ]; then
            $SUDO DEBIAN_FRONTEND=noninteractive apt-get install -y -qq mariadb-server mariadb-client
            $SUDO service mariadb start || $SUDO systemctl start mariadb
        else
            $SUDO yum install -y -q mariadb-server mariadb
            $SUDO systemctl enable mariadb
            $SUDO systemctl start mariadb
        fi
        info "MySQL/MariaDB 安装完成"
    else
        info "MySQL/MariaDB 已安装"
    fi

    # pip
    if ! $PYTHON_CMD -m pip --version &>/dev/null; then
        $PYTHON_CMD -m ensurepip --upgrade 2>/dev/null || {
            curl -sS https://bootstrap.pypa.io/get-pip.py | $PYTHON_CMD
        }
    fi

    mark_done "dependencies"
}

# ==================== 步骤2: 项目部署 ====================
deploy_project() {
    if is_done "project_deploy"; then
        info "项目部署已完成，跳过"
        return
    fi
    step "部署项目"

    if [ -d "$APP_DIR/.git" ]; then
        info "项目目录已存在，执行 git pull..."
        cd "$APP_DIR"
        git pull
    else
        info "克隆项目..."
        git clone "$REPO_URL" "$APP_DIR"
        cd "$APP_DIR"
    fi

    # 后端依赖
    info "安装后端依赖..."
    cd "$APP_DIR/backend"
    if [ ! -d "venv" ]; then
        $PYTHON_CMD -m venv venv
    fi
    . venv/bin/activate
    pip install --upgrade pip -q
    if [ -f requirements.txt ]; then
        pip install -r requirements.txt -q
    fi

    # 前端依赖
    info "安装前端依赖..."
    cd "$APP_DIR/frontend"
    # 确保nvm可用
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
    npm install --silent 2>/dev/null || npm install

    mark_done "project_deploy"
}

# ==================== 步骤3: 数据库配置 ====================
setup_database() {
    if is_done "database_setup"; then
        info "数据库配置已完成，跳过"
        return
    fi
    step "数据库配置"

    read -rsp "请输入 MySQL/MariaDB root 密码 (回车跳过，留空则无密码): " DB_ROOT_PASS
    echo ""

    DB_NAME="tg_monitor"
    DB_USER="tgmonitor"
    DB_PASS=""

    # 生成随机密码
    DB_PASS=$(openssl rand -hex 16)

    MYSQL_CMD="mysql"
    if [ -n "$DB_ROOT_PASS" ]; then
        MYSQL_CMD="mysql -u root -p$DB_ROOT_PASS"
    fi

    # 确保服务运行
    if [ "$PKG_MANAGER" = "apt" ]; then
        $SUDO service mariadb start 2>/dev/null || $SUDO service mysql start 2>/dev/null || true
    else
        $SUDO systemctl start mariadb 2>/dev/null || $SUDO systemctl start mysqld 2>/dev/null || true
    fi

    # 创建数据库和用户
    info "创建数据库和用户..."
    $MYSQL_CMD -e "
        CREATE DATABASE IF NOT EXISTS \`$DB_NAME\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASS';
        GRANT ALL PRIVILEGES ON \`$DB_NAME\`.* TO '$DB_USER'@'localhost';
        FLUSH PRIVILEGES;
    " 2>/dev/null || fail "数据库创建失败" "请检查root密码是否正确，MySQL服务是否已启动"

    # 初始化数据库
    info "初始化数据库表结构..."
    cd "$APP_DIR/backend"
    . venv/bin/activate
    if [ -f init_db.py ]; then
        MYSQL_HOST=localhost MYSQL_PORT=3306 MYSQL_USER=$DB_USER MYSQL_PASSWORD=$DB_PASS MYSQL_DATABASE=$DB_NAME \
        python init_db.py
    fi

    # 保存数据库配置供后续使用
    cat > /tmp/tg_monitor_db_config <<EOF
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=$DB_USER
MYSQL_PASSWORD=$DB_PASS
MYSQL_DATABASE=$DB_NAME
EOF

    info "数据库配置完成 (用户: $DB_USER, 数据库: $DB_NAME)"
    mark_done "database_setup"
}

# ==================== 步骤4: 环境配置 ====================
setup_env() {
    if is_done "env_setup"; then
        info "环境配置已完成，跳过"
        return
    fi
    step "环境配置 (.env)"

    cd "$APP_DIR/backend"
    ENV_FILE=".env"

    if [ -f "$ENV_FILE" ]; then
        warn ".env 已存在，将保留现有配置，仅补充缺失项"
    fi

    # 加载数据库配置
    if [ -f /tmp/tg_monitor_db_config ]; then
        . /tmp/tg_monitor_db_config
    fi

    # 交互式填写
    echo ""
    info "配置 Telegram API (访问 https://my.telegram.org/apps 获取)"
    read -rp "  API ID (留空跳过): " API_ID
    read -rp "  API Hash (留空跳过): " API_HASH
    echo ""
    read -rp "  代理地址 (如 http://127.0.0.1:7890，留空跳过): " PROXY
    read -rp "  监听端口 (默认8000): " PORT
    PORT=${PORT:-8000}
    read -rp "  SECRET_KEY (留空自动生成): " SECRET_KEY
    SECRET_KEY=${SECRET_KEY:-$(openssl rand -hex 32)}

    # 写入.env
    {
        echo "# TG 监控告警系统 - 自动生成"
        echo ""
        echo "# 数据库配置"
        echo "DATABASE_TYPE=mysql"
        echo "MYSQL_HOST=localhost"
        echo "MYSQL_PORT=3306"
        echo "MYSQL_USER=${MYSQL_USER:-tgmonitor}"
        echo "MYSQL_PASSWORD=${MYSQL_PASSWORD:-}"
        echo "MYSQL_DATABASE=${MYSQL_DATABASE:-tg_monitor}"
        echo ""
        echo "# Telegram API"
        echo "TELEGRAM_API_ID=${API_ID:-}"
        echo "TELEGRAM_API_HASH=${API_HASH:-}"
        echo ""
        echo "# 服务器配置"
        echo "HOST=0.0.0.0"
        echo "PORT=${PORT}"
        echo "DEBUG=false"
        echo "LOG_LEVEL=INFO"
        echo ""
        echo "# 安全配置"
        echo "SECRET_KEY=${SECRET_KEY}"
        echo "ACCESS_TOKEN_EXPIRE_MINUTES=240"
        echo ""
        echo "# CORS 配置"
        echo "CORS_ORIGINS=*"
    } > "$ENV_FILE"

    # 合并已有配置中非默认的值
    if [ -f "$ENV_FILE.bak" ]; then
        while IFS='=' read -r key value; do
            [ -z "$key" ] || [[ "$key" =~ ^# ]] && continue
            # 如果用户之前配置了代理等，保留
            if grep -q "^${key}=" "$ENV_FILE"; then
                sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
            fi
        done < "$ENV_FILE.bak"
    fi

    # 追加代理配置
    if [ -n "$PROXY" ]; then
        echo "" >> "$ENV_FILE"
        echo "# 代理配置" >> "$ENV_FILE"
        echo "HTTP_PROXY=${PROXY}" >> "$ENV_FILE"
        echo "HTTPS_PROXY=${PROXY}" >> "$ENV_FILE"
    fi

    info ".env 配置完成: $ENV_FILE"
    mark_done "env_setup"
}

# ==================== 步骤5: systemd 服务 ====================
setup_services() {
    if is_done "services_setup"; then
        info "systemd 服务已配置，跳过"
        return
    fi
    step "配置 systemd 服务"

    # 确定nvm node路径
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
    NODE_PATH=$(which node)

    # 后端服务
    $SUDO tee /etc/systemd/system/tg-monitor-v2-backend.service > /dev/null <<EOF
[Unit]
Description=TG Monitor v2 Backend
After=network.target mysql.service mariadb.service
Wants=mysql.service mariadb.service

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR/backend
ExecStart=$APP_DIR/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
Restart=always
RestartSec=5
EnvironmentFile=$APP_DIR/backend/.env

[Install]
WantedBy=multi-user.target
EOF

    # 前端服务
    $SUDO tee /etc/systemd/system/tg-monitor-v2-frontend.service > /dev/null <<EOF
[Unit]
Description=TG Monitor v2 Frontend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR/frontend
ExecStart=$NODE_PATH $APP_DIR/frontend/node_modules/.bin/vite --host 0.0.0.0 --port 5173
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    $SUDO systemctl daemon-reload
    $SUDO systemctl enable tg-monitor-v2-backend
    $SUDO systemctl enable tg-monitor-v2-frontend

    info "systemd 服务配置完成"
    mark_done "services_setup"
}

# ==================== 步骤6: 启动验证 ====================
start_and_verify() {
    step "启动服务"

    $SUDO systemctl restart tg-monitor-v2-backend
    $SUDO systemctl restart tg-monitor-v2-frontend

    sleep 3

    # 检查后端
    BACKEND_STATUS=$($SUDO systemctl is-active tg-monitor-v2-backend)
    if [ "$BACKEND_STATUS" = "active" ]; then
        info "✅ 后端服务运行正常"
    else
        warn "⚠️  后端服务异常，请检查: journalctl -u tg-monitor-v2-backend -n 50"
    fi

    # 检查前端
    FRONTEND_STATUS=$($SUDO systemctl is-active tg-monitor-v2-frontend)
    if [ "$FRONTEND_STATUS" = "active" ]; then
        info "✅ 前端服务运行正常"
    else
        warn "⚠️  前端服务异常，请检查: journalctl -u tg-monitor-v2-frontend -n 50"
    fi

    # 健康检查
    sleep 2
    if curl -sf "http://localhost:${PORT:-8000}/api/v1/health" &>/dev/null; then
        info "✅ API 健康检查通过"
    else
        warn "⚠️  API 健康检查未通过（可能还在启动中，稍等片刻再试）"
    fi

    echo ""
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}  听风追影部署完成！${NC}"
    echo -e "${GREEN}============================================${NC}"
    echo ""
    echo -e "  前端地址: ${BLUE}http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost'):5173${NC}"
    echo -e "  后端地址: ${BLUE}http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost'):${PORT:-8000}${NC}"
    echo -e "  后端API:  ${BLUE}http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost'):${PORT:-8000}/docs${NC}"
    echo ""
    echo -e "  常用命令:"
    echo -e "    查看后端日志: ${YELLOW}journalctl -u tg-monitor-v2-backend -f${NC}"
    echo -e "    查看前端日志: ${YELLOW}journalctl -u tg-monitor-v2-frontend -f${NC}"
    echo -e "    重启后端:     ${YELLOW}systemctl restart tg-monitor-v2-backend${NC}"
    echo -e "    重启前端:     ${YELLOW}systemctl restart tg-monitor-v2-frontend${NC}"
    echo ""

    # 清理状态文件
    rm -f "$STATE_FILE"
}

# ==================== 主流程 ====================
main() {
    echo -e "${BLUE}"
    echo "  ╔══════════════════════════════════════╗"
    echo "  ║   听风追影 TG Monitor v2 部署脚本    ║"
    echo "  ╚══════════════════════════════════════╝"
    echo -e "${NC}"

    detect_system
    install_dependencies
    deploy_project
    setup_database
    setup_env
    setup_services
    start_and_verify
}

main "$@"
