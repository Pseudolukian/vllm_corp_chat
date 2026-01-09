# vLLM Corporate Chat

Корпоративный чат с LLM на базе OpenWebUI, LiteLLM и vLLM.

## Быстрый старт

1. **Настройте .env файл:**
```bash
cp .env.example .env
nano .env
```

Обязательно измените:
- `VLLM_API_BASE` - адрес вашего vLLM сервера
- `WEBUI_SECRET_KEY` - сгенерируйте: `openssl rand -hex 32`

2. **Очистите старые данные и запустите:**
```bash
./clean_and_restart.sh
```

3. **Откройте браузер:**
```
https://chat.sweetsweep.online
```

4. **Зарегистрируйте первого пользователя** - он станет администратором

## Архитектура

```
User → Caddy (HTTPS) → OpenWebUI → LiteLLM → vLLM (remote)
```

### Компоненты

- **Caddy** - Reverse proxy с автоматическим SSL (Let's Encrypt)
- **OpenWebUI** - Веб-интерфейс для чата
- **LiteLLM** - Прокси-сервер для унификации API
- **vLLM** - Сервер LLM модели (на отдельной машине)

## Настройка vLLM сервера

На удаленной машине с GPU:

```bash
docker run --gpus all \
    -p 8000:8000 \
    --ipc=host \
    vllm/vllm-openai:latest \
    --model mistralai/Mistral-7B-Instruct-v0.2 \
    --host 0.0.0.0
```

Или используя Python:

```bash
python -m vllm.entrypoints.openai.api_server \
    --model mistralai/Mistral-7B-Instruct-v0.2 \
    --host 0.0.0.0 \
    --port 8000
```

## Конфигурация

### Основные переменные окружения (.env)

| Переменная | Описание | Пример |
|-----------|----------|--------|
| `VLLM_API_BASE` | URL vLLM сервера | `http://192.168.1.100:8000` |
| `LITELLM_MASTER_KEY` | API ключ LiteLLM | `sk-1234` |
| `WEBUI_SECRET_KEY` | Секретный ключ WebUI | `random_32_char_hex` |
| `ENABLE_SIGNUP` | Разрешить регистрацию | `true`/`false` |

### litellm_config.yaml

Конфигурация LiteLLM для проксирования на vLLM. По умолчанию настроен для подключения к vLLM используя OpenAI-совместимый API.

## Полезные команды

### Управление сервисами

```bash
# Запуск
docker compose up -d

# Остановка
docker compose down

# Перезапуск
docker compose restart

# Логи
docker compose logs -f

# Логи конкретного сервиса
docker compose logs -f litellm
```

### Проверка статуса

```bash
# Все сервисы
docker compose ps

# Проверка LiteLLM
curl http://localhost:4000/health

# Проверка связи с vLLM через LiteLLM
curl -X POST http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-1234" \
  -d '{
    "model": "vllm-model",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### Очистка данных

```bash
# Полная очистка и перезапуск
./clean_and_restart.sh

# Ручная очистка
docker compose down
docker volume rm vllm_corp_chat_open_webui_data
docker compose up -d
```

## Управление пользователями

1. Первый зарегистрированный пользователь становится администратором
2. После создания админа отключите регистрацию:
   - Установите `ENABLE_SIGNUP=false` в .env
   - Перезапустите: `docker compose restart open-webui`
3. Добавляйте пользователей через админ-панель OpenWebUI

## Безопасность

- SSL сертификаты управляются автоматически через Caddy
- LiteLLM требует API ключ (`LITELLM_MASTER_KEY`)
- OpenWebUI требует аутентификацию
- vLLM сервер должен быть доступен только из внутренней сети

## Troubleshooting

### LiteLLM не может подключиться к vLLM

1. Проверьте доступность vLLM сервера:
```bash
curl http://VLLM_IP:8000/health
```

2. Проверьте переменную `VLLM_API_BASE` в .env

3. Проверьте логи:
```bash
docker compose logs litellm
```

### OpenWebUI не видит модели

1. Проверьте что LiteLLM запущен:
```bash
docker compose ps litellm
```

2. Проверьте конфигурацию в Settings → Connections

3. Убедитесь что `OPENAI_API_BASE_URL` указывает на `http://litellm:4000/v1`

### Проблемы с SSL сертификатом

1. Проверьте DNS:
```bash
nslookup chat.sweetsweep.online
```

2. Проверьте логи Caddy:
```bash
docker compose logs caddy
```

## Документация

Подробная документация в [DEPLOYMENT.md](./DEPLOYMENT.md)

## Ссылки

- [vLLM Documentation](https://docs.vllm.ai/)
- [LiteLLM Documentation](https://docs.litellm.ai/)
- [OpenWebUI Documentation](https://docs.openwebui.com/)
- [Caddy Documentation](https://caddyserver.com/docs/)

## Лицензия

MIT
