# Тексты и emoji для интерфейса
BUTTON_TEXTS = {
    "roles": {
        "assistant": "👨‍💻 Ассистент",
        "scientist": "🔬 Ученый",
        "creative": "🎨 Креатив",
        "developer": "💻 Разработчик"
    },
    "models": {
        "openai": "🟢 OpenAI",
        "deepseek": "🔵 DeepSeek"
    }
}

MODELS = {
    "openai": {
        "text": ["gpt-3.5-turbo", "gpt-4"],
        "vision": ["gpt-4-vision-preview"]
    },
    "deepseek": {
        "text": ["deepseek-chat"],
        "vision": []  # На момент написания DeepSeek не поддерживает vision
    }
}

ROLES = {
    "assistant": "Ты полезный ассистент, который дает точные и подробные ответы.",
    "scientist": "Ты ученый, объясняющий сложные концепции простым языком.",
    "creative": "Ты креативный писатель с богатым воображением.",
    "developer": "Ты senior разработчик, который пишет код на разных языках программирования.",
}

DEFAULT_ROLE = "assistant"
DEFAULT_MODEL = "openai"
DEFAULT_PROMPT = "Опиши это изображение подробно."

MAX_MESSAGE_LENGTH = 4000  # Лимит Telegram для одного сообщения
IMAGE_SIZE_LIMIT_MB = 10   # Макс. размер изображения

CACHE_PREFIX_TEXT = "text:"
CACHE_PREFIX_IMAGE = "image:"

CACHE_TTL_HOURS = 1