"""文件缓存模块 - 用于多Worker进程间共享缓存"""
import json
import os
import time
from typing import Any, Optional

CACHE_DIR = "/tmp/tg-monitor-cache"

class FileCache:
    """文件缓存"""
    
    def __init__(self, cache_dir: str = CACHE_DIR):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
    
    def get(self, key: str, ttl: int = 60) -> Optional[Any]:
        """获取缓存值"""
        cache_file = os.path.join(self.cache_dir, f"{key}.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                if time.time() - data.get('time', 0) < ttl:
                    return data.get('value')
                else:
                    os.remove(cache_file)
            except Exception:
                pass
        return None
    
    def set(self, key: str, value: Any) -> None:
        """设置缓存值"""
        cache_file = os.path.join(self.cache_dir, f"{key}.json")
        try:
            with open(cache_file, 'w') as f:
                json.dump({'value': value, 'time': time.time()}, f)
        except Exception:
            pass
    
    def invalidate(self, key: str) -> None:
        """使缓存失效"""
        cache_file = os.path.join(self.cache_dir, f"{key}.json")
        if os.path.exists(cache_file):
            try:
                os.remove(cache_file)
            except Exception:
                pass

# 全局缓存实例
file_cache = FileCache()
