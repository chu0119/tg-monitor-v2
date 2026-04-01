#!/bin/bash
# ============================================================
#  TG Monitor v2 - 一键部署脚本
#  用法: ./start.sh [--reset] [--no-autostart]
#  适用: Ubuntu 20.04+ / Debian 11+ (全新系统直接跑)
# ============================================================
# 不用 set -e，手动处理错误，避免静默退出

# ── 颜色 ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

# ── 路径 ──
# 脚本所在目录（解析软链接）
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"

# 项目根目录：向上查找包含 backend/ 和 frontend/ 的目录
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
  echo -e "${RED}❌ 找不到包含 backend/ 和 frontend/ 的项目目录${NC}"
  echo -e "${YELLOW}当前目录: $SCRIPT_DIR${NC}"
  echo -e "${YELLOW}请确认从项目根目录运行: cd <项目目录> && ./start.sh${NC}"
  exit 1
fi

MARKER="$PROJECT_DIR/.deployed"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/venv"
SERVICE_NAME="tgmonitor"

echo -e "${CYAN}${BOLD}"
echo "╔══════════════════════════════════════╗"
echo "║   TG Monitor v2 - 一键部署          ║"
echo "║   项目目录: $PROJECT_DIR"
echo "╚══════════════════════════════════════╝"
echo -e "${NC}"

# ── 参数解析 ──
RESET=false
NO_AUTOSTART=false
for arg in "$@"; do
  case "$arg" in
    --reset) RESET=true ;;
    --no-autostart) NO_AUTOSTART=true ;;
    --help) echo "用法: ./start.sh [--reset] [--no-autostart]"; exit 0 ;;
  esac
done

if $RESET; then
  rm -f "$MARKER"
  echo -e "${YELLOW}已重置部署状态，将重新执行所有步骤${NC}"
fi

# ═══════════════════════════════════════════
# Step 1: 检测系统环境
# ═══════════════════════════════════════════
echo -e "${BOLD}[1/8] 检测系统环境...${NC}"

# 检测是否为root或有无sudo权限
if [ "$EUID" -ne 0 ] && ! sudo -n true 2>/dev/null; then
  echo -e "${YELLOW}⚠️  需要sudo权限来安装系统依赖${NC}"
fi

# 检测操作系统
if [ -f /etc/os-release ]; then
  . /etc/os-release
  echo -e "  ${GREEN}✅ 系统: $ID $VERSION_ID ($PRETTY_NAME)${NC}"
  if [[ "$ID" != "ubuntu" && "$ID" != "debian" ]]; then
    echo -e "  ${YELLOW}⚠️  本脚本主要支持 Ubuntu/Debian，其他系统可能需要手动调整${NC}"
  fi
else
  echo -e "  ${YELLOW}⚠️  无法检测操作系统版本${NC}"
fi

# 检测架构
ARCH=$(uname -m)
echo -e "  ${GREEN}✅ 架构: $ARCH${NC}"

# 检测磁盘空间（至少需要2GB）
AVAIL_DISK=$(df "$PROJECT_DIR" | awk 'NR==2 {print $4}')
AVAIL_GB=$((AVAIL_DISK / 1024 / 1024))
if [ "$AVAIL_GB" -lt 2 ]; then
  echo -e "  ${RED}❌ 磁盘空间不足: 仅剩 ${AVAIL_GB}GB，建议至少 2GB${NC}"
  exit 1
else
  echo -e "  ${GREEN}✅ 磁盘空间: ${AVAIL_GB}GB 可用${NC}"
fi

check_cmd() {
  if command -v "$1" &>/dev/null; then
    local ver=$($1 --version 2>/dev/null | head -1 | grep -oP '[\d.]+' | head -1)
    echo -e "  ${GREEN}✅ $1${ver:+ ($ver)}${NC}"
    return 0
  else
    echo -e "  ${RED}❌ $1 未安装${NC}"
    return 1
  fi
}

check_cmd python3 || true
check_cmd git || true

