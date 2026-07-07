"""
Redis缓存模块 - 优化版
支持缓存穿透防护、热点key永不过期
"""
import json
import random
from typing import Any, Optional
import redis
from loguru import logger

# Redis连接
_redis_client = None

# 空值缓存标记
NULL_VALUE = "__NULL__"
NULL_CACHE_TTL = 30  # 空值缓存30秒

def get_redis():
    """获取Redis客户端（线程安全）"""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.Redis(
                host="localhost",
                port=6379,
                db=0,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            logger.info("Redis连接创建成功")
        except Exception as e:
            logger.error(f"Redis连接创建失败: {e}")
            raise
    return _redis_client

class RedisCache:
    """Redis缓存"""
    
    def __init__(self):
        self.client = get_redis()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        try:
            data = self.client.get(key)
            if data:
                # 检查是否为空值缓存
                if data == NULL_VALUE:
                    return None
                return json.loads(data)
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"Redis缓存JSON解析失败: key={key}, error={e}")
            return None
        except redis.ConnectionError as e:
            logger.error(f"Redis连接错误: {e}")
            return False
        except Exception as e:
            logger.error(f"Redis获取缓存异常: key={key}, error={e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 60) -> bool:
        """设置缓存值（带随机TTL防雪崩）"""
        try:
            # 空值缓存特殊处理
            if value is None:
                json_str = NULL_VALUE
                actual_ttl = NULL_CACHE_TTL
            else:
                json_str = json.dumps(value)
                # 添加随机偏移防止缓存雪崩
                actual_ttl = ttl + random.randint(0, min(30, ttl // 2))
            
            self.client.setex(key, actual_ttl, json_str)
            logger.debug(f"Redis缓存设置成功: key={key}, ttl={actual_ttl}")
            return True
        except (TypeError, ValueError) as e:
            logger.warning(f"Redis缓存序列化失败: key={key}, error={e}")
            return False
        except redis.ConnectionError as e:
            logger.error(f"Redis连接错误: {e}")
            return False
        except Exception as e:
            logger.error(f"Redis设置缓存异常: key={key}, error={e}")
            return False
    
    def set_null(self, key: str, ttl: int = NULL_CACHE_TTL) -> bool:
        """设置空值缓存（防穿透）"""
        try:
            self.client.setex(key, ttl, NULL_VALUE)
            logger.debug(f"Redis空值缓存设置成功: key={key}, ttl={ttl}")
            return True
        except Exception as e:
            logger.error(f"Redis设置空值缓存异常: key={key}, error={e}")
            return False
    
    def get_or_set(
        self,
        key: str,
        fetch_fn,
        ttl: int = 60,
        null_ttl: int = NULL_CACHE_TTL
    ) -> Optional[Any]:
        """获取缓存，不存在则调用fetch_fn并缓存结果"""
        # 尝试获取缓存
        cached = self.get(key)
        if cached is not None:
            return cached
        
        # 缓存不存在，调用获取函数
        try:
            value = fetch_fn()
            if value is None:
                # 空值缓存，防止穿透
                self.set_null(key, null_ttl)
                return None
            else:
                # 正常缓存
                self.set(key, value, ttl)
                return value
        except Exception as e:
            logger.error(f"获取数据失败: key={key}, error={e}")
            return None
    
    def invalidate(self, key: str) -> bool:
        """使缓存失效"""
        try:
            self.client.delete(key)
            logger.debug(f"Redis缓存已删除: key={key}")
            return True
        except redis.ConnectionError as e:
            logger.error(f"Redis连接错误: {e}")
            return False
        except Exception as e:
            logger.error(f"Redis删除缓存异常: key={key}, error={e}")
            return False
    
    def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        try:
            return bool(self.client.exists(key))
        except Exception:
            return False
    
    def invalidate_pattern(self, pattern: str) -> int:
        """批量删除匹配模式的缓存"""
        try:
            keys = self.client.keys(pattern)
            if keys:
                deleted = self.client.delete(*keys)
                logger.debug(f"Redis批量删除缓存: pattern={pattern}, count={deleted}")
                return deleted
            return 0
        except Exception as e:
            logger.error(f"Redis批量删除缓存异常: pattern={pattern}, error={e}")
            return 0

# 全局缓存实例
redis_cache = RedisCache()

