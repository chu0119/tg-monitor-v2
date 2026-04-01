#!/bin/bash
#############################################
# TG 监控系统 - 监控控制脚本
# 用于管理和查看健康监控服务
#############################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="tgjiankong-monitor"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

#############################################
# 显示使用帮助
#############################################
show_help() {
    cat << EOF
${BLUE}TG 监控系统 - 监控控制脚本${NC}

用法: $0 [命令]

命令:
  start       启动健康监控服务
  stop        停止健康监控服务
  restart     重启健康监控服务
  status      查看监控服务状态
  enable      启用开机自启
  disable     禁用开机自启
  logs        查看监控日志
  logf        实时跟踪监控日志
  test        手动触发健康检查
  stats       显示监控统计信息

示例:
  $0 start              # 启动监控
  $0 logs               # 查看日志
  $0 test               # 测试健康检查

EOF
}

#############################################
# 检查 root 权限（安装服务需要）
#############################################
need_root() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}错误: 此命令需要 root 权限${NC}"
        echo "请使用: sudo $0 $1"
        exit 1
    fi
}

#############################################
# 安装服务
#############################################
install_service() {
    need_root "install"

    echo -e "${BLUE}安装健康监控服务...${NC}"

    # 复制服务文件
    cp "${SCRIPT_DIR}/tgjiankong-monitor.service" /etc/systemd/system/
    cp "${SCRIPT_DIR}/tgjiankong-backend.service" /etc/systemd/system/
    cp "${SCRIPT_DIR}/tgjiankong-frontend.service" /etc/systemd/system/

    # 重新加载 systemd
    systemctl daemon-reload

    # 启用服务
    systemctl enable "$SERVICE_NAME"

    echo -e "${GREEN}✓ 服务已安装并启用${NC}"
    echo ""
    echo "使用以下命令管理监控服务:"
    echo "  $0 start     # 启动监控"
    echo "  $0 status    # 查看状态"
    echo "  $0 logs      # 查看日志"
}

#############################################
# 卸载服务
#############################################
uninstall_service() {
    need_root "uninstall"

    echo -e "${YELLOW}卸载健康监控服务...${NC}"

    # 停止并禁用服务
    systemctl stop "$SERVICE_NAME" 2>/dev/null
    systemctl disable "$SERVICE_NAME" 2>/dev/null

    # 删除服务文件
    rm -f /etc/systemd/system/tgjiankong-monitor.service

    # 重新加载
    systemctl daemon-reload

    echo -e "${GREEN}✓ 监控服务已卸载${NC}"
}

#############################################
# 启动监控
#############################################
start_monitor() {
    echo -e "${BLUE}启动健康监控服务...${NC}"

    # 如果服务未安装，先安装
    if ! systemctl list-unit-files | grep -q "$SERVICE_NAME"; then
        echo -e "${YELLOW}监控服务未安装，正在安装...${NC}"
        install_service
    fi

    systemctl start "$SERVICE_NAME"
    sleep 2

    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo -e "${GREEN}✓ 监控服务已启动${NC}"
        show_status
    else
        echo -e "${RED}✗ 监控服务启动失败${NC}"
        journalctl -u "$SERVICE_NAME" -n 20 --no-pager
    fi
}

#############################################
# 停止监控
#############################################
stop_monitor() {
    echo -e "${YELLOW}停止健康监控服务...${NC}"
    systemctl stop "$SERVICE_NAME"
    echo -e "${GREEN}✓ 监控服务已停止${NC}"
}

#############################################
# 重启监控
#############################################
restart_monitor() {
    echo -e "${BLUE}重启健康监控服务...${NC}"
    systemctl restart "$SERVICE_NAME"
    sleep 2

    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo -e "${GREEN}✓ 监控服务已重启${NC}"
        show_status
    else
        echo -e "${RED}✗ 监控服务重启失败${NC}"
    fi
}

#############################################
# 显示状态
#############################################
show_status() {
    echo -e "${BLUE}========== 监控服务状态 ==========${NC}"
    systemctl status "$SERVICE_NAME" --no-pager -l
    echo ""

    # 检查监控日志
    local log_file="${SCRIPT_DIR}/logs/health-monitor.log"
    if [ -f "$log_file" ]; then
        echo -e "${BLUE}========== 最近监控记录 ==========${NC}"
        tail -10 "$log_file"
    fi
}

#############################################
# 启用开机自启
#############################################
enable_monitor() {
    need_root "enable"
    echo -e "${BLUE}启用监控服务开机自启...${NC}"
    systemctl enable "$SERVICE_NAME"
    echo -e "${GREEN}✓ 监控服务将随系统启动${NC}"
}

