#!/usr/bin/env python3
"""
Session文件保护器
- 自动备份session文件
- 监控session文件完整性
- 自动恢复损坏的session
"""
import os
import shutil
import time
import sqlite3
from pathlib import Path
from datetime import datetime

SESSION_DIR = "/home/test/tg-monitor/backend/sessions"
BACKUP_DIR = "/home/test/tg-monitor/backend/sessions/backup"
PHONE = "+8613991539939"
CHECK_INTERVAL = 60  # 检查间隔（秒）

def ensure_dirs():
    """确保目录存在"""
    os.makedirs(BACKUP_DIR, exist_ok=True)

def get_session_path(phone):
    """获取session文件路径"""
    return os.path.join(SESSION_DIR, f"{phone}.session")

def get_backup_path(phone):
    """获取备份文件路径"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(BACKUP_DIR, f"{phone}.session.{timestamp}")

def get_latest_backup(phone):
    """获取最新的备份文件"""
    pattern = os.path.join(BACKUP_DIR, f"{phone}.session.*")
    import glob
    backups = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    return backups[0] if backups else None

def is_session_valid(session_path):
    """检查session文件是否有效"""
    if not os.path.exists(session_path):
        return False
    
    # 检查文件大小
    size = os.path.getsize(session_path)
    if size < 1024:  # 小于1KB可能是空文件
        return False
    
    # 检查是否是有效的SQLite
    try:
        conn = sqlite3.connect(session_path)
        cursor = conn.cursor()
        # 检查是否有sessions表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return "sessions" in tables
    except:
        return False

def backup_session(phone):
    """备份session文件"""
    session_path = get_session_path(phone)
    if not os.path.exists(session_path):
        return False
    
    backup_path = get_backup_path(phone)
    shutil.copy2(session_path, backup_path)
    print(f"[{datetime.now()}] 备份session: {backup_path}")
    return True

def restore_session(phone):
    """从备份恢复session文件"""
    session_path = get_session_path(phone)
    backup_path = get_latest_backup(phone)
    
    if backup_path and os.path.exists(backup_path):
        shutil.copy2(backup_path, session_path)
        print(f"[{datetime.now()}] 恢复session: {backup_path} -> {session_path}")
        return True
    else:
        print(f"[{datetime.now()}] 无可用备份，需要重新登录")
        return False

def cleanup_old_backups(phone, keep=5):
    """清理旧备份，只保留最近N个"""
    import glob
    pattern = os.path.join(BACKUP_DIR, f"{phone}.session.*")
    backups = sorted(glob.glob(pattern), key=os.path.getmtime)
    
    if len(backups) > keep:
        for old_backup in backups[:-keep]:
            os.remove(old_backup)
            print(f"[{datetime.now()}] 清理旧备份: {old_backup}")

def monitor():
    """主监控循环"""
    ensure_dirs()
    last_backup_time = 0
    
    print(f"[{datetime.now()}] Session保护器启动")
    print(f"[{datetime.now()}] 监控目录: {SESSION_DIR}")
    print(f"[{datetime.now()}] 备份目录: {BACKUP_DIR}")
    
    while True:
        try:
            session_path = get_session_path(PHONE)
            
            # 检查session文件
            if not is_session_valid(session_path):
                print(f"[{datetime.now()}] Session文件无效，尝试恢复...")
                if restore_session(PHONE):
                    print(f"[{datetime.now()}] Session恢复成功")
                else:
                    print(f"[{datetime.now()}] 需要重新登录Telegram")
            else:
                # 定期备份（每5分钟）
                if time.time() - last_backup_time > 300:
                    if backup_session(PHONE):
                        last_backup_time = time.time()
                        cleanup_old_backups(PHONE)
            
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            print(f"[{datetime.now()}] Session保护器停止")
            break
        except Exception as e:
            print(f"[{datetime.now()}] 错误: {e}")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    monitor()
