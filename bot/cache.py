import pickle
import redis
import logging
from datetime import timedelta
from typing import Optional, Any
from config import Config

logger = logging.getLogger(__name__)

class CacheManager:
    def __init__(self):
        try:
            self.redis = redis.from_url(Config.REDIS_URL)
            # Проверяем подключение
            self.redis.ping()
            logger.info("Redis connection established")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis = None
        
        self.ttl = timedelta(seconds=Config.CACHE_TTL)

    def _generate_key(self, prefix: str, identifier: str) -> str:
        return f"{prefix}:{identifier}"

    async def get(self, prefix: str, identifier: str) -> Optional[Any]:
        if not self.redis:
            return None
            
        try:
            key = self._generate_key(prefix, identifier)
            cached_data = self.redis.get(key)
            if cached_data:
                logger.debug(f"Cache hit for key: {key}")
                return pickle.loads(cached_data)
            return None
        except Exception as e:
            logger.error(f"Error getting from cache: {e}")
            return None

    async def set(self, prefix: str, identifier: str, data: Any) -> bool:
        if not self.redis:
            return False
            
        try:
            key = self._generate_key(prefix, identifier)
            self.redis.setex(key, self.ttl, pickle.dumps(data))
            logger.debug(f"Cache set for key: {key}")
            return True
        except Exception as e:
            logger.error(f"Error setting cache: {e}")
            return False

    async def clear(self, prefix: str, identifier: str) -> bool:
        if not self.redis:
            return False
            
        try:
            key = self._generate_key(prefix, identifier)
            self.redis.delete(key)
            logger.debug(f"Cache cleared for key: {key}")
            return True
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False

    async def clear_all(self, prefix: str) -> bool:
        """Очищает все ключи с указанным префиксом"""
        if not self.redis:
            return False
            
        try:
            pattern = f"{prefix}:*"
            keys = self.redis.keys(pattern)
            if keys:
                self.redis.delete(*keys)
                logger.info(f"Cleared {len(keys)} cache entries with prefix: {prefix}")
            return True
        except Exception as e:
            logger.error(f"Error clearing cache prefix: {e}")
            return False