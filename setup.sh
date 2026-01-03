#!/bin/bash

# Скрипт для первоначальной настройки

set -e

echo "=== Проверка требований ==="

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен"
    exit 1
fi
echo "✓ Docker установлен"

# Проверка Docker Compose
if ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose не установлен"
    exit 1
fi
echo "✓ Docker Compose установлен"

# Проверка NVIDIA runtime
if ! docker run --rm --runtime=nvidia nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi &> /dev/null; then
    echo "❌ NVIDIA Container Toolkit не настроен правильно"
    exit 1
fi
echo "✓ NVIDIA Container Toolkit работает"

echo ""
echo "=== Настройка переменных окружения ==="

if [ ! -f .env ]; then
    cp .env.example .env
    
    # Генерация случайного пароля для PostgreSQL
    POSTGRES_PASS=$(openssl rand -base64 32)
    sed -i "s/your_very_secure_password_here_change_me/$POSTGRES_PASS/" .env
    
    # Генерация secret key для Open WebUI
    WEBUI_SECRET=$(openssl rand -hex 32)
    sed -i "s/your_random_secret_key_here_change_me_generate_with_openssl/$WEBUI_SECRET/" .env
    
    echo "✓ Файл .env создан с автоматически сгенерированными паролями"
    echo ""
    echo "⚠️  ВАЖНО: Сохраните эти данные в безопасном месте!"
    echo ""
else
    echo "✓ Файл .env уже существует"
fi

echo ""
echo "=== Проверка DNS ==="

DOMAIN="chat.sweetsweep.online"
SERVER_IP=$(curl -s ifconfig.me)

echo "IP сервера: $SERVER_IP"
echo "Проверяем DNS для $DOMAIN..."

DOMAIN_IP=$(dig +short $DOMAIN | head -n1)

if [ -z "$DOMAIN_IP" ]; then
    echo "⚠️  DNS запись для $DOMAIN не найдена"
    echo "   Создайте A-запись, указывающую на $SERVER_IP"
else
    echo "DNS $DOMAIN указывает на: $DOMAIN_IP"
    if [ "$DOMAIN_IP" != "$SERVER_IP" ]; then
        echo "⚠️  IP адреса не совпадают! Обновите DNS запись."
    else
        echo "✓ DNS настроен правильно"
    fi
fi

echo ""
echo "=== Создание томов ==="

docker volume create llm_models_value
docker volume create vllm_cache
docker volume create postgres_data
docker volume create open_webui_data
docker volume create caddy_data
docker volume create caddy_config

echo "✓ Тома созданы"

echo ""
echo "=== Инструкции ==="
echo ""
echo "1. Скачайте модель в том llm_models_value"
echo "   Пример:"
echo "   docker run --rm -v llm_models_value:/root/.cache/huggingface -it python:3.11-slim bash"
echo "   pip install huggingface-hub"
echo "   huggingface-cli download <model-name> --local-dir /root/.cache/huggingface/models/<model-name>"
echo ""
echo "2. Обновите путь к модели в compose.yaml"
echo "   Замените: /root/.cache/huggingface/models/your-model-name"
echo ""
echo "3. Запустите сервисы:"
echo "   docker compose up -d"
echo ""
echo "4. Создайте первого пользователя (администратора):"
echo "   Откройте https://$DOMAIN и зарегистрируйтесь"
echo ""
echo "5. Мониторинг:"
echo "   docker compose logs -f"
echo "   docker compose ps"
echo ""
