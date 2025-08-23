"""
Обработчики для настройки периодичности напоминаний
"""
import logging
from datetime import date, timedelta
from aiogram import F, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.states import ReminderStates
from .reminder_utils import moscow_date, safe_edit_message, parse_date

logger = logging.getLogger(__name__)


async def process_recurrence_type(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор типа периодичности"""
    recurrence = callback.data.replace("recurrence_", "")
    await state.update_data(recurrence_type=recurrence)
    
    if recurrence == "none":
        # Одноразовое напоминание - сразу к подтверждению
        from .confirmation_handlers import show_confirmation
        await show_confirmation(callback, state)
    elif recurrence == "monthly":
        # Для ежемесячных спрашиваем конкретный день
        await ask_for_monthly_day(callback, state)
    else:
        # Для остальных спрашиваем интервал
        await ask_for_interval(callback, state, recurrence)


async def ask_for_monthly_day(callback: types.CallbackQuery, state: FSMContext):
    """Спрашивает день месяца для ежемесячных напоминаний"""
    await state.set_state(ReminderStates.waiting_for_monthly_day)
    
    data = await state.get_data()
    remind_date = data['remind_date']
    
    text = (
        f"✅ Повтор: <b>Ежемесячно</b>\n\n"
        "📅 <b>Выберите день месяца:</b>\n\n"
        "• <b>Тот же день</b> - как в первом напоминании\n"
        "• <b>Конкретный день</b> - например, всегда 5-го числа"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text=f"📅 Тот же день ({remind_date.day}-го)", callback_data="monthly_same_day")
    builder.button(text="🗓 Конкретный день", callback_data="monthly_specific_day")
    builder.button(text="❌ Отмена", callback_data="cancel_reminder")
    builder.adjust(1)
    
    await safe_edit_message(callback, text, reply_markup=builder.as_markup())
    await callback.answer()


async def process_monthly_same_day(callback: types.CallbackQuery, state: FSMContext):
    """Использует тот же день месяца"""
    await state.update_data(monthly_day=None, recurrence_interval=1)
    await ask_for_end_conditions(callback, state)


async def ask_specific_monthly_day(callback: types.CallbackQuery, state: FSMContext):
    """Спрашивает конкретный день месяца"""
    text = (
        "🗓 <b>Введите день месяца (1-31):</b>\n\n"
        "Например:\n"
        "• <b>5</b> - каждое 5-е число\n"
        "• <b>15</b> - каждое 15-е число\n"
        "• <b>1</b> - первое число каждого месяца"
    )
    
    builder = InlineKeyboardBuilder()
    # Популярные дни
    for day in [1, 5, 10, 15, 20, 25]:
        builder.button(text=f"{day}-го", callback_data=f"monthly_day_{day}")
    
    builder.button(text="❌ Отмена", callback_data="cancel_reminder")
    builder.adjust(3, 3, 1)
    
    await safe_edit_message(callback, text, reply_markup=builder.as_markup())
    await callback.answer()


async def process_monthly_day(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор дня месяца"""
    day = int(callback.data.replace("monthly_day_", ""))
    await state.update_data(monthly_day=day, recurrence_interval=1)
    await ask_for_end_conditions(callback, state)


async def ask_for_interval(callback: types.CallbackQuery, state: FSMContext, recurrence_type: str):
    """Спрашивает интервал повторения"""
    await state.set_state(ReminderStates.waiting_for_recurrence_interval)
    
    type_names = {
        'daily': 'Ежедневно',
        'weekly': 'Еженедельно', 
        'yearly': 'Ежегодно'
    }
    
    type_units = {
        'daily': 'дней',
        'weekly': 'недель',
        'yearly': 'лет'
    }
    
    text = (
        f"✅ Повтор: <b>{type_names[recurrence_type]}</b>\n\n"
        f"📊 <b>Укажите интервал повторения:</b>\n\n"
        f"Каждые сколько {type_units[recurrence_type]}?"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="1", callback_data=f"interval_{recurrence_type}_1")
    
    if recurrence_type == 'daily':
        builder.button(text="2", callback_data=f"interval_{recurrence_type}_2")
        builder.button(text="3", callback_data=f"interval_{recurrence_type}_3")
        builder.button(text="7", callback_data=f"interval_{recurrence_type}_7")
    elif recurrence_type == 'weekly':
        builder.button(text="2", callback_data=f"interval_{recurrence_type}_2")
        builder.button(text="4", callback_data=f"interval_{recurrence_type}_4")
    elif recurrence_type == 'yearly':
        builder.button(text="2", callback_data=f"interval_{recurrence_type}_2")
        builder.button(text="5", callback_data=f"interval_{recurrence_type}_5")
    
    builder.button(text="❌ Отмена", callback_data="cancel_reminder")
    builder.adjust(2, 2, 1)
    
    await safe_edit_message(callback, text, reply_markup=builder.as_markup())
    await callback.answer()


async def process_interval(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор интервала"""
    parts = callback.data.split("_")
    recurrence_type = parts[1]
    interval = int(parts[2])
    
    await state.update_data(recurrence_interval=interval)
    await ask_for_end_conditions(callback, state)


async def ask_for_end_conditions(callback: types.CallbackQuery, state: FSMContext):
    """Спрашивает условия окончания повторений"""
    await state.set_state(ReminderStates.waiting_for_end_date)
    
    data = await state.get_data()
    recurrence_type = data.get('recurrence_type', 'none')
    
    if recurrence_type == 'none':
        from .confirmation_handlers import show_confirmation
        await show_confirmation(callback, state)
        return
    
    text = (
        "⏰ <b>Условия окончания повторений:</b>\n\n"
        "Выберите, когда прекратить повторения:"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="♾ Никогда", callback_data="end_never")
    builder.button(text="📅 До даты", callback_data="end_by_date")
    builder.button(text="🔢 Количество раз", callback_data="end_by_count")
    builder.button(text="❌ Отмена", callback_data="cancel_reminder")
    builder.adjust(1)
    
    await safe_edit_message(callback, text, reply_markup=builder.as_markup())
    await callback.answer()


async def process_end_never(callback: types.CallbackQuery, state: FSMContext):
    """Никогда не заканчивать"""
    await state.update_data(end_date=None, max_occurrences=None)
    from .confirmation_handlers import show_confirmation
    await show_confirmation(callback, state)


async def ask_end_date(callback: types.CallbackQuery, state: FSMContext):
    """Спрашивает дату окончания"""
    text = (
        "📅 <b>Введите дату окончания повторений:</b>\n\n"
        "Формат: <b>ДД.ММ.ГГГГ</b> или <b>ДД.ММ</b>\n"
        "Например: <i>31.12.2025</i>"
    )
    
    builder = InlineKeyboardBuilder()
    today = moscow_date()
    
    # Быстрые варианты
    in_month = today + timedelta(days=30)
    in_year = today + timedelta(days=365)
    
    builder.button(text=f"Через месяц ({in_month.strftime('%d.%m')})", 
                  callback_data=f"end_date_{in_month.isoformat()}")
    builder.button(text=f"Через год ({in_year.strftime('%d.%m.%Y')})", 
                  callback_data=f"end_date_{in_year.isoformat()}")
    builder.button(text="❌ Отмена", callback_data="cancel_reminder")
    builder.adjust(1)
    
    await safe_edit_message(callback, text, reply_markup=builder.as_markup())
    await callback.answer()


async def process_end_date_quick(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает быстрый выбор даты окончания"""
    date_str = callback.data.replace("end_date_", "")
    end_date = date.fromisoformat(date_str)
    
    await state.update_data(end_date=end_date, max_occurrences=None)
    from .confirmation_handlers import show_confirmation
    await show_confirmation(callback, state)


async def process_end_date_text(message: types.Message, state: FSMContext):
    """Обрабатывает введенную дату окончания"""
    try:
        end_date = parse_date(message.text.strip())
        
        # Проверяем, что дата в будущем
        if end_date <= moscow_date():
            await message.answer("⚠️ Дата окончания должна быть в будущем.")
            return
        
        await state.update_data(end_date=end_date, max_occurrences=None)
        
        class FakeCallback:
            def __init__(self, message):
                self.message = message
            async def answer(self):
                pass
        
        fake_callback = FakeCallback(message)
        from .confirmation_handlers import show_confirmation
        await show_confirmation(fake_callback, state, is_new_message=True)
        
    except ValueError as e:
        await message.answer(f"⚠️ Неверный формат даты. {str(e)}")


async def ask_max_occurrences(callback: types.CallbackQuery, state: FSMContext):
    """Спрашивает максимальное количество повторений"""
    await state.set_state(ReminderStates.waiting_for_max_occurrences)
    
    text = (
        "🔢 <b>Сколько раз повторить напоминание?</b>\n\n"
        "Введите число от 1 до 365:"
    )
    
    builder = InlineKeyboardBuilder()
    # Популярные варианты
    for count in [5, 10, 20, 30, 50, 100]:
        builder.button(text=f"{count} раз", callback_data=f"max_count_{count}")
    
    builder.button(text="❌ Отмена", callback_data="cancel_reminder")
    builder.adjust(3, 3, 1)
    
    await safe_edit_message(callback, text, reply_markup=builder.as_markup())
    await callback.answer()


async def process_max_count_quick(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает быстрый выбор количества"""
    count = int(callback.data.replace("max_count_", ""))
    await state.update_data(max_occurrences=count, end_date=None)
    from .confirmation_handlers import show_confirmation
    await show_confirmation(callback, state)


async def process_max_occurrences_text(message: types.Message, state: FSMContext):
    """Обрабатывает введенное количество повторений"""
    try:
        count = int(message.text.strip())
        
        if count < 1 or count > 365:
            await message.answer("⚠️ Количество должно быть от 1 до 365.")
            return
        
        await state.update_data(max_occurrences=count, end_date=None)
        
        class FakeCallback:
            def __init__(self, message):
                self.message = message
            async def answer(self):
                pass
        
        fake_callback = FakeCallback(message)
        from .confirmation_handlers import show_confirmation
        await show_confirmation(fake_callback, state, is_new_message=True)
        
    except ValueError:
        await message.answer("⚠️ Введите корректное число.")
