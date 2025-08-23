"""
Модуль для создания напоминаний - весь пошаговый процесс создания
"""
import logging
from datetime import datetime, date, time, timedelta
from aiogram import Router, F, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.states import ReminderStates
from .reminder_utils import (
    moscow_now, moscow_date, moscow_datetime, safe_edit_message, 
    get_reminder_manager, parse_date, parse_time, get_recurrence_description
)

logger = logging.getLogger(__name__)
creation_router = Router()


@creation_router.callback_query(F.data == "create_reminder")
async def start_reminder_creation(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс создания напоминания"""
    await state.set_state(ReminderStates.waiting_for_type)
    
    text = (
        "📝 <b>Создание напоминания</b>\n\n"
        "Шаг 1/6: Выберите тип напоминания"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Обычное", callback_data="reminder_type_simple")
    builder.button(text="🤖 AI-запрос", callback_data="reminder_type_ai")
    builder.button(text="❌ Отмена", callback_data="cancel_reminder")
    builder.adjust(2, 1)
    
    await safe_edit_message(callback, text, reply_markup=builder.as_markup())
    await callback.answer()


@creation_router.callback_query(F.data.in_(["reminder_type_simple", "reminder_type_ai"]))
async def select_reminder_type(callback: types.CallbackQuery, state: FSMContext):
    """Выбор типа напоминания"""
    reminder_type = "simple" if callback.data == "reminder_type_simple" else "ai_query"
    await state.update_data(reminder_type=reminder_type)
    await state.set_state(ReminderStates.waiting_for_title)
    
    if reminder_type == "simple":
        text = (
            "📝 <b>Обычное напоминание</b>\n\n"
            "Шаг 2/6: Введите название напоминания\n\n"
            "Например: <i>Оплатить коммуналку</i>"
        )
    else:
        text = (
            "🤖 <b>AI-напоминание</b>\n\n"
            "Шаг 2/6: Введите название напоминания\n\n"
            "Например: <i>Проверить курс биткоина</i>"
        )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="cancel_reminder")
    
    await safe_edit_message(callback, text, reply_markup=builder.as_markup())
    await callback.answer()


@creation_router.message(StateFilter(ReminderStates.waiting_for_title))
async def process_reminder_title(message: types.Message, state: FSMContext):
    """Обрабатывает название напоминания"""
    title = message.text.strip()
    
    if len(title) > 100:
        await message.answer("⚠️ Название слишком длинное. Максимум 100 символов.")
        return
    
    await state.update_data(title=title)
    
    # Получаем тип напоминания
    data = await state.get_data()
    reminder_type = data.get('reminder_type', 'simple')
    
    if reminder_type == 'simple':
        await state.set_state(ReminderStates.waiting_for_description)
        text = (
            f"✅ Название: <b>{title}</b>\n\n"
            "📝 <b>Обычное напоминание</b>\n\n"
            "Шаг 3/6: Введите описание напоминания\n\n"
            "Например: <i>Оплатить до 10 числа, сумма около 5000 рублей</i>"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="⏭ Пропустить", callback_data="skip_description")
        builder.button(text="❌ Отмена", callback_data="cancel_reminder")
        builder.adjust(1)
    else:
        await state.set_state(ReminderStates.waiting_for_ai_prompt)
        text = (
            f"✅ Название: <b>{title}</b>\n\n"
            "🤖 <b>AI-напоминание</b>\n\n"
            "Шаг 3/6: Введите AI-запрос\n\n"
            "Например: <i>Какой сейчас курс биткоина к доллару?</i>"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="❌ Отмена", callback_data="cancel_reminder")
    
    await message.answer(text, reply_markup=builder.as_markup())


@creation_router.message(StateFilter(ReminderStates.waiting_for_ai_prompt))
async def process_ai_prompt(message: types.Message, state: FSMContext):
    """Обрабатывает AI-промпт"""
    ai_prompt = message.text.strip()
    
    if len(ai_prompt) > 1000:
        await message.answer("⚠️ AI-запрос слишком длинный. Максимум 1000 символов.")
        return
    
    await state.update_data(ai_prompt=ai_prompt)
    await state.set_state(ReminderStates.waiting_for_ai_role)
    
    data = await state.get_data()
    title = data.get('title', '')
    
    text = (
        f"✅ Название: <b>{title}</b>\n"
        f"✅ AI-запрос: <i>{ai_prompt}</i>\n\n"
        "🤖 <b>AI-напоминание</b>\n\n"
        "Шаг 4/6: Выберите роль для AI"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="👨‍💻 Ассистент", callback_data="ai_role_assistant")
    builder.button(text="🔬 Ученый", callback_data="ai_role_scientist")
    builder.button(text="🎨 Креатив", callback_data="ai_role_creative")
    builder.button(text="💻 Разработчик", callback_data="ai_role_developer")
    builder.button(text="❌ Отмена", callback_data="cancel_reminder")
    builder.adjust(2, 2, 1)
    
    await message.answer(text, reply_markup=builder.as_markup())


@creation_router.callback_query(F.data.startswith("ai_role_"))
async def select_ai_role(callback: types.CallbackQuery, state: FSMContext):
    """Выбор роли для AI"""
    role = callback.data.replace("ai_role_", "")
    await state.update_data(ai_role=role)
    
    # Переходим к выбору даты
    await ask_for_date_ai(callback, state)


async def ask_for_date_ai(callback: types.CallbackQuery, state: FSMContext):
    """Запрашивает дату для AI-напоминания"""
    await state.set_state(ReminderStates.waiting_for_date)
    
    data = await state.get_data()
    title = data.get('title', '')
    ai_prompt = data.get('ai_prompt', '')
    ai_role = data.get('ai_role', 'assistant')
    
    role_names = {
        'assistant': '👨‍💻 Ассистент',
        'scientist': '🔬 Ученый',
        'creative': '🎨 Креатив',
        'developer': '💻 Разработчик'
    }
    
    text = (
        f"✅ Название: <b>{title}</b>\n"
        f"✅ AI-запрос: <i>{ai_prompt}</i>\n"
        f"✅ Роль: {role_names.get(ai_role, ai_role)}\n\n"
        "🤖 <b>AI-напоминание</b>\n\n"
        "Шаг 5/6: Введите дату напоминания\n\n"
        "Формат: <b>ДД.ММ.ГГГГ</b> или <b>ДД.ММ</b>\n"
        "Например: <i>15.03.2024</i> или <i>15.03</i> (текущий год)"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="cancel_reminder")
    
    await safe_edit_message(callback, text, reply_markup=builder.as_markup())
    await callback.answer()


@creation_router.callback_query(F.data == "skip_description")
async def skip_description(callback: types.CallbackQuery, state: FSMContext):
    """Пропускает описание"""
    await state.update_data(description="")
    await ask_for_date(callback, state)


@creation_router.message(StateFilter(ReminderStates.waiting_for_description))
async def process_reminder_description(message: types.Message, state: FSMContext):
    """Обрабатывает описание напоминания"""
    description = message.text.strip()
    
    if len(description) > 500:
        await message.answer("⚠️ Описание слишком длинное. Максимум 500 символов.")
        return
    
    await state.update_data(description=description)
    
    # Создаем callback как объект для передачи в ask_for_date
    class FakeCallback:
        def __init__(self, message):
            self.message = message
        async def answer(self):
            pass
    
    fake_callback = FakeCallback(message)
    await ask_for_date(fake_callback, state, is_new_message=True)


async def ask_for_date(callback, state: FSMContext, is_new_message: bool = False):
    """Просит ввести дату"""
    await state.set_state(ReminderStates.waiting_for_date)
    
    data = await state.get_data()
    
    text = (
        f"✅ Название: <b>{data['title']}</b>\n"
        f"✅ Описание: <i>{data.get('description', 'Не указано')}</i>\n\n"
        "📅 <b>Создание напоминания</b>\n\n"
        "Шаг 4/6: Введите дату напоминания\n\n"
        "Формат: <b>ДД.ММ.ГГГГ</b> или <b>ДД.ММ</b>\n"
        "Например: <i>01.09.2025</i> или <i>01.09</i>"
    )
    
    # Быстрые кнопки для популярных дат
    builder = InlineKeyboardBuilder()
    today = moscow_date()
    
    # Завтра
    tomorrow = today + timedelta(days=1)
    builder.button(text=f"Завтра ({tomorrow.strftime('%d.%m')})", 
                  callback_data=f"quick_date_{tomorrow.isoformat()}")
    
    # Через неделю
    week_later = today + timedelta(days=7)
    builder.button(text=f"Через неделю ({week_later.strftime('%d.%m')})", 
                  callback_data=f"quick_date_{week_later.isoformat()}")
    
    # Первое число следующего месяца
    if today.month == 12:
        next_month_first = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month_first = today.replace(month=today.month + 1, day=1)
    
    builder.button(text=f"1 число ({next_month_first.strftime('%d.%m')})", 
                  callback_data=f"quick_date_{next_month_first.isoformat()}")
    
    builder.button(text="❌ Отмена", callback_data="cancel_reminder")
    builder.adjust(1)
    
    if is_new_message:
        await callback.message.answer(text, reply_markup=builder.as_markup())
    else:
        await safe_edit_message(callback, text, reply_markup=builder.as_markup())
        await callback.answer()


@creation_router.callback_query(F.data.startswith("quick_date_"))
async def process_quick_date(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает быстрый выбор даты"""
    date_str = callback.data.split("_", 2)[2]
    remind_date = date.fromisoformat(date_str)
    
    await state.update_data(remind_date=remind_date)
    await ask_for_time(callback, state)


@creation_router.message(StateFilter(ReminderStates.waiting_for_date))
async def process_reminder_date(message: types.Message, state: FSMContext):
    """Обрабатывает дату напоминания"""
    date_text = message.text.strip()
    
    try:
        # Парсим дату
        remind_date = parse_date(date_text)
        
        # Проверяем, что дата не в прошлом
        if remind_date < moscow_date():
            await message.answer("⚠️ Дата не может быть в прошлом.")
            return
        
        await state.update_data(remind_date=remind_date)
        
        # Создаем fake callback для ask_for_time
        class FakeCallback:
            def __init__(self, message):
                self.message = message
            async def answer(self):
                pass
        
        fake_callback = FakeCallback(message)
        await ask_for_time(fake_callback, state, is_new_message=True)
        
    except ValueError as e:
        await message.answer(f"⚠️ Неверный формат даты. {str(e)}")


async def ask_for_time(callback, state: FSMContext, is_new_message: bool = False):
    """Просит ввести время"""
    await state.set_state(ReminderStates.waiting_for_time)
    
    data = await state.get_data()
    remind_date = data['remind_date']
    
    text = (
        f"✅ Название: <b>{data['title']}</b>\n"
        f"✅ Описание: <i>{data.get('description', 'Не указано')}</i>\n"
        f"✅ Дата: <b>{remind_date.strftime('%d.%m.%Y')}</b>\n\n"
        "🕐 <b>Создание напоминания</b>\n\n"
        "Шаг 5/6: Введите время напоминания\n\n"
        "Формат: <b>ЧЧ:ММ</b>\n"
        "Например: <i>09:00</i> или <i>18:30</i>"
    )
    
    # Быстрые кнопки для популярного времени
    builder = InlineKeyboardBuilder()
    common_times = ["09:00", "12:00", "15:00", "18:00", "20:00"]
    
    for time_str in common_times:
        builder.button(text=time_str, callback_data=f"quick_time_{time_str}")
    
    builder.button(text="❌ Отмена", callback_data="cancel_reminder")
    builder.adjust(3, 2, 1)
    
    if is_new_message:
        await callback.message.answer(text, reply_markup=builder.as_markup())
    else:
        await safe_edit_message(callback, text, reply_markup=builder.as_markup())
        await callback.answer()


@creation_router.callback_query(F.data.startswith("quick_time_"))
async def process_quick_time(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает быстрый выбор времени"""
    time_str = callback.data.split("_", 2)[2]
    remind_time = time.fromisoformat(time_str)
    
    await state.update_data(remind_time=remind_time)
    await ask_for_recurrence(callback, state)


@creation_router.message(StateFilter(ReminderStates.waiting_for_time))
async def process_reminder_time(message: types.Message, state: FSMContext):
    """Обрабатывает время напоминания"""
    time_text = message.text.strip()
    
    try:
        # Парсим время
        remind_time = parse_time(time_text)
        await state.update_data(remind_time=remind_time)
        
        # Создаем fake callback для show_confirmation
        class FakeCallback:
            def __init__(self, message):
                self.message = message
            async def answer(self):
                pass
        
        fake_callback = FakeCallback(message)
        await ask_for_recurrence(fake_callback, state, is_new_message=True)
        
    except ValueError as e:
        await message.answer(f"⚠️ Неверный формат времени. {str(e)}")


async def ask_for_recurrence(callback, state: FSMContext, is_new_message: bool = False):
    """Просит выбрать тип периодичности"""
    await state.set_state(ReminderStates.waiting_for_recurrence)
    
    data = await state.get_data()
    
    text = (
        f"✅ Название: <b>{data['title']}</b>\n"
        f"✅ Дата: <b>{data['remind_date'].strftime('%d.%m.%Y')}</b>\n"
        f"✅ Время: <b>{data['remind_time'].strftime('%H:%M')}</b>\n\n"
        "🔄 <b>Создание напоминания</b>\n\n"
        "Шаг 6/6: Выберите тип повторения"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🚫 Одноразово", callback_data="recurrence_none")
    builder.button(text="📅 Ежедневно", callback_data="recurrence_daily")
    builder.button(text="📆 Еженедельно", callback_data="recurrence_weekly")
    builder.button(text="🗓 Ежемесячно", callback_data="recurrence_monthly")
    builder.button(text="🎂 Ежегодно", callback_data="recurrence_yearly")
    builder.button(text="❌ Отмена", callback_data="cancel_reminder")
    builder.adjust(1)
    
    if is_new_message:
        await callback.message.answer(text, reply_markup=builder.as_markup())
    else:
        await safe_edit_message(callback, text, reply_markup=builder.as_markup())
        await callback.answer()


# Импортируем функции из других модулей будут подключены в основном роутере
