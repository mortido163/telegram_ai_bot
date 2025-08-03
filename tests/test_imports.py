import sys
from unittest.mock import MagicMock

# Mock Redis
sys.modules['redis'] = MagicMock()
sys.modules['redis.asyncio'] = MagicMock()

# Mock aiogram
sys.modules['aiogram'] = MagicMock()
sys.modules['aiogram.types'] = MagicMock()
sys.modules['aiogram.filters'] = MagicMock()
sys.modules['aiogram.fsm.context'] = MagicMock()

def test_imports():
    import bot
    print('✅ All modules imported successfully')
    
    import config
    print('✅ Config imported successfully')
    
    # Не импортируем main.py, так как он инициализирует бота
    # import main
    print('✅ Import tests completed')

if __name__ == '__main__':
    test_imports()
