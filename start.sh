#!/bin/bash
# ============================================================
#  TG Monitor v2 - 一键部署脚本
#  用法: ./start.sh [--reset] [--no-autostart] [--mirror <tsinghua|aliyun|off>]
#  适用: Ubuntu 20.04+ / Debian 11+ (全新系统直接跑)
# ============================================================

# ── 颜色 ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

# ── 颜色日志 ──
log_info()  { echo -e "  ${GREEN}✅ $1${NC}"; }
log_warn()  { echo -e "  ${YELLOW}⏳ $1${NC}"; }
log_err()   { echo -e "  ${RED}❌ $1${NC}"; }
log_step()  { echo -e "\n${BOLD}[$1] $2${NC}"; }

# ── 路径（向上查找项目根目录）──
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
PROJECT_DIR=""
_dir="$SCRIPT_DIR"
while [ "$_dir" != "/" ]; do
  if [ -d "$_dir/backend" ] && [ -d "$_dir/frontend" ]; then
    PROJECT_DIR="$_dir"
    break
  fi
  _dir="$(dirname "$_dir")"
done

if [ -z "$PROJECT_DIR" ]; then
  log_err "找不到包含 backend/ 和 frontend/ 的项目目录"
  log_err "当前目录: $SCRIPT_DIR"
  exit 1
fi

MARKER="$PROJECT_DIR/.deployed"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/venv"
SERVICE_NAME="tgmonitor"
LOG_FILE="/tmp/tg-monitor-deploy.log"

# ── 参数解析 ──
RESET=false
NO_AUTOSTART=false
MIRROR="auto"  # auto=自动检测，tsinghua/aliyun/off

for arg in "$@"; do
  case "$arg" in
    --reset) RESET=true ;;
    --no-autostart) NO_AUTOSTART=true ;;
    --mirror) shift; MIRROR="$1" ;;
    --mirror=*) MIRROR="${arg#*=}" ;;
    --help)
      echo "用法: ./start.sh [--reset] [--no-autostart] [--mirror <tsinghua|aliyun|off>]"
      exit 0 ;;
  esac
done

# ── 镜像配置 ──
if [ "$MIRROR" = "auto" ]; then
  # 通过IP判断是否在国内
  IP_REGION=$(curl -fsSL --connect-timeout 3 ipinfo.io/country 2>/dev/null || echo "CN")
  if [[ "$IP_REGION" == "CN" ]]; then
    MIRROR="tsinghua"
  else
    MIRROR="off"
  fi
fi

case "$MIRROR" in
  tsinghua)
    PIP_INDEX="https://pypi.tuna.tsinghua.edu.cn/simple"
    NPM_REGISTRY="https://registry.npmmirror.com"
    MIRROR_LABEL="清华镜像"
    ;;
  aliyun)
    PIP_INDEX="https://mirrors.aliyun.com/pypi/simple/"
    NPM_REGISTRY="https://registry.npmmirror.com"
    MIRROR_LABEL="阿里云镜像"
    ;;
  off|*)
    PIP_INDEX=""
    NPM_REGISTRY=""
    MIRROR_LABEL="官方源"
    ;;
esac

# ── 端口检测 ──
check_port() {
  if ss -tlnp 2>/dev/null | grep -q ":$1 "; then
    return 0  # 被占用
  fi
  if command -v lsof &>/dev/null && lsof -i ":$1" &>/dev/null; then
    return 0
  fi
  return 1  # 空闲
}

# ── 打印Banner ──
echo -e "${CYAN}${BOLD}"
echo "╔══════════════════════════════════════════╗"
echo "║   TG Monitor v2 - 一键部署              ║"
echo "╠══════════════════════════════════════════╣"
echo "║  项目: $PROJECT_DIR"
echo "║  镜像: $MIRROR_LABEL"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

if $RESET; then
  rm -f "$MARKER"
  log_warn "已重置部署状态，将重新执行所有步骤"
fi

# 记录日志
exec > >(tee -a "$LOG_FILE") 2>&1

# ═══════════════════════════════════════════════
# Step 1: 检测系统环境
# ═══════════════════════════════════════════════
log_step "1/9" "检测系统环境"

# 系统
if [ -f /etc/os-release ]; then
  . /etc/os-release
  log_info "系统: $PRETTY_NAME"
  if [[ "$ID" != "ubuntu" && "$ID" != "debian" ]]; then
    log_warn "本脚本主要支持 Ubuntu/Debian，其他系统可能需要手动调整"
  fi
