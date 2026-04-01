#!/bin/bash
# ============================================================
#  TG Monitor v2 - 一键部署脚本
#  用法: ./start.sh [--reset] [--no-autostart]
# ============================================================
set -e

# ── 颜色 ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
MARKER="$PROJECT_DIR/.deployed"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/venv"
SERVICE_NAME="tgmonitor"

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

echo -e "${CYAN}${BOLD}"
echo "╔══════════════════════════════════════╗"
echo "║   TG Monitor v2 - 一键部署          ║"
echo "╚══════════════════════════════════════╝"
echo -e "${NC}"

# ── Step 1: 检测环境 ──
echo -e "${BOLD}[1/7] 检测系统环境...${NC}"
MISSING=""

check_cmd() {
  if command -v "$1" &>/dev/null; then
    local ver=$($1 --version 2>/dev/null | head -1 | grep -oP '[\d.]+' | head -1)
    echo -e "  ${GREEN}✅ $1${ver:+ ($ver)}${NC}"
  else
    echo -e "  ${RED}❌ $1 未安装${NC}"
    MISSING="$MISSING $1"
  fi
}

check_cmd python3
check_cmd pip3
check_cmd node
check_cmd npm
check_cmd mysql

# 检查MySQL服务状态
if command -v mysql &>/dev/null; then
  if systemctl is-active --quiet mysql 2>/dev/null || systemctl is-active --quiet mysqld 2>/dev/null; then
    echo -e "  ${GREEN}✅ MySQL 服务运行中${NC}"
  else
    echo -e "  ${YELLOW}⚠️ MySQL 已安装但未运行，将尝试启动${NC}"
    sudo systemctl start mysql 2>/dev/null || sudo systemctl start mysqld 2>/dev/null || true
  fi
fi

# ── Step 2: 安装缺失依赖 ──
echo -e "\n${BOLD}[2/7] 安装缺失的系统依赖...${NC}"
sudo apt-get update -qq

# Node.js (需要特殊处理，先统一装)
if ! command -v node &>/dev/null; then
  echo -e "  ${YELLOW}⏳ 安装 Node.js...${NC}"
  if ! dpkg -l | grep -q nodesource; then
    curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash - 2>/dev/null
  fi
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nodejs 2>&1 | tail -2
  echo -e "  ${GREEN}✅ Node.js $(node --version 2>/dev/null) 已安装${NC}"
else
  echo -e "  ${GREEN}✅ Node.js 已存在${NC}"
fi

# pip3 + python3-venv
if ! command -v pip3 &>/dev/null || ! dpkg -l | grep -q python3-venv; then
  echo -e "  ${YELLOW}⏳ 安装 pip3 和 python3-venv...${NC}"
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-pip python3-venv 2>&1 | tail -2
  echo -e "  ${GREEN}✅ pip3 已安装${NC}"
fi

# MySQL
if ! command -v mysql &>/dev/null; then
  echo -e "  ${YELLOW}⏳ 安装 MySQL（可能需要1-2分钟）...${NC}"
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq mysql-server
  sudo service mysql start 2>/dev/null || sudo systemctl start mysql 2>/dev/null || true
  echo -e "  ${GREEN}✅ MySQL 已安装${NC}"
fi

# ── Step 3: Python虚拟环境和依赖 ──
echo -e "\n${BOLD}[3/7] 安装Python依赖...${NC}"
if [ ! -d "$VENV_DIR" ]; then
  echo -e "  ${YELLOW}⏳ 创建虚拟环境...${NC}"
  python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
echo -e "  ${YELLOW}⏳ pip install -r requirements.txt${NC}"
if [ -f "$BACKEND_DIR/requirements.txt" ]; then
  pip install -r "$BACKEND_DIR/requirements.txt" -q 2>&1 | tail -3
fi
echo -e "  ${GREEN}✅ Python依赖安装完成${NC}"

# ── Step 4: Node依赖 ──
echo -e "\n${BOLD}[4/7] 安装前端依赖...${NC}"
cd "$FRONTEND_DIR"
if [ ! -d "node_modules" ]; then
  echo -e "  ${YELLOW}⏳ npm install${NC}"
  npm install --silent 2>&1 | tail -3
else
  echo -e "  ${GREEN}✅ node_modules 已存在${NC}"
fi
cd "$PROJECT_DIR"

# ── Step 5: 数据库初始化 ──
echo -e "\n${BOLD}[5/7] 初始化数据库...${NC}"
source "$VENV_DIR/bin/activate"
if [ -f "$BACKEND_DIR/init_db.py" ]; then
  python3 "$BACKEND_DIR/init_db.py" 2>&1
fi
echo -e "  ${GREEN}✅ 数据库初始化完成${NC}"

# ── Step 6: 下载代理内核 ──
echo -e "\n${BOLD}[6/7] 检查代理内核...${NC}"
PROXY_DIR="$BACKEND_DIR/app/proxy"
MIHOMO_PATH="$PROXY_DIR/mihomo"

