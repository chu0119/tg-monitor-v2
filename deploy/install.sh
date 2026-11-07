#!/usr/bin/env bash
# =============================================================================
# TG Monitor v3 一键安装（宝塔式：全环境兼容 + 预检 + 幂等 + 装完自检）
#
# 支持: Ubuntu 20/22/24, Debian 11/12, CentOS 7/8-Stream/9, Rocky/Alma 8/9
# 架构: x86_64 / arm64
# 用法: bash install.sh [选项]
#   --repo-dir <path>   代码目录（默认当前用户家目录下 tg-monitor）
#   --db-pass <pass>    MySQL 密码（默认随机生成并打印）
#   --skip-build        跳过前端构建（已有 dist 时）
#   --mirror-cn         强制使用国内镜像（检测到国内网络会自动启用）
# =============================================================================
set -uo pipefail

# ---------- 可调参数 ----------
REPO_DIR=""
DB_PASS=""
SKIP_BUILD=0
FORCE_CN=0
APP_PORT=3000
API_PORT=8000
STATUS_PORT=9010
LOG_FILE="/tmp/tgmonitor-install-$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

log()  { echo -e "\033[32m[✓]\033[0m $*"; }
warn() { echo -e "\033[33m[!]\033[0m $*"; }
err()  { echo -e "\033[31m[✗]\033[0m $*"; }
step() { echo -e "\n\033[36m======== $* ========\033[0m"; }

# ---------- 解析参数 ----------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo-dir) REPO_DIR="$2"; shift 2;;
        --db-pass)  DB_PASS="$2"; shift 2;;
        --skip-build) SKIP_BUILD=1; shift;;
        --mirror-cn) FORCE_CN=1; shift;;
        *) err "未知参数: $1"; exit 1;;
    esac
done

# ============================================================
# 0. 环境探测
# ============================================================
step "0/10 环境探测"

if [[ $EUID -ne 0 ]]; then
    err "请用 root 或 sudo 运行"
    exit 1
fi

# OS 识别
if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    OS_ID="${ID:-unknown}"; OS_VER="${VERSION_ID:-0}"; OS_NAME="${PRETTY_NAME:-unknown}"
else
    err "无法识别操作系统（缺 /etc/os-release），仅支持主流 Linux 发行版"
    exit 1
fi
ARCH=$(uname -m)
[[ "$ARCH" == "x86_64" || "$ARCH" == "aarch64" ]] || { err "不支持的架构: $ARCH"; exit 1; }

# 包管理器
if command -v apt-get >/dev/null; then
    PKG_MGR="apt"
elif command -v dnf >/dev/null; then
    PKG_MGR="dnf"
elif command -v yum >/dev/null; then
    PKG_MGR="yum"
else
    err "未找到 apt-get/dnf/yum"
    exit 1
fi

log "系统: $OS_NAME ($ARCH, $PKG_MGR)"

# systemd 可用性（容器内可能没有）
if pidof systemd >/dev/null 2>&1 || [[ -d /run/systemd/system ]]; then
    HAS_SYSTEMD=1; log "systemd: 可用"
else
    HAS_SYSTEMD=0; warn "systemd 不可用（容器环境?），服务将由脚本直接启动，仅用于测试"
fi

# 内存/磁盘预检（free 输出格式因发行版/locale 而异，解析失败仅警告不阻断）
MEM_GB=$(free -m 2>/dev/null | awk '/^Mem(:| )/{print $2}' | head -1)
DISK_GB=$(df -BG / 2>/dev/null | tail -1 | awk '{print $4}' | tr -dc '0-9')
if [[ -n "$MEM_GB" && "$MEM_GB" -ge 0 ]] 2>/dev/null; then
    MEM_GB=$(( MEM_GB / 1024 ))
    if (( MEM_GB < 2 )); then err "内存不足（需要 ≥2G，当前 ${MEM_GB}G）"; exit 1; fi
    log "资源: ${MEM_GB}G 内存 / ${DISK_GB:-?}G 可用磁盘"
else
    warn "无法解析内存信息（free 格式异常），跳过内存预检"
fi
if [[ -n "$DISK_GB" ]] 2>/dev/null; then
    (( DISK_GB >= 20 )) || { err "根分区剩余空间不足（需要 ≥20G，当前 ${DISK_GB}G）"; exit 1; }
fi

