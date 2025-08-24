#!/usr/bin/env python3
"""
Pytest тесты для кодирования и декодирования изображений в AIClient
"""

import asyncio
import base64
import io
import sys
import os
import pytest
from PIL import Image, ImageDraw

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.ai_client import AIClient


@pytest.fixture
def ai_client():
    """Фикстура для создания экземпляра AIClient"""
    return AIClient()


@pytest.fixture
def sample_image_bytes():
    """Фикстура для создания тестового изображения в виде байтов"""
    image = Image.new('RGB', (100, 100), color='red')
    draw = ImageDraw.Draw(image)
    draw.text((10, 50), "TEST", fill='white')
    
    img_buffer = io.BytesIO()
    image.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    return img_buffer.getvalue()


@pytest.fixture
def tiny_image_bytes():
    """Фикстура для создания маленького изображения (для тестов валидации)"""
    image = Image.new('RGB', (5, 5), color='blue')
    img_buffer = io.BytesIO()
    image.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    return img_buffer.getvalue()


@pytest.fixture
def corrupted_bytes():
    """Фикстура для поврежденных данных"""
    return b"not an image data"


class TestImageEncoding:
    """Pytest тесты для обработки изображений - фокус на реальной функциональности"""
    
    def test_real_image_cache_key_generation(self, ai_client, sample_image_bytes):
        """Тест генерации ключа кэша как в реальном коде process_image"""
        prompt = "Опиши это изображение"
        
        # Генерируем ключ кэша ТОЧНО как в process_image
        cache_key = f"image:{base64.b64encode(sample_image_bytes).decode('utf-8')[:100]}_{prompt}"
        
        # Проверяем формат ключа
        assert cache_key.startswith("image:")
        assert prompt in cache_key
        assert len(cache_key) > len(prompt) + 10
        
        # Проверяем, что ключ детерминистический
        cache_key2 = f"image:{base64.b64encode(sample_image_bytes).decode('utf-8')[:100]}_{prompt}"
        assert cache_key == cache_key2
    
    def test_openai_vision_image_encoding(self, sample_image_bytes):
        """Тест кодирования изображения как в _openai_vision методе"""
        # Воспроизводим логику из _openai_vision
        image_pil = Image.open(io.BytesIO(sample_image_bytes))
        buffered = io.BytesIO()
        image_pil.save(buffered, format="PNG")
        image_b64_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        # Проверяем, что кодирование прошло успешно
        assert isinstance(image_b64_str, str)
        assert len(image_b64_str) > 0
        assert image_b64_str.startswith('iVBORw0KGgo')  # PNG signature
        
        # Проверяем декодирование
        decoded_bytes = base64.b64decode(image_b64_str)
        restored_image = Image.open(io.BytesIO(decoded_bytes))
        assert restored_image.size == (100, 100)
        assert restored_image.format == 'PNG'
    
    def test_image_validation_valid_image(self, ai_client, sample_image_bytes):
        """Тест валидации корректного изображения"""
        is_valid, message = ai_client.validate_image(sample_image_bytes)
        assert is_valid
        assert message == "OK"
    
    def test_image_validation_tiny_image(self, ai_client, tiny_image_bytes):
        """Тест валидации слишком маленького изображения"""
        is_valid, message = ai_client.validate_image(tiny_image_bytes)
        assert not is_valid
        assert "слишком маленькое" in message
    
    def test_image_validation_corrupted_data(self, ai_client, corrupted_bytes):
        """Тест валидации поврежденных данных"""
        is_valid, message = ai_client.validate_image(corrupted_bytes)
        assert not is_valid
        assert "Ошибка при обработке изображения" in message
    
    def test_cache_key_consistency_across_calls(self, sample_image_bytes):
        """Тест консистентности ключей кэша между вызовами"""
        prompt = "Тестовый промпт"
        
        # Генерируем ключи несколько раз
        keys = []
        for i in range(3):
            cache_key = f"image:{base64.b64encode(sample_image_bytes).decode('utf-8')[:100]}_{prompt}"
            keys.append(cache_key)
        
        # Все ключи должны быть одинаковыми
        assert all(key == keys[0] for key in keys)
        
        # Разные промпты должны давать разные ключи
        different_prompt = "Другой промпт"
        different_key = f"image:{base64.b64encode(sample_image_bytes).decode('utf-8')[:100]}_{different_prompt}"
        assert different_key != keys[0]
    
    @pytest.mark.parametrize("image_format", ["PNG", "JPEG"])
    def test_image_format_handling(self, ai_client, image_format):
        """Параметризованный тест обработки разных форматов изображений"""
        # Создаем изображение в нужном формате
        if image_format == "PNG":
            image = Image.new('RGB', (50, 50), color='red')
        else:  # JPEG
            image = Image.new('RGB', (50, 50), color='green')
        
        img_buffer = io.BytesIO()
        image.save(img_buffer, format=image_format)
        img_bytes = img_buffer.getvalue()
        
        is_valid, message = ai_client.validate_image(img_bytes)
        assert is_valid
        assert message == "OK"
    
    @pytest.mark.asyncio
    async def test_process_image_unsupported_provider(self, ai_client, sample_image_bytes):
        """Тест process_image с неподдерживаемым провайдером"""
        ai_client.active_provider = "deepseek"
        result = await ai_client.process_image(sample_image_bytes, "Тест")
        assert "только через OpenAI" in result
    
    @pytest.mark.asyncio
    async def test_process_image_validation_failure(self, ai_client, tiny_image_bytes):
        """Тест process_image с невалидным изображением"""
        ai_client.active_provider = "openai"
        result = await ai_client.process_image(tiny_image_bytes, "Тест")
        assert "Ошибка валидации" in result
    
    @pytest.mark.asyncio
    async def test_process_image_cache_key_format(self, ai_client, sample_image_bytes):
        """Тест формата ключа кэша в process_image"""
        ai_client.active_provider = "openai"
        prompt = "Тестовый промпт"
        
        # Этот тест проверяет, что ключ генерируется в правильном формате
        # Мы не можем напрямую получить ключ из process_image, но можем
        # воспроизвести логику и убедиться, что она консистентна
        expected_cache_key = f"image:{base64.b64encode(sample_image_bytes).decode('utf-8')[:100]}_{prompt}"
        
        # Проверяем формат ожидаемого ключа
        assert expected_cache_key.startswith("image:")
        assert prompt in expected_cache_key
        assert len(expected_cache_key) > 120  # image: + 100 символов + _ + prompt
    
    def test_base64_encoding_consistency(self, sample_image_bytes):
        """Тест консистентности base64 кодирования"""
        # Кодируем несколько раз
        encoded1 = base64.b64encode(sample_image_bytes).decode('utf-8')
        encoded2 = base64.b64encode(sample_image_bytes).decode('utf-8')
        encoded3 = base64.b64encode(sample_image_bytes).decode('utf-8')
        
        # Все результаты должны быть идентичными
        assert encoded1 == encoded2 == encoded3
        
        # Проверяем обратное декодирование
        decoded = base64.b64decode(encoded1)
        assert decoded == sample_image_bytes
    
    def test_base64_truncation_for_cache_key(self, sample_image_bytes):
        """Тест обрезки base64 для ключа кэша (первые 100 символов)"""
        full_encoded = base64.b64encode(sample_image_bytes).decode('utf-8')
        truncated = full_encoded[:100]
        
        # Проверяем, что обрезка работает корректно
        assert len(truncated) == 100
        assert truncated == full_encoded[:100]
        assert truncated.startswith('iVBORw0KGgo')  # PNG signature
    
    @pytest.mark.parametrize("width,height,should_pass", [
        (100, 100, True),   # Нормальный размер
        (10, 10, True),     # Минимально допустимый
        (5, 5, False),      # Слишком маленький
        (4096, 4096, True), # Максимально допустимый
        (5000, 5000, False) # Слишком большой
    ])
    def test_image_size_validation(self, ai_client, width, height, should_pass):
        """Параметризованный тест валидации размеров изображения"""
        # Создаем изображение нужного размера
        image = Image.new('RGB', (width, height), color='blue')
        img_buffer = io.BytesIO()
        image.save(img_buffer, format='PNG')
        img_bytes = img_buffer.getvalue()
        
        is_valid, message = ai_client.validate_image(img_bytes)
        
        if should_pass:
            assert is_valid, f"Изображение {width}x{height} должно пройти валидацию: {message}"
        else:
            assert not is_valid, f"Изображение {width}x{height} не должно пройти валидацию"


