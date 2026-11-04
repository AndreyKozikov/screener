"""Формирование будущих денежных потоков облигации и портфеля."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Iterable, List

from app.portfolio.models import (
    BondCashFlow,
    BondValuationInput,
    PortfolioCashFlow,
)


def calculate_bond_cash_flows(
    bond: BondValuationInput,
    quantity: int,
    valuation_date: date,
) -> List[BondCashFlow]:
    """Формирует будущие купоны и погашение номинала по одной облигации.

    Выплаты до даты оценки и после даты погашения не включаются. Купон,
    дата выплаты которого совпадает с датой оценки, считается уже выплаченным.
    """
    if quantity <= 0:
        return []
    if bond.maturity_date <= valuation_date:
        return []

    flows: List[BondCashFlow] = []
    for coupon in bond.coupons:
        if coupon.coupondate <= valuation_date:
            continue
        if coupon.coupondate > bond.maturity_date:
            continue
        amount = coupon.value * quantity
        if amount <= 0:
            continue
        flows.append(
            BondCashFlow(
                date=coupon.coupondate,
                amount=amount,
                kind="coupon",
            )
        )

    redemption = bond.nominal * quantity
    if redemption > 0:
        flows.append(
            BondCashFlow(
                date=bond.maturity_date,
                amount=redemption,
                kind="redemption",
            )
        )

    return flows


def consolidate_cash_flows(
    cash_flows: Iterable[BondCashFlow],
) -> List[PortfolioCashFlow]:
    """Объединяет денежные потоки по датам и сортирует по возрастанию даты."""
    totals: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
    for cash_flow in cash_flows:
        totals[cash_flow.date] += cash_flow.amount

    return [
        PortfolioCashFlow(date=cash_date, amount=totals[cash_date])
        for cash_date in sorted(totals)
    ]
