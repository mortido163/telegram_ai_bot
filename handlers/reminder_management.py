"""
Модуль для управления напоминаниями - просмотр, редактирование, удаление
"""
import logging
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.states import EditReminderStates
from .reminder_utils import (
    moscow_datetime, safe_edit_message, get_reminder_manager
)

logger = logging.getLogger(__name__)
management_router = Router()


@management_router.callback_query(F.data == "list_reminders")
async def list_user_reminders(callback: types.CallbackQuery, **kwargs):
    """Показывает список напоминаний пользователя"""
    reminder_manager = await get_reminder_manager(kwargs)
    
    try:
        reminders = await reminder_manager.get_user_reminders(callback.from_user.id)
        
        if not reminders:
            text = (
                "📭 <b>У вас пока нет напоминаний</b>\n\n"
                "Создайте первое напоминание!"
            )
            
            builder = InlineKeyboardBuilder()
            builder.button(text="📝 Создать напоминание", callback_data="create_reminder")
            builder.button(text="🔙 Назад", callback_data="reminders_menu")
            builder.button(text="❌ Закрыть", callback_data="close_reminders")
            builder.adjust(1)
            
        else:
            text = f"📋 <b>Ваши напоминания ({len(reminders)}):</b>\n\n"
            
            builder = InlineKeyboardBuilder()
            
            for i, reminder in enumerate(reminders[:10], 1):  # Показываем максимум 10
                # Определяем статус
                if reminder.recurrence_type.value == "none":
                    status = "⏰" if not reminder.is_sent else "✅"
                else:
                    status = "🔄" if reminder.is_active else "✅"
                
                type_icon = "🤖" if reminder.reminder_type.value == "ai_query" else "📝"
                short_title = reminder.title[:20] + "..." if len(reminder.title) > 20 else reminder.title
                date_str = reminder.remind_date.strftime("%d.%m")
                time_str = reminder.remind_time.strftime("%H:%M")
                
                # Добавляем информацию о периодичности
                recurrence_info = ""
                if reminder.recurrence_type.value != "none":
                    if reminder.recurrence_type.value == "daily":
                        recurrence_info = " (ежедн.)"
                    elif reminder.recurrence_type.value == "weekly":
                        recurrence_info = " (еженед.)"
                    elif reminder.recurrence_type.value == "monthly":
                        recurrence_info = " (ежемес.)"
                    elif reminder.recurrence_type.value == "yearly":
                        recurrence_info = " (ежегод.)"
                
                text += f"{status} {type_icon} <b>{short_title}</b>{recurrence_info}\n"
                
                # Для периодических показываем следующую дату, для одноразовых - исходную
                if reminder.recurrence_type.value != "none" and reminder.next_occurrence:
                    display_date = reminder.next_occurrence.strftime("%d.%m")
                    text += f"    📅 {display_date} в {time_str}"
                    if reminder.occurrence_count > 0:
                        text += f" (выполнено {reminder.occurrence_count} раз)"
                    text += "\n\n"
                else:
                    text += f"    📅 {date_str} в {time_str}\n\n"
                
                builder.button(
                    text=f"{i}. {type_icon} {short_title}", 
                    callback_data=f"view_reminder_{reminder.id}"
                )
            
            builder.button(text="📝 Создать новое", callback_data="create_reminder")
            builder.button(text="🔙 Назад", callback_data="reminders_menu")
            builder.button(text="❌ Закрыть", callback_data="close_reminders")
            builder.adjust(1)
        
        await safe_edit_message(callback, text, reply_markup=builder.as_markup())
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error listing reminders: {e}")
        await callback.answer("⚠️ Ошибка при загрузке напоминаний", show_alert=True)


