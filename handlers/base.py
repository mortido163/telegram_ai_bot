import logging
from aiogram import Router, types
from aiogram.filters import CommandStart

logger = logging.getLogger(__name__)
router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    """Handle /start command"""
    try:
        welcome_msg = (
            "🤖 <b>Добро пожаловать в AI-ассистент!</b>\n\n"
            "Я поддерживаю несколько моделей и ролей:\n"
            "• <b>Модели:</b> OpenAI, DeepSeek\n"
            "• <b>Роли:</b> Ассистент, Ученый, Креатив, Разработчик\n\n"
            "🔔 <b>Новое:</b> Система напоминаний!\n"
            "• Создавайте персональные напоминания\n"
            "• Получайте уведомления в нужное время\n\n"
            "<b>Команды:</b>\n"
            "• /settings - настройки AI\n"
            "• /reminders - управление напоминаниями\n\n"
            "Просто отправьте текст или фото для запроса"
        )
        await message.answer(welcome_msg)
    except Exception as e:
        logger.error(f"Error in start handler: {e}")
        await message.answer("⚠️ Ошибка при запуске бота")
