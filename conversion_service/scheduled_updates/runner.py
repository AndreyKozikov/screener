"""Run one of the conversion service's existing data refresh operations."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal
import threading
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from uuid import uuid4

from conversion_service.app.repository.db.remote_repository import DataUpdateRunsRepository

logger = logging.getLogger(__name__)

_MAX_LOG_CHARS = 64_000
_MAX_LOG_KEYS = 30
_MAX_LOG_STRING = 300
_TRIGGER_SCHEDULED = "scheduled"
_STATUS_SUCCESS = "success"
_STATUS_ERROR = "error"

# Если другое обновление уже идёт, плановая задача спит и проверяет снова.
UPDATE_WAIT_INTERVAL_SECONDS = 15 * 60
# Период записи heartbeat в журнал, чтобы панель видела прогресс.
HEARTBEAT_INTERVAL_SECONDS = 30

_current_progress: Optional["ProgressTracker"] = None
_progress_lock = threading.Lock()


class ProgressTracker:
    """Потокобезопасное состояние прогресса текущей задачи."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: dict[str, Any] = {"phase": "starting"}

    def update(self, **values: Any) -> None:
        """Обновить поля прогресса, игнорируя None."""
        with self._lock:
            self._state.update({key: value for key, value in values.items() if value is not None})

    def snapshot(self) -> dict[str, Any]:
        """Вернуть копию текущего состояния прогресса."""
        with self._lock:
            return dict(self._state)


def _set_progress_tracker(tracker: Optional[ProgressTracker]) -> None:
    global _current_progress
    with _progress_lock:
        _current_progress = tracker


def _get_progress_tracker() -> Optional[ProgressTracker]:
    with _progress_lock:
        return _current_progress

_SCHEDULED_TASK_IDS = {
    "bonds": "bonds",
    "coupons": "coupons",
    "ratings": "ratings",
    "emitents": "emitents",
    "trading_history": "trading-history",
    "zerocupon": "zerocupon",
    "currency": "currency",
    "ruonia": "ruonia",
    "keyrate": "keyrate",
    "inflation_expectations": "inflation-expectations",
    "ipc": "ipc",
}


