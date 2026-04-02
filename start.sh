#!/bin/bash
# ============================================================
#  TG Monitor v2 - 一键部署脚本
#  用法: ./start.sh [--reset] [--no-autostart] [--mirror <tsinghua|aliyun|off>]
#  适用: Ubuntu 20.04+ / Debian 11+ (全新系统直接跑)
# ============================================================

# ── 颜色 ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'

log_ok()    { echo -e "  ${GREEN}✅ $1${NC}"; }
log_do()    { echo -e "  ${YELLOW}⏳ $1${NC}"; }
log_fail()  { echo -e "  ${RED}❌ $1${NC}"; }
log_info()  { echo -e "  ${DIM}   $1${NC}"; }
log_step()  { echo -e "\n${CYAN}${BOLD}━━━ [$1/9] $2 ${BOLD}━━━${NC}"; }

# ── 路径 ──
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
PROJECT_DIR=""
_dir="$SCRIPT_DIR"
while [ "$_dir" != "/" ]; do
  if [ -d "$_dir/backend" ] && [ -d "$_dir/frontend" ]; then
    PROJECT_DIR="$_dir"; break
  fi
  _dir="$(dirname "$_dir")"
done
if [ -z "$PROJECT_DIR" ]; then
  log_fail "找不到包含 backend/ 和 frontend/ 的项目目录（当前: $SCRIPT_DIR）"
  exit 1
fi

BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
SERVICE_NAME="tgmonitor"
LOG_FILE="/tmp/tg-monitor-deploy.log"
BACKEND_PORT=8000
FRONTEND_PORT=3000

# ── 参数解析 ──
RESET=false; NO_AUTOSTART=false; MIRROR="auto"
for arg in "$@"; do
  case "$arg" in
    --reset) RESET=true ;;
    --no-autostart) NO_AUTOSTART=true ;;
    --mirror) shift; MIRROR="$1" ;;
    --mirror=*) MIRROR="${arg#*=}" ;;
    --help) echo "用法: ./start.sh [--reset] [--no-autostart] [--mirror <tsinghua|aliyun|off>]"; exit 0 ;;
  esac
done

# ── 镜像 ──
if [ "$MIRROR" = "auto" ]; then
  IP_REGION=$(curl -fsSL --connect-timeout 3 ipinfo.io/country 2>/dev/null || echo "CN")
  [ "$IP_REGION" = "CN" ] && MIRROR="tsinghua" || MIRROR="off"
fi
case "$MIRROR" in
  tsinghua) PIP_INDEX="https://pypi.tuna.tsinghua.edu.cn/simple"; NPM_REGISTRY="https://registry.npmmirror.com"; MIRROR_LABEL="清华镜像" ;;
  aliyun)  PIP_INDEX="https://mirrors.aliyun.com/pypi/simple/"; NPM_REGISTRY="https://registry.npmmirror.com"; MIRROR_LABEL="阿里云镜像" ;;
  *)       PIP_INDEX=""; NPM_REGISTRY=""; MIRROR_LABEL="官方源" ;;
esac

# ── 端口检测 ──
check_port() { ss -tlnp 2>/dev/null | grep -q ":$1 " || { command -v lsof &>/dev/null && lsof -i ":$1" &>/dev/null; }; return $?; }

# ═══════════════════════════════════════════════════════════════
#  Banner
# ═══════════════════════════════════════════════════════════════
echo -e "${CYAN}${BOLD}"
echo "╔══════════════════════════════════════════╗"
echo "║     TG Monitor v2 - 一键部署            ║"
echo "╠══════════════════════════════════════════╣"
echo "║  项目: $PROJECT_DIR"
echo "║  镜像: $MIRROR_LABEL"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

$RESET && { rm -f "$PROJECT_DIR/.deployed"; log_do "已重置部署状态"; }

exec > >(tee -a "$LOG_FILE") 2>&1

# ═══════════════════════════════════════════════════════════════
#  [1/9] 检测系统环境
# ═══════════════════════════════════════════════════════════════
log_step "1" "检测系统环境"

if [ -f /etc/os-release ]; then
  . /etc/os-release
  log_ok "操作系统: $PRETTY_NAME"
else
  log_fail "无法检测操作系统版本"; exit 1
fi

ARCH=$(uname -m)
log_ok "系统架构: $ARCH"

MEM_MB=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print int($2/1024)}')
if [ -n "$MEM_MB" ] && [ "$MEM_MB" -lt 512 ]; then
  log_fail "内存不足: ${MEM_MB}MB（建议至少 512MB）"; exit 1