# 网络区域检测（决定镜像源）
if (( FORCE_CN )) || [[ -z "${SKIP_CN_CHECK:-}" ]] && curl -sf -m 3 -o /dev/null http://connect.rom.miui.com/generate_204 2>/dev/null; then
    CN_NETWORK=1; log "网络: 检测到国内环境，启用国内镜像加速"
else
    CN_NETWORK=0; log "网络: 国际线路"
fi

# 端口占用预检
for port in $APP_PORT $API_PORT $STATUS_PORT; do
    if ss -tln 2>/dev/null | grep -q ":${port} "; then
        err "端口 $port 已被占用，请先释放: ss -tlnp | grep $port"
        exit 1
    fi
done
log "端口 ${APP_PORT}/${API_PORT}/${STATUS_PORT} 空闲"

# 旧部署冲突检测
OLD_UNITS="tgmonitor-backend.service tg-monitor-frontend.service"
for u in $OLD_UNITS; do
    if systemctl list-unit-files 2>/dev/null | grep -q "^$u"; then
        warn "检测到旧版服务 $u，将停止并禁用（不删除）"
        systemctl disable --now "$u" 2>/dev/null
    fi
done

# ---------- 代码目录 ----------
if [[ -z "$REPO_DIR" ]]; then
    NORMAL_USER=$(logname 2>/dev/null || echo "")
    if [[ -n "$NORMAL_USER" && "$NORMAL_USER" != "root" ]]; then
        REPO_DIR="/home/$NORMAL_USER/tg-monitor"
    else
        REPO_DIR="/opt/tg-monitor"
    fi
fi
if [[ -d "$REPO_DIR/.git" ]]; then
    log "代码目录已存在: $REPO_DIR（执行 git pull 更新）"
    git -C "$REPO_DIR" fetch origin main 2>/dev/null && git -C "$REPO_DIR" reset --hard origin/main
elif [[ -d "$REPO_DIR" && -n "$(ls -A "$REPO_DIR" 2>/dev/null)" ]]; then
    err "目录 $REPO_DIR 非空且不是 git 仓库，请手动处理"
    exit 1
else
    mkdir -p "$(dirname "$REPO_DIR")"
    git clone --depth 50 https://github.com/chu0119/tg-monitor-v2.git "$REPO_DIR" \
        || { err "git clone 失败"; exit 1; }
    log "代码已克隆: $REPO_DIR"
fi

BACKEND="$REPO_DIR/backend"
FRONTEND="$REPO_DIR/frontend"
DEPLOY="$REPO_DIR/deploy"

# ============================================================
# 1. 基础依赖
# ============================================================
step "1/10 基础依赖"
if [[ "$PKG_MGR" == "apt" ]]; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq curl wget git gzip tar cron logrotate \
        build-essential libssl-dev libffi-dev python3-dev >/dev/null
else
    $PKG_MGR install -y -q curl wget git gzip tar cronie logrotate \
        gcc openssl-devel libffi-devel python3-devel >/dev/null
fi
log "基础工具就绪"

