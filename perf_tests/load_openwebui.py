#!/usr/bin/env python3
"""
Async load generator for Open WebUI.
- Logs in as multiple users from perf_tests/users.json (username@example.com, password from file)
- Picks random questions from perf_tests/requests.json (main + develop)
- Fires many concurrent chat completion requests to Open WebUI
- Records latency from request start until full response body is received (no streaming)
- Writes detailed results to CSV and prints a short summary
"""
import argparse
import asyncio
import csv
import json
import random
import time
from pathlib import Path
from typing import Dict, List, Tuple

import aiohttp

BASE_DIR = Path(__file__).resolve().parent
USERS_PATH = BASE_DIR / "users.json"
REQUESTS_PATH = BASE_DIR / "requests.json"


def load_users() -> List[Dict[str, str]]:
    data = json.loads(USERS_PATH.read_text())
    users = []
    for entry in data:
        username = entry.get("username")
        password = entry.get("password", "12345678")
        if not username:
            continue
        email = f"{username}@example.com"
        users.append({"email": email, "password": password})
    if not users:
        raise RuntimeError("No users loaded")
    return users


def load_questions() -> List[str]:
    data = json.loads(REQUESTS_PATH.read_text())
    themes = data.get("requests", {}).get("themes", {})
    questions = []
    for key in ("main_questions", "develop_questions"):
        questions.extend(themes.get(key, []))
    # dedupe while keeping order
    seen = set()
    unique = []
    for q in questions:
        if q in seen:
            continue
        seen.add(q)
        unique.append(q)
    if not unique:
        raise RuntimeError("No questions loaded")
    return unique


async def login(session: aiohttp.ClientSession, base_url: str, email: str, password: str) -> str:
    url = f"{base_url.rstrip('/')}/api/auth/login"
    async with session.post(url, json={"email": email, "password": password}) as resp:
        text = await resp.text()
        if resp.status != 200:
            raise RuntimeError(f"login failed ({resp.status}) for {email}: {text}")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            raise RuntimeError(f"login returned non-json for {email}: {text}")
        token = data.get("token") or data.get("data", {}).get("token")
        if not token:
            raise RuntimeError(f"no token in login response for {email}: {data}")
        return token


async def send_question(
    session: aiohttp.ClientSession,
    base_url: str,
    chat_url: str,
    model: str,
    user: Dict[str, str],
    token_cache: Dict[str, str],
    token_locks: Dict[str, asyncio.Lock],
    question: str,
    request_id: int,
) -> Tuple[int, str, float, int, str]:
    email = user["email"]

    # Per-user token cache with lock to avoid duplicate logins
    if email not in token_cache:
        lock = token_locks.setdefault(email, asyncio.Lock())
        async with lock:
            if email not in token_cache:
                token_cache[email] = await login(session, base_url, email, user["password"])
    token = token_cache[email]

    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": question}],
        "stream": False,
    }

    started = time.perf_counter()
    async with session.post(chat_url, json=payload, headers=headers) as resp:
        body = await resp.text()
        latency = time.perf_counter() - started
        if resp.status != 200:
            raise RuntimeError(f"request {request_id} failed ({resp.status}): {body}")
    return request_id, question, latency, resp.status, email


async def run_load(args):
    users = load_users()
    questions = load_questions()

    chat_url = f"{args.base_url.rstrip('/')}{args.chat_endpoint}"

    connector = aiohttp.TCPConnector(limit=args.concurrency * 2, ssl=False)
    timeout = aiohttp.ClientTimeout(total=args.request_timeout)

    token_cache: Dict[str, str] = {}
    token_locks: Dict[str, asyncio.Lock] = {}
    results = []
    errors = []

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        sem = asyncio.Semaphore(args.concurrency)

        async def worker(rid: int):
            async with sem:
                user = random.choice(users)
                question = random.choice(questions)
                try:
                    res = await send_question(
                        session,
                        args.base_url,
                        chat_url,
                        args.model,
                        user,
                        token_cache,
                        token_locks,
                        question,
                        rid,
                    )
                    results.append(res)
                except Exception as exc:  # noqa: BLE001
                    errors.append((rid, str(exc)))

        tasks = [asyncio.create_task(worker(i)) for i in range(1, args.requests + 1)]
        await asyncio.gather(*tasks)

    return results, errors


def write_csv(path: Path, rows: List[Tuple[int, str, float, int, str]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["request_id", "question", "latency_seconds", "status_code", "user_email"])
        writer.writerows(rows)


def summarize(results: List[Tuple[int, str, float, int, str]]):
    if not results:
        return None
    latencies = [r[2] for r in results]
    latencies.sort()
    total = len(latencies)
    avg = sum(latencies) / total
    p50 = latencies[int(0.5 * (total - 1))]
    p90 = latencies[int(0.9 * (total - 1))]
    p99 = latencies[int(0.99 * (total - 1))]
    return {
        "total": total,
        "avg": avg,
        "p50": p50,
        "p90": p90,
        "p99": p99,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Load test for Open WebUI")
    parser.add_argument("--base-url", default="http://localhost:8080", help="Open WebUI base URL")
    parser.add_argument(
        "--chat-endpoint",
        default="/api/chat/completions",
        help="Chat completions endpoint relative to base",
    )
    parser.add_argument("--model", default="llama3-8b", help="Model name to send in payload")
    parser.add_argument("--requests", type=int, default=100, help="Total number of requests to send")
    parser.add_argument("--concurrency", type=int, default=50, help="Concurrent in-flight requests")
    parser.add_argument("--request-timeout", type=int, default=120, help="Per request timeout in seconds")
    parser.add_argument(
        "--output",
        default=str(BASE_DIR / "results.csv"),
        help="Path to write CSV results",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    results, errors = asyncio.run(run_load(args))

    summary = summarize(results)
    write_csv(Path(args.output), results)

    print("=== Load completed ===")
    print(f"Requests ok: {len(results)}; errors: {len(errors)}; CSV: {args.output}")
    if summary:
        print(
            f"Avg: {summary['avg']:.2f}s | p50: {summary['p50']:.2f}s | p90: {summary['p90']:.2f}s | p99: {summary['p99']:.2f}s"
        )
        print(f"Count of req | time to answer: {summary['total']} | {summary['avg']:.2f}s")
    if errors:
        print("Sample errors (first 5):")
        for rid, err in errors[:5]:
            print(f"  #{rid}: {err}")


if __name__ == "__main__":
    main()