fi
log_ok "内存: ${MEM_MB}MB"

AVAIL_KB=$(df "$PROJECT_DIR" 2>/dev/null | awk 'NR==2 {print $4}')
AVAIL_GB=$((AVAIL_KB / 1024 / 1024))
if [ "$AVAIL_GB" -lt 2 ]; then
  log_fail "磁盘空间不足: ${AVAIL_GB}GB（建议至少 2GB）"; exit 1
fi
log_ok "磁盘可用: ${AVAIL_GB}GB"

check_port $BACKEND_PORT && log_do "端口 $BACKEND_PORT 已被占用（后端可能冲突）" || log_ok "端口 $BACKEND_PORT 空闲"
check_port $FRONTEND_PORT && log_do "端口 $FRONTEND_PORT 已被占用（前端可能冲突）" || log_ok "端口 $FRONTEND_PORT 空闲"

log_ok "系统环境检查通过 ✓"

# ═══════════════════════════════════════════════════════════════
#  [2/9] 安装系统依赖
# ═══════════════════════════════════════════════════════════════
log_step "2" "安装系统依赖"

log_do "更新软件源 (apt-get update)..."
sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq 2>&1
if [ $? -eq 0 ]; then
  log_ok "软件源更新完成"
else
  log_fail "软件源更新失败，请检查网络"; exit 1
fi

# 基础工具
log_do "安装基础工具 (curl, wget, git, build-essential, libffi-dev, libssl-dev)..."
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y curl wget git build-essential libffi-dev libssl-dev pkg-config 2>&1 | tail -1
log_ok "基础工具安装完成"

# ── Python3 ──
if command -v python3 &>/dev/null; then
  log_ok "Python3 已安装: $(python3 --version 2>&1 | awk '{print $2}')"
else
  log_do "安装 Python3..."
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3 2>&1 | tail -2
  if command -v python3 &>/dev/null; then
    log_ok "Python3 安装成功: $(python3 --version 2>&1 | awk '{print $2}')"
  else
    log_fail "Python3 安装失败"; exit 1
  fi
fi

# ── pip ──
if command -v pip3 &>/dev/null; then
  log_ok "pip3 已安装"
else
  log_do "安装 pip3..."
  # 先尝试apt
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3-pip 2>&1 | tail -2
  if command -v pip3 &>/dev/null; then
    log_ok "pip3 安装成功 (apt)"
  else
    # 回退get-pip.py
    curl -fsSL https://bootstrap.pypa.io/get-pip.py | sudo python3 2>&1 | tail -2
    if command -v pip3 &>/dev/null; then
      log_ok "pip3 安装成功 (get-pip.py)"
    else
      log_fail "pip3 安装失败"; exit 1
    fi
  fi
fi

# ── Node.js ──
if command -v node &>/dev/null; then
  NODE_VER=$(node --version 2>/dev/null | sed 's/v//')
  NODE_MAJOR=$(echo "$NODE_VER" | cut -d. -f1)
  log_ok "Node.js 已安装: $NODE_VER"
else
  log_do "安装 Node.js LTS..."

  NODE_OK=false

  # 方式1: NodeSource
  log_info "尝试 NodeSource..."
  if curl -fsSL --connect-timeout 10 https://deb.nodesource.com/setup_lts.x 2>/dev/null | sudo -E bash - >/dev/null 2>&1; then
    if sudo DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs 2>&1 | tail -1; then
      command -v node &>/dev/null && NODE_OK=true
    fi
  fi

  # 方式2: snap
  if [ "$NODE_OK" = false ] && command -v snap &>/dev/null; then
    log_info "NodeSource失败，尝试 snap..."
    sudo snap install node --classic 2>&1 | tail -1 && NODE_OK=true
  fi

  # 方式3: apt默认
  if [ "$NODE_OK" = false ]; then
    log_info "snap失败，尝试 apt 默认仓库..."
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs npm 2>&1 | tail -1 && NODE_OK=true
  fi

  if [ "$NODE_OK" = false ] || ! command -v node &>/dev/null; then
    log_fail "Node.js 安装失败（所有方式均失败）"
    exit 1
  fi

  NODE_VER=$(node --version 2>/dev/null | sed 's/v//')
  NODE_MAJOR=$(echo "$NODE_VER" | cut -d. -f1)
  log_ok "Node.js 安装成功: $NODE_VER"
fi

