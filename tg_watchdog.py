#!/usr/bin/env python3
"""Telegram 监控看门狗：检测消息停滞后自动重启监控"""

import requests
import time
import logging
import sys
from datetime import datetime, timezone, timedelta

API_BASE = "http://127.0.0.1:8000"
CHECK_INTERVAL = 60        # 每 60 秒检查一次
STALE_THRESHOLD = 15 * 60  # 15 分钟没有新消息视为停滞
LOG_FILE = "/var/log/tg_watchdog.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("tg_watchdog")


def get_latest_message_time():
    try:
        r = requests.get(
            f"{API_BASE}/api/v1/messages",
            params={"limit": 1, "sort_by": "date", "order": "desc"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        items = data.get("items", [])
        if items and items[0].get("date"):
            return datetime.fromisoformat(items[0]["date"])
    except Exception as e:
        log.warning(f"获取最新消息失败: {e}")
    return None


def get_monitoring_status():
    try:
        r = requests.get(f"{API_BASE}/api/v1/monitoring/status", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning(f"获取监控状态失败: {e}")
    return None


def restart_monitoring():
    log.info(">>> 开始执行监控重启 <<<")
    try:
        # 多进程架构下，api_worker 的 client_manager 是空的
        # 直接重启 monitor_worker 才能恢复监控
        import subprocess
        result = subprocess.run(
            ["sudo", "systemctl", "restart", "tgmonitor-monitor-0"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            log.info("monitor_worker 重启成功")
        else:
            log.error(f"monitor_worker 重启失败: {result.stderr}")
    except Exception as e:
        log.error(f"重启过程异常: {e}")


def main():
    log.info("Telegram 监控看门狗启动")
    log.info(f"检查间隔: {CHECK_INTERVAL}s, 停滞阈值: {STALE_THRESHOLD}s")

    while True:
        try:
            latest = get_latest_message_time()
            now = datetime.now(timezone.utc)

            if latest:
                age = (now - latest).total_seconds()
                if age > STALE_THRESHOLD:
                    log.warning(
                        f"检测到消息停滞! 最新消息: {latest.isoformat()} "
                        f"(距今 {age/60:.1f} 分钟)"
                    )
                    restart_monitoring()
                    # 重启后等待 120 秒让系统初始化
                    time.sleep(120)
                else:
                    log.info(f"正常: 最新消息 {age/60:.1f} 分钟前")
            else:
                log.warning("无法获取最新消息时间，跳过本轮检查")

            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            log.info("看门狗收到中断信号，退出")
            break
        except Exception as e:
            log.error(f"主循环异常: {e}")
            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
