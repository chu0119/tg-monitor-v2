"""缓存工具模块"""
import time
from functools import wraps
from typing import Any, Callable, Optional

class MemoryCache:
    """内存缓存"""
    
    def __init__(self):
        self._cache = {}
        self._timestamps = {}
    
    def get(self, key: str, ttl: int = 60) -> Optional[Any]:
        """获取缓存值"""
        if key in self._cache:
            if time.time() - self._timestamps[key] < ttl:
                return self._cache[key]
            else:
                del self._cache[key]
                del self._timestamps[key]
        return None
    
    def set(self, key: str, value: Any) -> None:
        """设置缓存值"""
        self._cache[key] = value
        self._timestamps[key] = time.time()
    
    def invalidate(self, key: str) -> None:
        """使缓存失效"""
        if key in self._cache:
            del self._cache[key]
            del self._timestamps[key]
    
    def clear(self) -> None:
        """清空所有缓存"""
        self._cache.clear()
        self._timestamps.clear()

# 全局缓存实例
memory_cache = MemoryCache()

def cached(ttl: int = 60, key_prefix: str = ""):
    """缓存装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # 尝试获取缓存
            cached_value = memory_cache.get(cache_key, ttl)
            if cached_value is not None:
                return cached_value
            
            # 执行函数
            result = await func(*args, **kwargs)
            
            # 缓存结果
            memory_cache.set(cache_key, result)
            
            return result
        return wrapper
    return decorator