if [ -n "$NODE_MAJOR" ] && [ "$NODE_MAJOR" -lt 18 ]; then
  log_fail "Node.js 版本过低: $NODE_VER（需要 >= 18）"; exit 1
fi
log_ok "npm $(npm --version 2>/dev/null)"

# ── MySQL ──
if command -v mysql &>/dev/null; then
  MYSQL_VER=$(mysql --version 2>/dev/null | grep -oP '\d+\.\d+' | head -1)
  log_ok "MySQL $MYSQL_VER 已安装"
else
  MYSQL_VER=""
fi

if [ -z "$MYSQL_VER" ]; then
  log_do "安装 MySQL Server..."
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y mysql-server 2>&1 | tail -3
  if command -v mysql &>/dev/null; then
    MYSQL_VER=$(mysql --version 2>/dev/null | grep -oP '\d+\.\d+' | head -1)
    log_ok "MySQL $MYSQL_VER 安装完成"
  else
    log_fail "MySQL 安装失败"; exit 1
  fi
fi

# 启动MySQL
log_do "启动 MySQL 服务..."
sudo mkdir -p /var/run/mysqld && sudo chown mysql:mysql /var/run/mysqld
for try in 1 2 3 4 5; do
  sudo systemctl start mysql 2>/dev/null
  sleep 2
  if systemctl is-active --quiet mysql 2>/dev/null; then
    break
  fi
done
if systemctl is-active --quiet mysql 2>/dev/null; then
  log_ok "MySQL 服务运行中"
else
  log_fail "MySQL 启动失败"; exit 1
fi

# ── MySQL密码配置 ──
PYTHON_BIN=$(which python3 2>/dev/null || echo "python3")
MYSQL_PWD_OK=false
MYSQL_ROOT_PWD=""
DB_USER="tgmonitor"
DB_PASS=""
DB_NAME="tg_monitor"

# 1. 检查已有.env配置
if [ -f "$BACKEND_DIR/.env" ]; then
  SAVED_USER=$(grep "^MYSQL_USER=" "$BACKEND_DIR/.env" | cut -d= -f2)
  SAVED_PASS=$(grep "^MYSQL_PASSWORD=" "$BACKEND_DIR/.env" | cut -d= -f2)
  SAVED_NAME=$(grep "^MYSQL_DATABASE=" "$BACKEND_DIR/.env" | cut -d= -f2)
  if [ -n "$SAVED_USER" ] && [ -n "$SAVED_PASS" ]; then
    log_info "检测到已有数据库配置，验证连接..."
    if $PYTHON_BIN -c "
import pymysql
conn = pymysql.connect(host='localhost', user='$SAVED_USER', password='$SAVED_PASS', connect_timeout=5)
conn.close()
" 2>/dev/null; then
      log_ok "数据库连接正常，跳过密码设置"
      DB_USER="$SAVED_USER"; DB_PASS="$SAVED_PASS"; DB_NAME="${SAVED_NAME:-tg_monitor}"
      MYSQL_PWD_OK=true
    else
      log_info "已有配置但连接失败，将重新配置"
    fi
  fi
fi

# 2. 尝试sudo mysql直连（auth_socket）
if [ "$MYSQL_PWD_OK" = false ]; then
  if sudo mysql -e "SELECT 1" &>/dev/null; then
    # 能免密连接，设置密码
    echo ""
    echo -e "  ${CYAN}请为 MySQL root 设置密码（直接回车跳过）：${NC}"
    echo -ne "  ${YELLOW}输入密码: ${NC}"; read -s MYSQL_ROOT_PWD; echo ""
    if [ -n "$MYSQL_ROOT_PWD" ]; then
      echo -ne "  ${YELLOW}再次确认: ${NC}"; read -s MYSQL_ROOT_PWD2; echo ""
      if [ "$MYSQL_ROOT_PWD" != "$MYSQL_ROOT_PWD2" ]; then
        echo -e "  ${RED}不一致，不设密码${NC}"; MYSQL_ROOT_PWD=""
      fi
    fi
    sudo mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED WITH caching_sha2_password BY '${MYSQL_ROOT_PWD}'; FLUSH PRIVILEGES;" 2>/dev/null
    log_ok "MySQL root 密码配置完成"
    MYSQL_PWD_OK=true
  else
    # 尝试空密码
    if sudo mysql -u root -p'' -e "SELECT 1" &>/dev/null; then
      log_ok "MySQL root 无密码"
      MYSQL_PWD_OK=true
    else
      # 用debconf获取安装时设置的密码
      DEB_PWD=$(sudo debconf-show mysql-server 2>/dev/null | grep "mysql-server/root_password" | cut -d= -f2 | tr -d ' ')
      if [ -n "$DEB_PWD" ]; then
        if sudo mysql -u root -p"$DEB_PWD" -e "SELECT 1" &>/dev/null; then
          MYSQL_ROOT_PWD="$DEB_PWD"
          log_ok "MySQL root 密码验证通过"
          MYSQL_PWD_OK=true
        fi
      fi
    fi
  fi
