# QUICKSTART

## Шаг 1: Настройка переменных окружения

```bash
cd /root/vllm_corp_chat
nano .env
```

**Обязательно измените:**
- `VLLM_API_BASE` - укажите IP адрес вашего vLLM сервера (например: http://192.168.1.100:8000)
- `WEBUI_SECRET_KEY` - сгенерируйте: `openssl rand -hex 32`

## Шаг 2: Очистка старых данных

```bash
./clean_and_restart.sh
```

Этот скрипт:
- Остановит все контейнеры
- Удалит старые тома (ollama, postgres, litellm, openwebui)
- Создаст новые тома
- Запустит сервисы

## Шаг 3: Проверка работоспособности

```bash
./test_stack.sh
```

Скрипт проверит:
- Доступность vLLM сервера
- Работу LiteLLM прокси
- Проксирование запросов через LiteLLM → vLLM
- Статус OpenWebUI и Caddy

## Шаг 4: Создание администратора

1. Откройте https://chat.sweetsweep.online
2. Зарегистрируйте первого пользователя (он станет админом)
3. После регистрации админа отключите публичную регистрацию:

```bash
nano .env
# Измените: ENABLE_SIGNUP=false

docker compose restart open-webui
```

## Полезные команды

```bash
# Проверка статуса
docker compose ps

# Логи всех сервисов
docker compose logs -f

# Логи конкретного сервиса
docker compose logs -f litellm
docker compose logs -f open-webui

# Перезапуск сервисов
docker compose restart

# Полная остановка
docker compose down
```

## Если что-то не работает

1. **vLLM недоступен:**
   - Проверьте что vLLM запущен на удаленной машине
   - Проверьте `VLLM_API_BASE` в .env
   - Проверьте доступность: `curl http://YOUR_VLLM_IP:8000/health`

2. **LiteLLM не проксирует:**
   - Посмотрите логи: `docker compose logs litellm`
   - Проверьте litellm_config.yaml

3. **OpenWebUI не видит модель:**
   - Зайдите в Settings → Connections
   - Убедитесь что URL: `http://litellm:4000/v1`
   - API Key: значение из `LITELLM_MASTER_KEY` в .env

4. **SSL проблемы:**
   - Проверьте DNS: `nslookup chat.sweetsweep.online`
   - Логи Caddy: `docker compose logs caddy`

## Готово!

Теперь у вас работает:
- ✓ OpenWebUI на https://chat.sweetsweep.online
- ✓ LiteLLM прокси на http://localhost:4000
- ✓ Подключение к удаленному vLLM серверу
