"""Прокси-роутер к conversion_service через backend.

Фронтенд обращается только к backend; backend проверяет права администратора
и пробрасывает запрос в conversion_service с короткоживущей HMAC-подписью.
Пользовательский bearer-токен и роль не передаются общему прокси; ключ БД
также не передаётся.
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from app.routers.auth import require_admin
from app.services.conversion_proxy_auth import make_conversion_proxy_headers
from config.settings import settings

router = APIRouter(prefix="/api/conversion", tags=["conversion-proxy"])

_ADMIN_DEPENDENCY = [Depends(require_admin)]

def _forward_headers(request: Request) -> dict[str, str]:
    return {
        key: value
        for key, value in request.headers.items()
        if key.lower() in {"content-type", "accept"}
    }


async def _proxy(request: Request, method: str) -> Response:
    base = settings.CONVERSION_SERVICE_URL.rstrip("/")
    path = request.url.path
    prefix = "/api/conversion"
    suffix = path[len(prefix):] if path.startswith(prefix) else path
    url = f"{base}{suffix}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    body = await request.body()
    headers = _forward_headers(request)
    upstream_url = httpx.URL(url)
    headers.update(
        make_conversion_proxy_headers(method, upstream_url.raw_path.decode("ascii"))
    )

    async with httpx.AsyncClient(timeout=settings.CONVERSION_SERVICE_TIMEOUT_SECONDS) as client:
        response = await client.request(
            method,
            upstream_url,
            content=body,
            headers=headers,
        )

    response_headers = {
        key: value
        for key, value in response.headers.items()
        if key.lower() in {"content-type", "content-disposition", "cache-control"}
    }
    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=response_headers,
        media_type=response.headers.get("content-type"),
    )


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"], dependencies=_ADMIN_DEPENDENCY)
async def conversion_proxy(request: Request) -> Response:
    return await _proxy(request, request.method)