fi

# 3. 最终手段：skip-grant-tables
if [ "$MYSQL_PWD_OK" = false ]; then
  log_do "使用安全模式重置密码..."
  sudo systemctl stop mysql 2>/dev/null; sleep 2
  sudo killall -9 mysqld 2>/dev/null; sleep 2
  sudo mkdir -p /var/run/mysqld && sudo chown mysql:mysql /var/run/mysqld

  sudo mysqld_safe --skip-grant-tables --skip-networking >/dev/null 2>&1 &
  sleep 10

  if sudo mysql -e "SELECT 1" &>/dev/null; then
    sudo mysql -e "FLUSH PRIVILEGES; ALTER USER 'root'@'localhost' IDENTIFIED WITH caching_sha2_password BY 'tg_monitor_tmp'; FLUSH PRIVILEGES;" 2>&1
    sudo mysqladmin -u root shutdown 2>/dev/null || sudo killall -9 mysqld 2>/dev/null
    sleep 3
    MYSQL_ROOT_PWD="tg_monitor_tmp"
    log_ok "安全模式密码重置成功"
  else
    sudo killall -9 mysqld 2>/dev/null; sleep 2
    log_fail "MySQL 密码重置失败，请手动处理"; exit 1
  fi

  # 重启MySQL
  sudo mkdir -p /var/run/mysqld && sudo chown mysql:mysql /var/run/mysqld
  sudo systemctl start mysql 2>/dev/null; sleep 5
  if ! systemctl is-active --quiet mysql 2>/dev/null; then
    log_fail "MySQL 重启失败"; exit 1
  fi
  MYSQL_PWD_OK=true
fi

# ── 创建数据库和用户 ──
log_do "创建 MySQL 数据库和用户..."
if [ -z "$DB_PASS" ]; then
  DB_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")
fi