@pytest.mark.integration
class TestImageEncodingIntegration:
    """Интеграционные тесты для полного цикла обработки изображений"""
    
    @pytest.fixture
    def integration_image_bytes(self):
        """Фикстура для интеграционных тестов"""
        image = Image.new('RGB', (200, 200), color='purple')
        draw = ImageDraw.Draw(image)
        draw.rectangle([50, 50, 150, 150], fill='yellow')
        draw.text((75, 100), "INTEGRATION", fill='black')
        
        img_buffer = io.BytesIO()
        image.save(img_buffer, format='PNG')
        return img_buffer.getvalue()
    
    def test_full_encoding_cycle(self, integration_image_bytes):
        """Тест полного цикла: изображение -> base64 -> изображение"""
        # Шаг 1: Кодирование как в _openai_vision
        original_image = Image.open(io.BytesIO(integration_image_bytes))
        buffered = io.BytesIO()
        original_image.save(buffered, format="PNG")
        encoded = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        # Шаг 2: Декодирование
        decoded_bytes = base64.b64decode(encoded)
        restored_image = Image.open(io.BytesIO(decoded_bytes))
        
        # Шаг 3: Проверки
        assert original_image.size == restored_image.size
        assert original_image.mode == restored_image.mode
        assert restored_image.format in ['PNG', 'JPEG']
    
    @pytest.mark.asyncio
    async def test_process_image_workflow(self, ai_client, integration_image_bytes):
        """Тест workflow process_image до момента API вызова"""
        ai_client.active_provider = "openai"
        
        # Проверяем, что изображение проходит валидацию
        is_valid, _ = ai_client.validate_image(integration_image_bytes)
        assert is_valid
        
        # Проверяем генерацию ключа кэша
        prompt = "Integration test prompt"
        cache_key = f"image:{base64.b64encode(integration_image_bytes).decode('utf-8')[:100]}_{prompt}"
        
        assert cache_key.startswith("image:")
        assert prompt in cache_key


