"""Журналирование запусков обновления данных.

Модуль собирает статус, длительность и текстовый лог для ручных обновлений,
которые проходят через backend. Запись в ``db_repository`` выполняется
best-effort: сбой журнала не должен влиять на само обновление данных.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from app.repository.db.remote_repository import DataUpdateRunsRepository

logger = logging.getLogger(__name__)

MAX_LOG_CHARS = 64_000
MAX_ERROR_CHARS = 2_000
MAX_QUERY_CHARS = 2_000
JOURNAL_WRITE_TIMEOUT_SECONDS = 3.0
HEARTBEAT_INTERVAL_SECONDS = 30.0
_MAX_STRING_CHARS = 500
_MAX_KEYS = 30
_MAX_LIST_ITEMS = 10

TRIGGER_MANUAL = "manual"
TRIGGER_SCHEDULED = "scheduled"

STATUS_RUNNING = "running"
STATUS_SUCCESS = "success"
STATUS_ERROR = "error"

# Точные пути conversion_service, которые являются обновлением данных.
_UPDATE_TASKS: dict[tuple[str, str], str] = {
    ("POST", "/update/bonds_data"): "bonds",
    ("POST", "/zerocupon/refresh"): "zerocupon",
    ("POST", "/rating/refresh"): "ratings",
    ("POST", "/emitents/update"): "emitents",
    ("POST", "/bonds/refresh-coupons"): "coupons",
    ("POST", "/currency/refresh"): "currency",
    ("POST", "/ruonia/refresh"): "ruonia",
    ("POST", "/keyrate/load"): "keyrate",
    ("GET", "/trading-history/download"): "trading-history",
    ("POST", "/forecast/upload"): "forecast",
    ("POST", "/ipc/upload"): "ipc",
    ("POST", "/ipc/upload_ipc_weekly"): "ipc-weekly",
    ("POST", "/inflations/upload"): "inflation-expectations",
    ("POST", "/inflations/upload_by_url"): "inflation-expectations",
    ("POST", "/inflations/upload_inflation_data"): "inflation",
    ("POST", "/inflations/upload_inflation_data_by_url"): "inflation",
}


def utc_now() -> datetime:
    """Вернуть текущее время UTC без tzinfo."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def resolve_update_task(method: str, path: str) -> Optional[str]:
    """Определить пункт обновления по методу и пути запроса."""
    normalized = path.rstrip("/") or "/"
    return _UPDATE_TASKS.get((method.upper(), normalized))


def _format_ts(value: Optional[datetime]) -> str:
    if value is None:
        return "-"
    return value.strftime("%Y-%m-%d %H:%M:%S UTC")


def _summarize(value: Any, depth: int = 0) -> Any:
    """Сократить ответ сервиса для хранения в логе."""
    if isinstance(value, dict):
        items = list(value.items())
        summary = {
            str(key): _summarize(item, depth + 1)
            for key, item in items[:_MAX_KEYS]
        }
        if len(items) > _MAX_KEYS:
            summary["_omitted_keys"] = len(items) - _MAX_KEYS
        return summary
    if isinstance(value, (list, tuple)):
        if depth >= 2 or len(value) > _MAX_LIST_ITEMS:
            return f"<{len(value)} items>"
        return [_summarize(item, depth + 1) for item in value]
    if isinstance(value, str) and len(value) > _MAX_STRING_CHARS:
        return value[:_MAX_STRING_CHARS] + f"… <{len(value) - _MAX_STRING_CHARS} chars omitted>"
    return value


def _json_text(value: Any) -> str:
    try:
        return json.dumps(_summarize(value), ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)


def _extract_error_message(payload: Any, status_code: int) -> str:
    if isinstance(payload, dict):
        for key in ("detail", "error", "message"):
            value = payload.get(key)
            if value:
                if isinstance(value, str):
                    text = value
                else:
                    try:
                        text = json.dumps(value, ensure_ascii=False, default=str)
                    except (TypeError, ValueError):
                        text = str(value)
                return text[:MAX_ERROR_CHARS]
    return f"HTTP {status_code}"


def _int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _trading_history_outcome(
    payload: dict[str, Any],
) -> Optional[tuple[str, Optional[str], Optional[str]]]:
    """Оценить частичный сбой истории торгов.

    Обновление считается успешным, если хотя бы часть инструментов обработана:
    неудачные инструменты попадают в предупреждение. Полный провал (ничего не
    обновлено или упали все инструменты) остаётся ошибкой.
    """
    failed = _int_or_zero(payload.get("failed"))
    errors = payload.get("errors") or []
    if isinstance(errors, list):
        failed = max(failed, len(errors))
    if failed <= 0:
        return None

    total = _int_or_zero(payload.get("total"))
    updated = _int_or_zero(payload.get("updated"))
    detail = f"{failed} из {total} инструментов" if total else f"{failed} инструментов"
    message = f"Не обновлены данные по {detail} (обновлено {updated})"
    sample = "; ".join(
        f"{item.get('secid')}: {item.get('error')}"
        for item in (errors[:3] if isinstance(errors, list) else [])
        if isinstance(item, dict)
    )
    if sample:
        message += f". Примеры: {sample}"

    if updated <= 0 or (total and failed >= total):
        return STATUS_ERROR, message, None
    return STATUS_SUCCESS, None, message