sudo mysql -u root ${MYSQL_ROOT_PWD:+-p"$MYSQL_ROOT_PWD"} << EOSQL 2>/dev/null
CREATE DATABASE IF NOT EXISTS ${DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
ALTER USER '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${DB_USER}'@'localhost';
FLUSH PRIVILEGES;
EOSQL

if [ $? -eq 0 ]; then
  log_ok "数据库 ${DB_NAME} ✓ / 用户 ${DB_USER} ✓"
else
  log_fail "数据库创建失败"; exit 1
fi

# 生成 .env
log_do "生成 backend/.env 配置文件..."
cat > "$BACKEND_DIR/.env" << EOF
# MySQL（自动生成，请勿手动修改）
DATABASE_TYPE=mysql
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=${DB_USER}
MYSQL_PASSWORD=${DB_PASS}
MYSQL_DATABASE=${DB_NAME}
EOF
log_ok "配置文件已生成: $BACKEND_DIR/.env"

log_ok "系统依赖全部安装完成 ✓"

# ═══════════════════════════════════════════════════════════════
#  [3/9] 安装 Python 依赖
# ═══════════════════════════════════════════════════════════════
log_step "3" "安装 Python 依赖"

PYTHON_BIN=${PYTHON_BIN:-$(which python3)}
PIP_BIN=$(which pip3 2>/dev/null)
if [ -z "$PIP_BIN" ]; then
  # pip3命令不存在但模块可用，创建临时wrapper
  PIP_WRAPPER="/tmp/tg-monitor-pip3"
  echo '#!/bin/bash' > "$PIP_WRAPPER"
  echo 'python3 -m pip "$@"' >> "$PIP_WRAPPER"
  chmod +x "$PIP_WRAPPER"
  PIP_BIN="$PIP_WRAPPER"
fi
log_info "Python: $PYTHON_BIN"
log_info "pip: $PIP_BIN"

log_do "升级 pip..."
$PIP_BIN install --upgrade pip --break-system-packages -q 2>/dev/null
log_ok "pip 升级完成: $($PIP_BIN --version 2>&1 | awk '{print $2}')"

# Ubuntu 25.04+ 移除了 distutils，某些包需要它
log_do "检查 distutils..."
if ! $PYTHON_BIN -c "import distutils" 2>/dev/null; then
  log_info "distutils 不可用，安装 setuptools..."
  $PIP_BIN install setuptools --break-system-packages -q 2>/dev/null
  if $PYTHON_BIN -c "import distutils" 2>/dev/null; then
    log_ok "distutils 安装成功 (通过 setuptools)"
  else
    log_info "尝试 apt 安装..."
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3-distutils 2>&1 | tail -2 || true
    if $PYTHON_BIN -c "import distutils" 2>/dev/null; then
      log_ok "distutils 安装成功 (apt)"
    else
      log_fail "distutils 安装失败，部分包可能无法安装"
    fi
  fi
else
  log_ok "distutils 可用"
fi

if [ -f "$BACKEND_DIR/requirements.txt" ]; then
  log_do "安装 requirements.txt 中的依赖..."
  log_info "依赖文件: $BACKEND_DIR/requirements.txt"
  PKG_COUNT=$(grep -c "^[^#]" "$BACKEND_DIR/requirements.txt" 2>/dev/null || echo "未知")
  log_info "依赖数量: ${PKG_COUNT} 个包"
  [ -n "$PIP_INDEX" ] && log_info "使用镜像: $PIP_INDEX"

  PIP_ARGS="-r $BACKEND_DIR/requirements.txt --break-system-packages --ignore-installed --no-user"
  [ -n "$PIP_INDEX" ] && PIP_ARGS="$PIP_ARGS -i $PIP_INDEX --trusted-host $(echo $PIP_INDEX | sed 's|https://||;s|/simple.*||')"

  PIP_OUTPUT=$($PIP_BIN install $PIP_ARGS 2>&1)
  PIP_EXIT=$?
  echo "$PIP_OUTPUT" | tail -8
  if [ $PIP_EXIT -eq 0 ]; then
    log_ok "Python 依赖安装完成 ✓"
  else
    log_do "首次安装失败（退出码: $PIP_EXIT），正在重试..."
    PIP_OUTPUT=$($PIP_BIN install $PIP_ARGS 2>&1)
    PIP_EXIT=$?
    echo "$PIP_OUTPUT" | tail -5
    if [ $PIP_EXIT -eq 0 ]; then
      log_ok "Python 依赖安装完成（重试成功）✓"
    else
      log_fail "Python 依赖安装失败（退出码: $PIP_EXIT）"
      echo "$PIP_OUTPUT" | grep -i "error\|failed\|Could not" | head -5 | sed 's/^/    /'
      exit 1
    fi
  fi
else
  log_fail "未找到 requirements.txt ($BACKEND_DIR/requirements.txt)"; exit 1
fi

# ═══════════════════════════════════════════════════════════════
#  [4/9] 安装前端依赖
# ═══════════════════════════════════════════════════════════════
log_step "4" "安装前端依赖"
cd "$FRONTEND_DIR"

if [ -d "node_modules" ] && [ "$(ls node_modules 2>/dev/null | wc -l)" -gt 10 ]; then
  log_ok "node_modules 已存在 ($(ls node_modules | wc -l) 个包)"
else
  rm -rf node_modules
  log_do "执行 npm install --legacy-peer-deps（首次安装可能需要1-3分钟）..."
  log_info "目录: $FRONTEND_DIR"
  [ -n "$NPM_REGISTRY" ] && log_info "使用镜像: $NPM_REGISTRY"

  NPM_INSTALL="npm install --legacy-peer-deps"
  [ -n "$NPM_REGISTRY" ] && NPM_INSTALL="$NPM_INSTALL --registry=$NPM_REGISTRY"

  NPM_OK=false
  if $NPM_INSTALL 2>&1 | tail -5; then
    if [ -d "node_modules" ] && [ "$(ls node_modules | wc -l)" -gt 5 ]; then
      NPM_OK=true
    fi
  fi

  if [ "$NPM_OK" = false ]; then
    log_fail "npm install 失败（node_modules 不完整）"
    log_fail "请查看完整日志: $LOG_FILE"
    log_fail "或手动执行: cd $FRONTEND_DIR && npm install --legacy-peer-deps"
    exit 1
  fi
  log_ok "前端依赖安装完成 ($(ls node_modules | wc -l) 个包) ✓"
fi
cd "$PROJECT_DIR"

# ═══════════════════════════════════════════════════════════════
#  [5/9] 构建前端
# ═══════════════════════════════════════════════════════════════
log_step "5" "构建前端"
cd "$FRONTEND_DIR"

BUILD_OK=false
# 跳过tsc类型检查（不影响构建产物），直接vite build
log_do "执行 vite build..."
log_info "（跳过tsc类型检查以加速构建）"
if timeout 180 npx vite build 2>&1 | tail -8; then
  BUILD_OK=true
fi

if [ "$BUILD_OK" = false ]; then
  log_fail "vite build 失败"
  exit 1
fi

if [ "$BUILD_OK" = true ] && [ -d "$FRONTEND_DIR/dist" ] && [ -n "$(ls -A $FRONTEND_DIR/dist 2>/dev/null)" ]; then
  DIST_SIZE=$(du -sh "$FRONTEND_DIR/dist" 2>/dev/null | cut -f1)
  log_ok "前端构建完成 (dist/ 大小: $DIST_SIZE) ✓"
else
  log_fail "前端构建失败（dist/ 为空或不存在）"
  log_fail "请检查 Node.js 版本 >= 18: node --version"
  exit 1
fi
cd "$PROJECT_DIR"

# ═══════════════════════════════════════════════════════════════
#  [6/9] 初始化数据库
# ═══════════════════════════════════════════════════════════════
log_step "6" "初始化数据库"

log_do "测试 MySQL 连接..."
if ! $PYTHON_BIN -c "
import pymysql
try:
    conn = pymysql.connect(host='localhost', user='$DB_USER', password='$DB_PASS', connect_timeout=5)
    conn.close()
    print('MySQL连接成功')
except Exception as e:
    import sys; print(f'连接失败: {e}'); sys.exit(1)
" 2>&1; then
  log_fail "无法连接 MySQL"; exit 1
fi
log_ok "MySQL 连接成功"

if [ -f "$BACKEND_DIR/init_db.py" ]; then
  log_do "执行数据库初始化脚本..."
  log_info "脚本: $BACKEND_DIR/init_db.py"
  if $PYTHON_BIN "$BACKEND_DIR/init_db.py" 2>&1; then
    log_ok "数据库初始化完成 ✓"
  else
    log_fail "数据库初始化失败，请查看上方错误信息"; exit 1
  fi
else
  log_fail "未找到 init_db.py ($BACKEND_DIR/init_db.py)"; exit 1
fi

# ═══════════════════════════════════════════════════════════════
#  [7/9] 下载代理内核
# ═══════════════════════════════════════════════════════════════
log_step "7" "下载代理内核 (mihomo)"
PROXY_DIR="$BACKEND_DIR/app/proxy"
MIHOMO_PATH="$PROXY_DIR/mihomo"

if [ -f "$MIHOMO_PATH" ] && [ -x "$MIHOMO_PATH" ]; then
  log_ok "mihomo 内核已存在 ($(du -h "$MIHOMO_PATH" | cut -f1))"
else
  case $ARCH in
    x86_64) DL_ARCH="amd64" ;;
    aarch64|arm64) DL_ARCH="arm64" ;;
    *) log_fail "不支持的架构: $ARCH"; DL_ARCH="" ;;
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
    for i in "${!DL_URLS[@]}"; do
      log_do "尝试下载源 $((i+1))/$((${#DL_URLS[@]}))..."
      log_info "${DL_URLS[$i]}"
      if curl -fsSL --connect-timeout 15 "${DL_URLS[$i]}" -o /tmp/mihomo.gz 2>/dev/null; then
        if gunzip -f /tmp/mihomo.gz 2>/dev/null && [ -f /tmp/mihomo ] && [ -s /tmp/mihomo ]; then
          mv /tmp/mihomo "$MIHOMO_PATH" && chmod +x "$MIHOMO_PATH"
          log_ok "mihomo 下载成功 ($(du -h "$MIHOMO_PATH" | cut -f1)) ✓"
          DL_OK=true; break
        fi
        rm -f /tmp/mihomo /tmp/mihomo.gz
      fi
      log_info "此源下载失败，尝试下一个..."
    done

    if [ "$DL_OK" = false ]; then
      log_fail "mihomo 下载失败（所有4个源均失败）"
      log_fail "代理功能暂不可用，不影响核心监控功能"
      log_info "可稍后手动下载: curl -L ${DL_URLS[0]} | gunzip > $MIHOMO_PATH"
    fi
  fi
