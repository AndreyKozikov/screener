"""Проверка X-API-Key для межсервисного доступа к db_repository."""

from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from db_repository.config.settings import settings


def is_authorized(api_key: str | None) -> bool:
    """Вернуть True, если запрос разрешён при текущих настройках."""
    if not settings.require_api_key:
        return True
    expected_key = settings.api_key.get_secret_value()
    if not expected_key:
        return False
    return bool(api_key) and secrets.compare_digest(api_key, expected_key)


def require_api_key(api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """FastAPI-зависимость: fail-closed при require_api_key=true."""
    if not settings.require_api_key:
        return

    expected_key = settings.api_key.get_secret_value()
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API key is not configured for the database service",
        )
    if not api_key or not secrets.compare_digest(api_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )


__all__ = ["is_authorized", "require_api_key"]