else
  log_warn "无法检测操作系统版本"
fi

# 架构
ARCH=$(uname -m)
log_info "架构: $ARCH"

# 内存（至少512MB）
MEM_MB=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print int($2/1024)}')
if [ -n "$MEM_MB" ] && [ "$MEM_MB" -lt 512 ]; then
  log_err "内存不足: ${MEM_MB}MB，建议至少 512MB"
  exit 1
else
  log_info "内存: ${MEM_MB}MB"
fi

# 磁盘（至少2GB）
AVAIL_KB=$(df "$PROJECT_DIR" 2>/dev/null | awk 'NR==2 {print $4}')
if [ -n "$AVAIL_KB" ]; then
  AVAIL_GB=$((AVAIL_KB / 1024 / 1024))
  if [ "$AVAIL_GB" -lt 2 ]; then
    log_err "磁盘空间不足: ${AVAIL_GB}GB，建议至少 2GB"
    exit 1
  fi
  log_info "磁盘: ${AVAIL_GB}GB 可用"
fi

# sudo权限
if [ "$EUID" -ne 0 ]; then
  if ! sudo -n true 2>/dev/null; then
    log_warn "需要sudo权限，请输入密码"
    sudo true
  fi
  log_info "sudo: 可用"
else
  log_warn "不建议用root运行，建议用普通用户"
fi

# 端口
BACKEND_PORT=8000
FRONTEND_PORT=3000
if check_port $BACKEND_PORT; then
  log_warn "端口 $BACKEND_PORT 已被占用，后端可能无法启动"
fi
if check_port $FRONTEND_PORT; then
  log_warn "端口 $FRONTEND_PORT 已被占用，前端可能无法启动"
fi

# ═══════════════════════════════════════════════
# Step 2: 安装系统依赖
# ═══════════════════════════════════════════════
log_step "2/9" "安装系统依赖"

log_warn "apt-get update..."
sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq 2>&1 || {
  log_err "apt-get update 失败，请检查网络"
  exit 1
}

# 基础工具 + Python编译依赖
log_warn "安装基础工具..."
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  curl wget git build-essential \
  libffi-dev libssl-dev pkg-config 2>&1 | tail -1
log_info "基础工具已就绪"

# ── Python3 ──
log_warn "检查 Python3..."
if ! command -v python3 &>/dev/null; then
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3 2>&1 | tail -1
  if ! command -v python3 &>/dev/null; then
    log_err "python3 安装失败"; exit 1
  fi
fi

# python3-venv
PYTHON_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if ! python3 -c "import venv" 2>/dev/null; then
  log_warn "安装 python${PYTHON_VER}-venv..."
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "python${PYTHON_VER}-venv" 2>&1 | tail -2 || \
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv 2>&1 | tail -2
  if ! python3 -c "import venv" 2>/dev/null; then
    log_err "python3-venv 安装失败"; exit 1
  fi
fi

# pip
if ! command -v pip3 &>/dev/null; then
  log_warn "安装 pip..."
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3-pip 2>&1 | tail -2
fi
log_info "Python3 $(python3 --version 2>&1 | awk '{print $2}')"

# ── Node.js ──
log_warn "检查 Node.js..."
if ! command -v node &>/dev/null; then
  log_warn "安装 Node.js（LTS版本，可能需要1-2分钟）..."
  NODE_OK=false

  # 方式1: NodeSource（需要访问外网）
  if [ "$NODE_OK" = false ]; then
    log_warn "  尝试 NodeSource..."
    if curl -fsSL --connect-timeout 10 https://deb.nodesource.com/setup_lts.x 2>/dev/null | sudo -E bash - >/dev/null 2>&1; then
      if sudo DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs 2>&1 | tail -1; then
        if command -v node &>/dev/null; then
          NODE_OK=true
        fi
      fi
    fi
  fi

  # 方式2: snap（国内可能可用）
  if [ "$NODE_OK" = false ] && command -v snap &>/dev/null; then
    log_warn "  尝试 snap..."
    sudo snap install node --classic 2>&1 | tail -1 && NODE_OK=true
  fi

  # 方式3: apt 默认仓库（版本可能较旧）
  if [ "$NODE_OK" = false ]; then
    log_warn "  尝试 apt 默认仓库..."
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs npm 2>&1 | tail -1 && NODE_OK=true
  fi

  if [ "$NODE_OK" = false ] || ! command -v node &>/dev/null; then
    log_err "Node.js 安装失败（所有方式均失败）"
    log_err "请手动安装: curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash - && sudo apt install nodejs"
    exit 1
  fi
