#!/bin/bash
# =============================================================================
# 安装系统服务
# =============================================================================
# 将 TG 监控系统安装为 systemd 系统服务，支持开机自启
# 需要使用 sudo 运行
# =============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 项目路径
PROJECT_DIR="/home/xingchuan/桌面/tgjiankong"

# 辅助函数
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}➜ $1${NC}"
}

# 检查 root 权限
if [ "$EUID" -ne 0 ]; then
    print_error "请使用 sudo 运行此脚本"
    echo "用法: sudo ./install-services.sh"
    exit 1
fi

# 检查服务文件
print_info "检查服务文件..."
if [ ! -f "$PROJECT_DIR/tg-monitor-backend.service" ]; then
    print_error "服务文件不存在: tg-monitor-backend.service"
    exit 1
fi

# 停止旧服务
print_info "停止旧服务（如果存在）..."
systemctl stop tg-monitor-backend 2>/dev/null || true
systemctl disable tg-monitor-backend 2>/dev/null || true

# 复制服务文件
print_info "安装 systemd 服务文件..."
cp "$PROJECT_DIR/tg-monitor-backend.service" /etc/systemd/system/

# 重新加载 systemd
print_info "重新加载 systemd 配置..."
systemctl daemon-reload

# 启用服务
print_info "启用服务开机自启..."
systemctl enable tg-monitor-backend

# 启动服务
print_info "启动服务..."
systemctl start tg-monitor-backend

# 检查状态
sleep 2
if systemctl is-active --quiet tg-monitor-backend; then
    print_success "服务已启动并启用开机自启"
else
    print_error "服务启动失败"
    echo "查看日志: sudo journalctl -u tg-monitor-backend -n 50"
    exit 1
fi

echo ""
echo "========================================="
echo "安装完成！"
echo "========================================="
echo ""
echo -e "${YELLOW}服务管理命令:${NC}"
echo "  启动: sudo systemctl start tg-monitor-backend"
echo "  停止: sudo systemctl stop tg-monitor-backend"
echo "  重启: sudo systemctl restart tg-monitor-backend"
echo "  状态: sudo systemctl status tg-monitor-backend"
echo "  日志: sudo journalctl -u tg-monitor-backend -f"
echo ""
echo -e "${YELLOW}服务地址:${NC}"
echo "  后端: http://localhost:8000"
echo "  API:  http://localhost:8000/docs"
echo ""
