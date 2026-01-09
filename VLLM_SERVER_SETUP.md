# Конфигурация vLLM сервера (удаленная машина)

Это инструкция для настройки vLLM на отдельной машине с GPU.

## Требования

- NVIDIA GPU
- NVIDIA Driver
- Docker + NVIDIA Container Toolkit
- Или: Python 3.10+ и CUDA

## Вариант 1: Docker (рекомендуется)

### Простой запуск

```bash
docker run --gpus all \
    -p 8000:8000 \
    --ipc=host \
    vllm/vllm-openai:latest \
    --model mistralai/Mistral-7B-Instruct-v0.2 \
    --host 0.0.0.0 \
    --port 8000
```

### Продакшн запуск с оптимизацией

```bash
docker run -d \
    --name vllm-server \
    --gpus all \
    -p 8000:8000 \
    --ipc=host \
    --restart unless-stopped \
    -v ~/.cache/huggingface:/root/.cache/huggingface \
    vllm/vllm-openai:latest \
    --model mistralai/Mistral-7B-Instruct-v0.2 \
    --host 0.0.0.0 \
    --port 8000 \
    --gpu-memory-utilization 0.9 \
    --max-model-len 4096 \
    --enable-prefix-caching \
    --disable-log-requests
```

### Параметры оптимизации

| Параметр | Описание | Рекомендация |
|----------|----------|--------------|
| `--gpu-memory-utilization` | Процент GPU памяти | 0.9 (90%) |
| `--max-model-len` | Макс. длина контекста | 4096-8192 |
| `--enable-prefix-caching` | Кеширование префиксов | Да |
| `--tensor-parallel-size` | Количество GPU | 1-8 |
| `--max-num-seqs` | Макс. одновременных запросов | 256 |

## Вариант 2: Python

### Установка

```bash
# Создать venv
python3 -m venv vllm-env
source vllm-env/bin/activate

# Установить vLLM
pip install vllm
```

### Запуск

```bash
python -m vllm.entrypoints.openai.api_server \
    --model mistralai/Mistral-7B-Instruct-v0.2 \
    --host 0.0.0.0 \
    --port 8000 \
    --gpu-memory-utilization 0.9 \
    --enable-prefix-caching
```

### Systemd сервис

Создайте `/etc/systemd/system/vllm.service`:

```ini
[Unit]
Description=vLLM OpenAI API Server
After=network.target

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/home/YOUR_USER
Environment="PATH=/home/YOUR_USER/vllm-env/bin"
ExecStart=/home/YOUR_USER/vllm-env/bin/python -m vllm.entrypoints.openai.api_server \
    --model mistralai/Mistral-7B-Instruct-v0.2 \
    --host 0.0.0.0 \
    --port 8000 \
    --gpu-memory-utilization 0.9 \
    --enable-prefix-caching
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Активация:

```bash
sudo systemctl daemon-reload
sudo systemctl enable vllm
sudo systemctl start vllm
sudo systemctl status vllm
```

## Модели

### Популярные модели для начала

| Модель | Размер | RAM | Использование |
|--------|--------|-----|---------------|
| `mistralai/Mistral-7B-Instruct-v0.2` | 7B | ~14GB | Общего назначения |
| `meta-llama/Llama-2-7b-chat-hf` | 7B | ~14GB | Чат |
| `meta-llama/Llama-2-13b-chat-hf` | 13B | ~26GB | Чат |
| `codellama/CodeLlama-7b-Instruct-hf` | 7B | ~14GB | Код |

### Загрузка модели из HuggingFace

```bash
# Если модель требует авторизации
huggingface-cli login

# Скачать модель заранее
huggingface-cli download mistralai/Mistral-7B-Instruct-v0.2
```

## Проверка работоспособности

### Health check

```bash
curl http://localhost:8000/health
# Должен вернуть: {"status":"ok"}
```

### Список моделей

```bash
curl http://localhost:8000/v1/models
```

### Тестовый запрос

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "mistralai/Mistral-7B-Instruct-v0.2",
        "messages": [
            {"role": "user", "content": "Hello! How are you?"}
        ],
        "max_tokens": 100
    }'
```

## Безопасность

### Рекомендации

1. **Не открывайте порт в интернет!** vLLM должен быть доступен только из внутренней сети

2. **Используйте firewall:**
```bash
# Разрешить доступ только с определенного IP
sudo ufw allow from YOUR_PROXY_SERVER_IP to any port 8000
sudo ufw enable
```

3. **Или используйте VPN/Tailscale** для безопасного соединения

## Мониторинг

### Логи Docker

```bash
docker logs -f vllm-server
```

### Метрики

```bash
# vLLM предоставляет Prometheus метрики на /metrics
curl http://localhost:8000/metrics
```

### GPU мониторинг

```bash
# Установить nvtop
sudo apt install nvtop

# Запустить
nvtop
```

Или:

```bash
watch -n 1 nvidia-smi
```

## Troubleshooting

### Out of Memory

Уменьшите:
- `--gpu-memory-utilization` до 0.8
- `--max-model-len` до меньшего значения
- `--max-num-seqs` до меньшего значения

### Медленный инференс

Увеличьте:
- `--gpu-memory-utilization` до 0.95
- Включите `--enable-prefix-caching`
- Используйте квантизацию: `--quantization awq`

### Модель не загружается

```bash
# Проверьте наличие модели
ls -la ~/.cache/huggingface/hub/

# Скачайте заново
rm -rf ~/.cache/huggingface/hub/models--mistralai--*
docker restart vllm-server
```

## После настройки

1. Запишите IP адрес vLLM сервера
2. Убедитесь что порт 8000 доступен с прокси-сервера
3. Обновите `VLLM_API_BASE` в .env файле основного проекта
4. Запустите `./test_stack.sh` для проверки соединения

## Дополнительные ресурсы

- [vLLM Documentation](https://docs.vllm.ai/)
- [Supported Models](https://docs.vllm.ai/en/stable/models/supported_models/)
- [Performance Optimization](https://docs.vllm.ai/en/stable/configuration/optimization/)
