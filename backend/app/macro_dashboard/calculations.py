"""Date-aware calculations shared by the dashboard's indicators and signals."""

from __future__ import annotations

import calendar
import math
from datetime import date, datetime, timedelta
from typing import Any, Iterable


def parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    for candidate in (text[:10], text):
        try:
            return date.fromisoformat(candidate)
        except ValueError:
            pass
    for pattern in ("%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def as_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def row_value(row: Any, *keys: str) -> Any:
    if isinstance(row, dict):
        for key in keys:
            if key in row:
                return row[key]
        return None
    for key in keys:
        value = getattr(row, key, None)
        if value is not None:
            return value
    return None


def normalize_series(
    rows: Iterable[Any],
    *,
    date_keys: tuple[str, ...],
    value_keys: tuple[str, ...],
    transform=None,
) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for row in rows or []:
        observed_date = parse_date(row_value(row, *date_keys))
        if observed_date is None:
            continue
        value = as_number(row_value(row, *value_keys))
        if value is not None and transform is not None:
            value = transform(value)
        points.append({"date": observed_date.isoformat(), "_date": observed_date, "value": value})
    points.sort(key=lambda item: item["_date"])
    # Keep the last source row if an upstream service returned duplicate dates.
    by_date = {item["date"]: item for item in points}
    return list(by_date.values())


def _month_number(value: date) -> int:
    return value.year * 12 + value.month - 1


def _shift_month(value: date, months: int) -> date:
    month_number = _month_number(value) + months
    year, month_zero = divmod(month_number, 12)
    month = month_zero + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _lookup_at_or_before(
    series: list[dict[str, Any]],
    target: date,
    *,
    max_age_days: int | None,
) -> dict[str, Any] | None:
    match = next((point for point in reversed(series) if point["_date"] <= target and point["value"] is not None), None)
    if match is None:
        return None
    if max_age_days is not None and (target - match["_date"]).days > max_age_days:
        return None
    return match


def _monthly_value_map(series: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {_month_number(point["_date"]): point for point in series}


def _monthly_lag_point(series: list[dict[str, Any]], latest: dict[str, Any], months: int) -> dict[str, Any] | None:
    return _monthly_value_map(series).get(_month_number(latest["_date"]) - months)


def summarize_series(series: list[dict[str, Any]], *, frequency: str) -> dict[str, Any]:
    valid = [point for point in series if point.get("value") is not None]
    if not valid:
        return {
            "value": None, "date": None, "change": None,
            "change_3m": None, "change_6m": None,
            "mean_recent": None, "mean_previous": None, "trend_delta": None,
            "status": "insufficient_data",
        }

    latest = valid[-1]
    previous = None
    if len(valid) > 1:
        candidate = valid[-2]
        gap = (latest["_date"] - candidate["_date"]).days
        if frequency == "monthly":
            if _month_number(latest["_date"]) - _month_number(candidate["_date"]) == 1:
                previous = candidate
        elif frequency == "weekly":
            if 5 <= gap <= 10:
                previous = candidate
        elif frequency == "daily":
            if 0 < gap <= 10:
                previous = candidate
        else:
            previous = candidate

    def period_change(months: int) -> float | None:
        if frequency == "monthly":
            old = _monthly_lag_point(valid, latest, months)
        else:
            target = _shift_month(latest["_date"], -months)
            max_age = 14 if frequency == "weekly" else (10 if frequency == "daily" else None)
            old = _lookup_at_or_before(valid, target, max_age_days=max_age)
        return latest["value"] - old["value"] if old is not None else None

    recent_mean = previous_mean = trend_delta = None
    if frequency == "monthly":
        values = _monthly_value_map(valid)
        end_month = _month_number(latest["_date"])
        current = [values.get(end_month - offset) for offset in (2, 1, 0)]
        earlier = [values.get(end_month - offset) for offset in (5, 4, 3)]
        if all(item is not None and item["value"] is not None for item in current + earlier):
            recent_mean = sum(item["value"] for item in current) / 3
            previous_mean = sum(item["value"] for item in earlier) / 3
            trend_delta = recent_mean - previous_mean
    elif frequency == "weekly" and len(valid) >= 8:
        recent = valid[-4:]
        earlier = valid[-8:-4]
        gaps = [(valid[index]["_date"] - valid[index - 1]["_date"]).days for index in range(len(valid) - 7, len(valid))]
        if all(5 <= gap <= 10 for gap in gaps):
            recent_mean = sum(item["value"] for item in recent) / 4
            previous_mean = sum(item["value"] for item in earlier) / 4
            trend_delta = recent_mean - previous_mean

    return {
        "value": latest["value"],
        "date": latest["date"],
        "change": latest["value"] - previous["value"] if previous else None,
        "change_3m": period_change(3),
        "change_6m": period_change(6),
        "mean_recent": recent_mean,
        "mean_previous": previous_mean,
        "trend_delta": trend_delta,
        "status": "available",
    }


def monthly_cpi_series(rows: Iterable[Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    indexes = normalize_series(
        rows,
        date_keys=("record_data", "record_date", "recorddata"),
        value_keys=("ipc", "monthly_ipc", "ИПЦ"),
    )
    index_by_month: dict[int, dict[str, Any]] = {}
    inflation: list[dict[str, Any]] = []
    for point in indexes:
        index_by_month[_month_number(point["_date"])] = point
        inflation.append({
            "date": point["date"],
            "_date": point["_date"],
            "value": point["value"] - 100 if point["value"] is not None else None,
        })

    yoy: list[dict[str, Any]] = []
    for point in indexes:
        end_month = _month_number(point["_date"])
        annual = [index_by_month.get(end_month - offset) for offset in range(11, -1, -1)]
        annual_value = None
        if all(item is not None and item["value"] is not None for item in annual):
            factor = 1.0
            for item in annual:
                factor *= item["value"] / 100
            annual_value = (factor - 1) * 100
        yoy.append({"date": point["date"], "_date": point["_date"], "value": annual_value})
    return inflation, yoy


def weekly_cpi_series(rows: Iterable[Any]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for row in rows or []:
        start = parse_date(row_value(row, "start_date"))
        end = parse_date(row_value(row, "end_date")) or start
        if end is None:
            continue
        index = as_number(row_value(row, "ipc_weekly"))
        points.append({
            "date": end.isoformat(),
            "start_date": start.isoformat() if start else None,
            "_date": end,
            "value": index - 100 if index is not None else None,
        })
    points.sort(key=lambda item: item["_date"])
    by_date = {item["date"]: item for item in points}
    return list(by_date.values())


def signal_from_delta(delta: float | None, threshold: float) -> int | None:
    if delta is None:
        return None
    if delta > threshold:
        return 1
    if delta < -threshold:
        return -1
    return 0


def dated_rows(rows: Iterable[Any], *, date_keys: tuple[str, ...], value_keys: tuple[str, ...]) -> list[dict[str, Any]]:
    return normalize_series(rows, date_keys=date_keys, value_keys=value_keys)


def shift_month(value: date, months: int) -> date:
    """Public calendar-month shift helper used to request bounded histories."""
    return _shift_month(value, months)


def lookup_as_of(series: list[dict[str, Any]], target: date, *, max_age_days: int | None = None) -> dict[str, Any] | None:
    return _lookup_at_or_before(series, target, max_age_days=max_age_days)
