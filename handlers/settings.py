import logging
from aiogram import Router, F, types, Dispatcher
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from typing import Any, Dict, Callable, Awaitable
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.constants import ROLES, BUTTON_TEXTS
from bot.metrics import metrics


router = Router()
logger = logging.getLogger(__name__)


class WorkflowMiddleware(BaseMiddleware):
    def __init__(self, dispatcher: Dispatcher, **kwargs):
        self.dispatcher = dispatcher
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[types.TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: types.TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if "workflow_data" not in data:
            data["workflow_data"] = self.dispatcher.workflow_data
        try:
            return await handler(event, data)
        except Exception as e:
            logger.error(f"Error in middleware: {e}")
            raise


async def get_owner_manager(data: Dict[str, Any]) -> Any:
    """Get owner manager from workflow data"""
    return data["workflow_data"]["owner_manager"]


async def is_owner(user_id: int, data: Dict[str, Any]) -> bool:
    """Check if user is bot owner"""
    owner_manager = await get_owner_manager(data)
    if owner_manager:
        return owner_manager.is_owner(user_id)
    return False


@router.message(Command("settings"))
async def cmd_settings(message: types.Message, state: FSMContext, **kwargs):
    """Handle /settings command"""
    try:
        ai_client = kwargs["workflow_data"]["ai_client"]
        if not ai_client:
            await message.answer("⚠️ Ошибка инициализации AI клиента")
            return

        current_model = ai_client.active_provider
        data = await state.get_data()
        current_role = data.get("role", "assistant")
        
        settings_text = (
            "⚙️ <b>Текущие настройки:</b>\n\n"
            f"🔧 <b>Модель:</b> {BUTTON_TEXTS['models'][current_model]}\n"
            f"🎭 <b>Роль:</b> {BUTTON_TEXTS['roles'][current_role]}\n\n"
            "Выберите что изменить:"
        )

        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Модель", callback_data="change_model")
        builder.button(text="🎭 Роль", callback_data="change_role")
        builder.adjust(2)

        if await is_owner(message.from_user.id, kwargs):
            builder.row(types.InlineKeyboardButton(
                text="📊 Статистика",
                callback_data="show_stats"
            ))

        builder.row(types.InlineKeyboardButton(
            text="❌ Закрыть",
            callback_data="close_settings"
        ))

        await message.answer(settings_text, reply_markup=builder.as_markup())
    except Exception as e:
        logger.error(f"Error in settings handler: {e}")
        await message.answer("⚠️ Ошибка отображения настроек")


@router.callback_query(F.data == "change_model")
async def change_model(callback: types.CallbackQuery, state: FSMContext, **kwargs):
    """Handle model change request"""
    try:
        ai_client = kwargs["workflow_data"]["ai_client"]
        builder = InlineKeyboardBuilder()
        
        for model in ["openai", "deepseek", "openrouter"]:
            is_active = ai_client.active_provider == model
            builder.button(
                text=f"{BUTTON_TEXTS['models'][model]} {'✅' if is_active else ''}",
                callback_data=f"set_model_{model}"
            )
        
        builder.row(types.InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="back_to_settings"
        ))
        
        await callback.message.edit_text(
            "Выберите модель AI:",
            reply_markup=builder.as_markup()
        )
    except Exception as e:
        logger.error(f"Error in change_model handler: {e}")
        await callback.answer("⚠️ Ошибка при выборе модели", show_alert=True)


@router.callback_query(F.data.startswith("set_model_"))
async def set_model(callback: types.CallbackQuery, state: FSMContext, **kwargs):
    """Handle model selection"""
    try:
        model = callback.data.split("_")[-1]
        ai_client = kwargs["workflow_data"]["ai_client"]
        await ai_client.set_provider(model)
        await show_updated_settings(callback, state, **kwargs)  # Передаем kwargs
        await callback.answer(f"Модель изменена на {model.upper()}")
        logger.info(f"User {callback.from_user.id} changed model to {model}")
    except Exception as e:
        logger.error(f"Error in set_model handler: {e}")
        await callback.answer(f"⚠️ Ошибка смены модели: {str(e)}", show_alert=True)


@router.callback_query(F.data == "change_role")
async def change_role(callback: types.CallbackQuery, state: FSMContext, **kwargs):
    """Handle role change request"""
    try:
        data = await state.get_data()
        current_role = data.get("role", "assistant")
        
        builder = InlineKeyboardBuilder()
        for role in ROLES:
            is_active = current_role == role
            builder.button(
                text=f"{BUTTON_TEXTS['roles'][role]} {'✅' if is_active else ''}",
                callback_data=f"set_role_{role}"
            )
        
        builder.row(types.InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="back_to_settings"
        ))
        
        builder.adjust(1)
        
        await callback.message.edit_text(
            "Выберите роль для AI:",
            reply_markup=builder.as_markup()
        )
    except Exception as e:
        logger.error(f"Error in change_role handler: {e}")
        await callback.answer("⚠️ Ошибка при выборе роли", show_alert=True)


