import logging
from aiogram import Router, F, types, Dispatcher
from aiogram.fsm.context import FSMContext
from typing import Any, Dict, Callable, Awaitable
from aiogram.types import TelegramObject
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from bot.constants import MAX_MESSAGE_LENGTH, IMAGE_SIZE_LIMIT_MB


router = Router(name=__name__)
logger = logging.getLogger(__name__)


class WorkflowMiddleware(BaseMiddleware):
    def __init__(self, dispatcher: Dispatcher, **kwargs):
        """Initialize middleware
        
        Args:
            dispatcher (Dispatcher): The dispatcher instance to access workflow_data
            **kwargs: Additional arguments that might be passed by aiogram (unused)
        """
        self.dispatcher = dispatcher
        super().__init__()

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        if "workflow_data" not in data:
            data["workflow_data"] = self.dispatcher.workflow_data
        try:
            return await handler(event, data)
        except Exception as e:
            logger.error(f"Error in middleware: {e}")
            raise


# We'll register middleware in main.py where we have access to dp


@router.message(F.text & ~F.command)
async def handle_text(message: types.Message, state: FSMContext, **kwargs):
    """Handle text messages"""
    try:
        ai_client = kwargs["workflow_data"]["ai_client"]
        if not ai_client:
            await message.answer("⚠️ Ошибка инициализации AI клиента")
            return

        # Validate message length
        if len(message.text) > MAX_MESSAGE_LENGTH:
            await message.answer(f"⚠️ Сообщение слишком длинное. Максимум {MAX_MESSAGE_LENGTH} символов.")
            return

        data = await state.get_data()
        role = data.get("role", "assistant")

        # Send processing message
        processing_msg = await message.answer("🤔 Обрабатываю запрос...")

        try:
            answer = await ai_client.process_text(message.text, role)

            # Split long responses
            if len(answer) > MAX_MESSAGE_LENGTH:
                chunks = [answer[i:i + MAX_MESSAGE_LENGTH] for i in range(0, len(answer), MAX_MESSAGE_LENGTH)]
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await processing_msg.edit_text(chunk)
                    else:
                        await message.answer(chunk)
            else:
                await processing_msg.edit_text(answer)

        except Exception as e:
            logger.error(f"Error processing text: {e}")
            await processing_msg.edit_text("⚠️ Ошибка обработки запроса")

    except Exception as e:
        logger.error(f"Error in handle_text: {e}")
        await message.answer("⚠️ Ошибка обработки текста")


@router.message(F.photo)
async def handle_image(message: types.Message, state: FSMContext, **kwargs):
    """Handle image messages"""
    try:
        ai_client = kwargs["workflow_data"]["ai_client"]
        if not ai_client:
            await message.answer("⚠️ Ошибка инициализации AI клиента")
            return

        # Check image size
        photo = message.photo[-1]
        if photo.file_size > IMAGE_SIZE_LIMIT_MB * 1024 * 1024:
            await message.answer(f"⚠️ Изображение слишком большое. Максимум {IMAGE_SIZE_LIMIT_MB}MB.")
            return

        processing_msg = await message.answer("🖼️ Обрабатываю изображение...")

        try:
            photo_file = await message.bot.get_file(photo.file_id)
            photo_bytes = await message.bot.download_file(photo_file.file_path)
            user_prompt = message.caption

            answer = await ai_client.process_image(photo_bytes, user_prompt)

            # Split long responses
            if len(answer) > MAX_MESSAGE_LENGTH:
                chunks = [answer[i:i + MAX_MESSAGE_LENGTH] for i in range(0, len(answer), MAX_MESSAGE_LENGTH)]
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await processing_msg.edit_text(chunk)
                    else:
                        await message.answer(chunk)
            else:
                await processing_msg.edit_text(answer)

        except Exception as e:
            logger.error(f"Error processing image: {e}")
            await processing_msg.edit_text("⚠️ Ошибка обработки изображения")

    except Exception as e:
        logger.error(f"Error in handle_image: {e}")
        await message.answer("⚠️ Ошибка обработки изображения")


@router.error()
async def error_handler(update: types.Update, exception: Exception):
    """Handle errors"""
    logger.error(f"Update {update} caused error {exception}")

    error_msg = "⚠️ Произошла ошибка. Пожалуйста, попробуйте позже."
    if update.message:
        await update.message.answer(error_msg)
    elif update.callback_query:
        await update.callback_query.answer(error_msg, show_alert=True)
