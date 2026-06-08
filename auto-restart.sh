#!/bin/bash
# =============================================================================
# TG 监控系统自动恢复脚本（systemd 版本）
# =============================================================================
# 通过 systemctl 管理服务，杜绝重复启动
# 由 systemd timer 驱动，或手动运行
# =============================================================================

set -e

PROJECT_DIR="/home/xingchuan/桌面/tgjiankong"
RESTART_LOG="$PROJECT_DIR/logs/auto-restart.log"
MIN_RESTART_INTERVAL=300

mkdir -p "$(dirname "$RESTART_LOG")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$RESTART_LOG"
}

# 检查重启间隔（防止频繁重启）
check_interval() {
    local flag="$PROJECT_DIR/.last_restart"
    if [ -f "$flag" ]; then
        local last=$(cat "$flag")
        local now=$(date +%s)
        local diff=$((now - last))
        if [ "$diff" -lt "$MIN_RESTART_INTERVAL" ]; then
            log "距上次重启仅${diff}秒，跳过"
            exit 0
        fi
    fi
}

# 检查后端健康
check_backend() {
    # 先检查 systemd 服务状态
    local state=$(systemctl is-active tgjiankong-backend 2>/dev/null)
    if [ "$state" != "active" ]; then
        log "后端服务状态: $state，需要重启"
        return 1
    fi
    # 再检查 API 是否响应
    if ! curl -sf --max-time 5 http://localhost:8000/health > /dev/null 2>&1; then
        log "API 无响应，需要重启"
        return 1
    fi
    return 0
}

# 检查前端健康
check_frontend() {
    local state=$(systemctl is-active tgjiankong-frontend 2>/dev/null)
    if [ "$state" != "active" ]; then
        log "前端服务状态: $state，需要重启"
        return 1
    fi
    if ! curl -sf --max-time 5 http://localhost:5173 > /dev/null 2>&1; then
        log "前端无响应，需要重启"
        return 1
    fi
    return 0
}

# 检查监控进程
check_monitor() {
    local state=$(systemctl is-active tgjiankong-monitor 2>/dev/null)
    if [ "$state" != "active" ]; then
        log "监控服务状态: $state，需要重启"
        return 1
    fi
    return 0
}

# 通过 systemctl 重启（确保不会重复进程）
restart_svc() {
    local svc="$1"
    log "通过 systemctl restart $svc"
    systemctl restart "$svc"
    sleep 3
    if systemctl is-active "$svc" > /dev/null 2>&1; then
        log "✓ $svc 重启成功"
    else
        log "✗ $svc 重启失败"
    fi
}

# 主流程
main() {
    check_interval

    local need_action=false

    if ! check_backend; then
        restart_svc tgjiankong-backend
        need_action=true
    fi

    if ! check_frontend; then
        restart_svc tgjiankong-frontend
        need_action=true
    fi

    if ! check_monitor; then
        restart_svc tgjiankong-monitor
        need_action=true
    fi

    if $need_action; then
        date +%s > "$PROJECT_DIR/.last_restart"
    else
        log "所有服务正常运行"
        rm -f "$PROJECT_DIR/.alert_sent_flag"
    fi
}

main
