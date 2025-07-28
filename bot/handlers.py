import logging
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from telegram.ext import ContextTypes
from .constants import ROLES, BUTTON_TEXTS, MAX_MESSAGE_LENGTH, IMAGE_SIZE_LIMIT_MB
from .metrics import metrics

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def get_owner_manager(context: ContextTypes.DEFAULT_TYPE):
    """Получает менеджер владельца из контекста"""
    return context.bot_data.get("owner_manager")

def is_owner(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Проверяет, является ли пользователь владельцем"""
    owner_manager = get_owner_manager(context)
    if owner_manager:
        return owner_manager.is_owner(user_id)
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start с инструкциями"""
    try:
        welcome_msg = (
            "🤖 <b>Добро пожаловать в AI-ассистент!</b>\n\n"
            "Я поддерживаю несколько моделей и ролей:\n"
            "• <b>Модели:</b> OpenAI, DeepSeek\n"
            "• <b>Роли:</b> Ассистент, Ученый, Креатив, Разработчик\n\n"
            "Используйте /settings для настройки\n"
            "Просто отправьте текст или фото для запроса"
        )
        await update.message.reply_text(welcome_msg, parse_mode="HTML")
        logger.info(f"User {update.effective_user.id} started the bot")
    except Exception as e:
        logger.error(f"Error in start handler: {e}")
        await update.message.reply_text("⚠️ Ошибка при запуске бота")


async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает текущие настройки с inline-кнопками"""
    try:
        ai_client = context.bot_data.get("ai_client")
        user_data = context.user_data

        if not ai_client:
            await update.message.reply_text("⚠️ Ошибка инициализации AI клиента")
            return

        current_model = ai_client.active_provider
        current_role = user_data.get("role", "assistant")

        settings_text = (
            "⚙️ <b>Текущие настройки:</b>\n\n"
            f"🔧 <b>Модель:</b> {BUTTON_TEXTS['models'][current_model]}\n"
            f"🎭 <b>Роль:</b> {BUTTON_TEXTS['roles'][current_role]}\n\n"
            "Выберите что изменить:"
        )

        keyboard = [
            [
                InlineKeyboardButton("🔄 Модель", callback_data="change_model"),
                InlineKeyboardButton("🎭 Роль", callback_data="change_role")
            ]
        ]
        
        # Добавляем кнопку статистики только для владельца
        if is_owner(update.effective_user.id, context):
            keyboard.append([InlineKeyboardButton("📊 Статистика", callback_data="show_stats")])
        
        keyboard.append([InlineKeyboardButton("❌ Закрыть", callback_data="close_settings")])

        await update.message.reply_text(
            settings_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error in show_settings: {e}")
        await update.message.reply_text("⚠️ Ошибка отображения настроек")


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику бота (только для владельца)"""
    try:
        user_id = update.effective_user.id
        
        # Проверяем, является ли пользователь владельцем
        if not is_owner(user_id, context):
            await update.message.reply_text("🚫 У вас нет доступа к статистике бота")
            logger.warning(f"User {user_id} attempted to access stats without permission")
            return
        
        stats = metrics.get_stats()
        
        if not stats:
            await update.message.reply_text("📊 Статистика пока недоступна")
            return
            
        stats_text = (
            "📊 <b>Статистика бота:</b>\n\n"
            f"📈 <b>Всего запросов:</b> {stats['total_requests']}\n"
            f"✅ <b>Успешных:</b> {stats['successful_requests']}\n"
            f"❌ <b>Ошибок:</b> {stats['failed_requests']}\n"
            f"📊 <b>Успешность:</b> {stats['success_rate']:.1%}\n"
            f"⏱️ <b>Среднее время ответа:</b> {stats['avg_response_time']:.2f}с\n\n"
            f"💾 <b>Кэш:</b>\n"
            f"• Попадания: {stats['cache_hits']}\n"
            f"• Промахи: {stats['cache_misses']}\n"
            f"• Эффективность: {stats['cache_hit_rate']:.1%}\n\n"
        )
        
        # Добавляем статистику по провайдерам
        if stats.get('providers'):
            stats_text += "<b>По провайдерам:</b>\n"
            for provider, provider_stats in stats['providers'].items():
                stats_text += (
                    f"• <b>{provider.upper()}:</b> "
                    f"{provider_stats['successful']}/{provider_stats['total']} "
                    f"({provider_stats['success_rate']:.1%}) "
                    f"⏱️ {provider_stats['avg_response_time']:.2f}с\n"
                )
        
        await update.message.reply_text(stats_text, parse_mode="HTML")
        logger.info(f"Owner {user_id} accessed bot statistics")
        
    except Exception as e:
        logger.error(f"Error in show_stats: {e}")
        await update.message.reply_text("⚠️ Ошибка отображения статистики")


async def show_stats_callback(query, context):
    """Показывает статистику через callback (только для владельца)"""
    try:
        user_id = query.from_user.id
        
        # Проверяем, является ли пользователь владельцем
        if not is_owner(user_id, context):
            await query.answer("🚫 У вас нет доступа к статистике бота", show_alert=True)
            logger.warning(f"User {user_id} attempted to access stats without permission")
            return
        
        stats = metrics.get_stats()
        
        if not stats:
            await query.answer("📊 Статистика пока недоступна", show_alert=True)
            return
            
        stats_text = (
            "📊 <b>Статистика бота:</b>\n\n"
            f"📈 <b>Всего запросов:</b> {stats['total_requests']}\n"
            f"✅ <b>Успешных:</b> {stats['successful_requests']}\n"
            f"❌ <b>Ошибок:</b> {stats['failed_requests']}\n"
            f"📊 <b>Успешность:</b> {stats['success_rate']:.1%}\n"
            f"⏱️ <b>Среднее время ответа:</b> {stats['avg_response_time']:.2f}с\n\n"
            f"💾 <b>Кэш:</b>\n"
            f"• Попадания: {stats['cache_hits']}\n"
            f"• Промахи: {stats['cache_misses']}\n"
            f"• Эффективность: {stats['cache_hit_rate']:.1%}\n\n"
        )
        
        # Добавляем статистику по провайдерам
        if stats.get('providers'):
            stats_text += "<b>По провайдерам:</b>\n"
            for provider, provider_stats in stats['providers'].items():
                stats_text += (
                    f"• <b>{provider.upper()}:</b> "
                    f"{provider_stats['successful']}/{provider_stats['total']} "
                    f"({provider_stats['success_rate']:.1%}) "
                    f"⏱️ {provider_stats['avg_response_time']:.2f}с\n"
                )
        
        # Создаем клавиатуру с кнопкой "Назад"
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_settings")]]
        
        await query.edit_message_text(
            stats_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        logger.info(f"Owner {user_id} accessed bot statistics via callback")
        
    except Exception as e:
        logger.error(f"Error in show_stats_callback: {e}")
        await query.answer("⚠️ Ошибка отображения статистики", show_alert=True)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик всех inline-кнопок"""
    try:
        query = update.callback_query
        await query.answer()

        ai_client = context.bot_data.get("ai_client")
        user_data = context.user_data

        if query.data == "change_model":
            await _show_model_selector(query, ai_client)
        elif query.data.startswith("set_model_"):
            await _handle_model_selection(query, context)
        elif query.data == "change_role":
            await _show_role_selector(query, user_data)
        elif query.data.startswith("set_role_"):
            await _handle_role_selection(query, context)
        elif query.data == "back_to_settings":
            await show_updated_settings(query, context)
        elif query.data == "close_settings":
            await query.delete_message()
        elif query.data == "show_stats":
            await show_stats_callback(query, context)
        else:
            logger.warning(f"Unknown callback data: {query.data}")
            
    except Exception as e:
        logger.error(f"Error in button_handler: {e}")
        if update.callback_query:
            await update.callback_query.answer("⚠️ Ошибка обработки кнопки", show_alert=True)


async def _show_model_selector(query, ai_client):
    """Показывает выбор модели"""
    try:
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{BUTTON_TEXTS['models']['openai']} {'✅' if ai_client.active_provider == 'openai' else ''}",
                    callback_data="set_model_openai"
                )
            ],
            [
                InlineKeyboardButton(
                    f"{BUTTON_TEXTS['models']['deepseek']} {'✅' if ai_client.active_provider == 'deepseek' else ''}",
                    callback_data="set_model_deepseek"
                )
            ],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_settings")]
        ]

        await query.edit_message_text(
            "Выберите модель AI:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Error in _show_model_selector: {e}")


async def _handle_model_selection(query, context):
    """Обрабатывает выбор модели"""
    try:
        model = query.data.split("_")[-1]
        await context.bot_data["ai_client"].set_provider(model)
        await show_updated_settings(query, context)
        await query.answer(f"Модель изменена на {model.upper()}", show_alert=False)
        logger.info(f"User {query.from_user.id} changed model to {model}")
    except Exception as e:
        logger.error(f"Error in _handle_model_selection: {e}")
        await query.answer(f"⚠️ Ошибка смены модели: {str(e)}", show_alert=True)


async def _show_role_selector(query, user_data):
    """Показывает выбор роли"""
    try:
        current_role = user_data.get("role", "assistant")
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{BUTTON_TEXTS['roles']['assistant']} {'✅' if current_role == 'assistant' else ''}",
                    callback_data="set_role_assistant"
                )
            ],
            [
                InlineKeyboardButton(
                    f"{BUTTON_TEXTS['roles']['scientist']} {'✅' if current_role == 'scientist' else ''}",
                    callback_data="set_role_scientist"
                )
            ],
            [
                InlineKeyboardButton(
                    f"{BUTTON_TEXTS['roles']['creative']} {'✅' if current_role == 'creative' else ''}",
                    callback_data="set_role_creative"
                )
            ],
            [
                InlineKeyboardButton(
                    f"{BUTTON_TEXTS['roles']['developer']} {'✅' if current_role == 'developer' else ''}",
                    callback_data="set_role_developer"
                )
            ],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_settings")]
        ]

        await query.edit_message_text(
            "Выберите роль для AI:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Error in _show_role_selector: {e}")


async def _handle_role_selection(query, context):
    """Обрабатывает выбор роли"""
    try:
        role = query.data.split("_")[-1]
        context.user_data["role"] = role
        await show_updated_settings(query, context)
        logger.info(f"User {query.from_user.id} changed role to {role}")
    except Exception as e:
        logger.error(f"Error in _handle_role_selection: {e}")


async def show_updated_settings(query, context):
    """Обновляет сообщение с настройками"""
    try:
        ai_client = context.bot_data.get("ai_client")
        user_data = context.user_data

        current_model = ai_client.active_provider
        current_role = user_data.get("role", "assistant")

        settings_text = (
            "⚙️ <b>Настройки обновлены:</b>\n\n"
            f"🔧 <b>Модель:</b> {BUTTON_TEXTS['models'][current_model]}\n"
            f"🎭 <b>Роль:</b> {BUTTON_TEXTS['roles'][current_role]}\n\n"
            "Выберите что изменить:"
        )

        keyboard = [
            [
                InlineKeyboardButton("🔄 Модель", callback_data="change_model"),
                InlineKeyboardButton("🎭 Роль", callback_data="change_role")
            ]
        ]
        
        # Добавляем кнопку статистики только для владельца
        if is_owner(query.from_user.id, context):
            keyboard.append([InlineKeyboardButton("📊 Статистика", callback_data="show_stats")])
        
        keyboard.append([InlineKeyboardButton("❌ Закрыть", callback_data="close_settings")])

        await query.edit_message_text(
            settings_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error in show_updated_settings: {e}")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовые сообщения"""
    try:
        ai_client = context.bot_data.get("ai_client")
        user_data = context.user_data

        if not ai_client:
            await update.message.reply_text("⚠️ Ошибка инициализации AI клиента")
            return

        # Валидация длины сообщения
        if len(update.message.text) > MAX_MESSAGE_LENGTH:
            await update.message.reply_text(f"⚠️ Сообщение слишком длинное. Максимум {MAX_MESSAGE_LENGTH} символов.")
            return

        role = user_data.get("role", "assistant")
        
        # Отправляем сообщение о том, что обрабатываем запрос
        processing_msg = await update.message.reply_text("🤔 Обрабатываю запрос...")
        
        try:
            answer = await ai_client.process_text(update.message.text, role)
            
            # Разбиваем длинный ответ на части
            if len(answer) > MAX_MESSAGE_LENGTH:
                chunks = [answer[i:i+MAX_MESSAGE_LENGTH] for i in range(0, len(answer), MAX_MESSAGE_LENGTH)]
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await processing_msg.edit_text(chunk)
                    else:
                        await update.message.reply_text(chunk)
            else:
                await processing_msg.edit_text(answer)
                
        except Exception as e:
            logger.error(f"Error processing text: {e}")
            await processing_msg.edit_text("⚠️ Ошибка обработки запроса")
            
    except Exception as e:
        logger.error(f"Error in handle_text: {e}")
        await update.message.reply_text("⚠️ Ошибка обработки текста")


async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает изображения"""
    try:
        ai_client = context.bot_data.get("ai_client")

        if not ai_client:
            await update.message.reply_text("⚠️ Ошибка инициализации AI клиента")
            return

        # Проверяем размер изображения
        photo = update.message.photo[-1]
        if photo.file_size > IMAGE_SIZE_LIMIT_MB:  # 10MB
            await update.message.reply_text("⚠️ Изображение слишком большое. Максимум 10MB.")
            return

        processing_msg = await update.message.reply_text("🖼️ Обрабатываю изображение...")
        
        try:
            photo_file = await photo.get_file()
            photo_bytes = await photo_file.download_as_bytearray()
            user_prompt = update.message.caption

            answer = await ai_client.process_image(photo_bytes, user_prompt)
            
            # Разбиваем длинный ответ на части
            if len(answer) > MAX_MESSAGE_LENGTH:
                chunks = [answer[i:i+MAX_MESSAGE_LENGTH] for i in range(0, len(answer), MAX_MESSAGE_LENGTH)]
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await processing_msg.edit_text(chunk)
                    else:
                        await update.message.reply_text(chunk)
            else:
                await processing_msg.edit_text(answer)
                
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            await processing_msg.edit_text("⚠️ Ошибка обработки изображения")
            
    except Exception as e:
        logger.error(f"Error in handle_image: {e}")
        await update.message.reply_text("⚠️ Ошибка обработки изображения")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Exception while handling an update: {context.error}")
    
    error_msg = "⚠️ Произошла ошибка. Пожалуйста, попробуйте позже."
    if update.callback_query:
        await update.callback_query.answer(error_msg, show_alert=True)
    elif update.message:
        await update.message.reply_text(error_msg)