"""Расчёт долей купонного периода для поддерживаемых day count conventions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.portfolio.models import DayCountConvention


def actual_days(start: date, end: date) -> int:
    """Возвращает фактическое количество календарных дней между датами."""
    return (end - start).days


def days_30_360(start: date, end: date) -> int:
    """Считает дни по упрощённой конвенции 30/360.

    Используется базовый вариант US 30/360: 31-е число приводится к 30-му,
    а для конечной даты 31-е приводится к 30-му только если начальный день
    уже был приведён к 30-му.
    """
    start_day = min(start.day, 30)
    end_day = end.day
    if start_day == 30 and end_day == 31:
        end_day = 30
    return (
        (end.year - start.year) * 360
        + (end.month - start.month) * 30
        + (end_day - start_day)
    )


def accrued_fraction(
    convention: DayCountConvention,
    period_start: date,
    period_end: date,
    valuation_date: date,
) -> Decimal:
    """Возвращает долю купона, накопленную к дате оценки.

    Для ACT/365 Fixed и ACT/360 знаменатель фиксирован (365/360), поэтому
    доля может не совпадать с отношением фактических дней периода.
    """
    if valuation_date < period_start:
        raise ValueError("Дата оценки раньше начала купонного периода")
    if valuation_date >= period_end:
        return Decimal("0")

    if convention == DayCountConvention.ACT_ACT:
        period_days = actual_days(period_start, period_end)
        if period_days <= 0:
            raise ValueError("Некорректный купонный период")
        return Decimal(actual_days(period_start, valuation_date)) / Decimal(period_days)

    if convention == DayCountConvention.ACT_365_FIXED:
        return Decimal(actual_days(period_start, valuation_date)) / Decimal(365)

    if convention == DayCountConvention.ACT_360:
        return Decimal(actual_days(period_start, valuation_date)) / Decimal(360)

    if convention == DayCountConvention.THIRTY_360:
        period_days = days_30_360(period_start, period_end)
        if period_days <= 0:
            raise ValueError("Некорректный купонный период")
        return Decimal(days_30_360(period_start, valuation_date)) / Decimal(period_days)

    raise ValueError(f"Неподдерживаемая конвенция расчёта дней: {convention}")


def accrued_days(
    convention: DayCountConvention,
    period_start: date,
    valuation_date: date,
) -> int:
    """Возвращает количество дней, прошедших с начала периода."""
    if convention == DayCountConvention.THIRTY_360:
        return days_30_360(period_start, valuation_date)
    return actual_days(period_start, valuation_date)


def period_days(
    convention: DayCountConvention,
    period_start: date,
    period_end: date,
) -> int:
    """Возвращает количество дней в текущем купонном периоде."""
    if convention == DayCountConvention.THIRTY_360:
        return days_30_360(period_start, period_end)
    return actual_days(period_start, period_end)
