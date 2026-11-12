"""Единый HTTP-клиент conversion_service к микросервису db_repository."""

from __future__ import annotations

import time
from typing import Any, Mapping

import httpx

from conversion_service.config.settings import settings


class DBRepositoryClient:
    """Собирает URL, X-API-Key, timeout, TLS и retry-политику в одном месте."""

    def __init__(self) -> None:
        self.base_url = settings.DB_REPOSITORY_URL.rstrip("/")
        self.api_key = settings.DB_REPOSITORY_API_KEY.get_secret_value()
        self.verify: bool | str = (
            settings.DB_REPOSITORY_CA_BUNDLE
            or settings.DB_REPOSITORY_VERIFY_TLS
        )
        self.timeout = httpx.Timeout(
            settings.DB_REPOSITORY_TIMEOUT_SECONDS,
            connect=settings.DB_REPOSITORY_CONNECT_TIMEOUT_SECONDS,
        )
        self.max_retries = max(0, settings.DB_REPOSITORY_MAX_RETRIES)
        self._client = httpx.Client(timeout=self.timeout, verify=self.verify)

    def _headers(self, extra: Mapping[str, str] | None = None) -> dict[str, str]:
        headers = dict(extra or {})
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def request(
        self,
        method: str,
        path: str,
        *,
        idempotent: bool = False,
        headers: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Выполнить запрос; повторы только для идемпотентных операций."""
        url = f"{self.base_url}{path}"
        attempts = self.max_retries + 1 if idempotent else 1
        last_error: httpx.TransportError | None = None

        for attempt in range(attempts):
            try:
                return self._client.request(
                    method,
                    url,
                    headers=self._headers(headers),
                    **kwargs,
                )
            except httpx.TransportError as exc:
                last_error = exc
                if attempt + 1 >= attempts:
                    raise
                time.sleep(min(0.2 * (attempt + 1), 2.0))

        assert last_error is not None
        raise last_error

    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", path, idempotent=True, **kwargs)

    def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", path, idempotent=False, **kwargs)


_client: DBRepositoryClient | None = None


def get_db_repository_client() -> DBRepositoryClient:
    global _client
    if _client is None:
        _client = DBRepositoryClient()
    return _client


def reset_db_repository_client() -> None:
    global _client
    if _client is not None:
        _client._client.close()
    _client = None


__all__ = [
    "DBRepositoryClient",
    "get_db_repository_client",
    "reset_db_repository_client",
]
