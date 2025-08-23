import logging
from aiogram import Router, F, types, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.types import ErrorEvent
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
            # Проверяем тип ошибки для более конкретного логирования
            error_message = str(e)
            if "message is not modified" in error_message:
                # Это частая ошибка, не выводим полные детали
                logger.warning("Attempted to edit message with same content")
            elif "query is too old" in error_message or "query ID is invalid" in error_message:
                # Устаревший callback query, это нормальная ситуация
                logger.warning("Callback query expired or invalid")
            elif "Bad Request" in error_message and "timeout" in error_message:
                # Таймаут запроса, тоже частая ситуация
                logger.warning("Request timeout from Telegram API")
            else:
                # Логируем только ключевые детали, без полного содержимого
                event_type = type(event).__name__
                if hasattr(event, 'update_id'):
                    logger.error(f"Error in AI middleware for {event_type} (update_id: {event.update_id}): {e}")
                else:
                    logger.error(f"Error in AI middleware for {event_type}: {e}")
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
            answer = await ai_client.get_response(message.text, message.from_user.id, role)

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

            answer = await ai_client.process_image_with_limit(photo_bytes, message.from_user.id, user_prompt)

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


@router.errors()
async def error_handler(event: types.ErrorEvent):
    """Handle errors"""
    update = event.update
    exception = event.exception
    
    # Более компактное логирование ошибок
    error_message = str(exception)
    if "message is not modified" in error_message:
        logger.warning("Attempted to edit message with same content")
        return  # Не отправляем сообщение пользователю для этой ошибки
    
    # Логируем только важную информацию без полного содержимого
    update_type = "unknown"
    update_id = "unknown"
    
    if hasattr(update, 'update_id'):
        update_id = update.update_id
    
    if update.message:
        update_type = "message"
    elif update.callback_query:
        update_type = "callback_query"
    elif update.edited_message:
        update_type = "edited_message"
    
    logger.error(f"Update {update_type} (ID: {update_id}) caused error: {error_message}")

    error_msg = "⚠️ Произошла ошибка. Пожалуйста, попробуйте позже."
    
    if update.message:
        try:
            await update.message.answer(error_msg)
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")
    elif update.callback_query:
        try:
            await update.callback_query.answer(error_msg, show_alert=True)
        except Exception as e:
            logger.error(f"Failed to send error callback: {e}")
    else:
        logger.error(f"No way to send error message for update: {update}")