fi

NODE_VER=$(node --version 2>/dev/null | sed 's/v//')
# 检查Node版本是否 >= 18
NODE_MAJOR=$(echo "$NODE_VER" | cut -d. -f1)
if [ -n "$NODE_MAJOR" ] && [ "$NODE_MAJOR" -lt 18 ]; then
  log_err "Node.js 版本过低: $NODE_VER，需要 >= 18"
  exit 1
fi
log_info "Node.js $NODE_VER"
log_info "npm $(npm --version 2>/dev/null)"

# ── MySQL ──
log_warn "检查 MySQL..."
if ! command -v mysql &>/dev/null; then
  log_warn "安装 MySQL Server（可能需要1-3分钟）..."
  sudo debconf-set-selections <<< "mysql-server mysql-server/root_password password ''" 2>/dev/null || true
  sudo debconf-set-selections <<< "mysql-server mysql-server/root_password_again password ''" 2>/dev/null || true
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y mysql-server 2>&1 | tail -3
  if ! command -v mysql &>/dev/null; then
    log_err "MySQL 安装失败"; exit 1
  fi
fi

# 启动MySQL
MYSQL_RUNNING=false
for try in 1 2 3; do
  if systemctl is-active --quiet mysql 2>/dev/null || systemctl is-active --quiet mysqld 2>/dev/null; then
    MYSQL_RUNNING=true
    break
  fi
  sudo systemctl start mysql 2>/dev/null || sudo systemctl start mysqld 2>/dev/null || sudo service mysql start 2>/dev/null || true
  sleep 3
done

if [ "$MYSQL_RUNNING" = false ]; then
  log_err "MySQL 启动失败"
  log_err "请检查: sudo systemctl status mysql"
  exit 1
fi
log_info "MySQL 运行中"

# 修复MySQL 8.x caching_sha2_password认证问题
log_warn "配置MySQL认证方式..."
sudo mysql -u root -e "
  ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '';
  FLUSH PRIVILEGES;
" 2>/dev/null || log_warn "MySQL认证配置跳过（可能已配置或权限不足）"

# ═══════════════════════════════════════════════
# Step 3: Python虚拟环境和依赖
# ═══════════════════════════════════════════════
log_step "3/9" "安装Python依赖"

if [ ! -d "$VENV_DIR" ] || [ ! -f "$VENV_DIR/bin/python3" ]; then
  log_warn "创建虚拟环境 → $VENV_DIR"
  rm -rf "$VENV_DIR"
  python3 -m venv "$VENV_DIR"
  if [ ! -f "$VENV_DIR/bin/python3" ]; then
    log_err "虚拟环境创建失败"; exit 1
  fi
  log_info "虚拟环境已创建"
else
  log_info "虚拟环境已存在"
fi

# 激活venv（用source可能不生效，直接用绝对路径更可靠）
VENV_PYTHON="$VENV_DIR/bin/python3"
VENV_PIP="$VENV_DIR/bin/pip3"
log_info "Python: $VENV_PYTHON ($($VENV_PYTHON --version 2>&1 | awk '{print $2}'))"

# 升级pip
$VENV_PIP install --upgrade pip -q 2>/dev/null

if [ -f "$BACKEND_DIR/requirements.txt" ]; then
  log_warn "pip install -r requirements.txt..."
  PIP_ARGS="-r $BACKEND_DIR/requirements.txt"
  if [ -n "$PIP_INDEX" ]; then
    PIP_ARGS="$PIP_ARGS -i $PIP_INDEX --trusted-host $(echo $PIP_INDEX | sed 's|https://||;s|/simple||')"
  fi
  if $VENV_PIP install $PIP_ARGS 2>&1 | tail -8; then
    log_info "Python依赖安装完成"
  else
    # 重试一次（网络不稳定）
    log_warn "首次安装可能有问题，重试中..."
    if $VENV_PIP install $PIP_ARGS 2>&1 | tail -5; then
      log_info "Python依赖安装完成（重试成功）"
    else
      log_err "Python依赖安装失败"
      exit 1
    fi
  fi
else
  log_warn "未找到 requirements.txt，跳过"
fi

