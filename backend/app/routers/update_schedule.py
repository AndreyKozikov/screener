"""Административные эндпоинты расписания плановых обновлений данных."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.routers.auth import require_admin
from app.services.update_schedule import collect_update_schedule

router = APIRouter(
    prefix="/api/admin/update-schedule",
    tags=["update-schedule"],
    dependencies=[Depends(require_admin)],
)


class UpdateScheduleItem(BaseModel):
    """Один пункт расписания планового обновления."""

    task_id: str
    timer_unit: str
    service_unit: str
    schedule: Optional[str] = None
    schedule_human: Optional[str] = None
    enabled: Optional[bool] = None
    active: Optional[bool] = None
    next_elapse: Optional[str] = None
    last_trigger_at: Optional[str] = None
    state: str
    source: str


class UpdateScheduleResponse(BaseModel):
    """Ответ с расписанием всех плановых обновлений."""

    generated_at: str
    systemd_available: bool
    items: list[UpdateScheduleItem]


@router.get("", response_model=UpdateScheduleResponse)
async def get_update_schedule() -> UpdateScheduleResponse:
    """Вернуть расписание плановых обновлений и время следующего запуска."""
    snapshot = await collect_update_schedule()
    return UpdateScheduleResponse(
        generated_at=snapshot.generated_at,
        systemd_available=snapshot.systemd_available,
        items=[UpdateScheduleItem(**item) for item in snapshot.items],
    )
