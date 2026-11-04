"""Расчёт истинной доходности портфеля через IRR агрегированного потока."""

from __future__ import annotations

import logging
import math
from datetime import date
from decimal import Decimal
from typing import List, Optional

from app.portfolio.models import PortfolioCashFlow

logger = logging.getLogger(__name__)


def _npv(
    rate: float,
    market_value: float,
    amounts: List[float],
    times: List[float],
) -> float:
    """Считает NPV портфеля при заданной годовой эффективной доходности."""
    total = -market_value
    for amount, years in zip(amounts, times):
        total += amount / ((1.0 + rate) ** years)
    return total


def calculate_portfolio_irr(
    market_value: Decimal,
    valuation_date: date,
    cash_flows: List[PortfolioCashFlow],
) -> Optional[Decimal]:
    """Находит годовую эффективную доходность портфеля методом Brent.

    Возвращает ``None``, если расчёт невозможен: нет будущих положительных
    потоков, стоимость портфеля не положительна, отсутствует scipy или
    корень не найден в расширяемом интервале.
    """
    if market_value <= 0:
        return None

    future_flows = [
        cash_flow
        for cash_flow in cash_flows
        if cash_flow.date > valuation_date and cash_flow.amount > 0
    ]
    if not future_flows:
        return None

    if any(cash_flow.amount < 0 for cash_flow in cash_flows):
        logger.warning("Portfolio IRR: обнаружены отрицательные будущие потоки")
        return None

    try:
        from scipy.optimize import brentq
    except ImportError:
        logger.warning("Portfolio IRR недоступен: библиотека scipy не установлена")
        return None

    times = [
        (cash_flow.date - valuation_date).days / 365.0
        for cash_flow in future_flows
    ]
    amounts = [float(cash_flow.amount) for cash_flow in future_flows]
    market_value_float = float(market_value)

    def npv(rate: float) -> float:
        return _npv(rate, market_value_float, amounts, times)

    lower_bound = -0.9999
    for upper_bound in (1.0, 2.0, 5.0, 10.0):
        try:
            npv_lower = npv(lower_bound)
            npv_upper = npv(upper_bound)
        except (OverflowError, ZeroDivisionError):
            continue

        if npv_lower == 0:
            return Decimal(str(lower_bound))
        if npv_upper == 0:
            return Decimal(str(upper_bound))

        if (npv_lower < 0 < npv_upper) or (npv_upper < 0 < npv_lower):
            try:
                root = brentq(
                    npv,
                    lower_bound,
                    upper_bound,
                    xtol=1e-12,
                    rtol=1e-12,
                    maxiter=1000,
                )
            except (ValueError, RuntimeError, ZeroDivisionError, OverflowError):
                continue

            if math.isfinite(root) and -1.0 < root <= 10.0:
                return Decimal(str(root))

    logger.warning(
        "Portfolio IRR: корень не найден в интервале [-0.9999, 10.0]"
    )
    return None