# ═══════════════════════════════════════════
# Step 2: 安装系统依赖
# ═══════════════════════════════════════════
echo -e "\n${BOLD}[2/8] 安装系统依赖...${NC}"

# 确保有基本的构建工具
sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq 2>&1 || { echo -e "  ${RED}❌ apt-get update 失败${NC}"; exit 1; }
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y curl wget git build-essential 2>&1 | tail -1
echo -e "  ${GREEN}✅ 基础工具已就绪${NC}"

# Python3 + venv + pip
echo -e "  ${YELLOW}⏳ 检查 Python3 环境...${NC}"
if ! command -v python3 &>/dev/null; then
  echo -e "  ${YELLOW}  安装 python3...${NC}"
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3 2>&1 | tail -2
  if ! command -v python3 &>/dev/null; then
    echo -e "  ${RED}❌ python3 安装失败${NC}"; exit 1
  fi
fi

# python3-venv（Ubuntu 24.04+需要单独装）
PYTHON_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if ! python3 -c "import venv" 2>/dev/null; then
  echo -e "  ${YELLOW}  安装 python${PYTHON_VER}-venv...${NC}"
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "python${PYTHON_VER}-venv" 2>&1 | tail -2 || \
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv 2>&1 | tail -2
fi

# pip
if ! command -v pip3 &>/dev/null; then
  echo -e "  ${YELLOW}  安装 pip...${NC}"
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3-pip 2>&1 | tail -2
fi
echo -e "  ${GREEN}✅ Python3 $(python3 --version 2>&1 | awk '{print $2}')${NC}"

# Node.js
echo -e "  ${YELLOW}⏳ 检查 Node.js...${NC}"
if ! command -v node &>/dev/null; then
  echo -e "  ${YELLOW}  安装 Node.js（LTS版本）...${NC}"
  if ! dpkg -l 2>/dev/null | grep -q nodesource; then
    curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash - > /dev/null 2>&1
  fi
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs
fi
echo -e "  ${GREEN}✅ Node.js $(node --version 2>/dev/null)${NC}"
echo -e "  ${GREEN}✅ npm $(npm --version 2>/dev/null)${NC}"

# MySQL
echo -e "  ${YELLOW}⏳ 检查 MySQL...${NC}"
if ! command -v mysql &>/dev/null; then
  echo -e "  ${YELLOW}  安装 MySQL Server（可能需要1-2分钟）...${NC}"
  # 预配置root密码为空（避免交互式提示）
  sudo debconf-set-selections <<< "mysql-server mysql-server/root_password password ''" 2>/dev/null || true
  sudo debconf-set-selections <<< "mysql-server mysql-server/root_password_again password ''" 2>/dev/null || true
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y mysql-server
fi

# 启动MySQL
if ! systemctl is-active --quiet mysql 2>/dev/null && ! systemctl is-active --quiet mysqld 2>/dev/null; then
  echo -e "  ${YELLOW}  启动 MySQL 服务...${NC}"
  sudo systemctl start mysql 2>/dev/null || sudo systemctl start mysqld 2>/dev/null || sudo service mysql start 2>/dev/null || true
  sleep 2
fi

if systemctl is-active --quiet mysql 2>/dev/null || systemctl is-active --quiet mysqld 2>/dev/null; then
  echo -e "  ${GREEN}✅ MySQL 运行中${NC}"
else
  echo -e "  ${RED}❌ MySQL 启动失败，请手动检查${NC}"
  exit 1
fi

# ═══════════════════════════════════════════
# Step 3: Python虚拟环境和依赖
# ═══════════════════════════════════════════
echo -e "\n${BOLD}[3/8] 安装Python依赖...${NC}"

if [ ! -d "$VENV_DIR" ] || [ ! -f "$VENV_DIR/bin/python3" ]; then
  echo -e "  ${YELLOW}⏳ 创建虚拟环境 → $VENV_DIR${NC}"
  rm -rf "$VENV_DIR"
  python3 -m venv "$VENV_DIR"
  if [ ! -f "$VENV_DIR/bin/python3" ]; then
    echo -e "  ${RED}❌ 虚拟环境创建失败，请先安装: sudo apt install python3-venv${NC}"
    exit 1
  fi
  echo -e "  ${GREEN}✅ 虚拟环境已创建${NC}"
