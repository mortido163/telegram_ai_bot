"""
Утилиты для работы с напоминаниями - общие функции, парсинг дат и времени
"""
import logging
from datetime import datetime, date, time, timezone, timedelta
from aiogram import types
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram import Dispatcher
from typing import Any, Dict, Callable, Awaitable
from aiogram.types import TelegramObject
from bot.reminders import ReminderManager

logger = logging.getLogger(__name__)

# Московский часовой пояс (UTC+3)
MOSCOW_TZ = timezone(timedelta(hours=3))

def moscow_now() -> datetime:
    """Возвращает текущее время в московском часовом поясе"""
    return datetime.now(MOSCOW_TZ)

def moscow_date() -> date:
    """Возвращает текущую дату в московском часовом поясе"""
    return moscow_now().date()

def moscow_time() -> time:
    """Возвращает текущее время в московском часовом поясе"""
    return moscow_now().time()

def moscow_datetime(date_obj: date, time_obj: time) -> datetime:
    """Создает datetime с московским часовым поясом из объектов date и time"""
    naive_dt = datetime.combine(date_obj, time_obj)
    return naive_dt.replace(tzinfo=MOSCOW_TZ)


async def safe_edit_message(callback: types.CallbackQuery, text: str, reply_markup=None):
    """Безопасное редактирование сообщения с обработкой частых ошибок Telegram API"""
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception as e:
        error_message = str(e)
        if "message is not modified" in error_message:
            # Сообщение не изменилось, просто отвечаем на callback без логирования
            await callback.answer()
        elif "query is too old" in error_message or "query ID is invalid" in error_message:
            # Устаревший callback query, игнорируем
            pass
        elif "Bad Request" in error_message and "timeout" in error_message:
            # Таймаут, попробуем хотя бы ответить на callback
            try:
                await callback.answer()
            except:
                pass
        else:
            # Другая ошибка - пробрасываем дальше
            raise


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
                    logger.error(f"Error in reminders middleware for {event_type} (update_id: {event.update_id}): {e}")
                else:
                    logger.error(f"Error in reminders middleware for {event_type}: {e}")
            raise


async def get_reminder_manager(kwargs) -> ReminderManager:
    """Получает менеджер напоминаний из workflow_data"""
    return kwargs["workflow_data"]["reminder_manager"]


def parse_date(date_text: str) -> date:
    """Парсит дату из строки"""
    date_text = date_text.replace(" ", "").replace("/", ".").replace("-", ".")
    
    today = moscow_date()
    
    try:
        if "." in date_text:
            parts = date_text.split(".")
            
            if len(parts) == 2:  # ДД.ММ
                day, month = int(parts[0]), int(parts[1])
                year = today.year
                
                # Если дата уже прошла в этом году, используем следующий год
                test_date = date(year, month, day)
                if test_date < today:
                    year += 1
                
                return date(year, month, day)
                
            elif len(parts) == 3:  # ДД.ММ.ГГГГ
                day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                
                # Поддержка короткого формата года
                if year < 100:
                    if year < 50:
                        year += 2000
                    else:
                        year += 1900
                
                return date(year, month, day)
        
        # Пытаемся парсить как число (день текущего месяца)
        day = int(date_text)
        month = today.month
        year = today.year
        
        # Если день уже прошел в текущем месяце, используем следующий месяц
        test_date = date(year, month, day)
        if test_date < today:
            if month == 12:
                month = 1
                year += 1
            else:
                month += 1
        
        return date(year, month, day)
        
    except (ValueError, IndexError):
        raise ValueError("Используйте формат ДД.ММ.ГГГГ или ДД.ММ")


def parse_time(time_text: str) -> time:
    """Парсит время из строки"""
    time_text = time_text.replace(" ", "").replace(".", ":").replace("-", ":")
    
    try:
        if ":" in time_text:
            parts = time_text.split(":")
            hour, minute = int(parts[0]), int(parts[1])
        else:
            # Если только час
            hour = int(time_text)
            minute = 0
        
        if hour < 0 or hour > 23:
            raise ValueError("Час должен быть от 0 до 23")
        if minute < 0 or minute > 59:
            raise ValueError("Минуты должны быть от 0 до 59")
        
        return time(hour, minute)
        
    except (ValueError, IndexError):
        raise ValueError("Используйте формат ЧЧ:ММ")


def get_recurrence_description(data: dict) -> str:
    """Возвращает описание периодичности на основе данных состояния"""
    recurrence_type = data.get('recurrence_type', 'none')
    
    if recurrence_type == 'none':
        return "Одноразово"
    
    interval = data.get('recurrence_interval', 1)
    base_desc = ""
    
    if recurrence_type == 'daily':
        if interval == 1:
            base_desc = "Ежедневно"
        else:
            base_desc = f"Каждые {interval} дня"
    elif recurrence_type == 'weekly':
        if interval == 1:
            base_desc = "Еженедельно"
        else:
            base_desc = f"Каждые {interval} недели"
    elif recurrence_type == 'monthly':
        monthly_day = data.get('monthly_day')
        if monthly_day:
            if interval == 1:
                base_desc = f"Ежемесячно {monthly_day}-го числа"
            else:
                base_desc = f"Каждые {interval} месяца {monthly_day}-го числа"
        else:
            if interval == 1:
                base_desc = "Ежемесячно в тот же день"
            else:
                base_desc = f"Каждые {interval} месяца в тот же день"
    elif recurrence_type == 'yearly':
        if interval == 1:
            base_desc = "Ежегодно"
        else:
            base_desc = f"Каждые {interval} года"
    else:
        base_desc = "Неизвестный тип"
    
    # Добавляем информацию об окончании
    end_info = ""
    if data.get('max_occurrences'):
        end_info = f" (макс. {data['max_occurrences']} раз)"
    elif data.get('end_date'):
        end_date = data['end_date']
        if isinstance(end_date, str):
            end_date = date.fromisoformat(end_date)
        end_info = f" (до {end_date.strftime('%d.%m.%Y')})"
    
    return f"{base_desc}{end_info}"


def get_base_description(recurrence_type: str, interval: int, data: dict) -> str:
    """Базовое описание без условий окончания"""
    if recurrence_type == 'daily':
        return "Ежедневно" if interval == 1 else f"Каждые {interval} дня"
    elif recurrence_type == 'weekly':
        return "Еженедельно" if interval == 1 else f"Каждые {interval} недели"
    elif recurrence_type == 'monthly':
        monthly_day = data.get('monthly_day')
        base = f"Ежемесячно" if interval == 1 else f"Каждые {interval} месяца"
        if monthly_day:
            base += f" {monthly_day}-го числа"
        return base
    elif recurrence_type == 'yearly':
        return "Ежегодно" if interval == 1 else f"Каждые {interval} года"
    return "Одноразово"
