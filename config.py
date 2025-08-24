import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class Config:
    # Основные настройки
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_URL = os.getenv("DEEPSEEK_URL", "https://api.deepseek.com/v1/chat/completions")

    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_URL = os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1")
    
    # Настройки Моделей
    OPENAI_TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-5-nano")
    OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-4-vision-preview")
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/auto")
    
    # Настройки Redis
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Настройки кэша
    CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))
    
    # Настройки логирования
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Настройки запросов
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
    
    # Настройки владельца
    BOT_OWNER_ID = os.getenv("BOT_OWNER_ID")
    
    @classmethod
    def validate(cls):
        """Проверяет наличие обязательных переменных окружения"""
        missing_vars = []
        
        if not cls.TELEGRAM_TOKEN:
            missing_vars.append("TELEGRAM_BOT_TOKEN")
        if not cls.OPENAI_API_KEY:
            missing_vars.append("OPENAI_API_KEY")
            
        if missing_vars:
            error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        logger.info("Configuration validated successfully")
    
    @classmethod
    def get_providers(cls):
        """Возвращает список доступных AI провайдеров"""
        providers = {}
        
        if cls.OPENAI_API_KEY:
            providers["openai"] = "OpenAI"
            
        if cls.DEEPSEEK_API_KEY:
            providers["deepseek"] = "DeepSeek"

        if cls.OPENROUTER_API_KEY:
            providers["openrouter"] = "OpenRouter"
            
        return providers
    
    @classmethod
    def is_owner(cls, user_id: int, bot_instance=None) -> bool:
        """Проверяет, является ли пользователь владельцем бота"""
        # Сначала проверяем переменную окружения
        if cls.BOT_OWNER_ID:
            try:
                owner_id = int(cls.BOT_OWNER_ID)
                return user_id == owner_id
            except (ValueError, TypeError):
                logger.warning(f"Invalid BOT_OWNER_ID: {cls.BOT_OWNER_ID}")
        
        # Если есть экземпляр бота, используем его для получения информации
        if bot_instance:
            try:
                bot_info = bot_instance.get_me()
                # В Telegram API нет прямого способа получить владельца бота
                # Но мы можем использовать логику определения первого пользователя
                logger.info(f"Bot info: {bot_info.id} - {bot_info.first_name}")
                return False  # По умолчанию возвращаем False для безопасности
            except Exception as e:
                logger.error(f"Error getting bot info: {e}")
        
        return False

    @classmethod
    def get_log_level(cls) -> int:
        """Возвращает уровень логирования"""
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        return level_map.get(cls.LOG_LEVEL.upper(), logging.WARNING)