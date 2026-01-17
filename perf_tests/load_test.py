#!/usr/bin/env python3
"""
Скрипт для нагрузочного тестирования LiteLLM API
Отправляет множество запросов параллельно и собирает статистику
"""

import requests
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
import statistics
import sys

# Конфигурация
API_URL = "http://localhost:4000/v1/chat/completions"
API_KEY = "sk-1234"
MODEL_NAME = "hosted_vllm/NousResearch/Meta-Llama-3-8B-Instruct"

# ВАЖНО: Разные параметры!
MAX_CONCURRENT_REQUESTS = 10  # Сколько запросов отправлять ОДНОВРЕМЕННО (параллельность)
TOTAL_REQUESTS_LIMIT = 10     # Сколько ВСЕГО запросов отправить (None = все из файла)

TEMPERATURE = 0.7
MAX_TOKENS = 500

def load_requests(filepath: str = "requests.json") -> List[str]:
    """Загружает запросы из JSON файла"""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    questions = []
    themes = data.get("requests", {}).get("themes", {})
    
    # Собираем все вопросы из всех категорий
    for category, items in themes.items():
        if isinstance(items, list):
            questions.extend(items)
        elif isinstance(items, dict):
            for subcategory, subitems in items.items():
                if isinstance(subitems, list):
                    questions.extend(subitems)
    
    return questions

def send_request_sync(question: str, index: int) -> Dict:
    """Синхронная отправка одного запроса"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    data = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": question
            }
        ],
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS
    }
    
    start_time = time.time()
    try:
        response = requests.post(API_URL, headers=headers, json=data, timeout=300)
        latency = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            return {
                "index": index,
                "question": question,
                "status": "success",
                "latency": latency,
                "tokens": result.get("usage", {}).get("total_tokens", 0),
                "response_length": len(result.get("choices", [{}])[0].get("message", {}).get("content", ""))
            }
        else:
            return {
                "index": index,
                "question": question,
                "status": "error",
                "latency": latency,
                "error": f"HTTP {response.status_code}: {response.text[:200]}"
            }
    except Exception as e:
        latency = time.time() - start_time
        return {
            "index": index,
            "question": question,
            "status": "error",
            "latency": latency,
            "error": str(e)
        }

def run_sync_parallel(questions: List[str], max_workers: int = MAX_CONCURRENT_REQUESTS):
    """Запускает запросы параллельно с использованием ThreadPoolExecutor"""
    results = []
    
    print(f"🚀 Запускаю {len(questions)} запросов с {max_workers} одновременными потоками...")
    print(f"📍 URL: {API_URL}")
    print(f"🤖 Model: {MODEL_NAME}")
    print("-" * 80)
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(send_request_sync, q, i): i for i, q in enumerate(questions)}
        
        completed = 0
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            completed += 1
            
            status_icon = "✅" if result["status"] == "success" else "❌"
            print(f"{status_icon} [{completed}/{len(questions)}] {result['question'][:50]}... "
                  f"({result['latency']:.2f}s)")
    
    total_time = time.time() - start_time
    
    # Статистика
    print("\n" + "=" * 80)
    print("📊 СТАТИСТИКА")
    print("=" * 80)
    
    successful = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] == "error"]
    
    print(f"✅ Успешных запросов: {len(successful)}")
    print(f"❌ Ошибок: {len(failed)}")
    print(f"⏱️  Общее время: {total_time:.2f}s")
    print(f"🚀 Запросов в секунду: {len(questions)/total_time:.2f}")
    
    if successful:
        latencies = [r["latency"] for r in successful]
        tokens = [r["tokens"] for r in successful]
        
        print(f"\n📈 Latency:")
        print(f"   Min:    {min(latencies):.2f}s")
        print(f"   Max:    {max(latencies):.2f}s")
        print(f"   Avg:    {statistics.mean(latencies):.2f}s")
        print(f"   Median: {statistics.median(latencies):.2f}s")
        
        if len(latencies) > 1:
            print(f"   StdDev: {statistics.stdev(latencies):.2f}s")
        
        print(f"\n🎯 Tokens:")
        print(f"   Total:  {sum(tokens)}")
        print(f"   Avg:    {statistics.mean(tokens):.0f}")
    
    if failed:
        print(f"\n❌ Ошибки ({len(failed)}):")
        for r in failed[:5]:  # Показываем первые 5 ошибок
            print(f"   - {r['question'][:50]}... : {r.get('error', 'Unknown')[:100]}")
        if len(failed) > 5:
            print(f"   ... и ещё {len(failed) - 5} ошибок")
    
    return results

if __name__ == "__main__":
    # Загружаем вопросы
    try:
        questions = load_requests()
        print(f"📚 Загружено {len(questions)} вопросов из requests.json\n")
    except FileNotFoundError:
        print("❌ Файл requests.json не найден!")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка загрузки requests.json: {e}")
        sys.exit(1)
    
    # Применяем ограничение количества запросов
    # Приоритет: аргумент командной строки > TOTAL_REQUESTS_LIMIT > все вопросы
    if len(sys.argv) > 1:
        limit = int(sys.argv[1])
        questions = questions[:limit]
        print(f"⚠️  Ограничено до {limit} вопросов (из аргумента командной строки)\n")
    elif TOTAL_REQUESTS_LIMIT is not None:
        questions = questions[:TOTAL_REQUESTS_LIMIT]
        print(f"⚠️  Ограничено до {TOTAL_REQUESTS_LIMIT} вопросов (TOTAL_REQUESTS_LIMIT)\n")
    else:
        print(f"⚠️  Будут отправлены ВСЕ {len(questions)} вопросов\n")
    
    print(f"⚙️  Параллельность: {MAX_CONCURRENT_REQUESTS} одновременных запросов\n")
    
    # Запускаем параллельные запросы
    results = run_sync_parallel(questions, max_workers=MAX_CONCURRENT_REQUESTS)
    
    # Сохраняем результаты
    output_file = f"results_{int(time.time())}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Результаты сохранены в {output_file}")
