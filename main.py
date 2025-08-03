import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.ai_client import AIClient
from bot.owner_manager import OwnerManager
from config import Config
from handlers.base import router as base_router
from handlers.settings import router as settings_router, WorkflowMiddleware as SettingsWorkflowMiddleware
from handlers.ai import router as ai_router, WorkflowMiddleware as AIWorkflowMiddleware

logging.basicConfig(
    format=Config.LOG_FORMAT,
    level=Config.get_log_level()
)
logger = logging.getLogger(__name__)

# Initialize storage, bot and dispatcher
storage = MemoryStorage()
bot = Bot(token=Config.TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=storage)

# Initialize workflow data
dp.workflow_data = {}

# Set up middleware
settings_router.message.middleware(SettingsWorkflowMiddleware(dp))
settings_router.callback_query.middleware(SettingsWorkflowMiddleware(dp))

# Set up AI middleware
ai_router.message.middleware(AIWorkflowMiddleware(dp))
ai_router.callback_query.middleware(AIWorkflowMiddleware(dp))
ai_router.edited_message.middleware(AIWorkflowMiddleware(dp))
ai_router.error.middleware(AIWorkflowMiddleware(dp))

# Include routers
dp.include_router(base_router)
dp.include_router(settings_router)
dp.include_router(ai_router)

async def startup(dispatcher: Dispatcher):
    """Startup actions"""
    try:
        # Validate configuration
        Config.validate()
        
        # Initialize owner manager
        owner_manager = OwnerManager(bot)
        await owner_manager.initialize()
        
        # Initialize AI client
        ai_client = AIClient()
        
        # Set data in dispatcher
        dispatcher.workflow_data["owner_manager"] = owner_manager
        dispatcher.workflow_data["ai_client"] = ai_client
        
        # Check available providers
        available_providers = Config.get_providers()
        if not available_providers:
            logger.error("No AI providers configured!")
            return
            
        logger.info(f"Available AI providers: {list(available_providers.keys())}")
        
        # Log owner information
        owner_id = owner_manager.get_owner_id()
        if owner_id:
            logger.info(f"Bot owner ID: {owner_id}")
        else:
            logger.warning("No bot owner detected")
            
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

async def shutdown(dispatcher: Dispatcher):
    """Shutdown actions"""
    logger.info("Shutting down...")
    await bot.session.close()

async def main():
    """Main function to start the bot"""
    try:
        # Set up startup and shutdown handlers
        dp.startup.register(startup)
        dp.shutdown.register(shutdown)
        
        # Start polling
        logger.info("Starting bot...")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped!")