# ═══════════════════════════════════════════════
# Step 4: 前端依赖
# ═══════════════════════════════════════════════
log_step "4/9" "安装前端依赖"
cd "$FRONTEND_DIR"

if [ ! -d "node_modules" ]; then
  log_warn "npm install（可能需要1-3分钟）..."
  NPM_INSTALL="npm install"
  if [ -n "$NPM_REGISTRY" ]; then
    NPM_INSTALL="$NPM_INSTALL --registry=$NPM_REGISTRY"
  fi

  if $NPM_INSTALL 2>&1 | tail -5; then
    log_info "前端依赖安装完成"
  else
    # 重试：legacy-peer-deps
    log_warn "首次安装失败，尝试 --legacy-peer-deps..."
    if npm install --legacy-peer-deps 2>&1 | tail -5; then
      log_info "前端依赖安装完成（legacy-peer-deps）"
    else
      log_err "npm install 失败"
      log_err "请手动执行: cd $FRONTEND_DIR && npm install --legacy-peer-deps"
      exit 1
    fi
  fi
else
  log_info "node_modules 已存在"
fi
cd "$PROJECT_DIR"

# ═══════════════════════════════════════════════
# Step 5: 构建前端
# ═══════════════════════════════════════════════
log_step "5/9" "构建前端"
cd "$FRONTEND_DIR"

BUILD_OK=false
if [ -f "node_modules/.bin/tsc" ]; then
  log_warn "tsc && vite build..."
  if npm run build 2>&1 | tail -5; then
    BUILD_OK=true
  fi
fi

if [ "$BUILD_OK" = false ]; then
  log_warn "跳过类型检查，直接 vite build..."
  if npx vite build 2>&1 | tail -5; then
    BUILD_OK=true
  fi
fi

if [ "$BUILD_OK" = false ]; then
  log_err "前端构建失败"
  log_err "请检查 Node.js >= 18: node --version"
  exit 1
fi

# 验证dist目录
if [ ! -d "$FRONTEND_DIR/dist" ] || [ -z "$(ls -A $FRONTEND_DIR/dist 2>/dev/null)" ]; then
  log_err "前端构建产物(dist/)为空"
  exit 1
fi
log_info "前端构建完成 ($(du -sh $FRONTEND_DIR/dist 2>/dev/null | cut -f1))"

cd "$PROJECT_DIR"

# ═══════════════════════════════════════════════
# Step 6: 数据库初始化
# ═══════════════════════════════════════════════
log_step "6/9" "初始化数据库"

# 测试MySQL连接
log_warn "测试MySQL连接..."
if ! $VENV_PYTHON -c "
import pymysql
try:
    conn = pymysql.connect(host='localhost', user='root', password='', connect_timeout=5)
    conn.close()
except Exception as e:
    print(f'连接失败: {e}')
    import sys; sys.exit(1)
" 2>&1; then
  log_err "无法连接MySQL"
  log_err "请检查: sudo systemctl status mysql"
  log_err "如果root有密码，请手动执行: $VENV_PYTHON $BACKEND_DIR/init_db.py"
  exit 1
fi

if [ -f "$BACKEND_DIR/init_db.py" ]; then
  log_warn "执行数据库初始化..."
  if $VENV_PYTHON "$BACKEND_DIR/init_db.py" 2>&1; then
    log_info "数据库初始化完成"
  else
    log_err "数据库初始化失败，请查看上方错误信息"
    exit 1
  fi
else
  log_warn "未找到 init_db.py，跳过"
fi

# ═══════════════════════════════════════════════
# Step 7: 下载代理内核
# ═══════════════════════════════════════════════
log_step "7/9" "检查代理内核"
PROXY_DIR="$BACKEND_DIR/app/proxy"
MIHOMO_PATH="$PROXY_DIR/mihomo"

if [ -f "$MIHOMO_PATH" ] && [ -x "$MIHOMO_PATH" ]; then
  log_info "mihomo 内核已存在"
