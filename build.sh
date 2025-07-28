#!/bin/bash

# Скрипт для сборки Docker образа с различными опциями

echo "🐳 Сборка Docker образа для Telegram AI Bot"

# Проверяем аргументы
if [ "$1" = "alpine" ]; then
    echo "📦 Используем Alpine Linux версию"
    DOCKERFILE="Dockerfile.alpine"
    TAG="telegram-ai-bot:alpine"
elif [ "$1" = "slim" ]; then
    echo "📦 Используем Debian Slim версию"
    DOCKERFILE="Dockerfile"
    TAG="telegram-ai-bot:slim"
else
    echo "📦 Используем стандартную версию (Debian Slim)"
    DOCKERFILE="Dockerfile"
    TAG="telegram-ai-bot:latest"
fi

# Опции для решения проблем с сетью
BUILD_OPTS="--build-arg BUILDKIT_INLINE_CACHE=1 --no-cache"

# Пробуем собрать с различными опциями
echo "🔨 Сборка образа: $TAG"
echo "📄 Dockerfile: $DOCKERFILE"

# Первая попытка - стандартная сборка
echo "🔄 Попытка 1: Стандартная сборка"
if docker build $BUILD_OPTS -f $DOCKERFILE -t $TAG .; then
    echo "✅ Сборка успешна!"
    exit 0
fi

# Вторая попытка - с дополнительными опциями сети
echo "🔄 Попытка 2: С дополнительными опциями сети"
if docker build $BUILD_OPTS --network=host -f $DOCKERFILE -t $TAG .; then
    echo "✅ Сборка успешна!"
    exit 0
fi

# Третья попытка - с DNS
echo "🔄 Попытка 3: С DNS серверами"
if docker build $BUILD_OPTS --dns=8.8.8.8 --dns=8.8.4.4 -f $DOCKERFILE -t $TAG .; then
    echo "✅ Сборка успешна!"
    exit 0
fi

# Четвертая попытка - с прокси (если есть)
if [ ! -z "$HTTP_PROXY" ]; then
    echo "🔄 Попытка 4: С прокси"
    if docker build $BUILD_OPTS --build-arg HTTP_PROXY=$HTTP_PROXY --build-arg HTTPS_PROXY=$HTTPS_PROXY -f $DOCKERFILE -t $TAG .; then
        echo "✅ Сборка успешна!"
        exit 0
    fi
fi

echo "❌ Все попытки сборки не удались"
echo "💡 Рекомендации:"
echo "   1. Проверьте интернет соединение"
echo "   2. Попробуйте использовать VPN"
echo "   3. Используйте другой Dockerfile: ./build.sh alpine"
echo "   4. Очистите Docker кэш: docker system prune -a"
exit 1 