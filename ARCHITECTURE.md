# Архитектура системы

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Internet/Users                             │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │ HTTPS
                                  │
┌─────────────────────────────────▼───────────────────────────────────┐
│                        ПРОКСИ СЕРВЕР                                 │
│  (chat.sweetsweep.online)                                            │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  Caddy (Reverse Proxy + SSL)                               │    │
│  │  - Автоматические SSL сертификаты (Let's Encrypt)         │    │
│  │  - HTTPS → HTTP проксирование                              │    │
│  │  - Порты: 80, 443                                          │    │
│  └────────────────────────┬───────────────────────────────────┘    │
│                           │ HTTP                                    │
│                           │                                         │
│  ┌────────────────────────▼───────────────────────────────────┐    │
│  │  OpenWebUI                                                  │    │
│  │  - Web интерфейс для чата                                  │    │
│  │  - Управление пользователями                               │    │
│  │  - Порт: 8080                                              │    │
│  └────────────────────────┬───────────────────────────────────┘    │
│                           │ HTTP (OpenAI API)                       │
│                           │                                         │
│  ┌────────────────────────▼───────────────────────────────────┐    │
│  │  LiteLLM                                                    │    │
│  │  - Прокси между OpenWebUI и vLLM                           │    │
│  │  - Унификация API (OpenAI-compatible)                      │    │
│  │  - Порт: 4000                                              │    │
│  │  - Config: litellm_config.yaml                             │    │
│  └────────────────────────┬───────────────────────────────────┘    │
│                           │                                         │
└───────────────────────────┼─────────────────────────────────────────┘
                            │ HTTP (OpenAI API)
                            │ ${VLLM_API_BASE}
                            │
┌───────────────────────────▼─────────────────────────────────────────┐
│                      vLLM СЕРВЕР (УДАЛЕННАЯ МАШИНА)                 │
│  - LLM Inference Engine                                              │
│  - NVIDIA GPU                                                        │
│  - OpenAI-compatible API                                             │
│  - Порт: 8000                                                        │
│                                                                      │
│  Примеры моделей:                                                    │
│  - mistralai/Mistral-7B-Instruct-v0.2                               │
│  - meta-llama/Llama-2-7b-chat-hf                                    │
│  - codellama/CodeLlama-7b-Instruct-hf                               │
└──────────────────────────────────────────────────────────────────────┘
```

## Поток данных

### Пользовательский запрос

```
User Request
    ↓
[1] HTTPS Request → Caddy (chat.sweetsweep.online:443)
    ↓
[2] HTTP → OpenWebUI (:8080)
    ↓
[3] POST /v1/chat/completions → LiteLLM (:4000)
    ↓
[4] POST /v1/chat/completions → vLLM Server (:8000)
    ↓
[5] GPU Inference (Model Processing)
    ↓
[6] Response ← vLLM Server
    ↓
[7] Response ← LiteLLM (format conversion if needed)
    ↓
[8] Response ← OpenWebUI (render in UI)
    ↓
[9] HTTPS Response ← Caddy
    ↓
User receives response
```

## Docker Networks

### Сеть `internal`
- litellm
- open-webui

**Назначение:** Внутренняя коммуникация между сервисами

### Сеть `web`
- caddy
- open-webui

**Назначение:** Доступ к OpenWebUI из интернета через Caddy

## Volumes

### open_webui_data
- Путь в контейнере: `/app/backend/data`
- Содержит: база данных SQLite, пользователи, настройки, история чатов

### caddy_data
- Путь в контейнере: `/data`
- Содержит: SSL сертификаты

### caddy_config
- Путь в контейнере: `/config`
- Содержит: конфигурация Caddy

## Порты

| Сервис | Внутренний | Внешний | Описание |
|--------|-----------|---------|----------|
| Caddy | 80, 443 | 80, 443 | HTTP/HTTPS |
| OpenWebUI | 8080 | - | Web UI (только internal) |
| LiteLLM | 4000 | 4000 | API Proxy |
| vLLM | 8000 | - | Удаленная машина |

## Environment Variables

### Критические переменные

| Переменная | Где используется | Назначение |
|-----------|-----------------|-----------|
| `VLLM_API_BASE` | LiteLLM | URL vLLM сервера |
| `LITELLM_MASTER_KEY` | LiteLLM, OpenWebUI | API ключ аутентификации |
| `WEBUI_SECRET_KEY` | OpenWebUI | Секретный ключ для сессий |
| `ENABLE_SIGNUP` | OpenWebUI | Разрешить регистрацию |

## Конфигурационные файлы

### compose.yaml
Определяет все сервисы, сети и тома

### litellm_config.yaml
Конфигурация LiteLLM:
- Список моделей
- URL vLLM сервера
- Параметры проксирования

### Caddyfile
Конфигурация Caddy:
- Домен
- SSL настройки
- Reverse proxy правила
- Security headers

### .env
Переменные окружения:
- API ключи
- URLs
- Секреты

## Security

### SSL/TLS
- Caddy автоматически получает SSL сертификаты от Let's Encrypt
- HTTPS обязателен для доступа из интернета
- HSTS включен

### Authentication
- OpenWebUI требует логин/пароль
- LiteLLM требует API ключ (`LITELLM_MASTER_KEY`)
- vLLM доступен только из внутренней сети

### Network Isolation
- vLLM сервер не должен быть доступен из интернета
- Только прокси-сервер имеет доступ к vLLM
- Используйте firewall/VPN для защиты vLLM

## Масштабирование

### Горизонтальное

1. **Несколько vLLM серверов:**
   - Добавьте несколько vLLM backend в `litellm_config.yaml`
   - LiteLLM автоматически распределит нагрузку

2. **Load balancing:**
   - Настройте nginx/HAProxy перед vLLM серверами
   - Укажите load balancer URL в `VLLM_API_BASE`

### Вертикальное

1. **Увеличьте ресурсы vLLM:**
   - Больше GPU
   - Больше RAM
   - `--tensor-parallel-size` для multi-GPU

2. **Оптимизация:**
   - `--enable-prefix-caching`
   - `--gpu-memory-utilization 0.95`
   - Квантизация модели

## Мониторинг

### Health checks
- Все сервисы имеют health checks
- Docker автоматически перезапустит упавшие контейнеры

### Логи
```bash
# Все сервисы
docker compose logs -f

# Конкретный сервис
docker compose logs -f litellm
```

### Метрики
- vLLM: Prometheus metrics на `/metrics`
- Caddy: Metrics на `:2019/metrics`
- OpenWebUI: встроенная аналитика

## Backup

### Критические данные

1. **OpenWebUI база данных:**
```bash
docker compose exec open-webui \
    tar czf /tmp/backup.tar.gz /app/backend/data
docker cp open-webui:/tmp/backup.tar.gz ./backup-$(date +%F).tar.gz
```

2. **Конфигурация:**
```bash
tar czf config-backup-$(date +%F).tar.gz \
    .env compose.yaml litellm_config.yaml Caddyfile
```

3. **SSL сертификаты (Caddy):**
```bash
docker run --rm -v vllm_corp_chat_caddy_data:/data \
    -v $(pwd):/backup alpine \
    tar czf /backup/caddy-certs-$(date +%F).tar.gz /data
```

## Disaster Recovery

### Восстановление из backup

1. Восстановите файлы конфигурации
2. Восстановите .env
3. Запустите `docker compose up -d`
4. Восстановите OpenWebUI данные:
```bash
docker cp backup.tar.gz open-webui:/tmp/
docker compose exec open-webui \
    tar xzf /tmp/backup.tar.gz -C /
docker compose restart open-webui
```
