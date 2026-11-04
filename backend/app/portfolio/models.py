"""Внутренние модели данных модуля оценки портфеля облигаций."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional


class DayCountConvention(str, Enum):
    """Поддерживаемые конвенции расчёта дней для НКД."""

    ACT_ACT = "ACT/ACT"
    ACT_365_FIXED = "ACT/365"
    ACT_360 = "ACT/360"
    THIRTY_360 = "30/360"

    @classmethod
    def from_value(cls, value: object) -> "DayCountConvention":
        """Нормализует значение из модели облигации в известную конвенцию.

        Неизвестное или отсутствующее значение трактуется как ACT/ACT
        в соответствии с требованиями MVP.
        """
        if value is None:
            return cls.ACT_ACT
        if isinstance(value, cls):
            return value

        text = (
            str(value)
            .strip()
            .upper()
            .replace(" ", "")
            .replace("_", "/")
            .replace("-", "/")
        )
        aliases = {
            "ACT/ACT": cls.ACT_ACT,
            "ACTUAL/ACTUAL": cls.ACT_ACT,
            "ACT/365": cls.ACT_365_FIXED,
            "ACT/365F": cls.ACT_365_FIXED,
            "ACT/365FIXED": cls.ACT_365_FIXED,
            "ACT/365/FIXED": cls.ACT_365_FIXED,
            "ACT/360": cls.ACT_360,
            "30/360": cls.THIRTY_360,
            "360/360": cls.THIRTY_360,
        }
        return aliases.get(text, cls.ACT_ACT)


@dataclass(frozen=True)
class CouponScheduleItem:
    """Одна запись фактического графика купонных выплат."""

    coupondate: date
    startdate: Optional[date]
    value: Decimal
    facevalue: Optional[Decimal] = None
    valueprc: Optional[Decimal] = None


@dataclass(frozen=True)
class BondValuationInput:
    """Данные облигации, необходимые для оценки одной позиции."""

    bond_id: Optional[int]
    secid: str
    isin: Optional[str]
    name: Optional[str]
    nominal: Decimal
    clean_price: Decimal
    ytm: Optional[Decimal]
    maturity_date: date
    coupon_frequency: Optional[Decimal]
    coupon_period_days: Optional[int]
    day_count_convention: DayCountConvention
    coupons: tuple[CouponScheduleItem, ...]
    currency: Optional[str]
    face_unit: Optional[str]
    warnings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AccruedInterestResult:
    """Результат расчёта НКД одной облигации."""

    accrued_interest: Decimal
    accrued_interest_percent: Decimal
    days_accrued: int
    days_in_period: int
    day_count_fraction: Decimal
    period_start: date
    period_end: date
    coupon_value: Decimal


@dataclass(frozen=True)
class BondCashFlow:
    """Будущий денежный поток одной облигации."""

    date: date
    amount: Decimal
    kind: str


@dataclass(frozen=True)
class PortfolioCashFlow:
    """Агрегированный будущий денежный поток портфеля."""

    date: date
    amount: Decimal
