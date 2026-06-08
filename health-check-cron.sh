#!/bin/bash
# TG Monitor 自动健康检查与恢复脚本
# 适配当前环境：/home/test/tg-monitor, systemd service: tgmonitor-backend
# 由 cron 定时驱动

PROJECT_DIR="/home/test/tg-monitor"
HEALTH_LOG="$PROJECT_DIR/logs/health-check.log"
BACKEND_SERVICE="tgmonitor-backend"
HEALTH_URL="http://localhost:8000/health"
MIN_RESTART_INTERVAL=300

mkdir -p "$(dirname "$HEALTH_LOG")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$HEALTH_LOG"
}

# 防止频繁重启
check_interval() {
    local flag="$PROJECT_DIR/.last_restart"
    if [ -f "$flag" ]; then
        local last=$(cat "$flag")
        local now=$(date +%s)
        local diff=$((now - last))
        if [ "$diff" -lt "$MIN_RESTART_INTERVAL" ]; then
            log "距上次重启仅${diff}秒，跳过重启"
            return 1
        fi
    fi
    return 0
}

# 检查后端 systemd 服务
check_backend_service() {
    local state=$(systemctl is-active "$BACKEND_SERVICE" 2>/dev/null)
    if [ "$state" != "active" ]; then
        log "后端服务状态: $state，尝试重启"
        return 1
    fi
    return 0
}

# 检查 API 健康端点
check_api_health() {
    local response=$(curl -sf --max-time 10 "$HEALTH_URL" 2>/dev/null)
    if [ -z "$response" ]; then
        log "API 无响应，尝试重启后端"
        return 1
    fi

    # 检查数据库连接状态
    local db_connected=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('database',{}).get('connected',False))" 2>/dev/null)
    if [ "$db_connected" != "True" ]; then
        log "数据库连接异常"
        return 1
    fi

    return 0
}

# 检查 MySQL
check_mysql() {
    if ! mysqladmin -u root ping --silent 2>/dev/null; then
        log "MySQL 无响应，尝试重启"
        systemctl restart mysql
        sleep 5
        if ! mysqladmin -u root ping --silent 2>/dev/null; then
            log "MySQL 重启后仍然无响应"
            return 1
        fi
        log "MySQL 重启成功"
    fi
    return 0
}

# 检查 Nginx
check_nginx() {
    local state=$(systemctl is-active nginx 2>/dev/null)
    if [ "$state" != "active" ]; then
        log "Nginx 状态: $state，尝试重启"
        systemctl restart nginx
        sleep 2
        log "Nginx 已重启"
        return 1
    fi
    return 0
}

# 检查磁盘空间
check_disk() {
    local disk_usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ "$disk_usage" -gt 90 ]; then
        log "磁盘严重不足: ${disk_usage}%"
        return 1
    elif [ "$disk_usage" -gt 80 ]; then
        log "磁盘空间警告: ${disk_usage}%"
    fi
    return 0
}

# 重启后端服务
restart_backend() {
    if check_interval; then
        log "正在重启后端服务..."
        systemctl restart "$BACKEND_SERVICE"
        sleep 5
        if systemctl is-active "$BACKEND_SERVICE" > /dev/null 2>&1; then
            log "后端重启成功"
            date +%s > "$PROJECT_DIR/.last_restart"
        else
            log "后端重启失败"
        fi
    fi
}

# 清理旧日志（保留最近 7 天的压缩日志）
cleanup_old_logs() {
    find "$PROJECT_DIR/logs/" -name "*.log.zip" -mtime +7 -delete 2>/dev/null
    find "$PROJECT_DIR/logs/" -name "*.zip" -mtime +7 -delete 2>/dev/null
}

# 主流程
main() {
    log "---------- 开始健康检查 ----------"
    local need_restart=false

    # 1. 检查后端服务
    if ! check_backend_service; then
        need_restart=true
    fi

    # 2. 检查 API
    if ! check_api_health; then
        need_restart=true
    fi

    # 3. 检查 MySQL
    check_mysql

    # 4. 检查 Nginx
    check_nginx

    # 5. 检查磁盘
    check_disk

    # 如需重启则执行
    if $need_restart; then
        restart_backend
    else
        log "所有服务正常运行"
    fi

    # 清理旧日志
    cleanup_old_logs

    log "---------- 健康检查完成 ----------"
}

main