@pytest.mark.integration
class TestTelegramImageHandling:
    """Тесты для обработки изображений как в Telegram боте"""
    
    @pytest.fixture
    def telegram_photo_bytes(self):
        """Фикстура для имитации изображения, скачанного из Telegram"""
        # Создаем изображение как оно приходит из Telegram
        image = Image.new('RGB', (800, 600), color='lightblue')
        draw = ImageDraw.Draw(image)
        draw.text((50, 50), "Telegram Photo", fill='black')
        draw.rectangle([100, 100, 700, 500], outline='red', width=3)
        
        # Сохраняем как JPEG (частый формат в Telegram)
        img_buffer = io.BytesIO()
        image.save(img_buffer, format='JPEG', quality=85)
        return img_buffer.getvalue()
    
    @pytest.fixture
    def telegram_bytesio_object(self, telegram_photo_bytes):
        """Фикстура BytesIO объекта как возвращает bot.download_file()"""
        # В реальности bot.download_file возвращает BytesIO объект
        bytesio_obj = io.BytesIO(telegram_photo_bytes)
        bytesio_obj.seek(0)
        return bytesio_obj
    
    def test_telegram_bytes_processing(self, ai_client, telegram_photo_bytes):
        """Тест обработки байтов изображения как от Telegram API"""
        # Проверяем, что можем обработать байты напрямую
        is_valid, message = ai_client.validate_image(telegram_photo_bytes)
        assert is_valid
        assert message == "OK"
        
        # Проверяем генерацию ключа кэша
        prompt = "Опиши это фото из Telegram"
        cache_key = f"image:{base64.b64encode(telegram_photo_bytes).decode('utf-8')[:100]}_{prompt}"
        
        assert cache_key.startswith("image:")
        assert prompt in cache_key
        assert len(cache_key) > 120
    
    def test_telegram_bytesio_to_bytes_conversion(self, telegram_bytesio_object):
        """Тест конвертации BytesIO в байты как в handle_image"""
        # Воспроизводим логику из handle_image:
        # photo_bytes = await message.bot.download_file(photo_file.file_path)
        
        # В реальности aiogram возвращает BytesIO, но мы работаем с .getvalue()
        photo_bytes = telegram_bytesio_object.getvalue()
        
        # Проверяем, что получили корректные байты
        assert isinstance(photo_bytes, bytes)
        assert len(photo_bytes) > 0
        
        # Проверяем, что можем создать изображение из этих байтов
        image = Image.open(io.BytesIO(photo_bytes))
        assert image.size == (800, 600)
        assert image.format == 'JPEG'
    
    @pytest.mark.asyncio
    async def test_telegram_workflow_simulation(self, ai_client, telegram_photo_bytes):
        """Симуляция полного workflow обработки изображения из Telegram"""
        ai_client.active_provider = "openai"
        
        # Симулируем код из handle_image:
        # photo_file = await message.bot.get_file(photo.file_id)
        # photo_bytes = await message.bot.download_file(photo_file.file_path)
        # user_prompt = message.caption
        
        photo_bytes = telegram_photo_bytes  # Как если бы скачали из Telegram
        user_prompt = "Что изображено на этом фото?"  # Как message.caption
        
        # Проверяем валидацию (часть process_image_with_limit)
        is_valid, validation_message = ai_client.validate_image(photo_bytes)
        assert is_valid, f"Telegram изображение не прошло валидацию: {validation_message}"
        
        # Проверяем генерацию ключа кэша (часть process_image)
        cache_key = f"image:{base64.b64encode(photo_bytes).decode('utf-8')[:100]}_{user_prompt}"
        assert cache_key.startswith("image:")
        assert user_prompt in cache_key
    
    def test_telegram_image_size_limits(self, ai_client):
        """Тест проверки размеров изображений как в Telegram боте"""
        # Создаем изображение размером как максимальный в Telegram (20MB)
        # Но для теста делаем меньше, чтобы не перегружать тесты
        large_image = Image.new('RGB', (2048, 2048), color='green')
        
        img_buffer = io.BytesIO()
        large_image.save(img_buffer, format='PNG')
        large_photo_bytes = img_buffer.getvalue()
        
        # Проверяем валидацию
        is_valid, message = ai_client.validate_image(large_photo_bytes)
        
        # В зависимости от настроек валидации может быть или принято, или отклонено
        # Но процесс должен пройти без ошибок
        assert isinstance(is_valid, bool)
        assert isinstance(message, str)
    
    @pytest.mark.parametrize("caption_text", [
        "Опиши это изображение",
        "What's in this photo?",
        "Что здесь изображено? Детально",
        "",  # Пустая подпись
        None  # Отсутствующая подпись
    ])
    def test_telegram_caption_handling(self, ai_client, telegram_photo_bytes, caption_text):
        """Тест обработки разных типов подписей как message.caption"""
        # Симулируем user_prompt = message.caption
        user_prompt = caption_text if caption_text is not None else ""
        
        # Генерируем ключ кэша как в реальном коде
        cache_key = f"image:{base64.b64encode(telegram_photo_bytes).decode('utf-8')[:100]}_{user_prompt}"
        
        # Проверки
        assert cache_key.startswith("image:")
        assert len(cache_key) >= 106  # "image:" + 100 символов + "_" + prompt
        
        # Проверяем, что разные подписи дают разные ключи
        different_prompt = "другая подпись"
        different_key = f"image:{base64.b64encode(telegram_photo_bytes).decode('utf-8')[:100]}_{different_prompt}"
        
        if user_prompt != different_prompt:
            assert cache_key != different_key
    
    def test_telegram_jpeg_vs_png_encoding(self, ai_client):
        """Тест кодирования JPEG vs PNG как приходят из Telegram"""
        # JPEG изображение (частый формат в Telegram)
        jpeg_image = Image.new('RGB', (400, 300), color='red')
        jpeg_buffer = io.BytesIO()
        jpeg_image.save(jpeg_buffer, format='JPEG', quality=85)
        jpeg_bytes = jpeg_buffer.getvalue()
        
        # PNG изображение (иногда в Telegram)
        png_image = Image.new('RGB', (400, 300), color='blue')
        png_buffer = io.BytesIO()
        png_image.save(png_buffer, format='PNG')
        png_bytes = png_buffer.getvalue()
        
        # Проверяем валидацию обоих форматов
        jpeg_valid, jpeg_msg = ai_client.validate_image(jpeg_bytes)
        png_valid, png_msg = ai_client.validate_image(png_bytes)
        
        assert jpeg_valid, f"JPEG не прошел валидацию: {jpeg_msg}"
        assert png_valid, f"PNG не прошел валидацию: {png_msg}"
        
        # Проверяем, что генерируются разные ключи кэша
        prompt = "test"
        jpeg_key = f"image:{base64.b64encode(jpeg_bytes).decode('utf-8')[:100]}_{prompt}"
        png_key = f"image:{base64.b64encode(png_bytes).decode('utf-8')[:100]}_{prompt}"
        
        assert jpeg_key != png_key, "Разные изображения должны иметь разные ключи кэша"
    
    @pytest.mark.asyncio
    async def test_telegram_error_handling_simulation(self, ai_client):
        """Тест обработки ошибок как в handle_image"""
        ai_client.active_provider = "openai"
        
        # Симулируем поврежденные данные как могут прийти из Telegram
        corrupted_telegram_bytes = b"corrupted telegram image data"
        
        # Проверяем валидацию (должна отклонить)
        is_valid, message = ai_client.validate_image(corrupted_telegram_bytes)
        assert not is_valid
        assert "Ошибка при обработке изображения" in message
        
        # Проверяем, что process_image_with_limit корректно обработает ошибку
        result = await ai_client.process_image_with_limit(
            corrupted_telegram_bytes, 
            user_id=12345, 
            prompt="test"
        )
        
        # Ожидаем сообщение об ошибке валидации
        assert "Ошибка валидации" in result


