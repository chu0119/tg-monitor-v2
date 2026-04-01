#!/bin/bash

# Telegram 监控系统 - Systemd 服务管理脚本

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 显示帮助信息
show_help() {
    echo -e "${GREEN}==================================${NC}"
    echo -e "${GREEN}  Telegram 监控系统服务管理${NC}"
    echo -e "${GREEN}==================================${NC}"
    echo ""
    echo "用法: $0 {start|stop|restart|status|logs|enable|disable}"
    echo ""
    echo "命令:"
    echo "  start    - 启动服务"
    echo "  stop     - 停止服务"
    echo "  restart  - 重启服务"
    echo "  status   - 查看服务状态"
    echo "  logs     - 查看服务日志"
    echo "  enable   - 启用开机自启"
    echo "  disable  - 禁用开机自启"
    echo ""
    echo "示例:"
    echo "  $0 status           # 查看所有服务状态"
    echo "  $0 restart backend  # 只重启后端"
    echo "  $0 logs frontend    # 查看前端日志"
    echo ""
}

# 检查 sudo 权限
check_sudo() {
    if [[ "$EUID" -ne 0 ]]; then
        if ! sudo -n true 2>/dev/null; then
            echo -e "${YELLOW}需要 sudo 权限...${NC}"
            sudo -v || exit 1
        fi
    fi
}

# 启动服务
start_services() {
    check_sudo
    local service=${1:-"all"}

    echo -e "${YELLOW}启动服务...${NC}"

    if [[ "$service" == "all" ]] || [[ "$service" == "backend" ]]; then
        echo -e "${BLUE}启动后端服务...${NC}"
        sudo systemctl start tg-monitor-backend.service
        echo -e "${GREEN}✓ 后端服务已启动${NC}"
    fi

    if [[ "$service" == "all" ]] || [[ "$service" == "frontend" ]]; then
        echo -e "${BLUE}启动前端服务...${NC}"
        sudo systemctl start tg-monitor-frontend.service
        echo -e "${GREEN}✓ 前端服务已启动${NC}"
    fi

    sleep 2
    show_status
}

# 停止服务
stop_services() {
    check_sudo
    local service=${1:-"all"}

    echo -e "${YELLOW}停止服务...${NC}"

    if [[ "$service" == "all" ]] || [[ "$service" == "frontend" ]]; then
        echo -e "${BLUE}停止前端服务...${NC}"
        sudo systemctl stop tg-monitor-frontend.service
        echo -e "${GREEN}✓ 前端服务已停止${NC}"
    fi

    if [[ "$service" == "all" ]] || [[ "$service" == "backend" ]]; then
        echo -e "${BLUE}停止后端服务...${NC}"
        sudo systemctl stop tg-monitor-backend.service
        echo -e "${GREEN}✓ 后端服务已停止${NC}"
    fi
}

# 重启服务
restart_services() {
    check_sudo
    local service=${1:-"all"}

    echo -e "${YELLOW}重启服务...${NC}"

    if [[ "$service" == "all" ]] || [[ "$service" == "backend" ]]; then
        echo -e "${BLUE}重启后端服务...${NC}"
        sudo systemctl restart tg-monitor-backend.service
        echo -e "${GREEN}✓ 后端服务已重启${NC}"
    fi

    if [[ "$service" == "all" ]] || [[ "$service" == "frontend" ]]; then
        echo -e "${BLUE}重启前端服务...${NC}"
        sudo systemctl restart tg-monitor-frontend.service
        echo -e "${GREEN}✓ 前端服务已重启${NC}"
    fi

    sleep 2
    show_status
}

