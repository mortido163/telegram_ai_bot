from aiogram.fsm.state import State, StatesGroup


class ReminderStates(StatesGroup):
    """Состояния для создания напоминания"""
    waiting_for_type = State()
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_date = State()
    waiting_for_time = State()
    # Для AI-напоминаний
    waiting_for_ai_prompt = State()
    waiting_for_ai_role = State()
    # Для периодических напоминаний
    waiting_for_recurrence = State()
    waiting_for_recurrence_interval = State()
    waiting_for_monthly_day = State()
    waiting_for_end_date = State()
    waiting_for_max_occurrences = State()
    confirmation = State()


class EditReminderStates(StatesGroup):
    """Состояния для редактирования напоминания"""
    choosing_field = State()
    editing_title = State()
    editing_description = State()
    editing_date = State()
    editing_time = State()
    editing_ai_prompt = State()
    editing_ai_role = State()
    confirmation = State()
