import base64
import io
from openai import AsyncOpenAI
from PIL import Image
from config import Config
from .cache import CacheManager
from .constants import ROLES, DEFAULT_PROMPT, DEFAULT_ROLE, CACHE_PREFIX_TEXT, CACHE_PREFIX_IMAGE

cache = CacheManager()
aclient = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)

class OpenAIClient:
    @staticmethod
    async def process_text(text: str, role: str = DEFAULT_ROLE) -> str:
        """Обработка текста с указанием роли"""
        if role not in ROLES:
            role = DEFAULT_ROLE

        # Проверка кэша с учетом роли
        cache_key = f"{role}:{text}"
        cached_response = await cache.get("text", cache_key)
        if cached_response:
            return cached_response

        response = await aclient.chat.completions.create(model=Config.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": ROLES[role]},
            {"role": "user", "content": text},
        ],
        temperature=0.7)

        answer = response.choices[0].message.content
        # Сохраняем в кэш
        await cache.set(CACHE_PREFIX_TEXT, text, answer)
        return answer

    @staticmethod
    async def process_image(
            image_bytes: bytes,
            prompt: str = None,
            role: str = DEFAULT_ROLE
    ) -> str:
        """Обработка изображения с кастомным промптом или по умолчанию"""
        if role not in ROLES:
            role = DEFAULT_ROLE

        final_prompt = prompt or DEFAULT_PROMPT
        cache_key = f"{role}:{base64.b64encode(image_bytes).decode('utf-8')[:100]}_{final_prompt}"

        cached_response = await cache.get("image", cache_key)
        if cached_response:
            return cached_response

        # Конвертируем в base64 для OpenAI
        image_b64 = Image.open(io.BytesIO(image_bytes))
        buffered = io.BytesIO()
        image_b64.save(buffered, format="PNG")
        image_b64_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

        response = await aclient.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "system",
                    "content": ROLES[role]
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": final_prompt},
                        {
                            "type": "image_url",
                            "image_url": f"data:image/png;base64,{image_b64_str}",
                        },
                    ],
                }
            ],
            max_tokens=1000
        )

        answer = response.choices[0].message.content
        # Сохраняем в кэш
        await cache.set(CACHE_PREFIX_IMAGE, cache_key, answer)
        return answer