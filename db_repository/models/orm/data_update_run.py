"""Модель журнала запусков обновления данных.

Журнал хранит по одной записи на каждый запуск обновления: ручной запуск из
админки или запуск по расписанию. Записи используются административной
страницей для отображения статуса, времени и лога конкретного обновления.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Index
from sqlmodel import Field, SQLModel


class DataUpdateRun(SQLModel, table=True):
    """Один запуск обновления данных."""

    __tablename__ = "data_update_runs"
    __table_args__ = (
        Index("ix_data_update_runs_task_started", "task_id", "started_at"),
    )

    run_id: str = Field(primary_key=True, max_length=36, description="Уникальный идентификатор запуска")
    task_id: str = Field(index=True, max_length=64, description="Идентификатор пункта обновления")
    status: str = Field(index=True, max_length=16, description="running | success | error")
    trigger: str = Field(max_length=16, description="manual | scheduled")
    started_at: datetime = Field(index=True, description="Время начала запуска (UTC, без tzinfo)")
    finished_at: Optional[datetime] = Field(default=None, description="Время завершения запуска (UTC, без tzinfo)")
    duration_ms: Optional[int] = Field(default=None, description="Длительность запуска в миллисекундах")
    error_message: Optional[str] = Field(default=None, description="Текст ошибки для неуспешного запуска")
    warning_message: Optional[str] = Field(
        default=None,
        description="Предупреждение для успешного запуска (например, часть инструментов не обновилась)",
    )
    request_path: Optional[str] = Field(default=None, max_length=500, description="Путь запроса обновления")
    request_query: Optional[str] = Field(default=None, description="Безопасные query-параметры запроса")
    log_text: Optional[str] = Field(default=None, description="Текст лога запуска")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        description="Время создания записи (UTC)",
    )