@router.callback_query(F.data.startswith("set_role_"))
async def set_role(callback: types.CallbackQuery, state: FSMContext, **kwargs):
    """Handle role selection"""
    try:
        role = callback.data.split("_")[-1]
        await state.update_data(role=role)
        await show_updated_settings(callback, state, **kwargs)
        logger.info(f"User {callback.from_user.id} changed role to {role}")
    except Exception as e:
        logger.error(f"Error in set_role handler: {e}")
        await callback.answer("⚠️ Ошибка при установке роли", show_alert=True)


@router.callback_query(F.data == "show_stats")
async def show_stats(callback: types.CallbackQuery, state: FSMContext, **kwargs):
    """Handle statistics request"""
    try:
        if not await is_owner(callback.from_user.id, kwargs):
            await callback.answer("🚫 У вас нет доступа к статистике бота", show_alert=True)
            logger.warning(f"User {callback.from_user.id} attempted to access stats without permission")
            return

        stats = metrics.get_stats()
        if not stats:
            await callback.answer("📊 Статистика пока недоступна", show_alert=True)
            return

        stats_text = get_stats_text(stats)
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад", callback_data="back_to_settings")

        await callback.message.edit_text(
            stats_text,
            reply_markup=builder.as_markup()
        )
        logger.info(f"Owner {callback.from_user.id} accessed bot statistics")

    except Exception as e:
        logger.error(f"Error in show_stats: {e}")
        await callback.answer("⚠️ Ошибка отображения статистики", show_alert=True)


def get_stats_text(stats: dict) -> str:
    """Generate statistics text"""
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

    if stats.get('providers'):
        stats_text += "<b>По провайдерам:</b>\n"
        for provider, provider_stats in stats['providers'].items():
            stats_text += (
                f"• <b>{provider.upper()}:</b> "
                f"{provider_stats['successful']}/{provider_stats['total']} "
                f"({provider_stats['success_rate']:.1%}) "
                f"⏱️ {provider_stats['avg_response_time']:.2f}с\n"
            )

    return stats_text


async def show_updated_settings(callback: types.CallbackQuery, state: FSMContext, **kwargs):
    """Show updated settings"""
    try:
        if "workflow_data" not in kwargs:
            logger.error("workflow_data not found in kwargs")
            await callback.answer("⚠️ Ошибка обновления настроек", show_alert=True)
            return
            
        ai_client = kwargs["workflow_data"].get("ai_client")
        if not ai_client:
            logger.error("ai_client not found in workflow_data")
            await callback.answer("⚠️ Ошибка инициализации AI клиента", show_alert=True)
            return

        data = await state.get_data()
        current_model = ai_client.active_provider
        current_role = data.get("role", "assistant")

        settings_text = (
            "⚙️ <b>Настройки обновлены:</b>\n\n"
            f"🔧 <b>Модель:</b> {BUTTON_TEXTS['models'][current_model]}\n"
            f"🎭 <b>Роль:</b> {BUTTON_TEXTS['roles'][current_role]}\n\n"
            "Выберите что изменить:"
        )

        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Модель", callback_data="change_model")
        builder.button(text="🎭 Роль", callback_data="change_role")
        builder.adjust(2)

        if await is_owner(callback.from_user.id, kwargs):
            builder.row(types.InlineKeyboardButton(
                text="📊 Статистика",
                callback_data="show_stats"
            ))

        builder.row(types.InlineKeyboardButton(
            text="❌ Закрыть",
            callback_data="close_settings"
        ))

        await callback.message.edit_text(
            settings_text,
            reply_markup=builder.as_markup()
        )
    except Exception as e:
        logger.error(f"Error in show_updated_settings: {e}")
        await callback.answer("⚠️ Ошибка обновления настроек", show_alert=True)


@router.callback_query(F.data == "back_to_settings")
async def back_to_settings(callback: types.CallbackQuery, state: FSMContext, **kwargs):
    """Handle back to settings request"""
    try:
        await show_updated_settings(callback, state, **kwargs)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in back_to_settings: {e}")
        await callback.answer("⚠️ Ошибка возврата к настройкам", show_alert=True)


@router.callback_query(F.data == "close_settings")
async def close_settings(callback: types.CallbackQuery, state: FSMContext, **kwargs):
    """Handle close settings request"""
    await callback.message.delete()