def _utc_now() -> datetime:
    """Вернуть текущее время UTC без tzinfo."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _format_ts(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S UTC")


def _build_journal_log(
    *,
    task_id: str,
    run_id: str,
    started_at: datetime,
    finished_at: datetime,
    status: str,
    result: Any = None,
    error_message: str | None = None,
    warning_message: str | None = None,
    exception_text: str | None = None,
) -> str:
    """Сформировать лог запуска по расписанию."""
    lines = [
        f"[{_format_ts(started_at)}] START task={task_id} trigger={_TRIGGER_SCHEDULED} run={run_id}",
    ]
    if error_message:
        lines.append(f"[{_format_ts(finished_at)}] ERROR {error_message}")
    if warning_message:
        lines.append(f"[{_format_ts(finished_at)}] WARNING {warning_message}")
    if exception_text:
        lines.append(f"[{_format_ts(finished_at)}] EXCEPTION {exception_text}")
    if result is not None:
        summary = json.dumps(_summarize(result), ensure_ascii=False, default=str)
        lines.append(f"[{_format_ts(finished_at)}] RESULT {summary}")
    lines.append(f"[{_format_ts(finished_at)}] FINISH {status}")
    log_text = "\n".join(lines)
    if len(log_text) > _MAX_LOG_CHARS:
        log_text = log_text[:_MAX_LOG_CHARS] + "\n… лог обрезан"
    return log_text


def _try_start_run(
    *,
    run_id: str,
    task_id: str,
    started_at: datetime,
) -> bool:
    """Атомарно занять слот обновления в журнале.

    Ошибки доступа к журналу не маскируются под «занято»: иначе при
    несовпадении версий или недоступной БД задача молча ждала бы до
    TimeoutStartSec. Исключение пробрасывается, и systemd фиксирует сбой.

    Returns:
        True, если запуск создан; False, если уже выполняется другое обновление.
    """
    return DataUpdateRunsRepository().try_start_run(
        run_id=run_id,
        task_id=task_id,
        trigger=_TRIGGER_SCHEDULED,
        started_at=started_at,
    )


def _build_heartbeat_log(
    *,
    task_id: str,
    run_id: str,
    started_at: datetime,
    tracker: ProgressTracker,
) -> str:
    """Сформировать короткий лог прогресса для записи в журнал."""
    now = _utc_now()
    elapsed = int(max(0.0, (now - started_at).total_seconds()))
    state = tracker.snapshot()

    parts = [f"elapsed={elapsed}s", f"phase={state.get('phase', 'running')}"]
    total = _int_or_zero(state.get("total"))
    if total:
        parts.append(f"processed={_int_or_zero(state.get('processed'))}/{total}")
    if "updated" in state:
        parts.append(f"updated={_int_or_zero(state.get('updated'))}")
    if "errors" in state:
        parts.append(f"errors={_int_or_zero(state.get('errors'))}")

    return "\n".join(
        [
            f"[{_format_ts(started_at)}] START task={task_id} trigger={_TRIGGER_SCHEDULED} run={run_id}",
            f"[{_format_ts(now)}] PROGRESS " + " ".join(parts),
        ]
    )


class _Heartbeat:
    """Фоновый поток, периодически обновляющий лог выполняющегося запуска."""

    def __init__(
        self,
        *,
        run_id: str,
        task_id: str,
        started_at: datetime,
        tracker: ProgressTracker,
        interval: float,
    ) -> None:
        self._run_id = run_id
        self._task_id = task_id
        self._started_at = started_at
        self._tracker = tracker
        self._interval = interval
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._loop,
            name=f"update-heartbeat-{self._task_id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                DataUpdateRunsRepository().update_run_log(
                    run_id=self._run_id,
                    log_text=_build_heartbeat_log(
                        task_id=self._task_id,
                        run_id=self._run_id,
                        started_at=self._started_at,
                        tracker=self._tracker,
                    ),
                )
            except Exception as exc:
                logger.warning(
                    "Не удалось записать heartbeat обновления %s: %s",
                    self._task_id,
                    exc,
                )


def _safe_finish_run(
    *,
    run_id: str,
    task_id: str,
    started_at: datetime,
    finished_at: datetime,
    status: str,
    log_text: str,
    error_message: str | None = None,
    warning_message: str | None = None,
) -> None:
    duration_ms = int(max(0.0, (finished_at - started_at).total_seconds() * 1000))
    try:
        DataUpdateRunsRepository().finish_run(
            run_id=run_id,
            task_id=task_id,
            trigger=_TRIGGER_SCHEDULED,
            started_at=started_at,
            status=status,
            finished_at=finished_at,
            duration_ms=duration_ms,
            error_message=error_message,
            warning_message=warning_message,
            log_text=log_text,
        )
    except Exception as exc:
        logger.warning("Не удалось записать завершение обновления %s: %s", task_id, exc)


def run_task_with_journal(
    task: str,
    runner: Callable[[str], Any] | None = None,
    *,
    sleep_func: Callable[[float], None] = time.sleep,
    wait_interval: float = UPDATE_WAIT_INTERVAL_SECONDS,
    heartbeat_interval: Optional[float] = HEARTBEAT_INTERVAL_SECONDS,
) -> Any:
    """Выполнить задачу планировщика и записать её результат в журнал.

    Если в журнале уже есть активное обновление, задача спит ``wait_interval``
    секунд и повторяет проверку. Слот занимается атомарно через
    ``DataUpdateRunsRepository.try_start_run``.
    """
    if runner is None:
        runner = _run
    task_id = _SCHEDULED_TASK_IDS.get(task, task)

    while True:
        run_id = str(uuid4())
        started_at = _utc_now()
        if _try_start_run(run_id=run_id, task_id=task_id, started_at=started_at):
            break
        logger.info(
            "Обновление %s отложено: уже выполняется другое обновление; "
            "повторная проверка через %s секунд",
            task_id,
            int(wait_interval),
        )
        sleep_func(wait_interval)

    tracker = ProgressTracker()
    tracker.update(phase=task_id)
    _set_progress_tracker(tracker)
    heartbeat: Optional[_Heartbeat] = None
    if heartbeat_interval:
        heartbeat = _Heartbeat(
            run_id=run_id,
            task_id=task_id,
            started_at=started_at,
            tracker=tracker,
            interval=heartbeat_interval,
        )
        heartbeat.start()

    try:
        result = run_task(task, runner)
    except KeyboardInterrupt:
        if heartbeat is not None:
            heartbeat.stop()
            heartbeat = None
        finished_at = _utc_now()
        _safe_finish_run(
            run_id=run_id,
            task_id=task_id,
            started_at=started_at,
            finished_at=finished_at,
            status=_STATUS_ERROR,
            error_message="Обновление прервано",
            log_text=_build_journal_log(
                task_id=task_id,
                run_id=run_id,
                started_at=started_at,
                finished_at=finished_at,
                status=_STATUS_ERROR,
                error_message="Обновление прервано",
                exception_text="Запуск остановлен сигналом SIGTERM",
            ),
        )
        raise
    except Exception as exc:
        if heartbeat is not None:
            heartbeat.stop()
            heartbeat = None
        finished_at = _utc_now()
        _safe_finish_run(
            run_id=run_id,
            task_id=task_id,
            started_at=started_at,
            finished_at=finished_at,
            status=_STATUS_ERROR,
            error_message=str(exc),
            log_text=_build_journal_log(
                task_id=task_id,
                run_id=run_id,
                started_at=started_at,
                finished_at=finished_at,
                status=_STATUS_ERROR,
                error_message=str(exc),
                exception_text=traceback.format_exc(),
            ),
        )
        raise
    else:
        if heartbeat is not None:
            heartbeat.stop()
            heartbeat = None
        finished_at = _utc_now()
        status, _, warning_message = _evaluate_result(task, result)
        _safe_finish_run(
            run_id=run_id,
            task_id=task_id,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            warning_message=warning_message,
            log_text=_build_journal_log(
                task_id=task_id,
                run_id=run_id,
                started_at=started_at,
                finished_at=finished_at,
                status=status,
                warning_message=warning_message,
                result=result,
            ),
        )
        return result
    finally:
        if heartbeat is not None:
            heartbeat.stop()
        _set_progress_tracker(None)


def _summarize(value: Any, depth: int = 0) -> Any:
    """Keep scheduler logs useful without dumping market-data payloads."""
    if isinstance(value, dict):
        summary = {
            str(key): _summarize(item, depth + 1)
            for key, item in list(value.items())[:_MAX_LOG_KEYS]
        }
        if len(value) > _MAX_LOG_KEYS:
            summary["_omitted_keys"] = len(value) - _MAX_LOG_KEYS
        return summary
    if isinstance(value, (list, tuple)):
        if depth >= 2 or len(value) > 5:
            return f"<{len(value)} items>"
        return [_summarize(item, depth + 1) for item in value]
    if isinstance(value, str) and len(value) > _MAX_LOG_STRING:
        return value[:_MAX_LOG_STRING] + f"… <{len(value) - _MAX_LOG_STRING} chars omitted>"
    return value


def _run(task: str) -> Any:
    if task == "bonds":
        from conversion_service.app.services.bonds_service import get_bonds_update_service

        return asyncio.run(get_bonds_update_service().update_bonds_data())
    if task == "coupons":
        from conversion_service.app.services.coupon_service import get_coupon_service

        tracker = _get_progress_tracker()
        progress = tracker.update if tracker is not None else None
        return asyncio.run(get_coupon_service().refresh_all(progress=progress))
    if task == "ratings":
        from conversion_service.app.services.bond_ratings_update_service import BondRatingsPipelineService

        return BondRatingsPipelineService().run_pipeline()
    if task == "emitents":
        from conversion_service.app.services.emitents_service import get_emitent_service

        return asyncio.run(get_emitent_service().update_emitents_data(None))
    if task == "trading_history":
        from conversion_service.app.services.trading_history_update_service import get_trading_history_service

        return get_trading_history_service().download_history_all()
    if task == "zerocupon":
        from conversion_service.app.services.zerocupon_update_service import get_zerocupon_update_service

        return get_zerocupon_update_service().refresh()
    if task == "currency":
        from conversion_service.app.services.currency_update_service import get_currency_service

        return get_currency_service().refresh_rates()
    if task == "ruonia":
        from conversion_service.app.services.ruonia_update_service import get_ruonia_service

        return get_ruonia_service().update_ruonia_data()
    if task == "keyrate":
        from conversion_service.app.services.keyrate_update_service import get_keyrate_service

        return get_keyrate_service().load_keyrate_data()
    if task == "inflation_expectations":
        from conversion_service.app.services.inflation_expectations_update_service import (
            get_inflation_expectations_update_service,
        )

        return asyncio.run(get_inflation_expectations_update_service().run())
    if task == "ipc":
        from conversion_service.app.services.ipc_update_service import get_ipc_update_service

        return asyncio.run(get_ipc_update_service().run())
    raise ValueError(f"Unknown update task: {task}")


def _int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _partial_failure_details(
    task: str,
    result: dict[str, Any],
) -> tuple[int, int, int, str, str]:
    """Вернуть failed, total, updated, единицу измерения и примеры ошибок.

    ВАЖНО: правило для coupons синхронизировано с _coupons_outcome в
    backend/app/services/data_update_journal.py. Изменения вносить в обе копии.
    """
    if task == "trading_history":
        failed = _int_or_zero(result.get("failed"))
        errors = result.get("errors") or []
        if isinstance(errors, list):
            failed = max(failed, len(errors))
        total = _int_or_zero(result.get("total"))
        updated = _int_or_zero(result.get("updated"))
        samples = "; ".join(
            f"{item.get('secid')}: {item.get('error')}"
            for item in (errors[:3] if isinstance(errors, list) else [])
            if isinstance(item, dict)
        )
        return failed, total, updated, "инструментов", samples

    failed = _int_or_zero(result.get("failed", result.get("errors")))
    total = _int_or_zero(result.get("total_bonds", result.get("total")))
    updated = _int_or_zero(result.get("updated"))
    samples_list = result.get("error_samples") or []
    samples = "; ".join(
        f"{item.get('secid')}: {item.get('error')}"
        for item in (samples_list[:3] if isinstance(samples_list, list) else [])
        if isinstance(item, dict)
    )
    return failed, total, updated, "облигаций", samples


def _evaluate_result(task: str, result: Any) -> tuple[str, str | None, str | None]:
    """Вернуть статус, ошибку и предупреждение по ответу сервиса.

    Частичный сбой истории торгов и купонов считается успешным запуском с
    предупреждением о необновлённых инструментах. Ошибкой остаётся только
    полный провал.
    """
    if isinstance(result, dict):
        if str(result.get("status", "")).lower() == "error":
            raise RuntimeError(result.get("error") or result.get("message") or "Service reported an error")
        if task in {"trading_history", "coupons"}:
            failed, total, updated, unit, samples = _partial_failure_details(task, result)
            if failed > 0:
                detail = f"{failed} из {total} {unit}" if total else f"{failed} {unit}"
                message = f"Не обновлены данные по {detail} (обновлено {updated})"
                if samples:
                    message += f". Примеры: {samples}"
                if updated <= 0 or (total and failed >= total):
                    return _STATUS_ERROR, message, None
                return _STATUS_SUCCESS, None, message
    return _STATUS_SUCCESS, None, None


def run_task(task: str, runner: Callable[[str], Any] = _run) -> Any:
    result = runner(task)
    status, error_message, _ = _evaluate_result(task, result)
    if status == _STATUS_ERROR:
        raise RuntimeError(error_message or "Service reported an error")
    return result


def _handle_sigterm(signum: int, frame: Any) -> None:
    """Превратить SIGTERM в исключение, чтобы завершить запись журнала."""
    raise KeyboardInterrupt


def _install_sigterm_handler() -> None:
    """Установить обработчик SIGTERM, если платформа это поддерживает."""
    try:
        signal.signal(signal.SIGTERM, _handle_sigterm)
    except (AttributeError, OSError, ValueError):
        logger.warning("Не удалось установить обработчик SIGTERM")


def main() -> int:
    parser = argparse.ArgumentParser(description="Выполнить задачу планового обновления данных")
    parser.add_argument(
        "task",
        choices=(
            "bonds",
            "coupons",
            "ratings",
            "emitents",
            "trading_history",
            "zerocupon",
            "currency",
            "ruonia",
            "keyrate",
            "inflation_expectations",
            "ipc",
        ),
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    _install_sigterm_handler()
    try:
        result = run_task_with_journal(args.task)
        status = result.get("status") if isinstance(result, dict) else None
        summary = json.dumps(_summarize(result), ensure_ascii=False, default=str)
        logging.getLogger(__name__).info(
            "Task %s finished with status %s: %s",
            args.task,
            status or "ok",
            summary,
        )
        return 3 if status == "not_completed" else 0
    except KeyboardInterrupt:
        logging.getLogger(__name__).warning("Scheduled task %s interrupted", args.task)
        return 1
    except Exception:
        logging.getLogger(__name__).exception("Scheduled task %s failed", args.task)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
