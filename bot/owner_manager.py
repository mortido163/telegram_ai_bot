import logging
from typing import Optional, Set
from aiogram import Bot
from config import Config

logger = logging.getLogger(__name__)

class OwnerManager:
    """Менеджер для управления владельцем бота"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self._owner_id: Optional[int] = None
        self._admin_ids: Set[int] = set()
        
    async def initialize(self):
        """Инициализация менеджера владельца"""
        try:
            # Получаем информацию о боте
            bot_info = await self.bot.get_me()
            logger.info(f"Bot initialized: {bot_info.first_name} (@{bot_info.username})")
            
            # Устанавливаем владельца из конфигурации
            if Config.BOT_OWNER_ID:
                try:
                    self._owner_id = int(Config.BOT_OWNER_ID)
                    logger.info(f"Owner ID set from config: {self._owner_id}")
                except (ValueError, TypeError):
                    logger.warning(f"Invalid BOT_OWNER_ID: {Config.BOT_OWNER_ID}")
            
            # Попытка автоматического определения владельца
            if not self._owner_id:
                await self._detect_owner()
                
        except Exception as e:
            logger.error(f"Error initializing owner manager: {e}")
    
    async def _detect_owner(self):
        """Автоматическое определение владельца бота"""
        try:
            # Владелец должен быть установлен через конфигурацию или явно через set_owner
            logger.warning("Auto-detection of owner is not supported in aiogram 3.x")
        except Exception as e:
            logger.error(f"Error detecting owner: {e}")
    
    def is_owner(self, user_id: int) -> bool:
        """Проверяет, является ли пользователь владельцем"""
        if self._owner_id is None:
            return False
        return user_id == self._owner_id
    
    def add_admin(self, user_id: int):
        """Добавляет администратора"""
        self._admin_ids.add(user_id)
        logger.info(f"Admin added: {user_id}")
    
    def remove_admin(self, user_id: int):
        """Удаляет администратора"""
        self._admin_ids.discard(user_id)
        logger.info(f"Admin removed: {user_id}")
    
    def is_admin(self, user_id: int) -> bool:
        """Проверяет, является ли пользователь администратором"""
        return user_id in self._admin_ids or self.is_owner(user_id)
    
    def get_owner_id(self) -> Optional[int]:
        """Возвращает ID владельца"""
        return self._owner_id
    
    def get_admin_ids(self) -> Set[int]:
        """Возвращает список ID администраторов"""
        return self._admin_ids.copy()
    
    def set_owner(self, user_id: int):
        """Устанавливает владельца бота"""
        self._owner_id = user_id
        logger.info(f"Owner set to: {user_id}")
    
    async def get_bot_info(self):
        """Получает информацию о боте"""
        try:
            return await self.bot.get_me()
        except Exception as e:
            logger.error(f"Error getting bot info: {e}")
            return None 