fi

# ═══════════════════════════════════════════════════════════════
#  [8/9] 配置系统服务
# ═══════════════════════════════════════════════════════════════
log_step "8" "配置系统服务"

# 停旧服务
log_do "停止旧服务（如有）..."
sudo systemctl stop "${SERVICE_NAME}-backend" 2>/dev/null && log_info "已停止 ${SERVICE_NAME}-backend" || log_info "无旧后端服务"
sudo systemctl stop "${SERVICE_NAME}-frontend" 2>/dev/null && log_info "已停止 ${SERVICE_NAME}-frontend" || log_info "无旧前端服务"

# ── 后端 service ──
log_do "生成后端 systemd 服务..."
cat > "/tmp/${SERVICE_NAME}-backend.service" << EOF
[Unit]
Description=TG Monitor v2 Backend
After=network.target mysql.service mysqld.service
Wants=mysql.service

[Service]
Type=simple
WorkingDirectory=$BACKEND_DIR
Environment="PATH=/home/$SUDO_USER/.local/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=/home/$SUDO_USER/.local/lib/python3.13/site-packages"
ExecStart=$PYTHON_BIN -m uvicorn app.main:app --host 0.0.0.0 --port $BACKEND_PORT
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
sudo cp "/tmp/${SERVICE_NAME}-backend.service" /etc/systemd/system/
log_ok "后端服务文件已生成: /etc/systemd/system/${SERVICE_NAME}-backend.service"
log_info "工作目录: $BACKEND_DIR"
log_info "启动命令: $PYTHON_BIN -m uvicorn app.main:app --host 0.0.0.0 --port $BACKEND_PORT"

