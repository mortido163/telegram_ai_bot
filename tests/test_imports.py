import os
import sys
from unittest.mock import MagicMock

# Add project root to PYTHONPATH
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Mock all external dependencies
mocks = {
    # Redis
    'redis': MagicMock(),
    'redis.asyncio': MagicMock(),
    
    # Aiogram and its submodules
    'aiogram': MagicMock(),
    'aiogram.types': MagicMock(),
    'aiogram.filters': MagicMock(),
    'aiogram.fsm.context': MagicMock(),
    'aiogram.dispatcher': MagicMock(),
    'aiogram.client': MagicMock(),
    'aiogram.utils': MagicMock(),
    'aiogram.enums': MagicMock(),
    
    # OpenAI
    'openai': MagicMock(),
    
    # Other dependencies
    'aiohttp': MagicMock(),
    'PIL': MagicMock()
}

# Apply all mocks
for module_name, mock in mocks.items():
    sys.modules[module_name] = mock

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
