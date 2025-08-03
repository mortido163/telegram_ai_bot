import aiohttp
import asyncio
import base64
import io
import logging
import time
from .cache import CacheManager
from .constants import DEFAULT_MODEL, DEFAULT_ROLE, DEFAULT_PROMPT, MODELS, ROLES, CACHE_PREFIX_TEXT, CACHE_PREFIX_IMAGE
from .metrics import metrics
from config import Config
from openai import AsyncOpenAI
from PIL import Image
from typing import Optional

cache = CacheManager()
aclient = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
or_client = AsyncOpenAI(base_url=Config.OPENROUTER_URL, api_key=Config.OPENROUTER_API_KEY)

logger = logging.getLogger(__name__)

class AIClient:
    def __init__(self):
        self.active_provider = DEFAULT_MODEL
        self.deepseek_url = Config.DEEPSEEK_URL
        self.max_retries = 3
        self.retry_delay = 1

    async def set_provider(self, provider: str) -> bool:
        if provider not in MODELS:
            raise ValueError(f"Unknown provider: {provider}")

        if provider == "deepseek" and not Config.DEEPSEEK_API_KEY:
            raise ValueError("DeepSeek API key not configured")

        if provider == "openrouter" and not Config.OPENROUTER_API_KEY:
            raise ValueError("OpenRouter API key not configured")

        self.active_provider = provider
        logger.info(f"Provider changed to: {provider}")
        return True

    async def process_text(self, text: str, role: str = DEFAULT_ROLE) -> str:
        if role not in ROLES:
            role = DEFAULT_ROLE

        cache_key = f"{self.active_provider}:{role}:{text}"
        cached_response = await cache.get(CACHE_PREFIX_TEXT, cache_key)
        if cached_response:
            metrics.record_cache_hit()
            return cached_response

        metrics.record_cache_miss()

        for attempt in range(self.max_retries):
            start_time = time.time()
            try:
                if self.active_provider == "openai":
                    response = await self._openai_text(text, role)
                elif self.active_provider == "deepseek":
                    response = await self._deepseek_text(text, role)
                else:
                    response = await self._openrouter_text(text, role)
                
                response_time = time.time() - start_time
                
                if response:
                    metrics.record_request(self.active_provider, response_time, True)
                    await cache.set(CACHE_PREFIX_TEXT, cache_key, response)
                    return response
                else:
                    raise Exception("Empty response from AI provider")
                    
            except Exception as e:
                response_time = time.time() - start_time
                metrics.record_request(self.active_provider, response_time, False, str(e))
                logger.error(f"Attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    return f"Ошибка обработки запроса: {str(e)}"

    async def process_image(self, image_bytes: bytes, prompt: str = None, role: str = DEFAULT_ROLE) -> str:
        if self.active_provider != "openai":
            return "Извините, обработка изображений пока доступна только через OpenAI"

        if role not in ROLES:
            role = DEFAULT_ROLE

        final_prompt = prompt or DEFAULT_PROMPT
        cache_key = f"image:{base64.b64encode(image_bytes).decode('utf-8')[:100]}_{final_prompt}"

        cached_response = await cache.get(CACHE_PREFIX_IMAGE, cache_key)
        if cached_response:
            metrics.record_cache_hit()
            return cached_response

        metrics.record_cache_miss()

        for attempt in range(self.max_retries):
            start_time = time.time()
            try:
                response = await self._openai_vision(image_bytes, final_prompt)
                response_time = time.time() - start_time
                
                if response:
                    metrics.record_request("openai_vision", response_time, True)
                    await cache.set(CACHE_PREFIX_IMAGE, cache_key, response)
                    return response
                else:
                    raise Exception("Empty response from OpenAI Vision")
                    
            except Exception as e:
                response_time = time.time() - start_time
                metrics.record_request("openai_vision", response_time, False, str(e))
                logger.error(f"Vision attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    return f"Ошибка обработки изображения: {str(e)}"

    async def _openai_text(self, text: str, role: str) -> Optional[str]:
        try:
            response = await aclient.chat.completions.create(
                model=Config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": ROLES[role]},
                    {"role": "user", "content": text}
                ],
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error processing text with OpenAI: {e}")
            return None

    async def _deepseek_text(self, text: str, role: str) -> Optional[str]:
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {Config.DEEPSEEK_API_KEY}",
            }

            data = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": ROLES[role]},
                    {"role": "user", "content": text}
                ],
                "temperature": 0.7,
                "max_tokens": 1000
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.deepseek_url,
                    headers=headers,
                    json=data,
                    timeout=30
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result["choices"][0]["message"]["content"]
                    else:
                        raise Exception(f"DeepSeek API error: {response.status}")
        except Exception as e:
            logger.error(f"Error processing text with DeepSeek: {e}")
            return None

    async def _openrouter_text(self, text: str, role: str) -> Optional[str]:
        try:
            response = await or_client.chat.completions.create(
                model=Config.OPENAI_MODEL,
                extra_body={},
                messages=[
                    {"role": "system", "content": ROLES[role]},
                    {"role": "user", "content": text}
                ],
                max_tokens=1000
            )
            return f"{response.model}: {response.choices[0].message.content}"
        except Exception as e:
            logger.error(f"Error processing text with OpenAI: {e}")
            return None

    async def _openai_vision(self, image_bytes: bytes, prompt: str) -> Optional[str]:
        try:
            image_b64 = Image.open(io.BytesIO(image_bytes))
            buffered = io.BytesIO()
            image_b64.save(buffered, format="PNG")
            image_b64_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            
            response = await aclient.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": f"data:image/png;base64,{image_b64_str}",
                            },
                        ],
                    }
                ],
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error processing image with OpenAI Vision: {e}")
            return None