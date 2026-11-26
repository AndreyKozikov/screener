"""Репозиторий журнала запусков обновления данных.

Репозиторий принадлежит микросервису ``db_repository`` и работает с таблицей
``data_update_runs``. Через RPC его используют backend и conversion_service.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import and_, delete, or_, select
from sqlmodel import Session, create_engine

from db_repository.config.paths import DB_PATH
from db_repository.models.orm.data_update_run import DataUpdateRun

logger = logging.getLogger(__name__)

_PRUNE_INTERVAL_SECONDS = 24 * 60 * 60
_last_prune_at: float = 0.0
_prune_lock = threading.Lock()


def _utc_now() -> datetime:
    """Вернуть текущее время UTC без tzinfo для хранения в SQLite."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _scalar_values(rows: list[Any]) -> list[Any]:
    """Извлечь значения из строк SQLModel/Row в зависимости от версии."""
    values: list[Any] = []
    for row in rows:
        if hasattr(row, "__getitem__") and not isinstance(row, (str, bytes)):
            values.append(row[0])
        else:
            values.append(row)
    return values


class DataUpdateRunsRepository:
    """Чтение и запись журнала запусков обновления данных."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if db_path is None:
            db_path = DB_PATH
        self.db_path = Path(db_path)
        self._engine = create_engine(
            f"sqlite:///{self.db_path.resolve()}",
            connect_args={"check_same_thread": False},
            echo=False,
        )

    @staticmethod
    def _to_dict(row: DataUpdateRun) -> dict[str, Any]:
        """Преобразовать ORM-запись в словарь для RPC-ответа."""
        return row.model_dump(mode="python")

    def start_run(
        self,
        run_id: str,
        task_id: str,
        trigger: str,
        started_at: datetime,
        request_path: Optional[str] = None,
        request_query: Optional[str] = None,
    ) -> dict[str, Any]:
        """Создать запись о начале запуска."""
        row = DataUpdateRun(
            run_id=run_id,
            task_id=task_id,
            status="running",
            trigger=trigger,
            started_at=started_at,
            request_path=request_path,
            request_query=request_query,
        )
        with Session(self._engine) as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            result = self._to_dict(row)
        self._maybe_prune()
        return result

    def finish_run(
        self,
        run_id: str,
        status: str,
        finished_at: datetime,
        duration_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        log_text: Optional[str] = None,
        *,
        task_id: Optional[str] = None,
        trigger: Optional[str] = None,
        started_at: Optional[datetime] = None,
        request_path: Optional[str] = None,
        request_query: Optional[str] = None,
    ) -> dict[str, Any]:
        """Завершить запуск.

        Если запись о начале не сохранилась, создаёт её по переданным метаданным,
        чтобы результат запуска не терялся при временной недоступности БД.
        """
        with Session(self._engine) as session:
            row = session.get(DataUpdateRun, run_id)
            if row is None:
                if task_id is None:
                    raise ValueError("Не удалось завершить запуск: запись не найдена")
                row = DataUpdateRun(
                    run_id=run_id,
                    task_id=task_id,
                    status=status,
                    trigger=trigger or "manual",
                    started_at=started_at or finished_at,
                    request_path=request_path,
                    request_query=request_query,
                )
                session.add(row)
            row.status = status
            row.finished_at = finished_at
            row.duration_ms = duration_ms
            row.error_message = error_message
            row.log_text = log_text
            if task_id is not None:
                row.task_id = task_id
            if trigger is not None:
                row.trigger = trigger
            if started_at is not None:
                row.started_at = started_at
            if request_path is not None:
                row.request_path = request_path
            if request_query is not None:
                row.request_query = request_query

            session.add(row)
            session.commit()
            session.refresh(row)
            return self._to_dict(row)

    def get_latest_runs(self) -> list[dict[str, Any]]:
        """Вернуть последний запуск по каждому пункту обновления."""
        with Session(self._engine) as session:
            task_ids = _scalar_values(
                list(session.exec(select(DataUpdateRun.task_id).distinct()).all())
            )
            latest: list[dict[str, Any]] = []
            for task_id in sorted(str(value) for value in task_ids):
                run_id_row = session.exec(
                    select(DataUpdateRun.run_id)
                    .where(DataUpdateRun.task_id == task_id)
                    .order_by(
                        DataUpdateRun.started_at.desc(),
                        DataUpdateRun.created_at.desc(),
                        DataUpdateRun.run_id.desc(),
                    )
                    .limit(1)
                ).first()
                run_ids = _scalar_values([run_id_row]) if run_id_row is not None else []
                if not run_ids:
                    continue
                row = session.get(DataUpdateRun, str(run_ids[0]))
                if row is not None:
                    latest.append(self._to_dict(row))
            return latest

    def get_run(self, run_id: str) -> Optional[dict[str, Any]]:
        """Вернуть запуск по идентификатору."""
        with Session(self._engine) as session:
            row = session.get(DataUpdateRun, run_id)
            return self._to_dict(row) if row is not None else None

    def prune(
        self,
        retention_days: int = 90,
        max_runs_per_task: int = 200,
    ) -> int:
        """Удалить устаревшие записи и ограничить историю по каждому пункту."""
        cutoff = _utc_now() - timedelta(days=max(1, retention_days))
        deleted = 0
        with Session(self._engine) as session:
            result = session.execute(
                delete(DataUpdateRun).where(
                    or_(
                        and_(
                            DataUpdateRun.finished_at.is_not(None),
                            DataUpdateRun.finished_at < cutoff,
                        ),
                        and_(
                            DataUpdateRun.status == "running",
                            DataUpdateRun.started_at < cutoff,
                        ),
                    )
                )
            )
            deleted += int(result.rowcount or 0)

            task_ids = _scalar_values(
                list(session.exec(select(DataUpdateRun.task_id).distinct()).all())
            )
            for task_id in task_ids:
                extra_ids = _scalar_values(
                    list(
                        session.exec(
                            select(DataUpdateRun.run_id)
                            .where(DataUpdateRun.task_id == task_id)
                            .order_by(
                                DataUpdateRun.started_at.desc(),
                                DataUpdateRun.created_at.desc(),
                            )
                            .offset(max(1, max_runs_per_task))
                        ).all()
                    )
                )
                if extra_ids:
                    result = session.execute(
                        delete(DataUpdateRun).where(DataUpdateRun.run_id.in_(extra_ids))
                    )
                    deleted += int(result.rowcount or 0)

            session.commit()
        return deleted

    def _maybe_prune(self) -> None:
        """Запускать очистку не чаще одного раза в сутки."""
        global _last_prune_at
        now = time.monotonic()
        if now - _last_prune_at < _PRUNE_INTERVAL_SECONDS:
            return
        if not _prune_lock.acquire(blocking=False):
            return
        try:
            if now - _last_prune_at < _PRUNE_INTERVAL_SECONDS:
                return
            _last_prune_at = now
            self.prune()
        except Exception as exc:
            # Очистка не должна мешать записи нового запуска.
            logger.warning("Не удалось очистить журнал обновлений: %s", exc)
        finally:
            _prune_lock.release()

    def close(self) -> None:
        """Освободить соединения с БД (используется в тестах и при остановке)."""
        self._engine.dispose()