def _coupons_outcome(
    payload: dict[str, Any],
) -> Optional[tuple[str, Optional[str], Optional[str]]]:
    """Оценить частичный сбой обновления купонов.

    Как и для истории торгов, успешный запуск с частью ошибок считается
    предупреждением; полный провал (ничего не обновлено или упали все
    облигации) остаётся ошибкой.

    ВАЖНО: правило синхронизировано с _partial_failure_details в
    conversion_service/scheduled_updates/runner.py. Изменения вносить в обе копии.
    """
    failed = _int_or_zero(payload.get("failed", payload.get("errors")))
    if failed <= 0:
        return None

    total = _int_or_zero(payload.get("total_bonds", payload.get("total")))
    updated = _int_or_zero(payload.get("updated"))
    detail = f"{failed} из {total} облигаций" if total else f"{failed} облигаций"
    message = f"Не обновлены данные по {detail} (обновлено {updated})"
    samples_list = payload.get("error_samples") or []
    sample = "; ".join(
        f"{item.get('secid')}: {item.get('error')}"
        for item in (samples_list[:3] if isinstance(samples_list, list) else [])
        if isinstance(item, dict)
    )
    if sample:
        message += f". Примеры: {sample}"

    if updated <= 0 or (total and failed >= total):
        return STATUS_ERROR, message, None
    return STATUS_SUCCESS, None, message


def classify_payload(
    task_id: str,
    payload: Any,
    status_code: int = 200,
) -> tuple[str, Optional[str], Optional[str]]:
    """Определить статус, ошибку и предупреждение по HTTP-коду и телу ответа."""
    if status_code >= 400:
        return STATUS_ERROR, _extract_error_message(payload, status_code), None
    if isinstance(payload, dict):
        status_value = str(payload.get("status") or "").strip().lower()
        if status_value in {"error", "failed"}:
            return STATUS_ERROR, _extract_error_message(payload, status_code), None
        if payload.get("success") is False:
            return STATUS_ERROR, _extract_error_message(payload, status_code), None
        if task_id == "trading-history":
            outcome = _trading_history_outcome(payload)
            if outcome is not None:
                return outcome
        if task_id == "coupons":
            outcome = _coupons_outcome(payload)
            if outcome is not None:
                return outcome
    return STATUS_SUCCESS, None, None


def classify_response(
    task_id: str,
    status_code: int,
    content_type: str,
    body: bytes,
) -> tuple[str, Optional[str], Optional[str], Any]:
    """Разобрать ответ и вернуть статус, ошибку, предупреждение и нагрузку."""
    payload: Any = None
    if body:
        text = body.decode("utf-8", errors="replace")
        if "json" in content_type.lower():
            try:
                payload = json.loads(text)
            except (TypeError, ValueError):
                payload = text
        else:
            payload = text[:_MAX_STRING_CHARS]
    status, error_message, warning_message = classify_payload(task_id, payload, status_code)
    return status, error_message, warning_message, payload


def extract_exception_text(payload: Any) -> Optional[str]:
    """Извлечь traceback из ответа conversion_service, если он передан."""
    if isinstance(payload, dict):
        traceback_text = payload.get("traceback")
        if isinstance(traceback_text, str) and traceback_text.strip():
            return traceback_text[:MAX_LOG_CHARS]
    return None


def build_update_log(
    *,
    task_id: str,
    trigger: str,
    run_id: str,
    request_path: str,
    request_query: Optional[str],
    started_at: datetime,
    finished_at: datetime,
    status: str,
    http_status: Optional[int] = None,
    error_message: Optional[str] = None,
    warning_message: Optional[str] = None,
    payload: Any = None,
    exception_text: Optional[str] = None,
) -> str:
    """Сформировать текст лога одного запуска."""
    duration_seconds = max(0.0, (finished_at - started_at).total_seconds())
    request_suffix = f"?{request_query}" if request_query else ""
    lines = [
        f"[{_format_ts(started_at)}] START task={task_id} trigger={trigger} run={run_id}",
        f"[{_format_ts(started_at)}] REQUEST {request_path}{request_suffix}",
    ]
    if http_status is not None:
        lines.append(
            f"[{_format_ts(finished_at)}] RESPONSE HTTP {http_status} ({duration_seconds:.1f} s)"
        )
    if error_message:
        lines.append(f"[{_format_ts(finished_at)}] ERROR {error_message}")
    if warning_message:
        lines.append(f"[{_format_ts(finished_at)}] WARNING {warning_message}")
    if exception_text:
        lines.append(f"[{_format_ts(finished_at)}] EXCEPTION {exception_text}")
    if payload is not None:
        lines.append(f"[{_format_ts(finished_at)}] RESULT {_json_text(payload)}")
    lines.append(f"[{_format_ts(finished_at)}] FINISH {status}")

    log_text = "\n".join(lines)
    if len(log_text) > MAX_LOG_CHARS:
        log_text = log_text[:MAX_LOG_CHARS] + "\n… лог обрезан"
    return log_text