else
  case $ARCH in
    x86_64) DL_ARCH="amd64" ;;
    aarch64|arm64) DL_ARCH="arm64" ;;
    *) log_warn "不支持的架构: $ARCH，跳过mihomo下载"; DL_ARCH="" ;;
  esac

  if [ -n "$DL_ARCH" ]; then
    MIHOMO_VER="v1.19.21"
    DL_URLS=(
      "https://github.com/MetaCubeX/mihomo/releases/download/${MIHOMO_VER}/mihomo-linux-${DL_ARCH}-${MIHOMO_VER}.gz"
      "https://bgithub.xyz/MetaCubeX/mihomo/releases/download/${MIHOMO_VER}/mihomo-linux-${DL_ARCH}-${MIHOMO_VER}.gz"
      "https://mirror.ghproxy.com/https://github.com/MetaCubeX/mihomo/releases/download/${MIHOMO_VER}/mihomo-linux-${DL_ARCH}-${MIHOMO_VER}.gz"
      "https://gh-proxy.com/https://github.com/MetaCubeX/mihomo/releases/download/${MIHOMO_VER}/mihomo-linux-${DL_ARCH}-${MIHOMO_VER}.gz"
    )
    mkdir -p "$PROXY_DIR"

    DL_OK=false
    for url in "${DL_URLS[@]}"; do
      log_warn "尝试: ${url%%\?*}..."
      if curl -fsSL --connect-timeout 15 "$url" -o /tmp/mihomo.gz 2>/dev/null; then
        if gunzip -f /tmp/mihomo.gz 2>/dev/null && [ -f /tmp/mihomo ] && [ -s /tmp/mihomo ]; then
          mv /tmp/mihomo "$MIHOMO_PATH"
          chmod +x "$MIHOMO_PATH"
          log_info "mihomo 内核已下载 ($(du -h "$MIHOMO_PATH" | cut -f1))"
          DL_OK=true
          break
        fi
        rm -f /tmp/mihomo /tmp/mihomo.gz
      fi
    done

    if [ "$DL_OK" = false ]; then
      log_warn "mihomo 下载失败（不影响核心功能，仅代理不可用）"
      log_warn "手动下载后放到: $MIHOMO_PATH"
      log_warn "下载地址: ${DL_URLS[0]}"
    fi
  fi
fi

# ═══════════════════════════════════════════════
# Step 8: 配置系统服务
# ═══════════════════════════════════════════════
log_step "8/9" "配置系统服务"

# 停止旧服务
sudo systemctl stop "${SERVICE_NAME}-backend" 2>/dev/null || true
sudo systemctl stop "${SERVICE_NAME}-frontend" 2>/dev/null || true

# ── 后端service ──
cat > "/tmp/${SERVICE_NAME}-backend.service" << EOF
[Unit]
Description=TG Monitor v2 Backend
After=network.target mysql.service mysqld.service
Wants=mysql.service

[Service]
Type=simple
WorkingDirectory=$BACKEND_DIR
Environment=PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=$VENV_PYTHON -m uvicorn app.main:app --host 0.0.0.0 --port $BACKEND_PORT
Restart=always
RestartSec=5
StartLimitBurst=5
StartLimitIntervalSec=60
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# ── 前端service ──
# 用nginx代理前端（支持SPA路由 + 更稳定）
FRONTEND_USING_NGINX=false
if command -v nginx &>/dev/null; then
  # 配置nginx
  cat > "/tmp/${SERVICE_NAME}-frontend.conf" << EOF
