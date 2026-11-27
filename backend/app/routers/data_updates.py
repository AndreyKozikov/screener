"""Административные эндпоинты журнала обновления данных."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.repository.db.remote_repository import (
    DataUpdateRunsRepository,
    RemoteRepositoryError,
    RepositoryUnavailableError,
)
from app.routers.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/data-updates",
    tags=["data-updates"],
    dependencies=[Depends(require_admin)],
)

_STALE_RUN_AFTER = timedelta(hours=6)


class DataUpdateStatusItem(BaseModel):
    """Краткий статус последнего запуска пункта обновления."""

    task_id: str
    status: Optional[str] = None
    trigger: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    warning_message: Optional[str] = None
    run_id: Optional[str] = None
    log_available: bool = False


class DataUpdateStatusesResponse(BaseModel):
    """Ответ со статусами всех пунктов, по которым есть запуски."""

    generated_at: str
    items: list[DataUpdateStatusItem]


class DataUpdateRunDetail(DataUpdateStatusItem):
    """Полные данные запуска вместе с логом."""

    log: Optional[str] = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: Optional[Any]) -> Optional[str]:
    """Сериализовать дату в ISO UTC; строки возвращаются как есть."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if not isinstance(value, datetime):
        return str(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    """Пометить зависшие запуски как прерванные."""
    normalized = dict(row)
    if normalized.get("status") == "running":
        started_at = normalized.get("started_at")
        if isinstance(started_at, datetime):
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            if _utc_now() - started_at > _STALE_RUN_AFTER:
                normalized["status"] = "error"
                normalized["error_message"] = (
                    "Обновление не завершилось и было прервано"
                )
    return normalized


def _to_status_item(row: dict[str, Any]) -> DataUpdateStatusItem:
    normalized = _normalize_row(row)
    return DataUpdateStatusItem(
        task_id=str(normalized.get("task_id") or ""),
        status=normalized.get("status"),
        trigger=normalized.get("trigger"),
        started_at=_iso(normalized.get("started_at")),
        finished_at=_iso(normalized.get("finished_at")),
        duration_ms=normalized.get("duration_ms"),
        error_message=normalized.get("error_message"),
        warning_message=normalized.get("warning_message"),
        run_id=normalized.get("run_id"),
        log_available=bool(normalized.get("log_text")),
    )


async def _load_latest_runs() -> list[dict[str, Any]]:
    def _read() -> list[dict[str, Any]]:
        return DataUpdateRunsRepository().get_latest_runs()

    try:
        return await asyncio.to_thread(_read)
    except RepositoryUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail="Сервис истории обновлений недоступен",
        ) from exc
    except RemoteRepositoryError as exc:
        logger.warning("Не удалось загрузить журнал обновлений: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Не удалось загрузить историю обновлений",
        ) from exc


@router.get("", response_model=DataUpdateStatusesResponse)
async def get_data_update_statuses() -> DataUpdateStatusesResponse:
    """Вернуть последний статус каждого пункта обновления."""
    rows = await _load_latest_runs()
    return DataUpdateStatusesResponse(
        generated_at=_iso(_utc_now()) or "",
        items=[_to_status_item(row) for row in rows],
    )


@router.get("/runs/{run_id}", response_model=DataUpdateRunDetail)
async def get_data_update_run(run_id: str) -> DataUpdateRunDetail:
    """Вернуть подробности и лог конкретного запуска."""
    def _read() -> Optional[dict[str, Any]]:
        return DataUpdateRunsRepository().get_run(run_id)

    try:
        row = await asyncio.to_thread(_read)
    except RepositoryUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail="Сервис истории обновлений недоступен",
        ) from exc
    except RemoteRepositoryError as exc:
        logger.warning("Не удалось загрузить запуск %s: %s", run_id, exc)
        raise HTTPException(
            status_code=502,
            detail="Не удалось загрузить лог обновления",
        ) from exc

    if row is None:
        raise HTTPException(status_code=404, detail="Запуск обновления не найден")

    item = _to_status_item(row)
    return DataUpdateRunDetail(
        **item.model_dump(),
        log=row.get("log_text"),
    )