#############################################
# 禁用开机自启
#############################################
disable_monitor() {
    need_root "disable"
    echo -e "${YELLOW}禁用监控服务开机自启...${NC}"
    systemctl disable "$SERVICE_NAME"
    echo -e "${GREEN}✓ 监控服务已禁用开机自启${NC}"
}

#############################################
# 查看日志
#############################################
show_logs() {
    if [ "$1" = "-f" ]; then
        echo -e "${BLUE}实时跟踪监控日志 (Ctrl+C 退出):${NC}"
        journalctl -u "$SERVICE_NAME" -f
    else
        echo -e "${BLUE}========== 监控服务日志 ==========${NC}"
        journalctl -u "$SERVICE_NAME" -n 50 --no-pager
    fi
}

#############################################
# 手动测试健康检查
#############################################
test_health() {
    echo -e "${BLUE}执行健康检查测试...${NC}"
    echo ""

    local url="http://localhost:8000/health"
    local start_time=$(date +%s)

    echo -n "检查 $url ... "
    local response=$(curl -s --max-time 10 "$url" 2>&1)
    local curl_exit=$?

    local end_time=$(date +%s)
    local response_time=$((end_time - start_time))

    if [ $curl_exit -eq 0 ]; then
        echo -e "${GREEN}OK${NC} (${response_time}s)"

        # 解析并显示详细信息
        echo ""
        echo -e "${BLUE}========== 健康状态 ==========${NC}"
        echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"

        # 检查资源使用
        echo ""
        echo -e "${BLUE}========== 资源使用 ==========${NC}"
        local memory_mb=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('resources', {}).get('memory_mb', 0))" 2>/dev/null)
        local cpu_percent=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('resources', {}).get('cpu_percent', 0))" 2>/dev/null)
        local ws_connections=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('websocket', {}).get('connections', 0))" 2>/dev/null)

        echo "内存: ${memory_mb} MB"
        echo "CPU: ${cpu_percent}%"
        echo "WebSocket 连接: ${ws_connections}"

        # 判断是否健康
        local status=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))" 2>/dev/null)
        echo ""
        if [ "$status" = "healthy" ]; then
            echo -e "${GREEN}✓ 服务健康${NC}"
            return 0
        else
            echo -e "${RED}✗ 服务异常: $status${NC}"
            return 1
        fi
    else
        echo -e "${RED}FAIL${NC}"
        echo -e "${RED}错误: $response${NC}"
        return 1
    fi
}

#############################################
# 显示统计信息
#############################################
show_stats() {
    echo -e "${BLUE}========== 监控统计信息 ==========${NC}"
    echo ""

    # 服务状态
    echo -e "${BLUE}服务状态:${NC}"
    systemctl is-active tgjiankong-backend && echo "  后端: ✓ 运行中" || echo "  后端: ✗ 未运行"
    systemctl is-active tgjiankong-frontend && echo "  前端: ✓ 运行中" || echo "  前端: ✗ 未运行"
    systemctl is-active "$SERVICE_NAME" && echo "  监控: ✓ 运行中" || echo "  监控: ✗ 未运行"
    echo ""

    # 进程信息
    echo -e "${BLUE}进程信息:${NC}"
    ps aux | grep -E "(uvicorn|vite)" | grep -v grep | awk '{printf "  PID %5s | 内存: %6s KB | CPU: %s%% | 命令: %s\n", $2, $6, $3, $11}'
    echo ""

    # 重启历史
    local restart_log="${SCRIPT_DIR}/logs/restart-history.log"
    if [ -f "$restart_log" ]; then
        echo -e "${BLUE}重启历史 (最近10次):${NC}"
        tail -10 "$restart_log" | while read line; do
            echo "  $line"
        done
    else
        echo "  无重启记录"
    fi
    echo ""

    # 最近监控日志
    local monitor_log="${SCRIPT_DIR}/logs/health-monitor.log"
    if [ -f "$monitor_log" ]; then
        echo -e "${BLUE}最近监控记录:${NC}"
        tail -5 "$monitor_log" | while read line; do
            echo "  $line"
        done
    fi
}

#############################################
# 主函数
#############################################
main() {
    case "${1:-help}" in
        start)
            start_monitor
            ;;
        stop)
            stop_monitor
            ;;
        restart)
            restart_monitor
            ;;
        status)
            show_status
            ;;
        enable)
            enable_monitor
            ;;
        disable)
            disable_monitor
            ;;
        logs)
            show_logs "$2"
            ;;
        logf)
            show_logs -f
            ;;
        test)
            test_health
            ;;
        stats)
            show_stats
            ;;
        install)
            install_service
            ;;
        uninstall)
            uninstall_service
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            echo -e "${RED}错误: 未知命令 '$1'${NC}"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

main "$@"
