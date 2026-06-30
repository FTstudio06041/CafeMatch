import time
import functools
import threading
from collections import OrderedDict

class MemoryCache:
    """
    簡易的「執行緒安全」in-memory LRU 快取，模擬 Redis-like 的行為。
    未來可直接抽換為真正的 Redis client。

    注意：此快取為單一程序的記憶體。若以 gunicorn 多 worker 部署，
    每個 worker 會各自持有一份，命中率較低且狀態不一致——正式環境建議改用 Redis。
    """
    def __init__(self, capacity=1000, ttl_seconds=3600):
        self.capacity = capacity
        self.ttl_seconds = ttl_seconds
        self.cache = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            entry = self.cache.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.time() > expires_at:
                del self.cache[key]
                return None
            self.cache.move_to_end(key)
            return value

    def set(self, key, value, ttl=None):
        with self._lock:
            expires_at = time.time() + (ttl if ttl is not None else self.ttl_seconds)
            self.cache[key] = (value, expires_at)
            self.cache.move_to_end(key)
            if len(self.cache) > self.capacity:
                self.cache.popitem(last=False)

    def delete(self, key):
        with self._lock:
            self.cache.pop(key, None)

# Global instance for the application
cache = MemoryCache()

def cached(prefix="", ttl=3600):
    """
    裝飾器：快取函式結果，並依各自指定的 ttl 設定存活時間。
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Create a simple string key from arguments
            key_parts = [prefix, func.__name__]
            key_parts.extend([str(arg) for arg in args])
            key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
            cache_key = ":".join(key_parts)

            result = cache.get(cache_key)
            if result is not None:
                return result

            result = func(*args, **kwargs)
            if result is not None:
                cache.set(cache_key, result, ttl=ttl)
            return result
        return wrapper
    return decorator