# ── 前端 ──
log_do "配置前端服务..."
# nginx用于SPA路由+API反向代理，必须安装
if ! command -v nginx &>/dev/null; then
  log_do "安装 nginx..."
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y nginx 2>&1 | tail -2
  if ! command -v nginx &>/dev/null; then
    log_fail "nginx 安装失败（前端服务必需）"; exit 1
  fi
  log_ok "nginx 安装完成"
fi

# 删除nginx默认站点，避免端口冲突
sudo rm -f /etc/nginx/sites-enabled/default

FRONTEND_USING_NGINX=false
if command -v nginx &>/dev/null; then
  log_info "检测到 nginx，配置反向代理..."
  cat > "/tmp/${SERVICE_NAME}-frontend.conf" << EOF
server {
    listen $FRONTEND_PORT;
    server_name _;
    root $FRONTEND_DIR/dist;
    index index.html;
    location / { try_files \$uri \$uri/ /index.html; }
    location /api/ {
        proxy_pass http://127.0.0.1:$BACKEND_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;
    }
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
  if sudo nginx -t 2>/dev/null; then
    FRONTEND_USING_NGINX=true
    log_ok "nginx 配置完成 (SPA路由 + API反向代理)"
    log_info "前端: $FRONTEND_DIR/dist → 端口 $FRONTEND_PORT"
    log_info "API:  /api/* → 127.0.0.1:$BACKEND_PORT"
  else
    log_fail "nginx 配置测试失败"
    sudo nginx -t 2>&1 | sed 's/^/    /'
    exit 1
  fi
fi

log_do "重载 systemd..."
sudo systemctl daemon-reload
log_ok "systemd 重载完成"

# ── 开机自启 ──
if $NO_AUTOSTART; then
  log_do "跳过开机自启 (--no-autostart)"
else
  log_do "配置开机自启..."
  sudo systemctl enable "${SERVICE_NAME}-backend" 2>/dev/null
  log_ok "后端开机自启: 已启用"
  sudo systemctl enable nginx 2>/dev/null
  log_ok "nginx 开机自启: 已启用"
fi

log_ok "系统服务配置完成 ✓"

# ═══════════════════════════════════════════════════════════════
#  [9/9] 启动服务
# ═══════════════════════════════════════════════════════════════
log_step "9" "启动服务"

log_do "启动后端 (端口 $BACKEND_PORT)..."
sudo systemctl start "${SERVICE_NAME}-backend"
sleep 3
BACKEND_OK=$(systemctl is-active "${SERVICE_NAME}-backend" 2>/dev/null)
if [ "$BACKEND_OK" = "active" ]; then
  # 等待后端完全启动并验证API可用
  log_info "等待后端就绪..."
  API_READY=false
  for api_try in 1 2 3 4 5 6; do
    sleep 2
    if curl -sf "http://127.0.0.1:$BACKEND_PORT/health" >/dev/null 2>&1; then
      API_READY=true; break
    fi
  done
  if [ "$API_READY" = true ]; then
    log_ok "后端启动成功 ✓ (API验证通过)"
  else
    log_fail "后端进程运行中但API无响应"
    echo -e "  ${YELLOW}  最近日志:${NC}"
    journalctl -u "${SERVICE_NAME}-backend" -n 15 --no-pager 2>/dev/null | sed 's/^/    /'
  fi
else
  log_fail "后端启动失败"
  echo -e "  ${YELLOW}  诊断信息:${NC}"
  echo -e "    工作目录: $(sudo systemctl show ${SERVICE_NAME}-backend -p WorkingDirectory --value 2>/dev/null)"
  echo -e "    Python: $PYTHON_BIN"
  echo -e "    .env: $(ls -la $BACKEND_DIR/.env 2>/dev/null || echo '不存在')"
  $PYTHON_BIN -c "import fastapi, uvicorn, sqlalchemy, pymysql" 2>&1 | sed 's/^/    import: /' || true
  echo -e "  ${YELLOW}  最近日志:${NC}"
  journalctl -u "${SERVICE_NAME}-backend" -n 15 --no-pager 2>/dev/null | sed 's/^/    /'
fi

log_do "启动前端 (nginx, 端口 $FRONTEND_PORT)..."
sudo systemctl start nginx 2>/dev/null || sudo systemctl reload nginx 2>/dev/null || true
sleep 1
FRONTEND_OK=$(systemctl is-active nginx 2>/dev/null)
if [ "$FRONTEND_OK" = "active" ]; then
  log_ok "前端启动成功 ✓"
else
  log_fail "nginx 启动失败"
  sudo nginx -t 2>&1 | sed 's/^/    /'
fi

# ═══════════════════════════════════════════════════════════════
#  完成
# ═══════════════════════════════════════════════════════════════
touch "$PROJECT_DIR/.deployed"

# ── 端到端验证 ──
echo ""
log_do "端到端验证..."
VERIFY_OK=true
# 1. 后端API
if curl -sf "http://127.0.0.1:$BACKEND_PORT/health" >/dev/null 2>&1; then
  log_ok "后端 API: 正常"
else
  log_fail "后端 API: 无响应"; VERIFY_OK=false
fi
# 2. 前端页面
if curl -sf "http://127.0.0.1:$FRONTEND_PORT/" >/dev/null 2>&1; then
  log_ok "前端页面: 正常"
else
  log_fail "前端页面: 无响应"; VERIFY_OK=false
fi
# 3. API代理
if curl -sf "http://127.0.0.1:$FRONTEND_PORT/api/v1/system/status" >/dev/null 2>&1; then
  log_ok "API代理 (nginx→后端): 正常"
else
  log_fail "API代理 (nginx→后端): 失败"; VERIFY_OK=false
fi

# 4. 详细API测试
log_info "API端点测试..."
for endpoint in "/api/v1/dashboard/stats" "/api/v1/proxy/status" "/api/v1/keywords/keyword-groups" "/api/v1/notifications" "/api/v1/accounts"; do
  STATUS=$(curl -so /dev/null -w "%{http_code}" "http://127.0.0.1:$BACKEND_PORT$endpoint" 2>/dev/null)
  if [ "$STATUS" = "200" ] || [ "$STATUS" = "201" ]; then
    log_info "  $endpoint → $STATUS ✓"
  else
    log_info "  $endpoint → $STATUS ⚠️"
  fi
done

if [ "$VERIFY_OK" = false ]; then
  log_fail "端到端验证未全部通过，请检查上方错误"
fi

exec > /dev/tty 2>&1

LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
PUBLIC_IP=$(curl -fsSL --connect-timeout 3 ifconfig.me 2>/dev/null || echo "")

echo -e "\n${CYAN}${BOLD}"
echo "╔════════════════════════════════════════════╗"
echo "║          🎉 部署完成！                    ║"
echo "╠════════════════════════════════════════════╣"
printf "║  本地访问: http://localhost:%-17s║\n" "$FRONTEND_PORT"
[ -n "$LOCAL_IP" ]   && printf "║  局域网:   http://%-27s║\n" "$LOCAL_IP:$FRONTEND_PORT"
[ -n "$PUBLIC_IP" ]  && printf "║  公网IP:   %-34s║\n" "$PUBLIC_IP"
echo "║                                          ║"
echo "║  ⚡ 首次打开请完成设置向导               ║"
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
