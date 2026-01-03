# Инструкция по развертыванию корпоративного LLM чата

## Требования

- Docker и Docker Compose
- NVIDIA GPU (RTX 6000 Ada 48GB)
- NVIDIA Container Toolkit
- Домен chat.sweetsweep.online с DNS записью A, указывающей на ваш сервер

## Установка

### 1. Настройка переменных окружения

```bash
cp .env.example .env
nano .env
```

Измените:
- `POSTGRES_PASSWORD` - надежный пароль для PostgreSQL
- `WEBUI_SECRET_KEY` - сгенерируйте: `openssl rand -hex 32`

### 2. Подготовка модели

Скачайте модель в директорию `llm_models_value`:

```bash
# Создайте том для моделей
docker volume create llm_models_value

# Скачайте модель (пример с использованием huggingface-cli)
docker run --rm -v llm_models_value:/models -it python:3.11-slim bash
pip install huggingface-hub
huggingface-cli download meta-llama/Llama-2-7b-chat-hf --local-dir /models/models/llama-2-7b-chat-hf
```

Затем обновите в `compose.yaml` строку:
```yaml
--model /root/.cache/huggingface/models/your-model-name
```
на актуальный путь к модели.

### 3. Запуск сервисов

```bash
# Запуск всех сервисов
docker compose up -d

# Проверка статуса
docker compose ps

# Логи
docker compose logs -f
```

### 4. Создание администратора

После запуска Open WebUI, создайте первого пользователя (он станет администратором):

1. Откройте https://chat.sweetsweep.online
2. Зарегистрируйте первого пользователя - он автоматически получит права admin
3. После этого регистрация будет отключена (`ENABLE_SIGNUP: "false"`)

### 5. Добавление пользователей

Только администратор может добавлять новых пользователей:

1. Войдите как admin
2. Перейдите в Settings → Users
3. Добавьте пользователей вручную
4. Все новые пользователи получат роль "user" без прав управления

## Управление кешем vLLM

Служба `vllm-cache-manager` автоматически очищает кеш:
- Проверка каждый час
- Удаляет файлы старше 7 дней, если размер кеша превышает 20GB

Ручная очистка кеша:
```bash
# Очистить весь кеш
docker compose exec vllm-cache-manager sh -c 'rm -rf /cache/*'

# Перезапустить vLLM
docker compose restart vllm
```

## Оптимизация для 50+ пользователей

### vLLM параметры

- `VLLM_MAX_NUM_SEQS: 256` - максимум 256 одновременных последовательностей
- `VLLM_GPU_MEMORY_UTILIZATION: 0.90` - использование 90% GPU памяти
- `VLLM_ENABLE_PREFIX_CACHING: true` - кеширование общих префиксов
- `shm_size: 16gb` - разделяемая память для батчинга

### Open WebUI параметры

- `WORKERS: 4` - 4 рабочих процесса
- `TIMEOUT: 300` - таймаут 5 минут для длинных запросов

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