def safe_query(query: str) -> Optional[str]:
    """Ограничить query-строку для журнала, не сохраняя лишние данные."""
    if not query:
        return None
    return query[:MAX_QUERY_CHARS]


async def try_begin_manual_run(
    task_id: str,
    request_path: str,
    request_query: Optional[str],
) -> Optional[tuple[str, datetime]]:
    """Атомарно начать ручное обновление, если другие обновления не идут.

    Returns:
        (run_id, started_at), если запуск создан; None, если сейчас уже
        выполняется другое обновление данных.
    """
    run_id = str(uuid4())
    started_at = utc_now()

    def _write() -> bool:
        repository = DataUpdateRunsRepository()
        return repository.try_start_run(
            run_id=run_id,
            task_id=task_id,
            trigger=TRIGGER_MANUAL,
            started_at=started_at,
            request_path=request_path,
            request_query=safe_query(request_query or ""),
        )

    try:
        # Не оборачиваем в wait_for: отмена ожидания не останавливает поток,
        # и закоммиченная запись running осталась бы без владельца.
        acquired = await asyncio.to_thread(_write)
    except Exception as exc:
        logger.warning("Не удалось проверить занятость обновлений для %s: %s", task_id, exc)
        raise
    if not acquired:
        return None
    return run_id, started_at


async def heartbeat_manual_run(
    *,
    run_id: str,
    task_id: str,
    started_at: datetime,
) -> None:
    """Записать в журнал heartbeat выполняющегося ручного обновления."""
    now = utc_now()
    elapsed = int(max(0.0, (now - started_at).total_seconds()))
    log_text = (
        f"[{_format_ts(started_at)}] START task={task_id} trigger={TRIGGER_MANUAL} run={run_id}\n"
        f"[{_format_ts(now)}] PROGRESS elapsed={elapsed}s phase=conversion"
    )

    def _write() -> bool:
        return DataUpdateRunsRepository().update_run_log(
            run_id=run_id,
            log_text=log_text,
        )

    try:
        await asyncio.wait_for(
            asyncio.to_thread(_write),
            timeout=JOURNAL_WRITE_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.warning("Не удалось записать heartbeat обновления %s: %s", task_id, exc)


async def run_manual_heartbeat(
    *,
    run_id: str,
    task_id: str,
    started_at: datetime,
    interval: float = HEARTBEAT_INTERVAL_SECONDS,
) -> None:
    """Периодически обновлять лог ручного запуска до его завершения."""
    while True:
        await asyncio.sleep(interval)
        await heartbeat_manual_run(
            run_id=run_id,
            task_id=task_id,
            started_at=started_at,
        )


async def finish_manual_run(
    *,
    run_id: str,
    task_id: str,
    request_path: str,
    request_query: Optional[str],
    started_at: datetime,
    status: str,
    http_status: Optional[int] = None,
    error_message: Optional[str] = None,
    warning_message: Optional[str] = None,
    payload: Any = None,
    exception_text: Optional[str] = None,
) -> None:
    """Зафиксировать завершение ручного обновления."""
    finished_at = utc_now()
    duration_ms = int(max(0.0, (finished_at - started_at).total_seconds() * 1000))
    log_text = build_update_log(
        task_id=task_id,
        trigger=TRIGGER_MANUAL,
        run_id=run_id,
        request_path=request_path,
        request_query=safe_query(request_query or ""),
        started_at=started_at,
        finished_at=finished_at,
        status=status,
        http_status=http_status,
        error_message=error_message,
        warning_message=warning_message,
        payload=payload,
        exception_text=exception_text,
    )

    def _write() -> None:
        repository = DataUpdateRunsRepository()
        repository.finish_run(
            run_id=run_id,
            task_id=task_id,
            trigger=TRIGGER_MANUAL,
            started_at=started_at,
            status=status,
            finished_at=finished_at,
            duration_ms=duration_ms,
            error_message=error_message,
            warning_message=warning_message,
            log_text=log_text,
            request_path=request_path,
            request_query=safe_query(request_query or ""),
        )

    try:
        await asyncio.wait_for(
            asyncio.to_thread(_write),
            timeout=JOURNAL_WRITE_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.warning("Не удалось записать завершение обновления %s: %s", task_id, exc)
