"""Сбор расписания плановых обновлений данных.

Источником истины для расписания служит systemd: по каждому таймеру
запрашиваются объявленный ``OnCalendar``, состояние включения и время
следующего запуска. Если systemd недоступен (локальная разработка или
контейнер), расписание читается из ``deploy/systemd/*.timer``, а время
следующего запуска остаётся неизвестным.
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

#: Каталог с исходными unit-файлами в репозитории.
DEPLOY_SYSTEMD_DIR = Path(__file__).resolve().parents[3] / "deploy" / "systemd"

SYSTEMCTL_TIMEOUT_SECONDS = 5.0
CACHE_TTL_SECONDS = 15.0

_SHOW_PROPERTIES = (
    "LoadState",
    "ActiveState",
    "UnitFileState",
    "NextElapseUSecRealtime",
    "LastTriggerUSec",
)

#: Состояния unit-файла, при которых таймер считается включённым.
_ENABLED_UNIT_FILE_STATES = frozenset(
    {"enabled", "enabled-runtime", "static", "indirect", "generated", "linked", "alias"}
)

_WEEKDAY_LABELS = {
    "mon": "пн",
    "tue": "вт",
    "wed": "ср",
    "thu": "чт",
    "fri": "пт",
    "sat": "сб",
    "sun": "вс",
}

_TIME_RE = re.compile(
    r"^(?P<hour>\d{1,2})(?:/(?P<step>\d+))?:(?P<minute>\d{2})(?::(?P<second>\d{2}))?$"
)
_DAY_RANGE_RE = re.compile(r"^\*-\*-(?P<start>\d{1,2})\.\.(?P<end>\d{1,2})$")


@dataclass(frozen=True)
class ScheduledUpdate:
    """Плановая задача обновления и её systemd-юниты."""

    task_id: str
    timer_unit: str
    service_unit: str


#: Задачи, которые запускаются автоматически. Порядок совпадает с пунктами
#: обновления данных в интерфейсе. Задачи без таймера сюда не входят.
SCHEDULED_UPDATES: tuple[ScheduledUpdate, ...] = (
    ScheduledUpdate(
        "bonds",
        "bondsscreener-data-update-bonds.timer",
        "bondsscreener-data-update@bonds.service",
    ),
    ScheduledUpdate(
        "zerocupon",
        "bondsscreener-data-update-zerocupon.timer",
        "bondsscreener-data-update@zerocupon.service",
    ),
    ScheduledUpdate(
        "ratings",
        "bondsscreener-data-update-ratings.timer",
        "bondsscreener-data-update@ratings.service",
    ),
    ScheduledUpdate(
        "emitents",
        "bondsscreener-data-update-emitents.timer",
        "bondsscreener-data-update@emitents.service",
    ),
    ScheduledUpdate(
        "coupons",
        "bondsscreener-data-update-coupons.timer",
        "bondsscreener-data-update@coupons.service",
    ),
    ScheduledUpdate(
        "currency",
        "bondsscreener-data-update-currency.timer",
        "bondsscreener-data-update@currency.service",
    ),
    ScheduledUpdate(
        "ruonia",
        "bondsscreener-data-update-ruonia.timer",
        "bondsscreener-data-update@ruonia.service",
    ),
    ScheduledUpdate(
        "keyrate",
        "bondsscreener-data-update-keyrate.timer",
        "bondsscreener-data-update@keyrate.service",
    ),
    ScheduledUpdate(
        "trading-history",
        "bondsscreener-data-update-trading-history.timer",
        "bondsscreener-data-update@trading_history.service",
    ),
    ScheduledUpdate(
        "ipc",
        "bondsscreener-data-update-ipc.timer",
        "bondsscreener-data-update@ipc.service",
    ),
    ScheduledUpdate(
        "inflation-expectations",
        "bondsscreener-data-update-inflation-expectations.timer",
        "bondsscreener-data-update@inflation_expectations.service",
    ),
)


@dataclass(frozen=True)
class UpdateScheduleSnapshot:
    """Снимок расписания плановых обновлений."""

    generated_at: str
    systemd_available: bool
    items: list[dict[str, Any]]


_cache: Optional[tuple[float, bool, list[dict[str, Any]]]] = None


def _utc_iso_now() -> str:
    """Вернуть текущее время UTC в ISO 8601."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_timer_values(path: Path, key: str) -> list[str]:
    """Прочитать все значения ключа из unit-файла таймера."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Не удалось прочитать %s: %s", path.name, exc)
        return []

    values: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", ";", "[")):
            continue
        name, separator, value = line.partition("=")
        if separator and name.strip() == key and value.strip():
            values.append(value.strip())
    return values


def _hours_word(value: int) -> str:
    """Согласовать слово «час» с числом."""
    remainder_100 = value % 100
    remainder_10 = value % 10
    if 11 <= remainder_100 <= 14:
        return "часов"
    if remainder_10 == 1:
        return "час"
    if 2 <= remainder_10 <= 4:
        return "часа"
    return "часов"


def _describe_day(day: str) -> Optional[str]:
    """Перевести календарный день systemd в русское описание."""
    text = day.strip()
    if text in {"*-*-*", "*"}:
        return "ежедневно"
    match = _DAY_RANGE_RE.match(text)
    if match is not None:
        return f"{match.group('start')}–{match.group('end')} числа"
    weekdays = [part.strip().lower() for part in text.split(",") if part.strip()]
    if weekdays and all(part in _WEEKDAY_LABELS for part in weekdays):
        return ", ".join(_WEEKDAY_LABELS[part] for part in weekdays)
    return None


def describe_schedule(on_calendar: Optional[str]) -> Optional[str]:
    """Сформировать понятное человеку описание ``OnCalendar``.

    Поддерживаются шаблоны, которые используются в проекте. Для остальных
    выражений возвращается ``None``, и интерфейс показывает исходную строку.
    """
    if not on_calendar:
        return None
    tokens = on_calendar.strip().split()
    if not tokens:
        return None
    time_index = next((index for index, token in enumerate(tokens) if ":" in token), None)
    if time_index is None:
        return None

    match = _TIME_RE.match(tokens[time_index])
    if match is None:
        return None
    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    step = match.group("step")
    if step and minute == 0:
        step_value = int(step)
        if step_value == 1:
            return "каждый час"
        return f"каждые {step_value} {_hours_word(step_value)}"

    day_text = _describe_day(" ".join(tokens[:time_index]))
    if day_text is None:
        return None
    return f"{day_text} в {hour:02d}:{minute:02d}"


def parse_show_output(text: str) -> dict[str, str]:
    """Разобрать вывод ``systemctl show`` в словарь свойств."""
    properties: dict[str, str] = {}
    for line in text.splitlines():
        name, separator, value = line.partition("=")
        if separator:
            properties[name.strip()] = value.strip()
    return properties


def usec_to_iso(value: Optional[str]) -> Optional[str]:
    """Перевести микросекунды epoch из systemd в ISO 8601 UTC."""
    if not value:
        return None
    try:
        usec = int(value)
    except (TypeError, ValueError):
        return None
    if usec <= 0:
        return None
    try:
        moment = datetime.fromtimestamp(usec / 1_000_000, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None
    return moment.isoformat().replace("+00:00", "Z")


def _find_systemctl() -> Optional[str]:
    """Найти исполняемый файл systemctl, если он доступен."""
    return shutil.which("systemctl")


async def _terminate_process(process: Optional[asyncio.subprocess.Process]) -> None:
    """Завершить зависший процесс systemctl."""
    if process is None or process.returncode is not None:
        return
    process.kill()
    await process.wait()


async def _show_unit(systemctl: str, unit: str) -> Optional[dict[str, str]]:
    """Запросить свойства таймера через ``systemctl show``."""
    command = [systemctl, "--no-pager", "show"]
    for name in _SHOW_PROPERTIES:
        command.extend(["-p", name])
    command.append(unit)

    process: Optional[asyncio.subprocess.Process] = None
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=SYSTEMCTL_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning("systemctl show %s не ответил за отведённое время", unit)
        await _terminate_process(process)
        return None
    except (FileNotFoundError, PermissionError, OSError) as exc:
        logger.warning("Не удалось получить состояние %s: %s", unit, exc)
        await _terminate_process(process)
        return None

    if process.returncode not in (0, 1):
        logger.warning(
            "systemctl show %s завершился с кодом %s: %s",
            unit,
            process.returncode,
            stderr.decode("utf-8", errors="replace").strip(),
        )
        return None

    properties = parse_show_output(stdout.decode("utf-8", errors="replace"))
    if not properties:
        error_text = stderr.decode("utf-8", errors="replace").lower()
        if "could not be loaded" in error_text or "not found" in error_text:
            return {"LoadState": "not-found"}
        return None
    return properties


def _state_for(properties: dict[str, str]) -> tuple[str, Optional[bool], Optional[bool]]:
    """Определить состояние таймера по свойствам systemd.

    Returns:
        Кортеж (состояние, включён, активен).
    """
    load_state = properties.get("LoadState")
    active_state = properties.get("ActiveState")
    unit_file_state = properties.get("UnitFileState")

    active = active_state == "active" if active_state else None
    enabled = (
        unit_file_state in _ENABLED_UNIT_FILE_STATES if unit_file_state else None
    )

    if load_state == "not-found":
        return "not_installed", False, False
    if unit_file_state in {"disabled", "masked", "bad"}:
        return "disabled", False, active
    if active is False:
        return "paused", enabled, False
    return "scheduled", enabled, active


def _build_item(
    entry: ScheduledUpdate,
    *,
    schedule: Optional[str],
    properties: Optional[dict[str, str]],
) -> dict[str, Any]:
    """Собрать элемент расписания по данным systemd или unit-файла."""
    if properties is None:
        return {
            "task_id": entry.task_id,
            "timer_unit": entry.timer_unit,
            "service_unit": entry.service_unit,
            "schedule": schedule,
            "schedule_human": describe_schedule(schedule),
            "enabled": None,
            "active": None,
            "next_elapse": None,
            "last_trigger_at": None,
            "state": "unknown",
            "source": "files",
        }

    state, enabled, active = _state_for(properties)
    return {
        "task_id": entry.task_id,
        "timer_unit": entry.timer_unit,
        "service_unit": entry.service_unit,
        "schedule": schedule,
        "schedule_human": describe_schedule(schedule),
        "enabled": enabled,
        "active": active,
        "next_elapse": usec_to_iso(properties.get("NextElapseUSecRealtime")),
        "last_trigger_at": usec_to_iso(properties.get("LastTriggerUSec")),
        "state": state,
        "source": "systemd",
    }


async def collect_update_schedule(
    *,
    systemd_dir: Optional[Path] = None,
    use_cache: bool = True,
) -> UpdateScheduleSnapshot:
    """Собрать расписание плановых обновлений и время следующего запуска."""
    global _cache

    now_monotonic = time.monotonic()
    if use_cache and _cache is not None:
        expires_at, systemd_available, items = _cache
        if now_monotonic < expires_at:
            return UpdateScheduleSnapshot(
                generated_at=_utc_iso_now(),
                systemd_available=systemd_available,
                items=list(items),
            )

    directory = systemd_dir or DEPLOY_SYSTEMD_DIR
    systemctl = _find_systemctl()

    show_results: list[Optional[dict[str, str]]] = [None] * len(SCHEDULED_UPDATES)
    if systemctl:
        show_results = await asyncio.gather(
            *(_show_unit(systemctl, entry.timer_unit) for entry in SCHEDULED_UPDATES)
        )

    items: list[dict[str, Any]] = []
    for entry, properties in zip(SCHEDULED_UPDATES, show_results):
        schedule_values = _read_timer_values(directory / entry.timer_unit, "OnCalendar")
        schedule = " ; ".join(schedule_values) if schedule_values else None
        items.append(_build_item(entry, schedule=schedule, properties=properties))

    systemd_available = any(properties is not None for properties in show_results)
    if use_cache:
        _cache = (now_monotonic + CACHE_TTL_SECONDS, systemd_available, items)

    return UpdateScheduleSnapshot(
        generated_at=_utc_iso_now(),
        systemd_available=systemd_available,
        items=items,
    )


def reset_cache() -> None:
    """Сбросить кэш расписания."""
    global _cache
    _cache = None