@management_router.callback_query(F.data.startswith("view_reminder_"))
async def view_reminder_details(callback: types.CallbackQuery, **kwargs):
    """Показывает детали конкретного напоминания"""
    reminder_id = callback.data.replace("view_reminder_", "")
    reminder_manager = await get_reminder_manager(kwargs)
    
    try:
        reminder = await reminder_manager.get_reminder(reminder_id)
        
        if not reminder:
            await callback.answer("⚠️ Напоминание не найдено", show_alert=True)
            return
            
        remind_datetime = moscow_datetime(reminder.remind_date, reminder.remind_time)
        
        if reminder.reminder_type.value == "simple":
            text = (
                f"📝 <b>Обычное напоминание</b>\n\n"
                f"📌 <b>Название:</b> {reminder.title}\n"
                f"📝 <b>Описание:</b> {reminder.description or 'Не указано'}\n"
                f"📅 <b>Дата:</b> {reminder.remind_date.strftime('%d.%m.%Y')}\n"
                f"🕐 <b>Время:</b> {reminder.remind_time.strftime('%H:%M')}\n"
                f"🔄 <b>Повтор:</b> {reminder.get_recurrence_description()}\n"
                f"📊 <b>Статус:</b> {'✅ Отправлено' if reminder.is_sent else '⏰ Ожидает'}\n"
                f"📆 <b>Создано:</b> {reminder.created_at.strftime('%d.%m.%Y %H:%M')}"
            )
            
            # Дополнительная информация для периодических напоминаний
            if reminder.recurrence_type.value != "none":
                text += f"\n🔢 <b>Выполнено:</b> {reminder.occurrence_count} раз"
                if reminder.next_occurrence:
                    text += f"\n⏭ <b>Следующее:</b> {reminder.next_occurrence.strftime('%d.%m.%Y')} в {reminder.remind_time.strftime('%H:%M')}"
                if reminder.max_occurrences:
                    text += f"\n🎯 <b>Максимум:</b> {reminder.max_occurrences} раз"
                if reminder.end_date:
                    text += f"\n📅 <b>До даты:</b> {reminder.end_date.strftime('%d.%m.%Y')}"
        else:
            role_names = {
                'assistant': '👨‍💻 Ассистент',
                'scientist': '🔬 Ученый',
                'creative': '🎨 Креатив',
                'developer': '💻 Разработчик'
            }
            
            text = (
                f"🤖 <b>AI-напоминание</b>\n\n"
                f"📌 <b>Название:</b> {reminder.title}\n"
                f"🤖 <b>AI-запрос:</b> {reminder.ai_prompt}\n"
                f"👤 <b>Роль:</b> {role_names.get(reminder.ai_role, reminder.ai_role)}\n"
                f"📅 <b>Дата:</b> {reminder.remind_date.strftime('%d.%m.%Y')}\n"
                f"🕐 <b>Время:</b> {reminder.remind_time.strftime('%H:%M')}\n"
                f"🔄 <b>Повтор:</b> {reminder.get_recurrence_description()}\n"
                f"📊 <b>Статус:</b> {'✅ Выполнено' if reminder.is_sent else '⏰ Ожидает'}\n"
                f"📆 <b>Создано:</b> {reminder.created_at.strftime('%d.%m.%Y %H:%M')}"
            )
            
            # Дополнительная информация для периодических напоминаний
            if reminder.recurrence_type.value != "none":
                text += f"\n🔢 <b>Выполнено:</b> {reminder.occurrence_count} раз"
                if reminder.next_occurrence:
                    text += f"\n⏭ <b>Следующее:</b> {reminder.next_occurrence.strftime('%d.%m.%Y')} в {reminder.remind_time.strftime('%H:%M')}"
                if reminder.max_occurrences:
                    text += f"\n🎯 <b>Максимум:</b> {reminder.max_occurrences} раз"
                if reminder.end_date:
                    text += f"\n📅 <b>До даты:</b> {reminder.end_date.strftime('%d.%m.%Y')}"
        
        builder = InlineKeyboardBuilder()
        
        # Для периодических напоминаний разрешаем редактирование даже после отправки
        # Для одноразовых - только до отправки
        can_edit = (reminder.recurrence_type.value == "none" and not reminder.is_sent) or \
                  (reminder.recurrence_type.value != "none" and reminder.is_active)
        
        if can_edit:
            builder.button(text="✏️ Редактировать", callback_data=f"edit_reminder_{reminder.id}")
            builder.button(text="🗑 Удалить", callback_data=f"delete_reminder_{reminder.id}")
        
        builder.button(text="📋 К списку", callback_data="list_reminders")
        builder.button(text="❌ Закрыть", callback_data="close_reminders")
        builder.adjust(2, 1)
        
        await safe_edit_message(callback, text, reply_markup=builder.as_markup())
        
    except Exception as e:
        logger.error(f"Error viewing reminder {reminder_id}: {e}")
        await callback.answer("⚠️ Ошибка при загрузке напоминания", show_alert=True)