server {
    listen $FRONTEND_PORT;
    server_name _;

    root $FRONTEND_DIR/dist;
    index index.html;

    # SPA路由：所有路径回退到index.html
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # API代理到后端
    location /api/ {
        proxy_pass http://127.0.0.1:$BACKEND_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;
    }

    # WebSocket支持（如果需要）
    location /ws/ {
        proxy_pass http://127.0.0.1:$BACKEND_PORT;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF
  sudo cp "/tmp/${SERVICE_NAME}-frontend.conf" "/etc/nginx/sites-available/${SERVICE_NAME}-frontend.conf"
  sudo ln -sf "/etc/nginx/sites-available/${SERVICE_NAME}-frontend.conf" "/etc/nginx/sites-enabled/"
  sudo nginx -t 2>/dev/null && FRONTEND_USING_NGINX=true
fi

if [ "$FRONTEND_USING_NGINX" = true ]; then
  FRONTEND_DESC="nginx (SPA路由 + API代理)"
else
  # 回退：Python HTTP Server（不支持SPA路由）
  FRONTEND_DESC="Python HTTP Server (无SPA路由，刷新可能404)"
  log_warn "nginx未安装，前端用Python HTTP Server（建议: sudo apt install nginx 后重新运行）"
  cat > "/tmp/${SERVICE_NAME}-frontend.service" << EOF
[Unit]
Description=TG Monitor v2 Frontend
After=network.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR
ExecStart=$VENV_PYTHON -m http.server $FRONTEND_PORT --directory $FRONTEND_DIR/dist
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
  sudo cp "/tmp/${SERVICE_NAME}-frontend.service" /etc/systemd/system/
fi

sudo cp "/tmp/${SERVICE_NAME}-backend.service" /etc/systemd/system/
sudo systemctl daemon-reload

if $NO_AUTOSTART; then
  log_warn "跳过开机自启 (--no-autostart)"
else
  sudo systemctl enable "${SERVICE_NAME}-backend" 2>/dev/null
  if [ "$FRONTEND_USING_NGINX" = true ]; then
    sudo systemctl enable nginx 2>/dev/null
  else
    sudo systemctl enable "${SERVICE_NAME}-frontend" 2>/dev/null
  fi
  log_info "开机自启已配置"
fi

# ═══════════════════════════════════════════════
# Step 9: 启动服务
# ═══════════════════════════════════════════════
log_step "9/9" "启动服务"

# 启动后端
sudo systemctl start "${SERVICE_NAME}-backend"
sleep 3
BACKEND_OK=$(systemctl is-active "${SERVICE_NAME}-backend" 2>/dev/null)
if [ "$BACKEND_OK" = "active" ]; then
  log_info "后端已启动 (端口 $BACKEND_PORT)"
else
  log_err "后端启动失败"
  echo -e "  ${YELLOW}  最近日志:${NC}"
  journalctl -u "${SERVICE_NAME}-backend" -n 10 --no-pager 2>/dev/null | sed 's/^/    /'
fi

# 启动前端
if [ "$FRONTEND_USING_NGINX" = true ]; then
  sudo systemctl start nginx 2>/dev/null || sudo systemctl reload nginx 2>/dev/null || true
  sleep 1
  FRONTEND_OK=$(systemctl is-active nginx 2>/dev/null)
else
  sudo systemctl start "${SERVICE_NAME}-frontend"
  sleep 1
  FRONTEND_OK=$(systemctl is-active "${SERVICE_NAME}-frontend" 2>/dev/null)
fi

if [ "$FRONTEND_OK" = "active" ]; then
  log_info "前端已启动 (端口 $FRONTEND_PORT) [$FRONTEND_DESC]"
else
  log_err "前端启动失败"
  echo -e "  ${YELLOW}  最近日志:${NC}"
  journalctl -u nginx -n 5 --no-pager 2>/dev/null | sed 's/^/    /'
  journalctl -u "${SERVICE_NAME}-frontend" -n 5 --no-pager 2>/dev/null | sed 's/^/    /'
fi

# ═══════════════════════════════════════════════
# 完成
# ═══════════════════════════════════════════════
touch "$MARKER"
exec > /dev/tty 2>&1

LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
PUBLIC_IP=$(curl -fsSL --connect-timeout 3 ifconfig.me 2>/dev/null || curl -fsSL --connect-timeout 3 ipinfo.io/ip 2>/dev/null || echo "")

echo -e "\n${CYAN}${BOLD}"
echo "╔════════════════════════════════════════════╗"
echo "║           🎉 部署完成！                   ║"
echo "╠════════════════════════════════════════════╣"
printf "║  本地访问: http://localhost:%-17s║\n" "$FRONTEND_PORT"
if [ -n "$LOCAL_IP" ]; then
  printf "║  局域网:   http://%-27s║\n" "$LOCAL_IP:$FRONTEND_PORT"
fi
if [ -n "$PUBLIC_IP" ]; then
  printf "║  公网IP:   %-34s║\n" "$PUBLIC_IP"
fi
echo "║                                          ║"
echo "║  ⚡ 首次打开请完成设置向导               ║"
if [ "$FRONTEND_USING_NGINX" = true ]; then
echo "║  🔗 API已通过nginx反向代理到后端         ║"
fi
echo "║                                          ║"
echo "║  常用命令:                               ║"
echo "║  查看状态: sudo systemctl status tgmonitor-backend"
echo "║  后端日志: journalctl -u tgmonitor-backend -f"
echo "║  重启服务: sudo systemctl restart tgmonitor-backend nginx"
echo "║  停止服务: sudo systemctl stop tgmonitor-backend nginx"
echo "║  重新部署: ./start.sh --reset            ║"
echo "║  部署日志: cat $LOG_FILE"
echo "╚════════════════════════════════════════════╝"
echo -e "${NC}"
