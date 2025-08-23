#!/usr/bin/env python3
"""
Полнофункциональные интеграционные тесты AI-напоминаний
Тестирует РЕАЛЬНУЮ функциональность с CacheManager, ReminderManager
Требует Redis и полную инициализацию системы
"""

import asyncio
import sys
import os
import pytest
from datetime import date, time

# Конфигурация для pytest-asyncio
pytest_plugins = ("pytest_asyncio",)

# Добавляем корневую директорию в путь для импортов
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.cache import CacheManager
from bot.reminders import ReminderManager, ReminderType
from config import Config

@pytest.mark.asyncio
async def test_full_reminder_workflow():
    """Тестирует полный workflow создания и управления напоминаниями"""
    
    print("🧪 Тестирование полного workflow AI-напоминаний...")
    
    # РЕАЛЬНАЯ инициализация компонентов
    cache_manager = CacheManager()
    reminder_manager = ReminderManager(cache_manager)
    
    test_user_id = 999888777  # Уникальный ID для тестов
    created_reminders = []
    
    try:
        # Очистка старых тестовых данных
        print("\n🧹 Предварительная очистка...")
        try:
            old_reminders = await reminder_manager.get_user_reminders(test_user_id)
            for reminder in old_reminders:
                await reminder_manager.delete_reminder(reminder.id, test_user_id)
            print(f"✅ Очищено {len(old_reminders)} старых напоминаний")
        except:
            print("✅ Старых данных не найдено")
        
        # 1. Создаем обычное напоминание
        print("\n📝 Создание обычного напоминания...")
        simple_id = await reminder_manager.create_reminder(
            user_id=test_user_id,
            title="Тест обычного напоминания",
            description="Это тестовое обычное напоминание",
            remind_date=date(2024, 12, 31),
            remind_time=time(12, 0),
            reminder_type=ReminderType.SIMPLE
        )
        created_reminders.append(simple_id)
        print(f"✅ Создано обычное напоминание: {simple_id}")
        
        # 2. Создаем AI-напоминание
        print("\n🤖 Создание AI-напоминания...")
        ai_id = await reminder_manager.create_reminder(
            user_id=test_user_id,
            title="Тест AI-напоминания",
            description="",
            remind_date=date(2024, 12, 31),
            remind_time=time(15, 0),
            reminder_type=ReminderType.AI_QUERY,
            ai_prompt="Какая погода сегодня?",
            ai_role="assistant"
        )
        created_reminders.append(ai_id)
        print(f"✅ Создано AI-напоминание: {ai_id}")
        
        # 3. Получаем список напоминаний через ReminderManager
        print("\n📋 Получение списка напоминаний...")
        reminders = await reminder_manager.get_user_reminders(test_user_id)
        print(f"✅ Найдено {len(reminders)} напоминаний:")
        
        simple_found = False
        ai_found = False
        
        for reminder in reminders:
            print(f"   - {reminder.reminder_type.value}: {reminder.title}")
            if reminder.reminder_type == ReminderType.SIMPLE and reminder.id == simple_id:
                simple_found = True
                assert reminder.description == "Это тестовое обычное напоминание"
            elif reminder.reminder_type == ReminderType.AI_QUERY and reminder.id == ai_id:
                ai_found = True
                print(f"     AI-запрос: {reminder.ai_prompt}")
                print(f"     Роль: {reminder.ai_role}")
                assert reminder.ai_prompt == "Какая погода сегодня?"
                assert reminder.ai_role == "assistant"
        
        assert simple_found, "Созданное обычное напоминание не найдено"
        assert ai_found, "Созданное AI-напоминание не найдено"
        
        # 4. Тест сериализации с реальными данными
        print("\n💾 Тестирование сериализации с реальными данными...")
        for reminder in reminders:
            if reminder.id in created_reminders:  # Проверяем только наши напоминания
                data = reminder.to_dict()
                restored = reminder.__class__.from_dict(data)
                
                assert restored.id == reminder.id
                assert restored.reminder_type == reminder.reminder_type
                assert restored.ai_prompt == reminder.ai_prompt
                assert restored.ai_role == reminder.ai_role
                assert restored.user_id == reminder.user_id
                
                print(f"   ✅ {reminder.reminder_type.value}: сериализация работает")
        
        # 5. Тест обновления напоминания
        print("\n✏️ Тестирование обновления AI-напоминания...")
        ai_reminder = next(r for r in reminders if r.id == ai_id)
        
        # Обновляем объект
        ai_reminder.title = "Обновленное AI-напоминание"
        ai_reminder.ai_prompt = "Расскажи анекдот"
        
        # Сохраняем обновление
        update_result = await reminder_manager.update_reminder(ai_reminder)
        assert update_result == True, "Обновление должно быть успешным"
        
        # Проверяем обновление
        updated_reminder = await reminder_manager.get_reminder(ai_id)
        assert updated_reminder.title == "Обновленное AI-напоминание"
        assert updated_reminder.ai_prompt == "Расскажи анекдот"
        print("✅ Обновление напоминания работает")
        
        # 6. Тест получения всех напоминаний от планировщика
        print("\n📅 Тестирование получения всех напоминаний...")
        final_reminders = await reminder_manager.get_user_reminders(test_user_id)
        our_reminders = [r for r in final_reminders if r.id in created_reminders]
        assert len(our_reminders) == 2, f"Ожидалось 2 напоминания, найдено {len(our_reminders)}"
        print(f"✅ Найдено {len(our_reminders)} наших напоминаний")
        
        print("\n🎉 Все полнофункциональные тесты прошли успешно!")
        
    except Exception as e:
        print(f"\n❌ Ошибка в полнофункциональных тестах: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Очистка тестовых данных
        print("\n🧹 Очистка тестовых данных...")
        try:
            for reminder_id in created_reminders:
                await reminder_manager.delete_reminder(reminder_id, test_user_id)
            print("✅ Тестовые данные очищены")
        except Exception as e:
            print(f"⚠️ Проблема при очистке: {e}")
    
    return True

@pytest.mark.asyncio
async def test_reminder_scheduler_integration():
    """Тест интеграции с планировщиком напоминаний"""
    
    print("\n🕒 Тестирование интеграции с планировщиком...")
    
    cache_manager = CacheManager()
    reminder_manager = ReminderManager(cache_manager)
    
    test_user_id = 987654321
    
    try:
        # Создаем напоминание на завтра
        from datetime import datetime, timedelta
        tomorrow = datetime.now() + timedelta(days=1)
        
        reminder_id = await reminder_manager.create_reminder(
            user_id=test_user_id,
            title="Тест планировщика",
            description="Напоминание для тестирования планировщика",
            remind_date=tomorrow.date(),
            remind_time=tomorrow.time(),
            reminder_type=ReminderType.SIMPLE
        )
        
        # Запускаем планировщик (только инициализация)
        await reminder_manager.start_scheduler()
        print("✅ Планировщик успешно запущен")
        
        # Проверяем, что напоминание загружено в планировщик  
        user_reminders = await reminder_manager.get_user_reminders(test_user_id)
        our_reminder = next((r for r in user_reminders if r.id == reminder_id), None)
        assert our_reminder is not None, "Напоминание не найдено"
        print("✅ Напоминание доступно через менеджер")
        
        # Остановка планировщика
        await reminder_manager.stop_scheduler()
        print("✅ Планировщик корректно остановлен")
        
        # Очистка
        await reminder_manager.delete_reminder(reminder_id, test_user_id)
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка в тесте планировщика: {e}")
        import traceback
        traceback.print_exc()
        return False

@pytest.mark.asyncio
async def test_cache_integration():
    """Тест интеграции с системой кеширования"""
    
    print("\n💾 Тестирование интеграции с кешем...")
    
    cache_manager = CacheManager()
    
    try:
        # Тест прямого кеширования
        test_key = "test_reminder_data"
        test_data = {
            "user_id": 123,
            "title": "Тест кеша",
            "type": "ai_query"
        }
        
        # Сохранение в кеш
        await cache_manager.set("test_reminders", test_key, test_data)
        
        # Получение из кеша
        cached_data = await cache_manager.get("test_reminders", test_key)
        assert cached_data == test_data, "Данные в кеше не совпадают"
        print("✅ Кеширование работает корректно")
        
        # Удаление из кеша
        await cache_manager.clear("test_reminders", test_key)
        deleted_data = await cache_manager.get("test_reminders", test_key)
        assert deleted_data is None, "Данные не удалены из кеша"
        print("✅ Удаление из кеша работает")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка в тесте кеша: {e}")
        import traceback
        traceback.print_exc()
        return False

async def run_integration_tests():
    """Запуск всех полнофункциональных интеграционных тестов"""
    
    tests = [
        ("Full Reminder Workflow", test_full_reminder_workflow),
        ("Reminder Scheduler Integration", test_reminder_scheduler_integration),
        ("Cache Integration", test_cache_integration),
    ]
    
    passed = 0
    total = len(tests)
    
    print(f"🧪 Запуск {total} полнофункциональных интеграционных тестов...")
    print("ℹ️  Эти тесты требуют Redis и полную инициализацию системы")
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"📝 Запуск теста: {test_name}")
        print('='*50)
        
        try:
            result = await test_func()
            if result:
                passed += 1
                print(f"\n✅ {test_name} ПРОШЕЛ")
            else:
                print(f"\n❌ {test_name} НЕ ПРОШЕЛ")
        except Exception as e:
            print(f"\n❌ {test_name} ЗАВЕРШИЛСЯ С ОШИБКОЙ: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*60}")
    print(f"📊 Результаты интеграционных тестов: {passed}/{total} прошли")
    
    if passed == total:
        print("🎉 Все интеграционные тесты прошли успешно!")
        return True
    else:
        print(f"💥 {total - passed} интеграционных тестов не прошли!")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_integration_tests())
    sys.exit(0 if success else 1)
