#!/bin/bash

# Telegram 监控系统 - Systemd 服务卸载脚本

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}==================================${NC}"
echo -e "${YELLOW}  卸载 Systemd 服务${NC}"
echo -e "${YELLOW}==================================${NC}"
echo ""

# 检查是否有 sudo 权限
if ! sudo -n true 2>/dev/null; then
    echo -e "${YELLOW}需要 sudo 权限来卸载系统服务...${NC}"
    sudo -v || exit 1
fi

# 停止并禁用服务
echo -e "${YELLOW}停止并禁用服务...${NC}"
sudo systemctl stop tg-monitor-backend.service 2>/dev/null || true
sudo systemctl stop tg-monitor-frontend.service 2>/dev/null || true
sudo systemctl disable tg-monitor-backend.service 2>/dev/null || true
sudo systemctl disable tg-monitor-frontend.service 2>/dev/null || true

# 删除服务文件
echo -e "${YELLOW}删除服务文件...${NC}"
sudo rm -f /etc/systemd/system/tg-monitor-backend.service
sudo rm -f /etc/systemd/system/tg-monitor-frontend.service

# 重新加载 systemd
echo -e "${YELLOW}重新加载 systemd 配置...${NC}"
sudo systemctl daemon-reload
sudo systemctl reset-failed

echo ""
echo -e "${GREEN}服务已成功卸载！${NC}"
echo ""
echo -e "${YELLOW}如需使用 start.sh 脚本启动服务，请运行:${NC}"
echo "  ./start.sh start"
echo ""