# ============================================================
# 2. Python 3.10+（带版本检查与源码编译兜底）
# ============================================================
step "2/10 Python 3.10+"
PY_OK=""
for cand in python3.12 python3.11 python3.10 python3; do
    if command -v $cand >/dev/null; then
        VER=$($cand -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        MAJOR=$(echo "$VER" | cut -d. -f1); MINOR=$(echo "$VER" | cut -d. -f2)
        if [[ "$MAJOR" -eq 3 && "$MINOR" -ge 10 ]]; then PY_BIN=$cand; PY_OK=1; break; fi
    fi
done
if [[ -z "$PY_OK" ]]; then
    warn "未找到 Python ≥3.10，尝试从发行版安装"
    if [[ "$PKG_MGR" == "apt" ]]; then
        apt-get install -y -qq python3 python3-venv python3-pip >/dev/null
    else
        $PKG_MGR install -y -q python3 python3-pip >/dev/null
    fi
    PY_BIN=python3
    $PY_BIN -c 'import sys; assert sys.version_info >= (3,10)' || {
        err "系统源 Python 版本过低，需手动安装 Python 3.10+（可参考 https://github.com/pyenv/pyenv）"
        exit 1
    }
fi
$PY_BIN -m venv --help >/dev/null 2>&1 || {
    if [[ "$PKG_MGR" == "apt" ]]; then apt-get install -y -qq python3-venv python3-pip >/dev/null; fi
}
log "Python: $($PY_BIN --version)"

# ============================================================
# 3. Node.js 18+（NodeSource → 二进制包兜底 → npmmirror 兜底）
# ============================================================
step "3/10 Node.js 18+"
NODE_OK=""
if command -v node >/dev/null; then
    NVER=$(node -v | tr -d v | cut -d. -f1)
    (( NVER >= 18 )) && NODE_OK=1 && log "Node.js: $(node -v)（已有）"
fi
if [[ -z "$NODE_OK" ]]; then
    NODE_VER="v20.18.1"
    NODE_ARCH="x64"; [[ "$ARCH" == "aarch64" ]] && NODE_ARCH="arm64"
    if [[ "$CN_NETWORK" == 1 ]]; then
        NODE_URL="https://npmmirror.com/mirrors/node/${NODE_VER}/node-${NODE_VER}-linux-${NODE_ARCH}.tar.xz"
    else
        NODE_URL="https://nodejs.org/dist/${NODE_VER}/node-${NODE_VER}-linux-${NODE_ARCH}.tar.xz"
    fi
    warn "安装 Node.js ${NODE_VER}（二进制包）"
    curl -fsSL "$NODE_URL" -o /tmp/node.tar.xz \
        && tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1 \
        && hash -r && NODE_OK=1 && log "Node.js: $(node -v)"
    rm -f /tmp/node.tar.xz
    [[ -n "$NODE_OK" ]] || { err "Node.js 安装失败"; exit 1; }
fi

# ============================================================
# 4. MySQL 8（发行版源 → 官方源兜底）
# ============================================================
step "4/10 MySQL 8"
MYSQL_READY=""
if systemctl is-active mysql >/dev/null 2>&1 || systemctl is-active mysqld >/dev/null 2>&1; then
    MYSQL_READY=1; log "MySQL 服务已在运行"
elif command -v mysqld >/dev/null; then
    systemctl enable --now mysql 2>/dev/null || systemctl enable --now mysqld 2>/dev/null
    MYSQL_READY=1; log "MySQL 已启动"
fi
if [[ -z "$MYSQL_READY" ]]; then
    warn "安装 MySQL 8"
    if [[ "$PKG_MGR" == "apt" ]]; then
        HAS_MYSQL_PKG=$(apt-cache policy mysql-server 2>/dev/null | awk '/Candidate:/{print $2}' | grep -vc none || true)
        HAS_MYSQL_PKG8=$(apt-cache policy mysql-server-8.0 2>/dev/null | awk '/Candidate:/{print $2}' | grep -vc none || true)
        if [[ "${HAS_MYSQL_PKG:-0}" != "0" || "${HAS_MYSQL_PKG8:-0}" != "0" ]]; then
            apt-get install -y -qq mysql-server >/dev/null && systemctl enable --now mysql && MYSQL_READY=1
        else
            # Debian 12 等：官方源无 MySQL，直接配置 repo.mysql.com 源（deb822 格式）
            warn "发行版源无 mysql-server，配置 repo.mysql.com 官方源"
            export DEBIAN_FRONTEND=noninteractive
            apt-get install -y -qq gnupg >/dev/null
            if curl -fsSL --retry 3 -m 60 https://repo.mysql.com/RPM-GPG-KEY-mysql-2023 | gpg --dearmor -o /usr/share/keyrings/mysql.gpg                 && echo "deb [signed-by=/usr/share/keyrings/mysql.gpg] http://repo.mysql.com/apt/debian $(. /etc/os-release && echo $VERSION_CODENAME) mysql-8.0" > /etc/apt/sources.list.d/mysql.list                 && apt-get update -qq                 && { echo "mysql-community-server mysql-community-server/root-pass password $DB_PASS";                      echo "mysql-community-server mysql-community-server/re-root-pass password $DB_PASS";                    } | debconf-set-selections                 && apt-get install -y -qq mysql-community-server 2>&1 | tail -2                 && systemctl enable --now mysql && MYSQL_READY=1; then
                log "MySQL 官方仓库安装完成"
            else
                warn "MySQL 官方仓库安装失败（网络或仓库不可达），回退 MariaDB（全文搜索将降级为 LIKE）"
                apt-get install -y -qq mariadb-server >/dev/null && systemctl enable --now mariadb && MYSQL_READY=1
            fi
        fi
    else
        # RHEL 系走 MySQL 官方仓库
        MYSQL_REPO_RPM="mysql80-community-release"
        curl -fsSL "https://dev.mysql.com/get/${MYSQL_REPO_RPM}-1.el$(grep -oE '[0-9]+' /etc/redhat-release | head -1).rpm" -o /tmp/mysql_repo.rpm \
            && rpm -Uvh /tmp/mysql_repo.rpm 2>/dev/null
        $PKG_MGR install -y -q mysql-community-server >/dev/null 2>&1 \
            && systemctl enable --now mysqld && MYSQL_READY=1
        rm -f /tmp/mysql_repo.rpm
    fi
    [[ -n "$MYSQL_READY" ]] || { err "MySQL 安装失败，请手动安装 MySQL 8 后重跑"; exit 1; }
    log "MySQL 安装完成"
fi
# 等待 socket 就绪
for i in $(seq 1 30); do
    mysqladmin ping >/dev/null 2>&1 && break
    (( i == 30 )) && { err "MySQL 未就绪"; exit 1; }
    sleep 2
done

# ============================================================
# 5. Redis / Nginx
# ============================================================
step "5/10 Redis + Nginx"
if [[ "$PKG_MGR" == "apt" ]]; then
    apt-get install -y -qq redis-server nginx >/dev/null
    systemctl enable --now redis-server nginx
else
    $PKG_MGR install -y -q redis nginx >/dev/null
    systemctl enable --now redis nginx
fi
redis-cli ping 2>/dev/null | grep -q PONG && log "Redis: PONG"
nginx -t >/dev/null 2>&1 && log "Nginx: 配置正常"

# ============================================================
# 6. Python 虚拟环境 + 依赖（国内 pip 镜像回退）
# ============================================================
step "6/10 Python 虚拟环境"
$PY_BIN -m venv "$BACKEND/venv"
if [[ ! -x "$BACKEND/venv/bin/pip" ]]; then
    err "venv 缺少 pip（ensurepip 不可用）。请安装: apt install python3-venv python3-pip 后重跑"
    exit 1
fi
PIP_ARGS=(-q --upgrade pip)
if [[ "$CN_NETWORK" == 1 ]]; then PIP_ARGS+=(-i https://pypi.tuna.tsinghua.edu.cn/simple); fi
"$BACKEND/venv/bin/pip" install "${PIP_ARGS[@]}"
PIP_OK=1
"$BACKEND/venv/bin/pip" install -q -r "$BACKEND/requirements.txt" ${CN_NETWORK:+-i https://pypi.tuna.tsinghua.edu.cn/simple} || PIP_OK=0
if (( ! PIP_OK )); then
    warn "主源安装失败，重试官方源"
    "$BACKEND/venv/bin/pip" install -q -r "$BACKEND/requirements.txt" || {
        err "Python 依赖安装失败（两次均失败），完整错误见上方；常见原因: 网络/编译缺 build-essential"
        exit 1
    }
fi
"$BACKEND/venv/bin/python" -c "import fastapi, telethon, sqlalchemy, uvicorn; print('Python 依赖: OK')"

# ============================================================
# 7. MySQL 库/用户/.env
# ============================================================
step "7/10 MySQL 库与配置"
DB_NAME="tg_monitor_v2"
DB_USER="tgmonitor"
if [[ -z "$DB_PASS" ]] && [[ -f "$BACKEND/.env" ]]; then
    # 重跑场景：.env 已有密码，必须沿用（否则 ALTER USER 换密码后与 .env 漂移 → Access denied）
    DB_PASS=$(grep '^MYSQL_PASSWORD=' "$BACKEND/.env" | cut -d= -f2)
    [[ -n "$DB_PASS" ]] && log "沿用 backend/.env 中的既有数据库密码"
fi
if [[ -z "$DB_PASS" ]]; then
    DB_PASS=$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 20)
    log "生成随机数据库密码: $DB_PASS （已写入 backend/.env）"
fi
mysql -e "CREATE DATABASE IF NOT EXISTS $DB_NAME CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -e "CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASS';"
mysql -e "ALTER USER '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASS';"
mysql -e "GRANT ALL PRIVILEGES ON $DB_NAME.* TO '$DB_USER'@'localhost'; FLUSH PRIVILEGES;"

# 运行用户（服务以非 root 跑；代码目录必须对其可读，否则 systemd CHDIR 失败）
APP_USER=$(stat -c '%U' "$REPO_DIR" 2>/dev/null || echo root)
[[ "$APP_USER" == "root" ]] && APP_USER="tgmonitor"
id -u "$APP_USER" >/dev/null 2>&1 || useradd -r -s /usr/sbin/nologin "$APP_USER"
chown -R "$APP_USER":"$APP_USER" "$REPO_DIR" 2>/dev/null || true
if ! sudo -u "$APP_USER" test -x "$REPO_DIR" 2>/dev/null; then
    warn "用户 $APP_USER 无法进入 $REPO_DIR（代码在受限目录?），服务改以 root 运行"
    APP_USER=root
fi

if [[ ! -f "$BACKEND/.env" ]]; then
    cat > "$BACKEND/.env" <<EOF
DATABASE_TYPE=mysql
# 用 127.0.0.1 而非 localhost：部分环境 localhost 解析为 IPv6 而 MySQL 只监听 IPv4
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=$DB_USER
MYSQL_PASSWORD=$DB_PASS
MYSQL_DATABASE=$DB_NAME
HOST=0.0.0.0
PORT=$API_PORT
LOG_LEVEL=INFO
# Telegram API 凭据（https://my.telegram.org 申请）
# TELEGRAM_API_ID=
# TELEGRAM_API_HASH=
EOF
    chmod 600 "$BACKEND/.env"; chown "$APP_USER":"$APP_USER" "$BACKEND/.env"
    log "backend/.env 已生成（记住填 TELEGRAM_API_ID/HASH）"
else
    log "backend/.env 已存在（保留现配置）"
fi

mkdir -p "$BACKEND/sessions" "$REPO_DIR/logs" "$REPO_DIR/backups" "$REPO_DIR/exports" "$REPO_DIR/uploads"
chown -R "$APP_USER":"$APP_USER" "$REPO_DIR"/{logs,backups,exports,uploads} "$BACKEND/sessions"

# ============================================================
# 8. 前端构建（npm 镜像回退）
# ============================================================
step "8/10 前端构建"
cd "$FRONTEND"
if (( SKIP_BUILD )) && [[ -f dist/index.html ]]; then
    log "跳过构建（--skip-build 且 dist 已存在）"
else
    NPM_CFG=()
    if [[ "$CN_NETWORK" == 1 ]]; then NPM_CFG+=(--registry=https://registry.npmmirror.com); fi
    sudo -u "$APP_USER" env HOME=/tmp npm install --no-audit --no-fund "${NPM_CFG[@]}" 2>&1 | tail -1 || npm install --no-audit --no-fund "${NPM_CFG[@]}"
    sudo -u "$APP_USER" env HOME=/tmp npm run build 2>&1 | tail -1 || npm run build
    [[ -f dist/index.html ]] || { err "前端构建产物缺失"; exit 1; }
    log "前端构建完成（dist/）"
fi

# ============================================================
# 9. 数据库迁移 + systemd 服务 + nginx 站点
# ============================================================
step "9/10 数据库迁移与服务注册"
cd "$BACKEND"
"$BACKEND/venv/bin/python" scripts/migrate_v3.py --skip-optimize | tail -3

for unit in tgmonitor-api-0 tgmonitor-monitor-0 tg-watchdog tgmonitor-session-protector; do
    sed "s|__REPO_DIR__|$REPO_DIR|g; s|__APP_USER__|$APP_USER|g; s|__VENV__|$BACKEND/venv|g" \
        "$DEPLOY/$unit.service" > "/etc/systemd/system/$unit.service"
done
systemctl daemon-reload
systemctl enable tgmonitor-api-0 tgmonitor-monitor-0 tg-watchdog tgmonitor-session-protector 2>/dev/null

# nginx 站点（幂等）
cat > /etc/nginx/sites-available/tgmonitor <<NGINX
server {
    listen $APP_PORT;
    client_max_body_size 200m;
    server_name _;
    root $FRONTEND/dist;
    index index.html;
    location / { try_files \$uri \$uri/ /index.html; }
    location /api/ {
        proxy_pass http://127.0.0.1:$API_PORT;
        proxy_set_header Host \$host; proxy_set_header X-Real-IP \$remote_addr;
        proxy_read_timeout 300s; proxy_send_timeout 300s;
    }
    location /health { proxy_pass http://127.0.0.1:$API_PORT; proxy_set_header Host \$host; }
    location /ws/ {
        proxy_pass http://127.0.0.1:$API_PORT;
        proxy_http_version 1.1; proxy_set_header Upgrade \$http_upgrade; proxy_set_header Connection "upgrade";
    }
}
NGINX
[[ -f /etc/nginx/sites-enabled ]] && ln -sf /etc/nginx/sites-available/tgmonitor /etc/nginx/sites-enabled/tgmonitor \
    && rm -f /etc/nginx/sites-enabled/default
[[ -d /etc/nginx/conf.d ]] && ln -sf /etc/nginx/sites-available/tgmonitor /etc/nginx/conf.d/tgmonitor.conf
nginx -t && { systemctl reload nginx 2>/dev/null || systemctl restart nginx; }
log "nginx 站点已配置（端口 $APP_PORT）"

# 防火墙放行
if command -v ufw >/dev/null && ufw status 2>/dev/null | grep -q "active"; then
    ufw allow "$APP_PORT/tcp" >/dev/null; ufw allow "$API_PORT/tcp" >/dev/null
    log "ufw 已放行 $APP_PORT/$API_PORT"
fi
if command -v firewall-cmd >/dev/null && firewall-cmd --state 2>/dev/null | grep -q running; then
    firewall-cmd --permanent --add-port="${APP_PORT}/tcp" --add-port="${API_PORT}/tcp" >/dev/null
    firewall-cmd --reload >/dev/null
    log "firewalld 已放行 $APP_PORT/$API_PORT"
fi

# ============================================================
# 10. 启动 + 装完自检（10 项）
# ============================================================
step "10/10 启动与自检"
if (( HAS_SYSTEMD )); then
    systemctl start tgmonitor-api-0
    sleep 20
    systemctl start tgmonitor-monitor-0
    sleep 10
    systemctl start tg-watchdog tgmonitor-session-protector 2>/dev/null
else
    sudo -u "$APP_USER" bash -c "cd $BACKEND && WORKER_ID=0 WORKER_TYPE=api nohup $BACKEND/venv/bin/python -m app.workers.api_worker > $REPO_DIR/logs/api.out 2>&1 &"
    sleep 15
    sudo -u "$APP_USER" bash -c "cd $BACKEND && WORKER_ID=0 WORKER_TYPE=monitor nohup $BACKEND/venv/bin/python -m app.workers.monitor_worker > $REPO_DIR/logs/monitor.out 2>&1 &"
    sleep 10
fi

PASS=0; FAIL=0
check() {
    local name="$1" cmd="$2"
    if eval "$cmd" >/dev/null 2>&1; then
        log "自检通过: $name"; ((PASS++))
    else
        err "自检失败: $name"; ((FAIL++))
    fi
}
check "1.数据库连接(utf8mb4)"   "mysql -u $DB_USER -p$DB_PASS -e 'SELECT 1' $DB_NAME"
check "2.Python依赖导入"        "cd $BACKEND && $BACKEND/venv/bin/python -c 'import app.workers.api_worker' 2>&1"
check "3.前端产物"              "test -f $FRONTEND/dist/index.html"
check "4.API健康(/health)"      "curl -sf -m 10 http://localhost:$API_PORT/health | grep -q '\"status\"'"
check "5.API登录接口可达"       "curl -s -m 10 -o /dev/null -w '%{http_code}' http://localhost:$API_PORT/api/v1/conversations?page_size=1 | grep -qE '200|401'"
check "6.前端页面(HTTP $APP_PORT)" "curl -sf -m 10 http://localhost:$APP_PORT/ | grep -q '<div id=\"root\">'"
check "7.前端API代理"           "curl -sf -m 10 http://localhost:$APP_PORT/api/v1/health >/dev/null || curl -s -m 10 -o /dev/null http://localhost:$APP_PORT/api/v1/conversations?page_size=1 | grep -qE '200|401'"
check "8.系统服务状态"          "systemctl is-active tgmonitor-api-0"
check "9.monitor状态服务"       "curl -sf -m 5 http://localhost:$STATUS_PORT/health"
check "10.Redis"                "redis-cli ping | grep -q PONG"

echo ""
echo "============================================================"
if (( FAIL == 0 )); then
    echo -e "\033[32m  ✅ 安装完成：$PASS/10 项自检全部通过\033[0m"
else
    echo -e "\033[31m  ⚠ 安装完成但 $FAIL 项自检未通过，详见上方与 $LOG_FILE\033[0m"
fi
echo "  浏览器打开: http://<本机IP>:$APP_PORT  →  /setup 完成初始化"
echo "  数据库密码: $DB_PASS （也写在 $BACKEND/.env）"
echo "  常用命令: systemctl {status|restart} tgmonitor-{api-0,monitor-0}"
echo "          deploy/update.sh  # 日常更新"
echo "============================================================"