else
  echo -e "  ${GREEN}✅ 虚拟环境已存在: $VENV_DIR${NC}"
fi

source "$VENV_DIR/bin/activate"
echo -e "  ${GREEN}  Python: $(which python3)$(python3 --version 2>&1 | awk '{print " ("$2")"}')${NC}"

# 升级pip
pip install --upgrade pip -q 2>/dev/null

if [ -f "$BACKEND_DIR/requirements.txt" ]; then
  echo -e "  ${YELLOW}⏳ pip install -r requirements.txt...${NC}"
  pip install -r "$BACKEND_DIR/requirements.txt" 2>&1 | grep -v "already satisfied" | tail -5
  echo -e "  ${GREEN}✅ Python依赖安装完成${NC}"
else
  echo -e "  ${YELLOW}⚠️  未找到 requirements.txt，跳过${NC}"
fi

# ═══════════════════════════════════════════
# Step 4: 前端依赖
# ═══════════════════════════════════════════
echo -e "\n${BOLD}[4/8] 安装前端依赖...${NC}"
cd "$FRONTEND_DIR"

if [ ! -d "node_modules" ]; then
  echo -e "  ${YELLOW}⏳ npm install（可能需要1-2分钟）...${NC}"
  if npm install 2>&1 | tail -5; then
    echo -e "  ${GREEN}✅ 前端依赖安装完成${NC}"
  else
    echo -e "  ${RED}❌ npm install 失败${NC}"
    echo -e "  ${YELLOW}  尝试: cd $FRONTEND_DIR && npm install --legacy-peer-deps${NC}"
    exit 1
  fi
else
  echo -e "  ${GREEN}✅ node_modules 已存在${NC}"
fi
cd "$PROJECT_DIR"

# ═══════════════════════════════════════════
# Step 5: 构建前端
# ═══════════════════════════════════════════
echo -e "\n${BOLD}[5/8] 构建前端...${NC}"
cd "$FRONTEND_DIR"

# 检查tsc是否可用
if ! npx tsc --version &>/dev/null; then
  echo -e "  ${YELLOW}⚠️  tsc 未找到，跳过类型检查，直接构建${NC}"
  npx vite build 2>&1 | tail -5
else
  npm run build 2>&1 | tail -5
fi
cd "$PROJECT_DIR"

# ═══════════════════════════════════════════
# Step 6: 数据库初始化
# ═══════════════════════════════════════════
echo -e "\n${BOLD}[6/8] 初始化数据库...${NC}"

# 确保在正确的venv中
source "$VENV_DIR/bin/activate"

# 检查MySQL连接
echo -e "  ${YELLOW}⏳ 检查MySQL连接...${NC}"
if ! python3 -c "
import pymysql
try:
    pymysql.connect(host='localhost', user='root', password='', connect_timeout=5)
    print('    MySQL连接成功（无密码）')
except Exception as e:
    print(f'    MySQL连接失败: {e}')
    print('    请检查MySQL是否运行，或手动设置root密码')
    import sys; sys.exit(1)
" 2>&1; then
  echo -e "  ${RED}❌ 无法连接MySQL，请先确保MySQL服务正常运行${NC}"
  echo -e "  ${YELLOW}  修复: sudo systemctl start mysql${NC}"
  echo -e "  ${YELLOW}  如果root有密码，请手动执行: $VENV_DIR/bin/python3 $BACKEND_DIR/init_db.py${NC}"
  exit 1
fi

if [ -f "$BACKEND_DIR/init_db.py" ]; then
  echo -e "  ${YELLOW}⏳ 执行数据库初始化...${NC}"
  if python3 "$BACKEND_DIR/init_db.py" 2>&1; then
    echo -e "  ${GREEN}✅ 数据库初始化完成${NC}"
  else
    echo -e "  ${YELLOW}⚠️  数据库初始化出现警告，请查看上方输出${NC}"
  fi
