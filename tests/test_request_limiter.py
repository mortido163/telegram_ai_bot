#!/usr/bin/env python3
"""
Тесты для системы ограничения запросов
"""

import asyncio
import sys
import os
import pytest
from datetime import datetime, timedelta

# Конфигурация для pytest-asyncio
pytest_plugins = ("pytest_asyncio",)

# Добавляем корневую директорию в путь для импортов
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.request_limiter import RequestLimiter

@pytest.mark.asyncio
async def test_request_limiter():
    """Тестирует работу ограничителя запросов"""
    
    print("🧪 Тестирование ограничителя запросов...")
    
    # Создаем ограничитель с коротким таймаутом для тестов
    limiter = RequestLimiter(max_request_time=5)
    await limiter.start()
    
    test_user_id = 123456
    
    try:
        # Тест 1: Первый запрос должен проходить
        print("\n📝 Тест 1: Первый запрос")
        result1 = await limiter.acquire_request_lock(test_user_id, 'text')
        assert result1 == True, "Первый запрос должен проходить"
        print("✅ Первый запрос принят")
        
        # Тест 2: Второй запрос от того же пользователя должен блокироваться
        print("\n📝 Тест 2: Второй запрос от того же пользователя")
        result2 = await limiter.acquire_request_lock(test_user_id, 'text')
        assert result2 == False, "Второй запрос должен блокироваться"
        print("✅ Второй запрос заблокирован")
        
        # Тест 3: Запрос от другого пользователя должен проходить
        print("\n📝 Тест 3: Запрос от другого пользователя")
        other_user_id = 789012
        result3 = await limiter.acquire_request_lock(other_user_id, 'text')
        assert result3 == True, "Запрос от другого пользователя должен проходить"
        print("✅ Запрос от другого пользователя принят")
        
        # Тест 4: Освобождение блокировки
        print("\n📝 Тест 4: Освобождение блокировки")
        await limiter.release_request_lock(test_user_id)
        result4 = await limiter.acquire_request_lock(test_user_id, 'image')
        assert result4 == True, "После освобождения блокировки запрос должен проходить"
        print("✅ Блокировка успешно освобождена")
        
        # Тест 5: Проверка информации о запросах
        print("\n📝 Тест 5: Информация о запросах")
        active_count = limiter.get_active_requests_count()
        assert active_count == 2, f"Ожидается 2 активных запроса, получено {active_count}"
        
        is_user_active = limiter.is_user_active(test_user_id)
        assert is_user_active == True, "Пользователь должен быть активным"
        
        user_info = limiter.get_user_request_info(test_user_id)
        assert user_info is not None, "Информация о запросе должна быть доступна"
        assert user_info.request_type == 'image', "Тип запроса должен быть 'image'"
        print("✅ Информация о запросах корректна")
        
        # Тест 6: Автоматическая очистка после таймаута
        print("\n📝 Тест 6: Автоматическая очистка (ждем 6 секунд...)")
        await asyncio.sleep(6)  # Ждем больше max_request_time
        
        # Попробуем сделать новый запрос - он должен пройти
        result5 = await limiter.acquire_request_lock(test_user_id, 'text')
        assert result5 == True, "После таймаута запрос должен проходить"
        print("✅ Автоматическая очистка работает")
        
        print("\n🎉 Все тесты ограничителя запросов прошли успешно!")
        
    except AssertionError as e:
        print(f"\n❌ Тест провален: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Ошибка в тестах: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Очистка
        print("\n🧹 Очистка...")
        await limiter.stop()
        print("✅ Ограничитель остановлен")
    
    return True

@pytest.mark.asyncio
async def test_ai_client_integration():
    """Тестирует интеграцию AI клиента с ограничителем"""
    
    print("\n🤖 Тестирование интеграции с AI клиентом...")
    
    from bot.ai_client import AIClient
    
    limiter = RequestLimiter()
    await limiter.start()
    
    ai_client = AIClient()
    ai_client.set_request_limiter(limiter)
    
    test_user_id = 555666
    
    try:
        # Проверяем, что первый запрос будет обработан (даже если не сработает из-за API ключей)
        print("\n📝 Тест интеграции: Первый запрос")
        response1 = await ai_client.get_response("Тест", test_user_id)
        # Ответ может быть ошибкой, но не должен быть сообщением о блокировке
        assert not response1.startswith("⏳"), "Первый запрос не должен блокироваться"
        print("✅ Первый запрос не заблокирован")
        
        # Проверяем, что второй запрос заблокируется (если первый еще не завершился)
        print("\n📝 Тест интеграции: Второй запрос")
        # Имитируем ситуацию с активным запросом
        await limiter.acquire_request_lock(test_user_id, 'text')
        response2 = await ai_client.get_response("Тест2", test_user_id)
        assert response2.startswith("⏳"), "Второй запрос должен блокироваться"
        print("✅ Второй запрос заблокирован корректно")
        
        print("\n🎉 Интеграция с AI клиентом работает!")
        
    except Exception as e:
        print(f"\n❌ Ошибка в тесте интеграции: {e}")
        return False
    
    finally:
        await limiter.stop()
    
    return True

if __name__ == "__main__":
    async def run_all_tests():
        success1 = await test_request_limiter()
        success2 = await test_ai_client_integration()
        return success1 and success2
    
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