@management_router.callback_query(F.data.startswith("edit_reminder_"))
async def start_edit_reminder(callback: types.CallbackQuery, state: FSMContext, **kwargs):
    """Начинает редактирование напоминания"""
    reminder_id = callback.data.replace("edit_reminder_", "")
    reminder_manager = await get_reminder_manager(kwargs)
    
    try:
        reminder = await reminder_manager.get_reminder(reminder_id)
        
        if not reminder:
            await callback.answer("⚠️ Напоминание не найдено", show_alert=True)
            return
            
        if reminder.is_sent:
            await callback.answer("⚠️ Нельзя редактировать отправленное напоминание", show_alert=True)
            return
        
        # Сохраняем ID напоминания для редактирования
        await state.update_data(editing_reminder_id=reminder_id)
        await state.set_state(EditReminderStates.choosing_field)
        
        text = (
            f"✏️ <b>Редактирование напоминания</b>\n\n"
            f"📌 <b>Текущие данные:</b>\n"
            f"Название: {reminder.title}\n"
        )
        
        if reminder.reminder_type.value == "simple":
            text += f"Описание: {reminder.description or 'Не указано'}\n"
        else:
            text += f"AI-запрос: {reminder.ai_prompt}\n"
            text += f"Роль: {reminder.ai_role}\n"
            
        text += f"Дата: {reminder.remind_date.strftime('%d.%m.%Y')}\n"
        text += f"Время: {reminder.remind_time.strftime('%H:%M')}\n\n"
        text += "Что хотите изменить?"
        
        builder = InlineKeyboardBuilder()
        builder.button(text="📝 Название", callback_data="edit_field_title")
        
        if reminder.reminder_type.value == "simple":
            builder.button(text="📄 Описание", callback_data="edit_field_description")
        else:
            builder.button(text="🤖 AI-запрос", callback_data="edit_field_ai_prompt")
            builder.button(text="👤 Роль", callback_data="edit_field_ai_role")
            
        builder.button(text="📅 Дата", callback_data="edit_field_date")
        builder.button(text="🕐 Время", callback_data="edit_field_time")
        builder.button(text="❌ Отмена", callback_data=f"view_reminder_{reminder_id}")
        builder.adjust(2, 2, 1, 1)
        
        await safe_edit_message(callback, text, reply_markup=builder.as_markup())
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error starting edit reminder {reminder_id}: {e}")
        await callback.answer("⚠️ Ошибка при загрузке напоминания", show_alert=True)


@management_router.callback_query(F.data.startswith("delete_reminder_"))
async def confirm_delete_reminder(callback: types.CallbackQuery, **kwargs):
    """Подтверждение удаления напоминания"""
    reminder_id = callback.data.replace("delete_reminder_", "")
    reminder_manager = await get_reminder_manager(kwargs)
    
    try:
        reminder = await reminder_manager.get_reminder(reminder_id)
        
        if not reminder:
            await callback.answer("⚠️ Напоминание не найдено", show_alert=True)
            return
            
        text = (
            f"🗑 <b>Удаление напоминания</b>\n\n"
            f"📌 <b>Название:</b> {reminder.title}\n"
            f"📅 <b>Дата:</b> {reminder.remind_date.strftime('%d.%m.%Y')}\n"
            f"🕐 <b>Время:</b> {reminder.remind_time.strftime('%H:%M')}\n\n"
            "❗ <b>Вы уверены, что хотите удалить это напоминание?</b>\n"
            "Это действие нельзя отменить."
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🗑 Да, удалить", callback_data=f"confirm_delete_{reminder_id}")
        builder.button(text="❌ Отмена", callback_data=f"view_reminder_{reminder_id}")
        builder.button(text="❌ Закрыть", callback_data="close_reminders")
        builder.adjust(1)
        
        await safe_edit_message(callback, text, reply_markup=builder.as_markup())
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error confirming delete reminder {reminder_id}: {e}")
        await callback.answer("⚠️ Ошибка при загрузке напоминания", show_alert=True)


@management_router.callback_query(F.data.startswith("confirm_delete_"))
async def delete_reminder(callback: types.CallbackQuery, **kwargs):
    """Удаляет напоминание"""
    reminder_id = callback.data.replace("confirm_delete_", "")
    reminder_manager = await get_reminder_manager(kwargs)
    
    try:
        success = await reminder_manager.delete_reminder(reminder_id, callback.from_user.id)
        
        if success:
            text = "✅ <b>Напоминание удалено</b>\n\nНапоминание успешно удалено из системы."
            
            builder = InlineKeyboardBuilder()
            builder.button(text="📋 Мои напоминания", callback_data="list_reminders")
            builder.button(text="📝 Создать новое", callback_data="create_reminder")
            builder.button(text="❌ Закрыть", callback_data="close_reminders")
            builder.adjust(1)
            
            await safe_edit_message(callback, text, reply_markup=builder.as_markup())
        else:
            await callback.answer("⚠️ Ошибка при удалении напоминания", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error deleting reminder {reminder_id}: {e}")
        await callback.answer("⚠️ Ошибка при удалении напоминания", show_alert=True)