else
  echo -e "  ${YELLOW}⚠️  未找到 init_db.py，跳过${NC}"
fi

# ═══════════════════════════════════════════
# Step 7: 下载代理内核
# ═══════════════════════════════════════════
echo -e "\n${BOLD}[7/8] 检查代理内核...${NC}"
PROXY_DIR="$BACKEND_DIR/app/proxy"
MIHOMO_PATH="$PROXY_DIR/mihomo"

if [ -f "$MIHOMO_PATH" ] && [ -x "$MIHOMO_PATH" ]; then
  echo -e "  ${GREEN}✅ mihomo 内核已存在${NC}"
else
  case $ARCH in
    x86_64) DL_ARCH="amd64" ;;
    aarch64|arm64) DL_ARCH="arm64" ;;
    *) echo -e "  ${YELLOW}⚠️  不支持的架构: $ARCH，跳过mihomo下载${NC}"; DL_ARCH="" ;;
  esac

  if [ -n "$DL_ARCH" ]; then
    echo -e "  ${YELLOW}⏳ 下载 mihomo ($DL_ARCH)...${NC}"
    MIHOMO_VER="v1.19.21"
    # 尝试多个下载源
    DL_URLS=(
      "https://github.com/MetaCubeX/mihomo/releases/download/${MIHOMO_VER}/mihomo-linux-${DL_ARCH}-${MIHOMO_VER}.gz"
      "https://bgithub.xyz/MetaCubeX/mihomo/releases/download/${MIHOMO_VER}/mihomo-linux-${DL_ARCH}-${MIHOMO_VER}.gz"
    )
    mkdir -p "$PROXY_DIR"

    DL_OK=false
    for url in "${DL_URLS[@]}"; do
      echo -e "  ${YELLOW}  尝试: ${url}${NC}"
      if [ -n "$DL_CMD" ] && $DL_CMD "$url" -o /tmp/mihomo.gz 2>/dev/null; then
        gunzip -f /tmp/mihomo.gz 2>/dev/null
        if [ -f /tmp/mihomo ] && [ -s /tmp/mihomo ]; then
          mv /tmp/mihomo "$MIHOMO_PATH"
          chmod +x "$MIHOMO_PATH"
          echo -e "  ${GREEN}✅ mihomo 内核已下载 ($(du -h "$MIHOMO_PATH" | cut -f1))${NC}"
          DL_OK=true
          break
        fi
      fi
    done

    if [ "$DL_OK" = false ]; then
      echo -e "  ${YELLOW}⚠️  所有源下载失败，请手动下载到 $MIHOMO_PATH${NC}"
      echo -e "  ${YELLOW}  源1: ${DL_URLS[0]}${NC}"
      echo -e "  ${YELLOW}  源2: ${DL_URLS[1]}${NC}"
    fi
  fi
fi

# ═══════════════════════════════════════════
# Step 8: 配置并启动服务
# ═══════════════════════════════════════════
echo -e "\n${BOLD}[8/8] 配置系统服务...${NC}"

# 查找npx的实际路径
NPX_PATH=$(which npx 2>/dev/null || echo "/usr/bin/npx")

# 查找前端构建产物目录
DIST_DIR="$FRONTEND_DIR/dist"
if [ -d "$DIST_DIR" ]; then
  # 用Python简单HTTP服务托管前端（最可靠，不依赖npx）
  FRONTEND_CMD="$VENV_DIR/bin/python3 -m http.server 3000 --directory $DIST_DIR"
  FRONTEND_DESC="Python HTTP Server (托管dist/)"
else
  # 回退到vite preview
  FRONTEND_CMD="$NPX_PATH vite preview --port 3000 --host 0.0.0.0"
  FRONTEND_DESC="Vite Preview"
fi

# 停止旧服务
sudo systemctl stop "${SERVICE_NAME}-backend" 2>/dev/null || true
sudo systemctl stop "${SERVICE_NAME}-frontend" 2>/dev/null || true

