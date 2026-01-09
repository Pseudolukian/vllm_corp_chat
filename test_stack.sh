#!/bin/bash
# Скрипт для проверки работоспособности стека

set -e

echo "=== Проверка vLLM Corporate Chat Stack ==="
echo ""

# Загрузить переменные окружения
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

VLLM_API_BASE=${VLLM_API_BASE:-http://192.168.1.100:8000}
LITELLM_KEY=${LITELLM_MASTER_KEY:-sk-1234}

echo "1. Проверка Docker контейнеров..."
docker compose ps

echo ""
echo "2. Проверка vLLM сервера..."
echo "   URL: ${VLLM_API_BASE}"
if curl -s -f "${VLLM_API_BASE}/health" > /dev/null 2>&1; then
    echo "   ✓ vLLM сервер доступен"
else
    echo "   ✗ vLLM сервер недоступен!"
    echo "   Проверьте:"
    echo "   - vLLM запущен на удаленной машине"
    echo "   - Порт 8000 открыт"
    echo "   - VLLM_API_BASE правильно настроен в .env"
fi

echo ""
echo "3. Проверка LiteLLM..."
if curl -s -f "http://localhost:4000/health" > /dev/null 2>&1; then
    echo "   ✓ LiteLLM доступен"
    
    echo ""
    echo "4. Тест запроса через LiteLLM..."
    RESPONSE=$(curl -s -X POST http://localhost:4000/v1/chat/completions \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer ${LITELLM_KEY}" \
      -d '{
        "model": "vllm-model",
        "messages": [{"role": "user", "content": "Say hello in one word"}],
        "max_tokens": 10
      }' 2>&1)
    
    if echo "$RESPONSE" | grep -q "choices"; then
        echo "   ✓ LiteLLM успешно проксирует запросы в vLLM"
        echo "   Ответ: $(echo $RESPONSE | jq -r '.choices[0].message.content' 2>/dev/null || echo 'N/A')"
    else
        echo "   ✗ Ошибка при проксировании:"
        echo "$RESPONSE" | jq . 2>/dev/null || echo "$RESPONSE"
    fi
else
    echo "   ✗ LiteLLM недоступен!"
    echo "   Проверьте: docker compose logs litellm"
fi

echo ""
echo "5. Проверка OpenWebUI..."
if curl -s -f "http://localhost:8080/health" > /dev/null 2>&1; then
    echo "   ✓ OpenWebUI доступен"
else
    echo "   ✗ OpenWebUI недоступен!"
    echo "   Проверьте: docker compose logs open-webui"
fi

echo ""
echo "6. Проверка Caddy..."
if docker compose ps caddy | grep -q "Up"; then
    echo "   ✓ Caddy запущен"
    echo "   URL: https://chat.sweetsweep.online"
else
    echo "   ✗ Caddy не запущен!"
    echo "   Проверьте: docker compose logs caddy"
fi

echo ""
echo "=== Проверка завершена ==="
echo ""
echo "Если все проверки прошли успешно, откройте:"
echo "https://chat.sweetsweep.online"