if [ ! -f "$MIHOMO_PATH" ]; then
  ARCH=$(uname -m)
  case $ARCH in
    x86_64) DL_ARCH="amd64" ;;
    aarch64) DL_ARCH="arm64" ;;
    *) echo -e "  ${RED}❌ 不支持的架构: $ARCH${NC}"; exit 1 ;;
  esac
  echo -e "  ${YELLOW}⏳ 下载 mihomo ($DL_ARCH)...${NC}"
  MIHOMO_VER="v1.19.21"
  DL_URL="https://github.com/MetaCubeX/mihomo/releases/download/${MIHOMO_VER}/mihomo-linux-${DL_ARCH}-${MIHOMO_VER}.gz"
  mkdir -p "$PROXY_DIR"
  if curl -fsSL "$DL_URL" -o /tmp/mihomo.gz 2>/dev/null; then
    gunzip -f /tmp/mihomo.gz
    mv /tmp/mihomo "$MIHOMO_PATH"
    chmod +x "$MIHOMO_PATH"
    echo -e "  ${GREEN}✅ mihomo 内核已下载${NC}"
  else
    echo -e "  ${YELLOW}⚠️ 下载失败，请手动下载 mihomo 到 $MIHOMO_PATH${NC}"
  fi
else
  echo -e "  ${GREEN}✅ mihomo 内核已存在${NC}"
fi

# ── Step 7: 配置服务 ──
echo -e "\n${BOLD}[7/7] 配置系统服务...${NC}"

# 停止旧服务
sudo systemctl stop "${SERVICE_NAME}-backend" 2>/dev/null || true
sudo systemctl stop "${SERVICE_NAME}-frontend" 2>/dev/null || true

# 后端service
cat > /tmp/${SERVICE_NAME}-backend.service << EOF
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

[Install]
WantedBy=multi-user.target
EOF

# 前端service (用npm run preview即vite preview，生产模式)
# 或者用nginx，这里先用简单方式
FRONTEND_PORT=3000
cat > /tmp/${SERVICE_NAME}-frontend.service << EOF
[Unit]
Description=TG Monitor v2 Frontend
After=network.target

[Service]
Type=simple
WorkingDirectory=$FRONTEND_DIR
ExecStart=/usr/bin/npx vite preview --port $FRONTEND_PORT --host 0.0.0.0
Restart=always
RestartSec=5
Environment=NODE_ENV=production

[Install]
WantedBy=multi-user.target
EOF

sudo cp /tmp/${SERVICE_NAME}-backend.service /etc/systemd/system/
sudo cp /tmp/${SERVICE_NAME}-frontend.service /etc/systemd/system/
sudo systemctl daemon-reload

if $NO_AUTOSTART; then
  echo -e "  ${YELLOW}⏭️ 跳过开机自启配置 (--no-autostart)${NC}"
else
  sudo systemctl enable "${SERVICE_NAME}-backend"
  sudo systemctl enable "${SERVICE_NAME}-frontend"
  echo -e "  ${GREEN}✅ 开机自启已配置${NC}"
fi

# 构建前端
echo -e "\n${BOLD}构建前端...${NC}"
cd "$FRONTEND_DIR"
npm run build 2>&1 | tail -5
cd "$PROJECT_DIR"

# 启动服务
echo -e "\n${BOLD}启动服务...${NC}"
sudo systemctl start "${SERVICE_NAME}-backend"
sleep 2
sudo systemctl start "${SERVICE_NAME}-frontend"
sleep 1

# 检查状态
BACKEND_OK=$(systemctl is-active "${SERVICE_NAME}-backend" 2>/dev/null)
FRONTEND_OK=$(systemctl is-active "${SERVICE_NAME}-frontend" 2>/dev/null)

if [ "$BACKEND_OK" = "active" ]; then
  echo -e "  ${GREEN}✅ 后端已启动 (端口 8000)${NC}"
else
  echo -e "  ${RED}❌ 后端启动失败，请检查: journalctl -u ${SERVICE_NAME}-backend${NC}"
fi

if [ "$FRONTEND_OK" = "active" ]; then
  echo -e "  ${GREEN}✅ 前端已启动 (端口 3000)${NC}"
else
  echo -e "  ${RED}❌ 前端启动失败，请检查: journalctl -u ${SERVICE_NAME}-frontend${NC}"
fi

# 获取本机IP
LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')

# 标记已部署
touch "$MARKER"

echo -e "\n${CYAN}${BOLD}"
echo "╔══════════════════════════════════════╗"
echo "║        🎉 部署完成！                 ║"
echo "╠══════════════════════════════════════╣"
echo "║  本地访问: http://localhost:3000     ║"
if [ -n "$LOCAL_IP" ]; then
echo "║  局域网:   http://$LOCAL_IP:3000"
fi
echo "║                                      ║"
echo "║  首次启动请完成设置向导               ║"
echo "║  常用命令:                           ║"
echo "║  查看状态: sudo systemctl status tgmonitor-*"
echo "║  查看日志: journalctl -u tgmonitor-backend -f"
echo "║  停止服务: sudo systemctl stop tgmonitor-*"
echo "║  重置部署: ./start.sh --reset        ║"
echo "╚══════════════════════════════════════╝"
echo -e "${NC}"
