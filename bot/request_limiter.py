import asyncio
import logging
import time
from typing import Dict, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class UserRequestInfo:
    """Информация о запросе пользователя"""
    user_id: int
    request_type: str  # 'text' или 'image'
    start_time: float
    task: asyncio.Task = None


class RequestLimiter:
    """Ограничитель одновременных запросов к AI от одного пользователя"""
    
    def __init__(self, max_request_time: int = 300):  # 5 минут максимум
        self.active_requests: Dict[int, UserRequestInfo] = {}
        self.max_request_time = max_request_time
        self._cleanup_task: asyncio.Task = None
        self._running = False
    
    async def start(self):
        """Запускает сервис очистки зависших запросов"""
        if self._running:
            return
            
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_expired_requests())
        logger.info("RequestLimiter started")
    
    async def stop(self):
        """Останавливает сервис"""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("RequestLimiter stopped")
    
    async def acquire_request_lock(self, user_id: int, request_type: str) -> bool:
        """
        Пытается получить блокировку для запроса пользователя
        
        Args:
            user_id: ID пользователя
            request_type: Тип запроса ('text' или 'image')
            
        Returns:
            bool: True если блокировка получена, False если уже есть активный запрос
        """
        current_time = time.time()
        
        # Проверяем, есть ли активный запрос от этого пользователя
        if user_id in self.active_requests:
            existing_request = self.active_requests[user_id]
            
            # Проверяем, не завис ли запрос
            if current_time - existing_request.start_time > self.max_request_time:
                logger.warning(
                    f"Request from user {user_id} expired after {self.max_request_time}s, releasing lock"
                )
                await self._release_request_lock(user_id)
            else:
                # Активный запрос есть, блокируем новый
                logger.info(f"User {user_id} already has active {existing_request.request_type} request")
                return False
        
        # Создаем новую блокировку
        self.active_requests[user_id] = UserRequestInfo(
            user_id=user_id,
            request_type=request_type,
            start_time=current_time
        )
        
        logger.info(f"Acquired request lock for user {user_id}, type: {request_type}")
        return True
    
    async def release_request_lock(self, user_id: int):
        """Освобождает блокировку запроса пользователя"""
        await self._release_request_lock(user_id)
    
    async def _release_request_lock(self, user_id: int):
        """Внутренний метод освобождения блокировки"""
        if user_id in self.active_requests:
            request_info = self.active_requests[user_id]
            duration = time.time() - request_info.start_time
            
            # Отменяем задачу, если она есть
            if request_info.task and not request_info.task.done():
                request_info.task.cancel()
            
            del self.active_requests[user_id]
            logger.info(f"Released request lock for user {user_id}, duration: {duration:.2f}s")
    
    async def _cleanup_expired_requests(self):
        """Периодически очищает зависшие запросы"""
        while self._running:
            try:
                current_time = time.time()
                expired_users = []
                
                for user_id, request_info in self.active_requests.items():
                    if current_time - request_info.start_time > self.max_request_time:
                        expired_users.append(user_id)
                
                for user_id in expired_users:
                    logger.warning(f"Cleaning up expired request for user {user_id}")
                    await self._release_request_lock(user_id)
                
                await asyncio.sleep(60)  # Проверяем каждую минуту
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(60)
    
    def get_active_requests_count(self) -> int:
        """Возвращает количество активных запросов"""
        return len(self.active_requests)
    
    def is_user_active(self, user_id: int) -> bool:
        """Проверяет, есть ли активный запрос у пользователя"""
        return user_id in self.active_requests
    
    def get_user_request_info(self, user_id: int) -> UserRequestInfo:
        """Возвращает информацию о запросе пользователя"""
        return self.active_requests.get(user_id)
