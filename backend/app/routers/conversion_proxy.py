"""Прокси-роутер к conversion_service через backend.

Фронтенд обращается только к backend; backend проверяет права администратора
и пробрасывает запрос в conversion_service с короткоживущей HMAC-подписью.
Пользовательский bearer-токен и роль не передаются общему прокси; ключ БД
также не передаётся.
"""

from __future__ import annotations

import asyncio
import json
import logging
import traceback
from contextlib import suppress

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from app.routers.auth import require_admin
from app.services.conversion_proxy_auth import make_conversion_proxy_headers
from app.services.data_update_journal import (
    STATUS_ERROR,
    classify_response,
    extract_exception_text,
    finish_manual_run,
    resolve_update_task,
    run_manual_heartbeat,
    try_begin_manual_run,
)
from config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversion", tags=["conversion-proxy"])

_ADMIN_DEPENDENCY = [Depends(require_admin)]

# Обновления могут идти дольше общего таймаута прокси. Пока запрос жив,
# backend удерживает слот и пишет heartbeat; ранний разрыв освободил бы слот,
# хотя conversion ещё продолжает работу.
UPDATE_PROXY_TIMEOUT_SECONDS = 6 * 60 * 60


async def _cancel_task(task: asyncio.Task | None) -> None:
    """Отменить фоновую задачу и дождаться её завершения."""
    if task is None:
        return
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


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

    task_id = resolve_update_task(method, suffix)
    run_id = None
    started_at = None
    heartbeat_task: asyncio.Task | None = None
    if task_id:
        started = await try_begin_manual_run(task_id, suffix, request.url.query)
        if started is None:
            return Response(
                status_code=409,
                content=json.dumps(
                    {
                        "detail": (
                            "Уже выполняется другое обновление данных. "
                            "Дождитесь его завершения и повторите запуск."
                        )
                    },
                    ensure_ascii=False,
                ),
                media_type="application/json",
            )
        run_id, started_at = started
        heartbeat_task = asyncio.create_task(
            run_manual_heartbeat(
                run_id=run_id,
                task_id=task_id,
                started_at=started_at,
            )
        )

    try:
        proxy_timeout = (
            UPDATE_PROXY_TIMEOUT_SECONDS
            if task_id
            else settings.CONVERSION_SERVICE_TIMEOUT_SECONDS
        )
        try:
            async with httpx.AsyncClient(timeout=proxy_timeout) as client:
                response = await client.request(
                    method,
                    upstream_url,
                    content=body,
                    headers=headers,
                )
        except asyncio.CancelledError:
            if heartbeat_task is not None:
                heartbeat_task.cancel()
                heartbeat_task = None
            if task_id and run_id:
                # Не завершаем запуск: conversion мог продолжить работу в
                # отдельном потоке. Запись освободится по heartbeat-lease.
                logger.warning(
                    "Запрос обновления %s прерван; запуск оставлен активным "
                    "до истечения heartbeat-lease",
                    task_id,
                )
            raise
        except Exception as exc:
            await _cancel_task(heartbeat_task)
            heartbeat_task = None
            if task_id and run_id and started_at:
                await finish_manual_run(
                    run_id=run_id,
                    task_id=task_id,
                    request_path=suffix,
                    request_query=request.url.query,
                    started_at=started_at,
                    status=STATUS_ERROR,
                    error_message=str(exc),
                    exception_text=traceback.format_exc(),
                )
            raise

        await _cancel_task(heartbeat_task)
        heartbeat_task = None

        if task_id and run_id and started_at:
            status, error_message, warning_message, payload = classify_response(
                task_id,
                response.status_code,
                response.headers.get("content-type", ""),
                response.content,
            )
            await finish_manual_run(
                run_id=run_id,
                task_id=task_id,
                request_path=suffix,
                request_query=request.url.query,
                started_at=started_at,
                status=status,
                http_status=response.status_code,
                error_message=error_message,
                warning_message=warning_message,
                payload=payload,
                exception_text=extract_exception_text(payload),
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
    finally:
        if heartbeat_task is not None:
            heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat_task


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"], dependencies=_ADMIN_DEPENDENCY)
async def conversion_proxy(request: Request) -> Response:
    return await _proxy(request, request.method)
