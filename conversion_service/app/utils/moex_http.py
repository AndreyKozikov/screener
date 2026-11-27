"""Общий HTTP-клиент для запросов к MOEX ISS.

Клиент переиспользует соединения (keep-alive), ограничивает общую частоту
запросов, повторяет временно неуспешные запросы с экспоненциальной задержкой
и использует системное хранилище корневых сертификатов (включая российские
корневые сертификаты, установленные на сервере).
"""

from __future__ import annotations

import logging
import random
import ssl
import threading
import time
from typing import Any, Callable, Optional

import httpx
import orjson

logger = logging.getLogger(__name__)

# Общий лимит частоты запросов к MOEX ISS на процесс.
MOEX_MAX_RPS = 4.0
# Всего попыток на один запрос, включая первую.
MOEX_MAX_ATTEMPTS = 3
MOEX_BACKOFF_BASE_SECONDS = 0.5
MOEX_BACKOFF_MAX_SECONDS = 8.0
MOEX_TIMEOUT_SECONDS = 30.0
MOEX_CONNECT_TIMEOUT_SECONDS = 10.0
MOEX_POOL_SIZE = 16
MOEX_KEEPALIVE_EXPIRY_SECONDS = 30.0
MOEX_USER_AGENT = "Mozilla/5.0"
MOEX_RETRY_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})


class RateLimiter:
    """Потокобезопасный ограничитель частоты запросов.

    Выдерживает минимальный интервал между запросами в одном процессе.
    Ожидание выполняется вне блокировки, поэтому лимит не сериализует
    параллельные HTTP-запросы.
    """

    def __init__(
        self,
        rps: float = MOEX_MAX_RPS,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if rps <= 0:
            raise ValueError("rps должен быть положительным")
        self._interval = 1.0 / float(rps)
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def wait(self) -> None:
        """Подождать, пока не будет разрешён следующий запрос."""
        with self._lock:
            now = self._clock()
            delay = max(0.0, self._next_allowed - now)
            self._next_allowed = max(now, self._next_allowed) + self._interval
        if delay > 0:
            self._sleep(delay)


def _retry_after_seconds(response: httpx.Response) -> Optional[float]:
    """Разобрать заголовок Retry-After, если он задан числом секунд."""
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(0.0, float(value.strip()))
    except (TypeError, ValueError):
        return None


class MoexHttpClient:
    """HTTP-клиент MOEX с пулом соединений, лимитом частоты и ретраями."""

    def __init__(
        self,
        *,
        rps: float = MOEX_MAX_RPS,
        attempts: int = MOEX_MAX_ATTEMPTS,
        timeout: float = MOEX_TIMEOUT_SECONDS,
        user_agent: str = MOEX_USER_AGENT,
        transport: Optional[httpx.BaseTransport] = None,
        rate_limiter: Optional[RateLimiter] = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if attempts < 1:
            raise ValueError("attempts должен быть не меньше 1")
        self._attempts = attempts
        self._timeout = timeout
        self._sleep = sleep
        self._limiter = rate_limiter or RateLimiter(rps)
        self._client = httpx.Client(
            timeout=httpx.Timeout(timeout, connect=MOEX_CONNECT_TIMEOUT_SECONDS),
            limits=httpx.Limits(
                max_connections=MOEX_POOL_SIZE,
                max_keepalive_connections=MOEX_POOL_SIZE,
                keepalive_expiry=MOEX_KEEPALIVE_EXPIRY_SECONDS,
            ),
            verify=ssl.create_default_context(),
            headers={"User-Agent": user_agent},
            follow_redirects=True,
            transport=transport,
        )

    def get_bytes(
        self,
        url: str,
        *,
        attempts: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> bytes:
        """Выполнить GET и вернуть тело ответа."""
        return self._request(url, attempts=attempts, timeout=timeout)

    def get_json(
        self,
        url: str,
        *,
        attempts: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Выполнить GET и разобрать JSON-ответ через orjson."""
        raw = self._request(url, attempts=attempts, timeout=timeout)
        try:
            return orjson.loads(raw)
        except orjson.JSONDecodeError as exc:
            raise RuntimeError(f"Некорректный JSON от MOEX для {url}: {exc}") from exc

    def get_text(
        self,
        url: str,
        *,
        attempts: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> str:
        """Выполнить GET и вернуть текст ответа в UTF-8."""
        return self._request(url, attempts=attempts, timeout=timeout).decode(
            "utf-8", errors="replace"
        )

    def _request(
        self,
        url: str,
        *,
        attempts: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> bytes:
        attempts_total = attempts or self._attempts
        request_timeout = timeout if timeout is not None else self._timeout
        last_error: Optional[BaseException] = None

        for attempt in range(1, attempts_total + 1):
            self._limiter.wait()
            try:
                response = self._client.get(url, timeout=request_timeout)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                if attempt >= attempts_total:
                    break
                logger.warning(
                    "MOEX запрос %s не удался (попытка %s/%s): %s",
                    url,
                    attempt,
                    attempts_total,
                    exc,
                )
                self._backoff(attempt, None)
                continue

            if response.status_code in MOEX_RETRY_STATUSES and attempt < attempts_total:
                last_error = RuntimeError(f"HTTP {response.status_code}")
                logger.warning(
                    "MOEX вернул HTTP %s для %s (попытка %s/%s)",
                    response.status_code,
                    url,
                    attempt,
                    attempts_total,
                )
                self._backoff(attempt, _retry_after_seconds(response))
                continue

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(
                    f"MOEX вернул HTTP {response.status_code} для {url}"
                ) from exc

            return response.content

        raise RuntimeError(
            f"Не удалось выполнить запрос к MOEX {url} за {attempts_total} попыток: {last_error}"
        ) from last_error

    def _backoff(self, attempt: int, retry_after: Optional[float]) -> None:
        """Подождать перед следующей попыткой."""
        if retry_after is not None:
            delay = min(max(retry_after, 0.0), MOEX_BACKOFF_MAX_SECONDS)
        else:
            delay = MOEX_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
            delay = min(delay, MOEX_BACKOFF_MAX_SECONDS)
            delay += random.uniform(0.0, delay * 0.25)
        if delay > 0:
            self._sleep(delay)

    def close(self) -> None:
        """Закрыть пул соединений."""
        self._client.close()


_client: Optional[MoexHttpClient] = None
_client_lock = threading.Lock()


def get_moex_http_client() -> MoexHttpClient:
    """Вернуть общий на процесс клиент MOEX."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = MoexHttpClient()
    return _client


def reset_moex_http_client() -> None:
    """Сбросить общий клиент (используется в тестах)."""
    global _client
    with _client_lock:
        if _client is not None:
            _client.close()
        _client = None
