import pickle
import redis
import logging
from datetime import timedelta
from typing import Optional, Any, Union
from config import Config

logger = logging.getLogger(__name__)

class CacheManager:
    # Предустановленные TTL для разных типов данных
    TTL_CONFIGS = {
        # Напоминания - бессрочно (очень долго)
        "reminder": None,  # Без TTL (бессрочно)
        "user_reminders": None,  # Без TTL (бессрочно)
        "global": None,  # Без TTL (бессрочно)
        
        # AI кэш - 1 час
        "ai_text": timedelta(hours=1),
        "ai_image": timedelta(hours=1),
        
        # По умолчанию - из конфига
        "default": timedelta(seconds=Config.CACHE_TTL)
    }
    
    def __init__(self):
        try:
            self.redis = redis.from_url(Config.REDIS_URL)
            # Проверяем подключение
            self.redis.ping()
            logger.info("Redis connection established")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis = None
        
        # Устаревший TTL для обратной совместимости
        self.ttl = timedelta(seconds=Config.CACHE_TTL)

    def _get_ttl_for_prefix(self, prefix: str) -> Optional[Union[int, timedelta]]:
        """Возвращает TTL для конкретного префикса"""
        ttl_config = self.TTL_CONFIGS.get(prefix, self.TTL_CONFIGS["default"])
        
        if ttl_config is None:
            return None  # Бессрочное хранение
        elif isinstance(ttl_config, timedelta):
            return ttl_config
        else:
            return self.TTL_CONFIGS["default"]

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

    async def set(self, prefix: str, identifier: str, data: Any, custom_ttl: Optional[Union[int, timedelta]] = None) -> bool:
        if not self.redis:
            return False
            
        try:
            key = self._generate_key(prefix, identifier)
            
            # Определяем TTL
            if custom_ttl is not None:
                ttl = custom_ttl
            else:
                ttl = self._get_ttl_for_prefix(prefix)
            
            # Сохраняем данные
            if ttl is None:
                # Бессрочное хранение
                self.redis.set(key, pickle.dumps(data))
                logger.debug(f"Cache set permanently for key: {key}")
            else:
                # С ограниченным временем жизни
                self.redis.setex(key, ttl, pickle.dumps(data))
                logger.debug(f"Cache set for key: {key} with TTL: {ttl}")
            
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