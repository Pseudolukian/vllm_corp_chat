# Производительность и балансировка

## Схема
- Клаент → Caddy (TLS, HTTP/2/3, редиректы, HSTS) → Open WebUI (uvicorn).
- Open WebUI → внутренний LB `litellm-lb` (Caddy, `least_conn`, health-check /health/liveliness) → три экземпляра LiteLLM (`litellm-1..3`) → vLLM API (`VLLM_API_BASE`).

## Ключевые опции и переменные
- Caddy (фронт):
  - `ulimit nofile 65536` для множества соединений.
  - Таймауты в `Caddyfile` транспортного блока (5m read/write, 30s dial).
  - Healthcheck в compose: `wget --spider http://open-webui:8080/health`.
- Open WebUI:
  - `OPENAI_API_BASE_URL=http://litellm-lb:4000/v1` — единая точка для балансировки.
  - `UVICORN_WORKERS` (по умолчанию 4) — масштаб рабочих процессов WebUI.
- LiteLLM:
  - Образ `ghcr.io/berriai/litellm:main-latest`, конфиг `litellm_config.yaml`, health `/health/liveliness`.
  - Общий мастер-ключ `LITELLM_MASTER_KEY`; путь к vLLM задаётся `VLLM_API_BASE`.
- Внутренний LB LiteLLM (`litellm_lb.Caddyfile`):
  - Политика `least_conn`, health `/health/liveliness`, таймауты 5m/5m/10s, upstreams `litellm-1..3`.

## Масштабирование
- Добавить LiteLLM: копировать сервис `litellm-N` в compose и вписать в `to` блока `reverse_proxy` файла `litellm_lb.Caddyfile` + в `depends_on` Open WebUI.
- Увеличить воркеры Open WebUI: `UVICORN_WORKERS=8..12` при достаточных CPU.
- Вертикально масштабировать vLLM: больше GPU/CPU, корректировать его флаги (`--gpu-memory-utilization`, `--max-num-batched-tokens`, `--max-model-len`).
- При высоком трафике HTTP/3: поднять системные буферы UDP (sysctl согласно рекомендации quic-go) и `nofile` ещё выше.

## Проверки
- `docker compose ps` — здоровье контейнеров.
- `docker exec caddy-proxy wget -qO- http://open-webui:8080/health` — доступность WebUI из фронта.
- `docker exec litellm-lb wget -qO- http://localhost:4000/v1/models --header "Authorization: Bearer <key>"` — ответ LB к LiteLLM.
- Метрики Caddy: `http://localhost:2019/metrics` (из контейнера).