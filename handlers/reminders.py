"""
Основной модуль обработчиков напоминаний
Объединяет все подмодули и предоставляет единую точку входа
"""
import logging
from aiogram import Router, F, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.states import ReminderStates
from .reminder_utils import WorkflowMiddleware, safe_edit_message
from .reminder_creation import creation_router
from .reminder_management import management_router
from .recurrence_handlers import (
    process_recurrence_type, ask_for_monthly_day, process_monthly_same_day,
    ask_specific_monthly_day, process_monthly_day, ask_for_interval,
    process_interval, ask_for_end_conditions, process_end_never,
    ask_end_date, process_end_date_quick, process_end_date_text,
    ask_max_occurrences, process_max_count_quick, process_max_occurrences_text
)
from .confirmation_handlers import (
    show_confirmation, confirm_reminder_creation, cancel_reminder_creation
)

logger = logging.getLogger(__name__)

# Создаем основной роутер
router = Router()

# Подключаем дочерние роутеры
router.include_router(creation_router)
router.include_router(management_router)

# Регистрируем обработчики периодичности
router.callback_query.register(process_recurrence_type, F.data.startswith("recurrence_"))
router.callback_query.register(process_monthly_same_day, F.data == "monthly_same_day")
router.callback_query.register(ask_specific_monthly_day, F.data == "monthly_specific_day")
router.callback_query.register(process_monthly_day, F.data.startswith("monthly_day_"))
router.callback_query.register(process_interval, F.data.startswith("interval_"))
router.callback_query.register(process_end_never, F.data == "end_never")
router.callback_query.register(ask_end_date, F.data == "end_by_date")
router.callback_query.register(process_end_date_quick, F.data.startswith("end_date_"))
router.message.register(process_end_date_text, StateFilter(ReminderStates.waiting_for_end_date))
router.callback_query.register(ask_max_occurrences, F.data == "end_by_count")
router.callback_query.register(process_max_count_quick, F.data.startswith("max_count_"))
router.message.register(process_max_occurrences_text, StateFilter(ReminderStates.waiting_for_max_occurrences))

# Регистрируем обработчики подтверждения
router.callback_query.register(confirm_reminder_creation, F.data == "confirm_reminder")
router.callback_query.register(cancel_reminder_creation, F.data == "cancel_reminder")


@router.message(Command("reminders"))
async def cmd_reminders(message: types.Message, state: FSMContext, **kwargs):
    """Команда /reminders - главное меню напоминаний"""
    await state.clear()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Создать напоминание", callback_data="create_reminder")
    builder.button(text="📋 Мои напоминания", callback_data="list_reminders")
    builder.button(text="⚙️ Настройки", callback_data="reminder_settings")
    builder.button(text="❌ Закрыть", callback_data="close_reminders")
    builder.adjust(1)
    
    text = (
        "🔔 <b>Управление напоминаниями</b>\n\n"
        "Выберите действие:"
    )
    
    await message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(F.data == "reminders_menu")
async def show_reminders_menu(callback: types.CallbackQuery, state: FSMContext):
    """Показывает главное меню напоминаний"""
    await state.clear()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Создать напоминание", callback_data="create_reminder")
    builder.button(text="📋 Мои напоминания", callback_data="list_reminders")
    builder.button(text="⚙️ Настройки", callback_data="reminder_settings")
    builder.button(text="❌ Закрыть", callback_data="close_reminders")
    builder.adjust(1)
    
    text = (
        "🔔 <b>Управление напоминаниями</b>\n\n"
        "Выберите действие:"
    )
    
    await safe_edit_message(callback, text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "reminder_settings")
async def show_reminder_settings(callback: types.CallbackQuery):
    """Показывает настройки напоминаний"""
    text = (
        "⚙️ <b>Настройки напоминаний</b>\n\n"
        "🔔 <b>Текущие настройки:</b>\n"
        "• Уведомления: Включены\n"
        "• Часовой пояс: UTC+3 (Москва)\n"
        "• Максимум напоминаний: 100\n\n"
        "💡 <b>Возможности:</b>\n"
        "• 📝 Обычные напоминания\n"
        "• 🤖 AI-запросы по расписанию\n"
        "• 📅 Гибкая настройка даты и времени\n"
        "• ✏️ Редактирование до отправки\n"
        "• 🗑 Удаление ненужных напоминаний\n"
        "• 🔄 Периодические напоминания"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="reminders_menu")
    builder.button(text="❌ Закрыть", callback_data="close_reminders")
    builder.adjust(1)
    
    await safe_edit_message(callback, text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "close_reminders")
async def close_reminders(callback: types.CallbackQuery, state: FSMContext):
    """Закрывает интерфейс напоминаний"""
    await state.clear()
    await callback.message.delete()