# 显示状态
show_status() {
    echo ""
    echo -e "${YELLOW}=== 服务状态 ===${NC}"

    echo ""
    echo -e "${BLUE}后端服务:${NC}"
    if systemctl is-active --quiet tg-monitor-backend.service; then
        echo -e "  状态: ${GREEN}运行中${NC}"
        echo -e "  地址: http://localhost:8000"
        local uptime=$(systemctl show tg-monitor-backend.service -p ActiveEnterTime --value)
        echo -e "  运行时间: $uptime"
    else
        echo -e "  状态: ${RED}未运行${NC}"
    fi

    echo ""
    echo -e "${BLUE}前端服务:${NC}"
    if systemctl is-active --quiet tg-monitor-frontend.service; then
        echo -e "  状态: ${GREEN}运行中${NC}"
        echo -e "  地址: http://localhost:5173"
        local uptime=$(systemctl show tg-monitor-frontend.service -p ActiveEnterTime --value)
        echo -e "  运行时间: $uptime"
    else
        echo -e "  状态: ${RED}未运行${NC}"
    fi

    echo ""
    echo -e "${BLUE}开机自启:${NC}"
    if systemctl is-enabled --quiet tg-monitor-backend.service; then
        echo -e "  后端: ${GREEN}已启用${NC}"
    else
        echo -e "  后端: ${RED}已禁用${NC}"
    fi

    if systemctl is-enabled --quiet tg-monitor-frontend.service; then
        echo -e "  前端: ${GREEN}已启用${NC}"
    else
        echo -e "  前端: ${RED}已禁用${NC}"
    fi
    echo ""
}

# 查看日志
show_logs() {
    local service=${1:-"all"}

    if [[ "$service" == "all" ]] || [[ "$service" == "backend" ]]; then
        echo -e "${YELLOW}=== 后端日志 ===${NC}"
        sudo journalctl -u tg-monitor-backend.service -n 50 --no-pager
    fi

    if [[ "$service" == "all" ]]; then
        echo ""
    fi

    if [[ "$service" == "all" ]] || [[ "$service" == "frontend" ]]; then
        echo -e "${YELLOW}=== 前端日志 ===${NC}"
        sudo journalctl -u tg-monitor-frontend.service -n 50 --no-pager
    fi
}

# 跟踪日志
follow_logs() {
    local service=${1:-"all"}

    if [[ "$service" == "all" ]]; then
        echo -e "${YELLOW}跟踪所有服务日志 (Ctrl+C 退出)${NC}"
        sudo journalctl -u tg-monitor-backend.service -u tg-monitor-frontend.service -f
    elif [[ "$service" == "backend" ]]; then
        echo -e "${YELLOW}跟踪后端日志 (Ctrl+C 退出)${NC}"
        sudo journalctl -u tg-monitor-backend.service -f
    elif [[ "$service" == "frontend" ]]; then
        echo -e "${YELLOW}跟踪前端日志 (Ctrl+C 退出)${NC}"
        sudo journalctl -u tg-monitor-frontend.service -f
    fi
}

# 启用开机自启
enable_services() {
    check_sudo
    echo -e "${YELLOW}启用开机自启...${NC}"
    sudo systemctl enable tg-monitor-backend.service
    sudo systemctl enable tg-monitor-frontend.service
    echo -e "${GREEN}✓ 开机自启已启用${NC}"
}

# 禁用开机自启
disable_services() {
    check_sudo
    echo -e "${YELLOW}禁用开机自启...${NC}"
    sudo systemctl disable tg-monitor-backend.service
    sudo systemctl disable tg-monitor-frontend.service
    echo -e "${GREEN}✓ 开机自启已禁用${NC}"
}

# 主命令
case "${1:-}" in
    start)
        start_services "${2:-all}"
        ;;
    stop)
        stop_services "${2:-all}"
        ;;
    restart)
        restart_services "${2:-all}"
        ;;
    status)
        show_status
        ;;
    logs)
        if [[ "$2" == "-f" ]] || [[ "$2" == "--follow" ]]; then
            follow_logs "${3:-all}"
        else
            show_logs "${2:-all}"
        fi
        ;;
    enable)
        enable_services
        ;;
    disable)
        disable_services
        ;;
    -h|--help|help)
        show_help
        ;;
    "")
        show_status
        ;;
    *)
        echo -e "${RED}错误: 未知命令 '$1'${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac
