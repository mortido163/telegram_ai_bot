"""
Обработчики для подтверждения и создания напоминаний
"""
import logging
from datetime import date
from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.states import ReminderStates
from .reminder_utils import (
    moscow_datetime, safe_edit_message, get_reminder_manager, 
    get_recurrence_description
)

logger = logging.getLogger(__name__)


async def show_confirmation(callback, state: FSMContext, is_new_message: bool = False):
    """Показывает подтверждение создания напоминания"""
    await state.set_state(ReminderStates.confirmation)
    
    data = await state.get_data()
    remind_datetime = moscow_datetime(data['remind_date'], data['remind_time'])
    reminder_type = data.get('reminder_type', 'simple')
    recurrence_type = data.get('recurrence_type', 'none')
    
    # Формируем описание периодичности
    recurrence_desc = get_recurrence_description(data)
    
    if reminder_type == 'simple':
        text = (
            "✅ <b>Подтверждение создания напоминания</b>\n\n"
            f"📌 <b>Название:</b> {data['title']}\n"
            f"📝 <b>Описание:</b> {data.get('description', 'Не указано')}\n"
            f"📅 <b>Дата:</b> {data['remind_date'].strftime('%d.%m.%Y')}\n"
            f"🕐 <b>Время:</b> {data['remind_time'].strftime('%H:%M')}\n"
            f"🔄 <b>Повтор:</b> {recurrence_desc}\n\n"
        )
        
        if recurrence_type == 'none':
            text += f"⏰ <b>Напоминание будет отправлено:</b>\n{remind_datetime.strftime('%d.%m.%Y в %H:%M')}\n\n"
        else:
            text += f"⏰ <b>Первое напоминание:</b>\n{remind_datetime.strftime('%d.%m.%Y в %H:%M')}\n\n"
            
        text += "Создать напоминание?"
        
    else:
        role_names = {
            'assistant': '👨‍💻 Ассистент',
            'scientist': '🔬 Ученый',
            'creative': '🎨 Креатив',
            'developer': '💻 Разработчик'
        }
        ai_role = data.get('ai_role', 'assistant')
        
        text = (
            "🤖 <b>Подтверждение создания AI-напоминания</b>\n\n"
            f"📌 <b>Название:</b> {data['title']}\n"
            f"🤖 <b>AI-запрос:</b> {data.get('ai_prompt', 'Не указан')}\n"
            f"👤 <b>Роль:</b> {role_names.get(ai_role, ai_role)}\n"
            f"📅 <b>Дата:</b> {data['remind_date'].strftime('%d.%m.%Y')}\n"
            f"🕐 <b>Время:</b> {data['remind_time'].strftime('%H:%M')}\n"
            f"🔄 <b>Повтор:</b> {recurrence_desc}\n\n"
        )
        
        if recurrence_type == 'none':
            text += f"⏰ <b>AI-запрос будет выполнен:</b>\n{remind_datetime.strftime('%d.%m.%Y в %H:%M')}\n\n"
        else:
            text += f"⏰ <b>Первый AI-запрос:</b>\n{remind_datetime.strftime('%d.%m.%Y в %H:%M')}\n\n"
            
        text += "Создать AI-напоминание?"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Создать", callback_data="confirm_reminder")
    builder.button(text="✏️ Редактировать", callback_data="edit_reminder_data")
    builder.button(text="❌ Отмена", callback_data="cancel_reminder")
    builder.adjust(1)
    
    if is_new_message:
        await callback.message.answer(text, reply_markup=builder.as_markup())
    else:
        await safe_edit_message(callback, text, reply_markup=builder.as_markup())
        await callback.answer()


async def confirm_reminder_creation(callback: types.CallbackQuery, state: FSMContext, **kwargs):
    """Подтверждает создание напоминания"""
    data = await state.get_data()
    reminder_manager = await get_reminder_manager(kwargs)
    reminder_type = data.get('reminder_type', 'simple')
    
    try:
        from bot.reminders import ReminderType, RecurrenceType
        
        # Подготавливаем параметры периодичности
        recurrence_type = RecurrenceType(data.get('recurrence_type', 'none'))
        recurrence_interval = data.get('recurrence_interval', 1)
        monthly_day = data.get('monthly_day')
        end_date = data.get('end_date')
        max_occurrences = data.get('max_occurrences')
        
        # Конвертируем end_date если это строка
        if isinstance(end_date, str):
            end_date = date.fromisoformat(end_date)
        
        if reminder_type == 'simple':
            reminder_id = await reminder_manager.create_reminder(
                user_id=callback.from_user.id,
                title=data['title'],
                description=data.get('description', ''),
                remind_date=data['remind_date'],
                remind_time=data['remind_time'],
                reminder_type=ReminderType.SIMPLE,
                recurrence_type=recurrence_type,
                recurrence_interval=recurrence_interval,
                monthly_day=monthly_day,
                end_date=end_date,
                max_occurrences=max_occurrences
            )
            
            recurrence_desc = get_recurrence_description(data)
            
            text = (
                "🎉 <b>Напоминание создано!</b>\n\n"
                f"📌 {data['title']}\n"
                f"⏰ {data['remind_date'].strftime('%d.%m.%Y')} в {data['remind_time'].strftime('%H:%M')}\n"
                f"🔄 {recurrence_desc}\n\n"
            )
            
            if recurrence_type == RecurrenceType.NONE:
                text += "Я обязательно напомню вам в указанное время!"
            else:
                text += "Я буду напоминать вам согласно выбранной периодичности!"
                
        else:
            reminder_id = await reminder_manager.create_reminder(
                user_id=callback.from_user.id,
                title=data['title'],
                description='',  # Для AI-напоминаний описание не используется
                remind_date=data['remind_date'],
                remind_time=data['remind_time'],
                reminder_type=ReminderType.AI_QUERY,
                ai_prompt=data.get('ai_prompt', ''),
                ai_role=data.get('ai_role', 'assistant'),
                recurrence_type=recurrence_type,
                recurrence_interval=recurrence_interval,
                monthly_day=monthly_day,
                end_date=end_date,
                max_occurrences=max_occurrences
            )
            
            recurrence_desc = get_recurrence_description(data)
            
            text = (
                "🤖 <b>AI-напоминание создано!</b>\n\n"
                f"📌 {data['title']}\n"
                f"🤖 AI-запрос: {data.get('ai_prompt', '')}\n"
                f"⏰ {data['remind_date'].strftime('%d.%m.%Y')} в {data['remind_time'].strftime('%H:%M')}\n"
                f"🔄 {recurrence_desc}\n\n"
            )
            
            if recurrence_type == RecurrenceType.NONE:
                text += "Я выполню AI-запрос и отправлю результат в указанное время!"
            else:
                text += "Я буду выполнять AI-запрос согласно выбранной периодичности!"
        
        builder = InlineKeyboardBuilder()
        builder.button(text="📋 Мои напоминания", callback_data="list_reminders")
        builder.button(text="➕ Создать еще", callback_data="create_reminder")
        builder.button(text="❌ Закрыть", callback_data="close_reminders")
        builder.adjust(1)
        
        await safe_edit_message(callback, text, reply_markup=builder.as_markup())
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error creating reminder: {e}")
        await callback.answer("⚠️ Ошибка при создании напоминания", show_alert=True)


async def cancel_reminder_creation(callback: types.CallbackQuery, state: FSMContext):
    """Отменяет создание напоминания"""
    await state.clear()
    
    text = "❌ Создание напоминания отменено."
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔔 Главное меню", callback_data="reminders_menu")
    builder.button(text="❌ Закрыть", callback_data="close_reminders")
    builder.adjust(1)
    
    await safe_edit_message(callback, text, reply_markup=builder.as_markup())
    await callback.answer()
