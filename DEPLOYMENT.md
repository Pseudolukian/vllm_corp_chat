# Инструкция по развертыванию корпоративного LLM чата

## Требования

- Docker и Docker Compose
- Домен chat.sweetsweep.online с DNS записью A, указывающей на ваш сервер
- Доступ к vLLM серверу на другой машине

## Архитектура

```
Internet → Caddy (HTTPS) → OpenWebUI → LiteLLM → vLLM (remote server)
```

### Компоненты:

1. **Caddy** - Reverse proxy с автоматическим SSL
2. **OpenWebUI** - Web интерфейс для чата
3. **LiteLLM** - Прокси для унификации API между OpenWebUI и vLLM
4. **vLLM** - LLM сервер на отдельной машине (не в этом compose)

## Установка

### 1. Клонирование репозитория

```bash
git clone https://github.com/Pseudolukian/vllm_corp_chat.git
cd vllm_corp_chat
```

### 2. Настройка переменных окружения

```bash
cp .env.example .env
nano .env
```

Обязательно измените:

- `VLLM_API_BASE` - URL вашего vLLM сервера (например: http://192.168.1.100:8000)
- `WEBUI_SECRET_KEY` - сгенерируйте: `openssl rand -hex 32`
- `LITELLM_MASTER_KEY` - ключ для доступа к LiteLLM API

### 3. Очистка старых данных и запуск

Если вы обновляете существующую установку и хотите начать с чистого листа:

```bash
./clean_and_restart.sh
```

Или вручную:

```bash
# Остановка контейнеров
docker compose down

# Удаление старых томов
docker volume rm vllm_corp_chat_ollama_data 2>/dev/null || true
docker volume rm vllm_corp_chat_postgres_data 2>/dev/null || true  
docker volume rm vllm_corp_chat_litellm_data 2>/dev/null || true
docker volume rm vllm_corp_chat_open_webui_data 2>/dev/null || true

# Запуск
docker compose up -d
```

### 4. Проверка статуса

```bash
# Статус сервисов
docker compose ps

# Логи всех сервисов
docker compose logs -f

# Логи конкретного сервиса
docker compose logs -f litellm
docker compose logs -f open-webui
```

### 5. Создание первого пользователя

После запуска Open WebUI:

1. Откройте https://chat.sweetsweep.online
2. Зарегистрируйте первого пользователя - он автоматически станет администратором
3. После создания админа установите в .env: `ENABLE_SIGNUP=false`
4. Перезапустите: `docker compose restart open-webui`

### 6. Настройка модели в OpenWebUI

1. Войдите как администратор
2. Перейдите в Settings → Connections
3. Проверьте что OpenAI API подключен к `http://litellm:4000/v1`
4. В Settings → Models должна быть доступна модель `vllm-model`

## Настройка vLLM сервера

На удаленной машине с GPU запустите vLLM:

```bash
python -m vllm.entrypoints.openai.api_server \
    --model YOUR_MODEL_NAME \
    --host 0.0.0.0 \
    --port 8000
```

Или с помощью Docker:

```bash
docker run --gpus all \
    -p 8000:8000 \
    --ipc=host \
    vllm/vllm-openai:latest \
    --model YOUR_MODEL_NAME \
    --host 0.0.0.0
```

Замените `YOUR_MODEL_NAME` на вашу модель, например:
- `meta-llama/Llama-2-7b-chat-hf`
- `mistralai/Mistral-7B-Instruct-v0.2`

## Проверка работоспособности

### Проверка LiteLLM

```bash
curl http://localhost:4000/health
```

### Проверка связи LiteLLM → vLLM

```bash

### Мониторинг производительности

```bash
# GPU utilization
nvidia-smi -l 1

# vLLM metrics
curl http://localhost:8000/metrics

# Логи vLLM
docker compose logs -f vllm

# Статистика PostgreSQL
docker compose exec postgresql psql -U openwebui -c "SELECT * FROM pg_stat_activity;"
```

## Безопасность

1. **Регистрация отключена** - только admin может добавлять пользователей
2. **TLS включен** - автоматические сертификаты Let's Encrypt через Caddy
3. **Изоляция сети** - vLLM и PostgreSQL недоступны извне
4. **Права пользователей** - только admin может управлять настройками

## Резервное копирование

```bash
# Backup PostgreSQL
docker compose exec postgresql pg_dump -U openwebui openwebui > backup_$(date +%Y%m%d).sql

# Backup Open WebUI data
docker run --rm -v open_webui_data:/data -v $(pwd):/backup alpine tar czf /backup/openwebui_backup_$(date +%Y%m%d).tar.gz /data

# Backup models (если нужно)
docker run --rm -v llm_models_value:/models -v $(pwd):/backup alpine tar czf /backup/models_backup_$(date +%Y%m%d).tar.gz /models
```

## Обновление

```bash
# Обновление образов
docker compose pull

# Перезапуск с новыми образами
docker compose up -d

# Очистка старых образов
docker image prune -a
```

## Масштабирование

Для большей нагрузки (100+ пользователей):

1. Увеличьте `WORKERS` в Open WebUI
2. Настройте `tensor-parallel-size` для использования нескольких GPU
3. Добавьте реплики Open WebUI с балансировкой нагрузки в Caddy
4. Используйте отдельный сервер для PostgreSQL с репликацией

## Troubleshooting

### vLLM не стартует

```bash
# Проверьте CUDA
docker run --rm --runtime=nvidia nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi

# Логи vLLM
docker compose logs vllm
```

### Open WebUI не подключается к vLLM

```bash
# Проверьте health check
docker compose exec open-webui curl http://vllm:8000/health

# Проверьте сеть
docker compose exec open-webui ping vllm
```

### Нехватка памяти GPU

Уменьшите параметры в compose.yaml:
- `VLLM_GPU_MEMORY_UTILIZATION: 0.85`
- `VLLM_MAX_NUM_SEQS: 128`
- `VLLM_MAX_MODEL_LEN: 4096`

## Мониторинг

Рекомендуется добавить:
- Prometheus + Grafana для метрик
- Loki для логов
- Alertmanager для алертов

Пример dashboard метрик vLLM: время отклика, throughput, GPU utilization, cache hit rate.
