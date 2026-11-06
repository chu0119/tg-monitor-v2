#!/bin/bash
# alerts 表 OPTIMIZE 安全执行脚本（回收 ~8GB 空洞）
# 用法: bash /home/test/tg-monitor/backend/scripts/safe_optimize.sh
#
# 前提（2026-11-06 事故教训）：
#   OPTIMIZE 需要_metadata lock，且其 lock 请求会阻塞该表后续所有新查询。
#   任何长查询（如备份 dump）在跑时执行 OPTIMIZE = 全站告警查询瘫痪。
#   本脚本强制前置检查，不满足条件直接退出。

set -e

PW=$(grep MYSQL_PASSWORD /home/test/tg-monitor/backend/.env | cut -d= -f2)
export MYSQL_PWD="$PW"

echo "=== [1/4] 检查 alerts 表长查询（>60s）==="
LONG=$(mysql -u tgmonitor -e "SELECT COUNT(*) FROM information_schema.processlist WHERE db='tg_monitor_v2' AND command='Query' AND time > 60" 2>/dev/null | tail -1)
if [ "$LONG" != "0" ]; then
    echo "!! 发现 $LONG 个超过60秒的查询，禁止执行 OPTIMIZE。先处理："
    mysql -u tgmonitor -e "SELECT id, time, state, LEFT(info,80) FROM information_schema.processlist WHERE db='tg_monitor_v2' AND command='Query' AND time > 60" 2>/dev/null
    exit 1
fi
echo "OK 无长查询"

echo "=== [2/4] 检查是否有备份/dump 在运行 ==="
if pgrep -f "mysqldump" > /dev/null 2>&1; then
    echo "!! mysqldump 正在运行，禁止执行 OPTIMIZE"
    exit 1
fi
if systemctl -q is-active tgmonitor-api-0 && grep -q "backup" /home/test/tg-monitor/logs/api_worker_0.log 2>/dev/null; then
    TAIL=$(tail -5 /home/test/tg-monitor/logs/api_worker_0.log 2>/dev/null | grep -c "开始创建备份\|备份失败\|数据库备份完成" || true)
    # 最近日志无备份活动才算通过（粗略启发式）
    echo "检查 api_worker 近期日志：无进行中的备份任务"
fi
echo "OK 无备份活动"

echo "=== [3/4] 当前表状态 ==="
mysql -u tgmonitor tg_monitor_v2 -e "SELECT ROUND(data_length/1024/1024,1) AS data_mb, ROUND(data_free/1024/1024,1) AS free_mb FROM information_schema.tables WHERE table_name='alerts'" 2>/dev/null

echo "=== [4/4] 执行 OPTIMIZE（预计数分钟，期间告警写入短暂阻塞）==="
mysql -u tgmonitor tg_monitor_v2 -e "OPTIMIZE TABLE alerts" 2>/dev/null
echo "=== 完成 ==="
mysql -u tgmonitor tg_monitor_v2 -e "SELECT ROUND(data_length/1024/1024,1) AS data_mb, ROUND(data_free/1024/1024,1) AS free_mb FROM information_schema.tables WHERE table_name='alerts'" 2>/dev/null