# 生成后端service
cat > "/tmp/${SERVICE_NAME}-backend.service" << EOF
[Unit]
Description=TG Monitor v2 Backend
After=network.target mysql.service mysqld.service
Wants=mysql.service

[Service]
Type=simple
WorkingDirectory=$BACKEND_DIR
Environment=PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=$VENV_DIR/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
StartLimitBurst=5
StartLimitIntervalSec=60
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# 生成前端service
cat > "/tmp/${SERVICE_NAME}-frontend.service" << EOF
[Unit]
Description=TG Monitor v2 Frontend ($FRONTEND_DESC)
After=network.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR
ExecStart=$FRONTEND_CMD
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo cp "/tmp/${SERVICE_NAME}-backend.service" /etc/systemd/system/
sudo cp "/tmp/${SERVICE_NAME}-frontend.service" /etc/systemd/system/
sudo systemctl daemon-reload

if $NO_AUTOSTART; then
  echo -e "  ${YELLOW}⏭️  跳过开机自启 (--no-autostart)${NC}"
else
  sudo systemctl enable "${SERVICE_NAME}-backend" 2>/dev/null
  sudo systemctl enable "${SERVICE_NAME}-frontend" 2>/dev/null
  echo -e "  ${GREEN}✅ 开机自启已配置${NC}"
fi

# 启动服务
echo -e "\n${BOLD}启动服务...${NC}"
sudo systemctl start "${SERVICE_NAME}-backend"
sleep 3

BACKEND_OK=$(systemctl is-active "${SERVICE_NAME}-backend" 2>/dev/null)
if [ "$BACKEND_OK" = "active" ]; then
  echo -e "  ${GREEN}✅ 后端已启动 (端口 8000)${NC}"
else
  echo -e "  ${RED}❌ 后端启动失败${NC}"
  echo -e "  ${YELLOW}  查看日志: journalctl -u ${SERVICE_NAME}-backend -n 20 --no-pager${NC}"
fi

sudo systemctl start "${SERVICE_NAME}-frontend"
sleep 1

FRONTEND_OK=$(systemctl is-active "${SERVICE_NAME}-frontend" 2>/dev/null)
if [ "$FRONTEND_OK" = "active" ]; then
  echo -e "  ${GREEN}✅ 前端已启动 (端口 3000)${NC}"
else
  echo -e "  ${RED}❌ 前端启动失败${NC}"
  echo -e "  ${YELLOW}  查看日志: journalctl -u ${SERVICE_NAME}-frontend -n 20 --no-pager${NC}"
fi

# ═══════════════════════════════════════════
# 完成
# ═══════════════════════════════════════════
touch "$MARKER"

# 获取IP
LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
PUBLIC_IP=$(curl -fsSL --connect-timeout 3 ifconfig.me 2>/dev/null || echo "")

echo -e "\n${CYAN}${BOLD}"
echo "╔══════════════════════════════════════════╗"
echo "║          🎉 部署完成！                   ║"
echo "╠══════════════════════════════════════════╣"
echo "║  本地访问: http://localhost:3000         ║"
if [ -n "$LOCAL_IP" ]; then
  printf "║  局域网:   http://%-24s║\n" "$LOCAL_IP:3000"
fi
if [ -n "$PUBLIC_IP" ]; then
  printf "║  公网IP:   %-31s║\n" "$PUBLIC_IP"
fi
echo "║                                          ║"
echo "║  ⚡ 首次打开请完成设置向导               ║"
echo "║                                          ║"
echo "║  常用命令:                               ║"
echo "║  查看状态: sudo systemctl status tgmonitor-*"
echo "║  后端日志: journalctl -u tgmonitor-backend -f"
echo "║  前端日志: journalctl -u tgmonitor-frontend -f"
echo "║  重启服务: sudo systemctl restart tgmonitor-*"
echo "║  停止服务: sudo systemctl stop tgmonitor-*"
echo "║  重新部署: ./start.sh --reset            ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"
