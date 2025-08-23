import asyncio
import logging
from uuid import uuid4
from datetime import datetime, date, time, timedelta, timezone
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum
import json
from .cache import CacheManager

logger = logging.getLogger(__name__)

# Московский часовой пояс (UTC+3)
MOSCOW_TZ = timezone(timedelta(hours=3))

def moscow_now() -> datetime:
    """Возвращает текущее время в московском часовом поясе"""
    return datetime.now(MOSCOW_TZ)

def moscow_datetime(date_obj: date, time_obj: time) -> datetime:
    """Создает datetime объект с московским часовым поясом"""
    naive_datetime = datetime.combine(date_obj, time_obj)
    return naive_datetime.replace(tzinfo=MOSCOW_TZ)

class ReminderType(Enum):
    """Типы напоминаний"""
    SIMPLE = "simple"  # Обычное напоминание
    AI_QUERY = "ai_query"  # AI-запрос


class RecurrenceType(Enum):
    """Типы повторений напоминаний"""
    NONE = "none"  # Одноразовое
    DAILY = "daily"  # Ежедневно
    WEEKLY = "weekly"  # Еженедельно
    MONTHLY = "monthly"  # Ежемесячно
    YEARLY = "yearly"  # Ежегодно

@dataclass
class Reminder:
    """Модель напоминания"""
    id: str
    user_id: int
    title: str
    description: str
    remind_date: date
    remind_time: time
    created_at: datetime
    reminder_type: ReminderType = ReminderType.SIMPLE
    ai_prompt: str = ""  # Промпт для AI (если это AI-напоминание)
    ai_role: str = "assistant"  # Роль AI для запроса
    is_sent: bool = False
    is_active: bool = True
    # Новые поля для периодических напоминаний
    recurrence_type: RecurrenceType = RecurrenceType.NONE
    recurrence_interval: int = 1  # Интервал повторения (каждые N дней/недель/месяцев)
    monthly_day: Optional[int] = None  # День месяца для ежемесячных (1-31)
    weekly_days: Optional[List[int]] = None  # Дни недели для еженедельных (0-6, где 0=понедельник)
    end_date: Optional[date] = None  # Дата окончания повторений
    max_occurrences: Optional[int] = None  # Максимальное количество повторений
    occurrence_count: int = 0  # Счетчик выполненных повторений
    next_occurrence: Optional[date] = None  # Дата следующего срабатывания
    
    def to_dict(self) -> dict:
        """Конвертация в словарь для сериализации"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'description': self.description,
            'remind_date': self.remind_date.isoformat(),
            'remind_time': self.remind_time.isoformat(),
            'created_at': self.created_at.isoformat(),
            'reminder_type': self.reminder_type.value,
            'ai_prompt': self.ai_prompt,
            'ai_role': self.ai_role,
            'is_sent': self.is_sent,
            'is_active': self.is_active,
            'recurrence_type': self.recurrence_type.value,
            'recurrence_interval': self.recurrence_interval,
            'monthly_day': self.monthly_day,
            'weekly_days': self.weekly_days,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'max_occurrences': self.max_occurrences,
            'occurrence_count': self.occurrence_count,
            'next_occurrence': self.next_occurrence.isoformat() if self.next_occurrence else None
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Reminder':
        """Создание из словаря"""
        return cls(
            id=data['id'],
            user_id=data['user_id'],
            title=data['title'],
            description=data['description'],
            remind_date=date.fromisoformat(data['remind_date']),
            remind_time=time.fromisoformat(data['remind_time']),
            created_at=datetime.fromisoformat(data['created_at']),
            reminder_type=ReminderType(data.get('reminder_type', 'simple')),
            ai_prompt=data.get('ai_prompt', ''),
            ai_role=data.get('ai_role', 'assistant'),
            is_sent=data.get('is_sent', False),
            is_active=data.get('is_active', True),
            recurrence_type=RecurrenceType(data.get('recurrence_type', 'none')),
            recurrence_interval=data.get('recurrence_interval', 1),
            monthly_day=data.get('monthly_day'),
            weekly_days=data.get('weekly_days'),
            end_date=date.fromisoformat(data['end_date']) if data.get('end_date') else None,
            max_occurrences=data.get('max_occurrences'),
            occurrence_count=data.get('occurrence_count', 0),
            next_occurrence=date.fromisoformat(data['next_occurrence']) if data.get('next_occurrence') else None
        )
    
    @property
    def remind_datetime(self) -> datetime:
        """Получить полную дату и время напоминания в московском часовом поясе"""
        return moscow_datetime(self.remind_date, self.remind_time)
    
    def is_ready_to_send(self) -> bool:
        """Проверяет, готово ли напоминание к отправке"""
        current_moscow_time = moscow_now()
        
        # Для одноразовых напоминаний
        if self.recurrence_type == RecurrenceType.NONE:
            return current_moscow_time >= self.remind_datetime and not self.is_sent and self.is_active
        
        # Для периодических напоминаний
        if not self.is_active:
            return False
            
        # Проверяем, не превышен ли лимит повторений
        if self.max_occurrences and self.occurrence_count >= self.max_occurrences:
            return False
            
        # Проверяем, не достигнута ли дата окончания
        if self.end_date and current_moscow_time.date() > self.end_date:
            return False
        
        # Используем next_occurrence для периодических напоминаний
        if self.next_occurrence:
            target_datetime = moscow_datetime(self.next_occurrence, self.remind_time)
            return current_moscow_time >= target_datetime
        else:
            # Если next_occurrence не установлен, используем remind_date
            return current_moscow_time >= self.remind_datetime
    
    def calculate_next_occurrence(self) -> Optional[date]:
        """Вычисляет дату следующего срабатывания для периодических напоминаний"""
        if self.recurrence_type == RecurrenceType.NONE:
            return None
            
        current_date = self.next_occurrence or self.remind_date
        
        if self.recurrence_type == RecurrenceType.DAILY:
            return current_date + timedelta(days=self.recurrence_interval)
            
        elif self.recurrence_type == RecurrenceType.WEEKLY:
            return current_date + timedelta(weeks=self.recurrence_interval)
            
        elif self.recurrence_type == RecurrenceType.MONTHLY:
            # Для ежемесячных напоминаний
            if self.monthly_day:
                # Конкретный день месяца
                next_month = current_date.month + self.recurrence_interval
                next_year = current_date.year
                
                while next_month > 12:
                    next_month -= 12
                    next_year += 1
                
                try:
                    return date(next_year, next_month, self.monthly_day)
                except ValueError:
                    # Если день не существует в месяце (например, 31 февраля)
                    # Используем последний день месяца
                    import calendar
                    last_day = calendar.monthrange(next_year, next_month)[1]
                    return date(next_year, next_month, last_day)
            else:
                # Тот же день месяца
                next_month = current_date.month + self.recurrence_interval
                next_year = current_date.year
                
                while next_month > 12:
                    next_month -= 12
                    next_year += 1
                
                try:
                    return date(next_year, next_month, current_date.day)
                except ValueError:
                    import calendar
                    last_day = calendar.monthrange(next_year, next_month)[1]
                    return date(next_year, next_month, last_day)
                    
        elif self.recurrence_type == RecurrenceType.YEARLY:
            try:
                return current_date.replace(year=current_date.year + self.recurrence_interval)
            except ValueError:
                # 29 февраля в невисокосный год
                return current_date.replace(year=current_date.year + self.recurrence_interval, day=28)
        
        return None
    
    def update_after_sending(self):
        """Обновляет напоминание после отправки"""
        if self.recurrence_type == RecurrenceType.NONE:
            # Одноразовое напоминание - помечаем как отправленное
            self.is_sent = True
        else:
            # Периодическое напоминание - увеличиваем счетчик и вычисляем следующую дату
            self.occurrence_count += 1
            self.next_occurrence = self.calculate_next_occurrence()
            
            # Проверяем, нужно ли деактивировать напоминание
            if self.max_occurrences and self.occurrence_count >= self.max_occurrences:
                self.is_active = False
            elif self.end_date and self.next_occurrence and self.next_occurrence > self.end_date:
                self.is_active = False
    
    def get_recurrence_description(self) -> str:
        """Возвращает описание периодичности"""
        if self.recurrence_type == RecurrenceType.NONE:
            return "Одноразово"
        elif self.recurrence_type == RecurrenceType.DAILY:
            if self.recurrence_interval == 1:
                return "Ежедневно"
            else:
                return f"Каждые {self.recurrence_interval} дня"
        elif self.recurrence_type == RecurrenceType.WEEKLY:
            if self.recurrence_interval == 1:
                return "Еженедельно"
            else:
                return f"Каждые {self.recurrence_interval} недели"
        elif self.recurrence_type == RecurrenceType.MONTHLY:
            if self.monthly_day:
                if self.recurrence_interval == 1:
                    return f"Ежемесячно {self.monthly_day}-го числа"
                else:
                    return f"Каждые {self.recurrence_interval} месяца {self.monthly_day}-го числа"
            else:
                if self.recurrence_interval == 1:
                    return "Ежемесячно"
                else:
                    return f"Каждые {self.recurrence_interval} месяца"
        elif self.recurrence_type == RecurrenceType.YEARLY:
            if self.recurrence_interval == 1:
                return "Ежегодно"
            else:
                return f"Каждые {self.recurrence_interval} года"
        return "Неизвестно"


class ReminderManager:
    """Менеджер для работы с напоминаниями"""
    
    def __init__(self, cache_manager: CacheManager, bot=None, ai_client=None):
        self.cache_manager = cache_manager
        self.bot = bot
        self.ai_client = ai_client
        self._scheduler_task = None
        self._is_running = False
        
    async def create_reminder(self, user_id: int, title: str, description: str, 
                             remind_date: date, remind_time: time, 
                             reminder_type: ReminderType = ReminderType.SIMPLE,
                             ai_prompt: str = '', ai_role: str = 'assistant',
                             recurrence_type: RecurrenceType = RecurrenceType.NONE,
                             recurrence_interval: int = 1,
                             monthly_day: Optional[int] = None,
                             weekly_days: Optional[List[int]] = None,
                             end_date: Optional[date] = None,
                             max_occurrences: Optional[int] = None) -> str:
        """Создание нового напоминания"""
        reminder = Reminder(
            id=str(uuid4()),
            user_id=user_id,
            title=title,
            description=description,
            remind_date=remind_date,
            remind_time=remind_time,
            created_at=moscow_now(),
            reminder_type=reminder_type,
            ai_prompt=ai_prompt,
            ai_role=ai_role,
            recurrence_type=recurrence_type,
            recurrence_interval=recurrence_interval,
            monthly_day=monthly_day,
            weekly_days=weekly_days,
            end_date=end_date,
            max_occurrences=max_occurrences
        )
        
        # Для периодических напоминаний устанавливаем next_occurrence
        if recurrence_type != RecurrenceType.NONE:
            reminder.next_occurrence = remind_date
        
        # Сохраняем в кеш
        await self.cache_manager.set("reminder", reminder.id, reminder.to_dict())
        
        # Добавляем в список напоминаний пользователя
        user_reminders = await self.cache_manager.get("user_reminders", str(user_id)) or []
        user_reminders.append(reminder.id)
        await self.cache_manager.set("user_reminders", str(user_id), user_reminders)
        
        logger.info(f"Создано напоминание {reminder.id} для пользователя {user_id}, тип: {recurrence_type.value}")
        return reminder.id
    
    async def get_user_reminders(self, user_id: int, active_only: bool = True, include_sent_oneoff: bool = False) -> List[Reminder]:
        """Получает все напоминания пользователя
        
        Args:
            user_id: ID пользователя
            active_only: Только активные напоминания
            include_sent_oneoff: Включать отправленные одноразовые напоминания
        """
        user_reminder_ids = await self.cache_manager.get("user_reminders", str(user_id)) or []
        
        reminders = []
        for reminder_id in user_reminder_ids:
            reminder_data = await self.cache_manager.get("reminder", reminder_id)
            if reminder_data:
                reminder = Reminder.from_dict(reminder_data)
                
                # Фильтр по активности
                if active_only and not reminder.is_active:
                    continue
                
                # Скрываем отправленные одноразовые напоминания, если не требуется их показывать
                if not include_sent_oneoff and reminder.recurrence_type == RecurrenceType.NONE and reminder.is_sent:
                    continue
                
                reminders.append(reminder)
        
        # Сортируем по дате и времени
        reminders.sort(key=lambda r: (r.remind_date, r.remind_time))
        return reminders
    
    async def get_reminder(self, reminder_id: str) -> Optional[Reminder]:
        """Получает напоминание по ID"""
        reminder_data = await self.cache_manager.get("reminder", reminder_id)
        if reminder_data:
            return Reminder.from_dict(reminder_data)
        return None
    
    async def update_reminder(self, reminder: Reminder) -> bool:
        """Обновляет напоминание"""
        return await self._save_reminder(reminder)
    
    async def delete_reminder(self, reminder_id: str, user_id: int) -> bool:
        """Удаляет напоминание"""
        reminder = await self.get_reminder(reminder_id)
        if reminder and reminder.user_id == user_id:
            # Помечаем как неактивное
            reminder.is_active = False
            await self._save_reminder(reminder)
            logger.info(f"Deleted reminder {reminder_id}")
            return True
        return False
    
    async def mark_as_sent(self, reminder_id: str) -> bool:
        """Помечает напоминание как отправленное и обновляет для периодических"""
        reminder = await self.get_reminder(reminder_id)
        if reminder:
            reminder.update_after_sending()
            await self._save_reminder(reminder)
            return True
        return False
    
    async def get_due_reminders(self) -> List[Reminder]:
        """Получает все напоминания, которые нужно отправить"""
        # Получаем список всех пользователей с напоминаниями
        all_users_key = "reminder_users"
        user_ids = await self.cache_manager.get("global", all_users_key) or []
        
        due_reminders = []
        
        # Если глобальный список пуст, попробуем найти пользователей через прямой поиск
        if not user_ids:
            logger.info("Global user list is empty, searching for active reminders")
            # Попробуем найти пользователей с активными напоминаниями
            known_user_ids = [505032693]  # Временно добавим известного пользователя
            for user_id in known_user_ids:
                try:
                    user_reminders = await self.get_user_reminders(user_id, active_only=True, include_sent_oneoff=True)
                    if user_reminders:
                        # Добавляем пользователя в глобальный список для будущих проверок
                        user_ids.append(user_id)
                        await self.cache_manager.set("global", all_users_key, user_ids)
                        logger.info(f"Added user {user_id} to global list, found {len(user_reminders)} reminders")
                except Exception as e:
                    logger.error(f"Error checking user {user_id}: {e}")
        
        # Проверяем напоминания для всех найденных пользователей
        for user_id in user_ids:
            try:
                user_reminders = await self.get_user_reminders(user_id, active_only=True, include_sent_oneoff=True)
                
                # Фильтруем те, которые пора отправлять
                ready_reminders = [r for r in user_reminders if r.is_ready_to_send()]
                if ready_reminders:
                    logger.info(f"User {user_id} has {len(ready_reminders)} due reminders")
                
                due_reminders.extend(ready_reminders)
            except Exception as e:
                logger.error(f"Error getting reminders for user {user_id}: {e}")
                continue
        
        logger.info(f"Found {len(due_reminders)} due reminders total")
        return due_reminders
    
    async def _save_reminder(self, reminder: Reminder) -> bool:
        """Сохраняет напоминание в кеше"""
        # Сохраняем само напоминание
        reminder_saved = await self.cache_manager.set("reminder", reminder.id, reminder.to_dict())
        
        if reminder_saved:
            # Обновляем список напоминаний пользователя
            user_reminders = await self.cache_manager.get("user_reminders", str(reminder.user_id)) or []
            
            if reminder.id not in user_reminders:
                user_reminders.append(reminder.id)
                await self.cache_manager.set("user_reminders", str(reminder.user_id), user_reminders)
            
            # Добавляем пользователя в глобальный список пользователей с напоминаниями
            all_users_key = "reminder_users"
            all_users = await self.cache_manager.get("global", all_users_key) or []
            if reminder.user_id not in all_users:
                all_users.append(reminder.user_id)
                await self.cache_manager.set("global", all_users_key, all_users)
        
        return reminder_saved
    
    async def start_scheduler(self):
        """Запускает планировщик проверки напоминаний"""
        if self._scheduler_task is None or self._scheduler_task.done():
            self._scheduler_task = asyncio.create_task(self._scheduler_loop())
            logger.info("Reminder scheduler started")
    
    async def stop_scheduler(self):
        """Останавливает планировщик"""
        if self._scheduler_task and not self._scheduler_task.done():
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
            logger.info("Reminder scheduler stopped")
    
    async def _scheduler_loop(self):
        """Основной цикл планировщика"""
        while True:
            try:
                await self._check_and_send_reminders()
                # Проверяем каждую минуту
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in reminder scheduler: {e}")
                await asyncio.sleep(60)
    
    async def _check_and_send_reminders(self):
        """Проверяет и отправляет напоминания"""
        if not self.bot:
            return
            
        due_reminders = await self.get_due_reminders()
        
        for reminder in due_reminders:
            try:
                await self._send_reminder(reminder)
                await self.mark_as_sent(reminder.id)
            except Exception as e:
                logger.error(f"Error sending reminder {reminder.id}: {e}")
    
    async def _send_reminder(self, reminder: Reminder):
        """Отправляет напоминание пользователю"""
        if not self.bot:
            raise Exception("Bot not configured")
        
        try:
            if reminder.reminder_type == ReminderType.SIMPLE:
                # Обычное напоминание
                message_text = (
                    f"⏰ <b>Напоминание!</b>\n\n"
                    f"📌 <b>{reminder.title}</b>\n"
                    f"📝 {reminder.description}\n\n"
                    f"🗓 Дата: {reminder.remind_date.strftime('%d.%m.%Y')}\n"
                    f"🕐 Время: {reminder.remind_time.strftime('%H:%M')}\n"
                    f"🔄 Повтор: {reminder.get_recurrence_description()}"
                )
                
                # Для периодических напоминаний добавляем информацию о следующем срабатывании
                if reminder.recurrence_type != RecurrenceType.NONE and reminder.next_occurrence:
                    message_text += f"\n\n⏭ Следующее напоминание: {reminder.next_occurrence.strftime('%d.%m.%Y')} в {reminder.remind_time.strftime('%H:%M')}"
                
                await self.bot.send_message(
                    chat_id=reminder.user_id,
                    text=message_text,
                    parse_mode="HTML"
                )
            
            elif reminder.reminder_type == ReminderType.AI_QUERY:
                # AI-запрос
                if not reminder.ai_prompt:
                    logger.error(f"AI-напоминание {reminder.id} без промпта")
                    return
                
                # Получаем AI клиент
                if not hasattr(self, 'ai_client') or not self.ai_client:
                    logger.error("AI клиент недоступен для AI-напоминания")
                    return
                
                try:
                    # Выполняем AI-запрос
                    ai_response = await self.ai_client.get_response(
                        prompt=reminder.ai_prompt,
                        user_id=reminder.user_id,
                        role=reminder.ai_role
                    )
                    
                    # Отправляем результат
                    message_text = (
                        f"🤖 <b>AI-напоминание:</b> {reminder.title}\n\n"
                        f"<b>Запрос:</b> {reminder.ai_prompt}\n\n"
                        f"<b>Ответ:</b>\n{ai_response}\n\n"
                        f"🔄 Повтор: {reminder.get_recurrence_description()}"
                    )
                    
                    # Для периодических напоминаний добавляем информацию о следующем срабатывании
                    if reminder.recurrence_type != RecurrenceType.NONE and reminder.next_occurrence:
                        message_text += f"\n\n⏭ Следующий AI-запрос: {reminder.next_occurrence.strftime('%d.%m.%Y')} в {reminder.remind_time.strftime('%H:%M')}"
                    
                    await self.bot.send_message(
                        chat_id=reminder.user_id,
                        text=message_text,
                        parse_mode="HTML"
                    )
                    
                except Exception as e:
                    logger.error(f"Ошибка выполнения AI-запроса в напоминании {reminder.id}: {e}")
                    # Отправляем уведомление об ошибке
                    error_message = (
                        f"❌ <b>Ошибка AI-напоминания:</b> {reminder.title}\n\n"
                        f"Не удалось выполнить AI-запрос: {reminder.ai_prompt}\n"
                        f"Ошибка: {str(e)}"
                    )
                    await self.bot.send_message(
                        chat_id=reminder.user_id,
                        text=error_message,
                        parse_mode="HTML"
                    )
            
            logger.info(f"Sent reminder {reminder.id} to user {reminder.user_id}")
            
        except Exception as e:
            logger.error(f"Ошибка отправки напоминания {reminder.id}: {e}")
