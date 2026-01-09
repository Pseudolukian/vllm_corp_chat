#!/bin/bash
set -e

echo "=== Очистка всех данных и перезапуск стека ==="
echo ""

# Остановить все контейнеры
echo "1. Останавливаем контейнеры..."
docker compose down

# Удалить старые тома
echo "2. Удаляем старые тома..."
docker volume rm vllm_corp_chat_ollama_data 2>/dev/null || true
docker volume rm vllm_corp_chat_postgres_data 2>/dev/null || true
docker volume rm vllm_corp_chat_litellm_data 2>/dev/null || true
docker volume rm vllm_corp_chat_open_webui_data 2>/dev/null || true

echo "3. Создаем новые тома..."
docker volume create vllm_corp_chat_open_webui_data

# Проверить .env файл
if [ ! -f .env ]; then
    echo "4. Создаем .env из .env.example..."
    cp .env.example .env
    echo "   ВНИМАНИЕ: Отредактируйте .env файл перед продолжением!"
    echo "   Особенно важно установить:"
    echo "   - VLLM_API_BASE (адрес вашего vLLM сервера)"
    echo "   - WEBUI_SECRET_KEY (сгенерируйте: openssl rand -hex 32)"
    echo ""
    read -p "Нажмите Enter после редактирования .env файла..."
fi

# Запустить сервисы
echo "5. Запускаем сервисы..."
docker compose up -d

echo ""
echo "=== Завершено! ==="
echo ""
echo "Проверьте статус: docker compose ps"
echo "Логи: docker compose logs -f"
echo ""
echo "Open WebUI будет доступен на: https://chat.sweetsweep.online"
echo "После первой регистрации установите ENABLE_SIGNUP=false в .env"
