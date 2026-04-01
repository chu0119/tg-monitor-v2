#!/bin/bash
# =============================================================================
# TG 监控系统健康检查脚本
# =============================================================================
# 用于监控系统健康状态，自动清理和优化
# 建议添加到 crontab 每小时运行一次
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 项目路径
PROJECT_DIR="/home/xingchuan/桌面/tgjiankong"
BACKEND_DIR="$PROJECT_DIR/backend"

# 日志文件
HEALTH_LOG="$PROJECT_DIR/logs/health-check.log"
mkdir -p "$(dirname "$HEALTH_LOG")"

# 辅助函数
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$HEALTH_LOG"
}

log_success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] ✓ $1${NC}" | tee -a "$HEALTH_LOG"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ✗ $1${NC}" | tee -a "$HEALTH_LOG"
}

log_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] ⚠ $1${NC}" | tee -a "$HEALTH_LOG"
}

# 检查后端进程
check_backend() {
    log "检查后端进程..."
    if pgrep -f "gunicorn app.main:app" > /dev/null; then
        local pid=$(pgrep -f "gunicorn app.main:app" | head -1)
        local cpu=$(ps -p "$pid" -o %cpu --no-headers | tr -d ' ')
        local mem=$(ps -p "$pid" -o %mem --no-headers | tr -d ' ')
        log_success "后端运行正常 (PID: $pid, CPU: ${cpu}%, MEM: ${mem}%)"

        # CPU 警告
        if (( $(echo "$cpu > 80" | bc -l) )); then
            log_warning "CPU 使用率过高: ${cpu}%"
        fi

        # 内存警告
        if (( $(echo "$mem > 80" | bc -l) )); then
            log_warning "内存使用率过高: ${mem}%"
        fi

        return 0
    else
        log_error "后端进程未运行！"
        return 1
    fi
}

# 检查数据库连接
check_database() {
    log "检查数据库连接..."
    if mysql -u tgmonitor -pTgMonitor2026Secure -e "SELECT 1" &> /dev/null; then
        log_success "数据库连接正常"

        # 检查表大小
        local alerts_size=$(mysql -u tgmonitor -pTgMonitor2026Secure tg_monitor -e "SELECT ROUND(data_length/1024/1024, 2) FROM information_schema.tables WHERE table_schema='tg_monitor' AND table_name='alerts'" 2>/dev/null | tail -1)
        local messages_size=$(mysql -u tgmonitor -pTgMonitor2026Secure tg_monitor -e "SELECT ROUND(data_length/1024/1024, 2) FROM information_schema.tables WHERE table_schema='tg_monitor' AND table_name='messages'" 2>/dev/null | tail -1)

        log "数据库大小: alerts=${alerts_size}MB, messages=${messages_size}MB"

        # 告警表过大警告
        if (( $(echo "$alerts_size > 500" | bc -l) )); then
            log_warning "告警表过大 (${alerts_size}MB)，建议清理"
        fi

        return 0
    else
        log_error "数据库连接失败！"
        return 1
    fi
}

# 检查磁盘空间
check_disk() {
    log "检查磁盘空间..."
    local disk_usage=$(df /home | awk 'NR==2 {print $5}' | sed 's/%//')
    log "磁盘使用率: ${disk_usage}%"

    if [ "$disk_usage" -gt 80 ]; then
        log_warning "磁盘空间不足 (${disk_usage}%)"

        # 清理备份目录
        log "清理旧备份..."
        find "$BACKEND_DIR/backups" -type d -mtime +7 -exec rm -rf {} \; 2>/dev/null || true
    fi

    if [ "$disk_usage" -gt 90 ]; then
        log_error "磁盘严重不足 (${disk_usage}%)！"
        return 1
    fi

    return 0
}

# 检查内存使用
check_memory() {
    log "检查系统内存..."
    local mem_usage=$(free | awk 'NR==2 {printf "%.1f", $3/$2*100}')
    log "内存使用率: ${mem_usage}%"

    if (( $(echo "$mem_usage > 90" | bc -l) )); then
        log_warning "内存使用率过高: ${mem_usage}%"
    fi

    return 0
}

# 检查备份目录
check_backups() {
    log "检查备份目录..."
    local backup_count=$(find "$BACKEND_DIR/backups" -maxdepth 1 -type d | wc -l)
    local backup_size=$(du -sh "$BACKEND_DIR/backups" 2>/dev/null | awk '{print $1}')

    log "备份目录: $((backup_count-1)) 个备份, 大小: $backup_size"

    # 警告：备份过多
    if [ "$backup_count" -gt 10 ]; then
        log_warning "备份文件过多，保留最新的 5 个..."
        cd "$BACKEND_DIR/backups" && ls -t | tail -n +6 | xargs -I {} rm -rf "{}" 2>/dev/null || true
    fi

    return 0
}

# 检查日志文件
check_logs() {
    log "检查日志文件..."
    local log_size=$(du -sh /tmp/tg-monitor*.log 2>/dev/null | awk '{sum+=$1} END {print sum}' || echo "0")

    if [ "$log_size" != "0" ]; then
        log "日志文件大小: ${log_size}K"

        # 清理大日志
        for log in /tmp/tg-monitor*.log; do
            local size=$(du -k "$log" 2>/dev/null | awk '{print $1}')
            if [ "$size" -gt 10000 ]; then
                log "清理大日志文件: $log (${size}K)"
                > "$log"
            fi
        done
    fi

    return 0
}

# 检查 API 响应
check_api() {
    log "检查 API 响应..."
    local start=$(date +%s.%N)
    local response=$(curl -s http://localhost:8000/health 2>/dev/null)
    local end=$(date +%s.%N)
    local duration=$(echo "$end - $start" | bc)

    if [ -n "$response" ]; then
        log_success "API 响应正常 (${duration}s)"

        # 检查响应时间
        if (( $(echo "$duration > 2" | bc -l) )); then
            log_warning "API 响应时间过长: ${duration}s"
        fi

        return 0
    else
        log_error "API 无响应！"
        return 1
    fi
}

# 数据库优化
optimize_database() {
    log "优化数据库表..."
    mysql -u tgmonitor -pTgMonitor2026Secure tg_monitor -e "OPTIMIZE TABLE alerts, messages, senders, conversations" 2>/dev/null && log_success "数据库优化完成" || log_warning "数据库优化失败"
}

# 主检查流程
main() {
    log "=========================================="
    log "开始健康检查"
    log "=========================================="

    local errors=0

    check_backend || ((errors++))
    check_database || ((errors++))
    check_disk || ((errors++))
    check_memory || ((errors++))
    check_backups || ((errors++))
    check_logs || ((errors++))
    check_api || ((errors++))

    # 每天凌晨 3 点执行数据库优化
    local hour=$(date +%H)
    if [ "$hour" = "03" ]; then
        optimize_database
    fi

    log "=========================================="
    if [ "$errors" -eq 0 ]; then
        log_success "健康检查完成，一切正常"
    else
        log_error "健康检查完成，发现 $errors 个问题"
    fi
    log "=========================================="

    exit $errors
}

# 运行检查
main
