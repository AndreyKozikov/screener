"""Калькулятор накопленного купонного дохода (НКД)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional, Tuple

from app.portfolio.calculators.day_count import (
    accrued_days,
    accrued_fraction,
    period_days,
)
from app.portfolio.exceptions import PortfolioValuationError
from app.portfolio.models import (
    AccruedInterestResult,
    BondValuationInput,
    CouponScheduleItem,
)


def _period_start_for_coupon(
    bond: BondValuationInput,
    coupons: tuple[CouponScheduleItem, ...],
    index: int,
    coupon: CouponScheduleItem,
) -> Optional[date]:
    """Определяет начало купонного периода для записи графика."""
    if coupon.startdate is not None:
        return coupon.startdate

    if index > 0:
        return coupons[index - 1].coupondate

    return None


def _select_current_period(
    bond: BondValuationInput,
    valuation_date: date,
) -> Tuple[date, date, Decimal]:
    """Выбирает текущий купонный период и размер купона.

    Возвращает (начало периода, конец периода, размер купона). Если будущих
    купонов нет, но облигация ещё не погашена, возвращается период с нулевым
    купоном — НКД в этом случае равен нулю.
    """
    coupons = bond.coupons
    if not coupons:
        raise PortfolioValuationError(
            f"Не удалось определить текущий купонный период для {bond.secid}: "
            "график купонных выплат отсутствует"
        )

    for index, coupon in enumerate(coupons):
        if coupon.coupondate <= valuation_date:
            continue

        period_start = _period_start_for_coupon(bond, coupons, index, coupon)
        if period_start is None:
            raise PortfolioValuationError(
                f"Не удалось определить текущий купонный период для {bond.secid}: "
                "в графике отсутствует дата начала периода"
            )
        if period_start > valuation_date:
            raise PortfolioValuationError(
                f"Дата оценки {valuation_date.isoformat()} находится вне допустимого "
                f"периода существования облигации {bond.secid}"
            )
        return period_start, coupon.coupondate, coupon.value

    raise PortfolioValuationError(
        f"Не удалось определить текущий купонный период для {bond.secid}: "
        "в графике нет выплаты после даты оценки"
    )


def calculate_accrued_interest(
    bond: BondValuationInput,
    valuation_date: date,
) -> AccruedInterestResult:
    """Рассчитывает НКД одной облигации на дату оценки."""
    if bond.nominal <= 0:
        raise PortfolioValuationError(
            f"Номинал облигации {bond.secid} должен быть положительным"
        )
    if valuation_date >= bond.maturity_date:
        raise PortfolioValuationError(
            f"Облигация {bond.secid} погашена или погашается на дату оценки"
        )

    period_start, period_end, coupon_value = _select_current_period(bond, valuation_date)

    try:
        fraction = accrued_fraction(
            bond.day_count_convention,
            period_start,
            period_end,
            valuation_date,
        )
    except ValueError as exc:
        raise PortfolioValuationError(
            f"Не удалось рассчитать НКД для {bond.secid}: {exc}"
        ) from exc

    if fraction < 0:
        fraction = Decimal("0")

    accrued_interest = coupon_value * fraction
    if accrued_interest < 0:
        accrued_interest = Decimal("0")

    accrued_interest_percent = accrued_interest / bond.nominal * Decimal("100")

    return AccruedInterestResult(
        accrued_interest=accrued_interest,
        accrued_interest_percent=accrued_interest_percent,
        days_accrued=accrued_days(bond.day_count_convention, period_start, valuation_date),
        days_in_period=period_days(bond.day_count_convention, period_start, period_end),
        day_count_fraction=fraction,
        period_start=period_start,
        period_end=period_end,
        coupon_value=coupon_value,
    )