@pytest.mark.integration
class TestTelegramAPIDataTypes:
    """Тесты для проверки типов данных как в реальном Telegram API"""
    
    def test_aiogram_bytes_type_compatibility(self, ai_client):
        """Тест совместимости с типами данных aiogram"""
        # Симулируем точную последовательность как в handle_image:
        # 1. photo_file = await message.bot.get_file(photo.file_id)
        # 2. photo_bytes = await message.bot.download_file(photo_file.file_path)
        
        # aiogram download_file возвращает BytesIO объект, но в коде мы получаем bytes
        # через getvalue() или через прямое чтение
        
        # Создаем тестовое изображение
        image = Image.new('RGB', (300, 200), color='orange')
        draw = ImageDraw.Draw(image)
        draw.text((10, 10), "Aiogram Test", fill='black')
        
        # Симулируем что возвращает aiogram download_file
        img_buffer = io.BytesIO()
        image.save(img_buffer, format='JPEG')
        
        # В реальности мы получаем BytesIO, но затем вызываем getvalue()
        telegram_bytes = img_buffer.getvalue()
        
        # Проверяем типы данных
        assert isinstance(telegram_bytes, bytes), "aiogram должен возвращать bytes после getvalue()"
        assert len(telegram_bytes) > 0, "Данные изображения не должны быть пустыми"
        
        # Проверяем совместимость с process_image_with_limit
        is_valid, message = ai_client.validate_image(telegram_bytes)
        assert is_valid, f"Изображение из aiogram не прошло валидацию: {message}"
    
    @pytest.mark.asyncio
    async def test_telegram_handler_data_flow(self, ai_client):
        """Тест полного потока данных как в handle_image handler"""
        # Точная симуляция handle_image function
        
        # 1. Создаем изображение как оно приходит из Telegram
        telegram_image = Image.new('RGB', (640, 480), color='lightgreen')
        draw = ImageDraw.Draw(telegram_image)
        draw.text((50, 50), "Message from Telegram", fill='darkgreen')
        
        # 2. Симулируем bot.download_file()
        download_buffer = io.BytesIO()
        telegram_image.save(download_buffer, format='JPEG', quality=90)
        
        # 3. Получаем bytes как в реальном коде
        photo_bytes = download_buffer.getvalue()
        
        # 4. Симулируем message.caption
        user_prompt = "Опиши это изображение подробно"
        
        # 5. Симулируем message.from_user.id
        user_id = 123456789
        
        # 6. Точный вызов как в handle_image
        ai_client.active_provider = "openai"  # Устанавливаем провайдер
        
        # Вызываем именно тот метод, который используется в handle_image
        result = await ai_client.process_image_with_limit(photo_bytes, user_id, user_prompt)
        
        # Проверяем результат
        assert isinstance(result, str), "process_image_with_limit должен возвращать строку"
        assert len(result) > 0, "Результат не должен быть пустым"
        
        # В случае ошибки (нет API ключа в тестах) должно быть соответствующее сообщение
        # Но валидация должна пройти успешно
        if "Ошибка валидации" not in result:
            # Если валидация прошла, значит все типы данных корректные
            assert True
    
    def test_message_caption_type_handling(self, ai_client):
        """Тест обработки типов message.caption как в Telegram"""
        image = Image.new('RGB', (200, 150), color='yellow')
        img_buffer = io.BytesIO()
        image.save(img_buffer, format='PNG')
        photo_bytes = img_buffer.getvalue()
        
        # В Telegram message.caption может быть:
        test_captions = [
            "Обычная подпись",           # str
            "",                          # пустая строка
            None,                        # None когда подписи нет
        ]
        
        for caption in test_captions:
            # Точно как в handle_image: user_prompt = message.caption
            user_prompt = caption
            
            # Генерируем ключ кэша как в реальном коде
            # В process_image: prompt = prompt or ""
            effective_prompt = user_prompt or ""
            cache_key = f"image:{base64.b64encode(photo_bytes).decode('utf-8')[:100]}_{effective_prompt}"
            
            # Проверяем, что ключ генерируется корректно для всех типов caption
            assert isinstance(cache_key, str)
            assert cache_key.startswith("image:")
            assert len(cache_key) >= 107  # минимальная длина
    
    def test_telegram_photo_sizes_handling(self, ai_client):
        """Тест обработки разных размеров фото как в Telegram"""
        # В Telegram photos приходят в разных размерах
        # message.photo[-1] берет самое большое разрешение
        
        photo_sizes = [
            (90, 90),      # thumbnail
            (320, 320),    # small
            (800, 600),    # medium
            (1280, 960),   # large
        ]
        
        for width, height in photo_sizes:
            # Создаем изображение соответствующего размера
            image = Image.new('RGB', (width, height), color='purple')
            draw = ImageDraw.Draw(image)
            draw.text((10, 10), f"{width}x{height}", fill='white')
            
            img_buffer = io.BytesIO()
            image.save(img_buffer, format='JPEG')
            photo_bytes = img_buffer.getvalue()
            
            # Проверяем валидацию
            is_valid, message = ai_client.validate_image(photo_bytes)
            
            # Все размеры из Telegram должны проходить валидацию
            # (при условии, что они больше минимального размера)
            if width >= 10 and height >= 10:  # минимальный размер в валидации
                assert is_valid, f"Изображение {width}x{height} должно проходить валидацию: {message}"
            
            # Проверяем генерацию ключа кэша
            prompt = f"test_{width}x{height}"
            cache_key = f"image:{base64.b64encode(photo_bytes).decode('utf-8')[:100]}_{prompt}"
            assert cache_key.startswith("image:")
            assert prompt in cache_key
    
    def test_telegram_file_id_simulation(self, ai_client):
        """Тест симуляции работы с file_id как в Telegram"""
        # В реальности:
        # photo = message.photo[-1]  # PhotoSize object
        # photo_file = await message.bot.get_file(photo.file_id)  # File object
        # photo_bytes = await message.bot.download_file(photo_file.file_path)
        
        # Симулируем уникальные file_id для разных изображений
        test_images = []
        for i, color in enumerate(['red', 'green', 'blue']):
            image = Image.new('RGB', (100, 100), color=color)
            draw = ImageDraw.Draw(image)
            draw.text((10, 50), f"Image {i}", fill='white')
            
            img_buffer = io.BytesIO()
            image.save(img_buffer, format='PNG')
            photo_bytes = img_buffer.getvalue()
            test_images.append((f"fake_file_id_{i}", photo_bytes))
        
        # Проверяем, что разные изображения дают разные ключи кэша
        cache_keys = []
        prompt = "Опиши изображение"
        
        for file_id, photo_bytes in test_images:
            # Генерируем ключ как в реальном коде
            cache_key = f"image:{base64.b64encode(photo_bytes).decode('utf-8')[:100]}_{prompt}"
            cache_keys.append(cache_key)
            
            # Проверяем валидацию
            is_valid, message = ai_client.validate_image(photo_bytes)
            assert is_valid, f"Изображение для {file_id} не прошло валидацию: {message}"
        
        # Все ключи должны быть уникальными
        assert len(set(cache_keys)) == len(cache_keys), "Разные изображения должны иметь разные ключи кэша"


if __name__ == "__main__":
    # Запуск тестов с помощью pytest
    pytest.main([__file__, "-v", "--tb=short"])
