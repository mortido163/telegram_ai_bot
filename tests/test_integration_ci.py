#!/usr/bin/env python3
"""
Быстрые модульные тесты для CI/CD pipeline
Проверяет основную функциональность БЕЗ внешних зависимостей (Redis, AI API)
Фокус на импортах, создании объектов, базовой логике
"""

import asyncio
import sys
import os
import logging
import pytest

# Конфигурация для pytest-asyncio
pytest_plugins = ("pytest_asyncio",)
from datetime import date, time, datetime

# Добавляем корневую директорию в путь для импортов
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Настройка логирования для CI
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_basic_imports():
    """Тест базовых импортов - КРИТИЧНО для CI"""
    try:
        from bot.reminders import ReminderManager, ReminderType, Reminder
        from bot.request_limiter import RequestLimiter, UserRequestInfo
        from bot.ai_client import AIClient
        from bot.cache import CacheManager
        logger.info("✅ All basic imports successful")
        return True
    except ImportError as e:
        logger.error(f"❌ Import failed: {e}")
        return False

@pytest.mark.asyncio
async def test_reminder_types():
    """Тест enum типов напоминаний - БЕЗ создания объектов"""
    try:
        from bot.reminders import ReminderType
        
        # Проверяем, что все типы доступны
        simple_type = ReminderType.SIMPLE
        ai_type = ReminderType.AI_QUERY
        
        assert simple_type.value == "simple"
        assert ai_type.value == "ai_query"
        
        logger.info("✅ Reminder types work correctly")
        return True
    except Exception as e:
        logger.error(f"❌ Reminder types test failed: {e}")
        return False

@pytest.mark.asyncio
async def test_reminder_model_creation():
    """Тест создания моделей напоминаний - БЕЗ сохранения в БД"""
    try:
        from bot.reminders import Reminder, ReminderType
        from uuid import uuid4
        
        # ТОЛЬКО создание объектов в памяти, БЕЗ CacheManager
        simple_reminder = Reminder(
            id=str(uuid4()),
            user_id=123,
            title="Test Simple",
            description="Test description",
            remind_date=date(2024, 12, 31),
            remind_time=time(12, 0),
            created_at=datetime.now(),
            reminder_type=ReminderType.SIMPLE
        )
        
        ai_reminder = Reminder(
            id=str(uuid4()),
            user_id=123,
            title="Test AI",
            description="",
            remind_date=date(2024, 12, 31),
            remind_time=time(15, 0),
            created_at=datetime.now(),
            reminder_type=ReminderType.AI_QUERY,
            ai_prompt="Test AI prompt",
            ai_role="assistant"
        )
        
        # Тест сериализации - ТОЛЬКО в памяти
        simple_dict = simple_reminder.to_dict()
        ai_dict = ai_reminder.to_dict()
        
        # Тест десериализации
        restored_simple = Reminder.from_dict(simple_dict)
        restored_ai = Reminder.from_dict(ai_dict)
        
        assert restored_simple.reminder_type == ReminderType.SIMPLE
        assert restored_ai.reminder_type == ReminderType.AI_QUERY
        assert restored_ai.ai_prompt == "Test AI prompt"
        
        logger.info("✅ Reminder model creation and serialization work correctly")
        return True
    except Exception as e:
        logger.error(f"❌ Reminder model test failed: {e}")
        return False

@pytest.mark.asyncio
async def test_request_limiter_logic():
    """Тест логики ограничителя - БЕЗ фоновых задач"""
    try:
        from bot.request_limiter import RequestLimiter
        
        # Создаем БЕЗ запуска фоновых задач
        limiter = RequestLimiter(max_request_time=60)
        # НЕ вызываем await limiter.start() - только логика
        
        test_user = 999
        
        # Тест логики блокировки
        result1 = await limiter.acquire_request_lock(test_user, 'text')
        assert result1 == True, "First request should succeed"
        
        result2 = await limiter.acquire_request_lock(test_user, 'text')
        assert result2 == False, "Second request should be blocked"
        
        # Проверка состояния
        assert limiter.is_user_active(test_user) == True
        assert limiter.get_active_requests_count() == 1
        
        # Освобождение
        await limiter.release_request_lock(test_user)
        assert limiter.is_user_active(test_user) == False
        
        logger.info("✅ Request limiter logic works correctly")
        return True
    except Exception as e:
        logger.error(f"❌ Request limiter logic test failed: {e}")
        return False

@pytest.mark.asyncio
async def test_ai_client_configuration():
    """Тест конфигурации AI клиента - БЕЗ реальных AI запросов"""
    try:
        from bot.ai_client import AIClient
        from bot.request_limiter import RequestLimiter
        
        # Создание и конфигурация БЕЗ внешних вызовов
        limiter = RequestLimiter()
        ai_client = AIClient()
        
        # Тест установки ограничителя
        ai_client.set_request_limiter(limiter)
        assert ai_client.request_limiter is not None
        
        # Тест смены провайдера
        original_provider = ai_client.active_provider
        await ai_client.set_provider("openai")  # Всегда доступен
        assert ai_client.active_provider == "openai"
        
        logger.info("✅ AI client configuration works correctly")
        return True
    except Exception as e:
        logger.error(f"❌ AI client configuration test failed: {e}")
        return False

@pytest.mark.asyncio
async def test_fsm_states():
    """Тест состояний FSM"""
    try:
        from bot.states import ReminderStates, EditReminderStates
        
        # Проверяем ТОЛЬКО наличие состояний
        required_states = [
            'waiting_for_type',
            'waiting_for_title', 
            'waiting_for_description',
            'waiting_for_date',
            'waiting_for_time',
            'waiting_for_ai_prompt',
            'waiting_for_ai_role',
            'confirmation'
        ]
        
        for state_name in required_states:
            state = getattr(ReminderStates, state_name, None)
            assert state is not None, f"State {state_name} should be defined"
        
        logger.info("✅ FSM states are correctly defined")
        return True
    except Exception as e:
        logger.error(f"❌ FSM states test failed: {e}")
        return False

async def run_all_tests():
    """Запуск всех быстрых модульных тестов для CI"""
    tests = [
        ("Basic Imports", test_basic_imports),
        ("Reminder Types", test_reminder_types),
        ("Reminder Model Creation", test_reminder_model_creation),
        ("Request Limiter Logic", test_request_limiter_logic),
        ("AI Client Configuration", test_ai_client_configuration),
        ("FSM States", test_fsm_states),
    ]
    
    passed = 0
    total = len(tests)
    
    logger.info(f"🧪 Running {total} unit tests for CI...")
    logger.info("ℹ️  These tests run WITHOUT external dependencies (Redis, AI APIs)")
    
    for test_name, test_func in tests:
        logger.info(f"\n📝 Running test: {test_name}")
        try:
            result = await test_func()
            if result:
                passed += 1
                logger.info(f"✅ {test_name} PASSED")
            else:
                logger.error(f"❌ {test_name} FAILED")
        except Exception as e:
            logger.error(f"❌ {test_name} FAILED with exception: {e}")
    
    logger.info(f"\n📊 Unit Test Results: {passed}/{total} passed")
    
    if passed == total:
        logger.info("🎉 All unit tests passed!")
        return True
    else:
        logger.error(f"💥 {total - passed} unit tests failed!")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
