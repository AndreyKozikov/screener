from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() and parsed > 0 else None


def _as_float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def calculate_ipc_kpis(
    monthly_data: list[dict[str, Any]],
    weekly_data: list[dict[str, Any]],
    today: date | None = None,
) -> dict[str, Any]:
    """Calculate CPI KPI values without rounding; presentation rounds them."""
    month_rows: list[tuple[date, Decimal | None]] = []
    monthly_by_period: dict[tuple[int, int], tuple[date, Decimal | None]] = {}
    for row in monthly_data:
        record_date = _parse_date(row.get("record_data"))
        if record_date is None:
            continue
        value = _decimal(row.get("ipc"))
        month_rows.append((record_date, value))
        monthly_by_period[(record_date.year, record_date.month)] = (record_date, value)
    month_rows.sort(key=lambda item: item[0])

    latest_month_date, latest_month_index = month_rows[-1] if month_rows else (None, None)
    latest_month_inflation = latest_month_index - Decimal("100") if latest_month_index is not None else None
    previous_month_index: Decimal | None = None
    if latest_month_date is not None:
        previous_month = latest_month_date.month - 1
        previous_year = latest_month_date.year
        if previous_month == 0:
            previous_year -= 1
            previous_month = 12
        previous = monthly_by_period.get((previous_year, previous_month))
        previous_month_index = previous[1] if previous else None
    monthly_change = (
        latest_month_index - previous_month_index
        if latest_month_index is not None and previous_month_index is not None
        else None
    )

    week_rows: list[tuple[date, date, Decimal | None]] = []
    for row in weekly_data:
        start_date = _parse_date(row.get("start_date"))
        end_date = _parse_date(row.get("end_date"))
        if start_date is None or end_date is None:
            continue
        week_rows.append((start_date, end_date, _decimal(row.get("ipc_weekly"))))
    week_rows.sort(key=lambda item: (item[1], item[0]))

    latest_week = week_rows[-1] if week_rows else None
    latest_week_index = latest_week[2] if latest_week else None
    latest_week_inflation = latest_week_index - Decimal("100") if latest_week_index is not None else None
    previous_week_index = week_rows[-2][2] if len(week_rows) > 1 else None
    weekly_change = (
        latest_week_index - previous_week_index
        if latest_week_index is not None and previous_week_index is not None
        else None
    )

    current_year = (today or date.today()).year
    year_rows = [row for row in month_rows if row[0].year == current_year]
    year_to_date_inflation: Decimal | None = None
    year_to_date_from: date | None = None
    year_to_date_to: date | None = None
    if year_rows:
        target_month = max(row[0].month for row in year_rows)
        values: list[Decimal] = []
        complete = True
        for month in range(1, target_month + 1):
            item = monthly_by_period.get((current_year, month))
            if item is None or item[1] is None:
                complete = False
                break
            if month == 1:
                year_to_date_from = item[0]
            year_to_date_to = item[0]
            values.append(item[1])
        if complete:
            product = Decimal("1")
            for value in values:
                product *= value / Decimal("100")
            year_to_date_inflation = (product - Decimal("1")) * Decimal("100")

    def rolling_index(end_year: int, end_month: int) -> tuple[Decimal | None, date | None, date | None]:
        values: list[Decimal] = []
        start_date: date | None = None
        end_date: date | None = None
        for offset in range(11, -1, -1):
            absolute_month = end_year * 12 + end_month - 1 - offset
            period = (absolute_month // 12, absolute_month % 12 + 1)
            item = monthly_by_period.get(period)
            if item is None or item[1] is None:
                return None, None, None
            if not values:
                start_date = item[0]
            end_date = item[0]
            values.append(item[1])

        product = Decimal("1")
        for value in values:
            product *= value / Decimal("100")
        return product * Decimal("100"), start_date, end_date

    twelve_month_index: Decimal | None = None
    twelve_month_inflation: Decimal | None = None
    twelve_month_change: Decimal | None = None
    twelve_month_from: date | None = None
    twelve_month_to: date | None = None
    if month_rows:
        latest_year, latest_month = latest_month_date.year, latest_month_date.month
        twelve_month_index, twelve_month_from, twelve_month_to = rolling_index(latest_year, latest_month)
        previous_absolute_month = latest_year * 12 + latest_month - 2
        previous_year, previous_month = previous_absolute_month // 12, previous_absolute_month % 12 + 1
        previous_twelve_month_index, _, _ = rolling_index(previous_year, previous_month)
        if twelve_month_index is not None:
            twelve_month_inflation = twelve_month_index - Decimal("100")
        if twelve_month_index is not None and previous_twelve_month_index is not None:
            twelve_month_change = twelve_month_index - previous_twelve_month_index

    observation_dates = [row[0] for row in month_rows]
    observation_dates.extend(row[1] for row in week_rows)
    latest_observation = max(observation_dates) if observation_dates else None

    return {
        "monthly": {
            "index": _as_float(latest_month_index),
            "inflation": _as_float(latest_month_inflation),
            "change": _as_float(monthly_change),
            "date": latest_month_date.isoformat() if latest_month_date else None,
        },
        "weekly": {
            "index": _as_float(latest_week_index),
            "inflation": _as_float(latest_week_inflation),
            "change": _as_float(weekly_change),
            "start_date": latest_week[0].isoformat() if latest_week else None,
            "end_date": latest_week[1].isoformat() if latest_week else None,
        },
        "year_to_date": {
            "inflation": _as_float(year_to_date_inflation),
            "year": current_year,
            "from_date": year_to_date_from.isoformat() if year_to_date_from else None,
            "to_date": year_to_date_to.isoformat() if year_to_date_to else None,
        },
        "twelve_month": {
            "index": _as_float(twelve_month_index),
            "inflation": _as_float(twelve_month_inflation),
            "change": _as_float(twelve_month_change),
            "from_date": twelve_month_from.isoformat() if twelve_month_from else None,
            "to_date": twelve_month_to.isoformat() if twelve_month_to else None,
        },
        "last_observation_date": latest_observation.isoformat() if latest_observation else None,
    }
