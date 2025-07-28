import asyncio
import logging
import signal
import sys
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)
from bot.ai_client import AIClient
from bot.owner_manager import OwnerManager
from bot.handlers import (
    start,
    button_handler,
    show_settings,
    show_stats,
    handle_text,
    handle_image,
    error_handler
)
from config import Config

# Настройка логирования
logging.basicConfig(
    format=Config.LOG_FORMAT,
    level=Config.get_log_level()
)
logger = logging.getLogger(__name__)


def shutdown(signal, frame):
    logger.info("Shutting down...")
    loop = asyncio.get_event_loop()
    loop.create_task(shutdown_async())
    sys.exit(0)


async def shutdown_async():
    if "application" in globals():
        await application.shutdown()
    sys.exit(0)
    

async def main() -> None:
    global application
    try:
        # Валидация конфигурации
        Config.validate()
        
        # Создание приложения
        application = Application.builder().token(Config.TELEGRAM_TOKEN).build()
        await application.initialize()

        # Инициализация менеджера владельца
        owner_manager = OwnerManager(application)
        await owner_manager.initialize()
        application.bot_data["owner_manager"] = owner_manager
        
        # Инициализация AI клиента
        ai_client = AIClient()
        application.bot_data["ai_client"] = ai_client
        
        # Проверяем доступные провайдеры
        available_providers = Config.get_providers()
        if not available_providers:
            logger.error("No AI providers configured!")
            return
            
        logger.info(f"Available AI providers: {list(available_providers.keys())}")
        
        # Логируем информацию о владельце
        owner_id = owner_manager.get_owner_id()
        if owner_id:
            logger.info(f"Bot owner ID: {owner_id}")
        else:
            logger.warning("No bot owner detected")

        # Регистрация обработчиков команд
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("settings", show_settings))
        application.add_handler(CommandHandler("stats", show_stats))

        # Регистрация обработчиков сообщений
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        application.add_handler(MessageHandler(filters.PHOTO, handle_image))

        # Обработчик ошибок
        application.add_error_handler(error_handler)

        logger.info("Bot started successfully")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

        while True:
            await asyncio.sleep(1)
        
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        return


if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    asyncio.run(main())
