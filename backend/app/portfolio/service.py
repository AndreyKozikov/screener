"""Сервис полной оценки портфеля облигаций."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from app.portfolio.calculators import (
    calculate_accrued_interest,
    calculate_bond_cash_flows,
    calculate_portfolio_irr,
    consolidate_cash_flows,
)
from app.portfolio.data_provider import PortfolioDataProvider
from app.portfolio.dto import (
    PortfolioPositionInputDTO,
    PortfolioPositionValuationDTO,
    PortfolioValuationDTO,
    PortfolioValuationRequestDTO,
)
from app.portfolio.exceptions import PortfolioValuationError
from app.portfolio.models import (
    AccruedInterestResult,
    BondCashFlow,
    BondValuationInput,
)

MONEY_QUANT = Decimal("0.01")
PRICE_QUANT = Decimal("0.0001")
PERCENT_QUANT = Decimal("0.0001")
WEIGHT_QUANT = Decimal("0.00000001")
YTM_QUANT = Decimal("0.000001")


def _value(obj: Any, name: str, default: Any = None) -> Any:
    """Читает поле из AttrDict, словаря или ORM-подобного объекта."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _round(value: Decimal, quantum: Decimal) -> Decimal:
    """Округляет значение до заданного количества знаков для DTO."""
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def _weighted_average_price(
    first_price: Optional[Decimal],
    first_quantity: int,
    second_price: Optional[Decimal],
    second_quantity: int,
) -> Optional[Decimal]:
    """Считает средневзвешенную цену покупки при объединении дублей."""
    if first_price is None and second_price is None:
        return None
    if first_price is None:
        return second_price
    if second_price is None:
        return first_price
    total_quantity = first_quantity + second_quantity
    if total_quantity <= 0:
        return None
    return (
        first_price * Decimal(first_quantity)
        + second_price * Decimal(second_quantity)
    ) / Decimal(total_quantity)


@dataclass
class _ResolvedPosition:
    """Позиция портфеля после сопоставления с SECID."""

    secid: str
    isin: Optional[str]
    quantity: int
    average_purchase_price: Optional[Decimal]
    detail: Any = None


@dataclass
class _PositionCalculation:
    """Промежуточные результаты расчёта одной позиции."""

    position: _ResolvedPosition
    bond: BondValuationInput
    accrued: AccruedInterestResult
    dirty_price: Decimal
    market_value: Decimal
    cash_flows: List[BondCashFlow]


class PortfolioValuationService:
    """Выполняет полный цикл оценки портфеля на заданную дату."""

    def __init__(self, data_provider: Optional[PortfolioDataProvider] = None) -> None:
        self._data_provider = data_provider or PortfolioDataProvider()

    def valuate(self, request: PortfolioValuationRequestDTO) -> PortfolioValuationDTO:
        """Оценивает портфель, состав которого передан с фронтенда."""
        valuation_date = request.valuation_date or date.today()
        warnings: List[str] = []

        resolved_positions = self._resolve_positions(request.positions, warnings)
        if not resolved_positions:
            raise PortfolioValuationError(
                "Портфель не содержит позиций с положительным количеством облигаций"
            )

        positions = self._aggregate_positions(resolved_positions, warnings)
        self._ensure_bond_details(positions)

        coupons_by_secid = self._data_provider.get_coupons(
            [position.secid for position in positions]
        )

        calculations: List[_PositionCalculation] = []
        all_cash_flows: List[BondCashFlow] = []
        currencies: set[str] = set()

        for position in positions:
            bond = self._data_provider.build_bond_input(
                secid=position.secid,
                detail=position.detail,
                coupon_rows=coupons_by_secid.get(position.secid, []),
                valuation_date=valuation_date,
            )
            warnings.extend(bond.warnings)
            if bond.currency:
                currencies.add(bond.currency)

            accrued = calculate_accrued_interest(bond, valuation_date)
            dirty_price = bond.clean_price + accrued.accrued_interest_percent
            market_value = (
                Decimal(position.quantity)
                * bond.nominal
                * dirty_price
                / Decimal("100")
            )
            if market_value < 0:
                raise PortfolioValuationError(
                    f"Рыночная стоимость позиции {bond.secid} отрицательна"
                )

            cash_flows = calculate_bond_cash_flows(
                bond=bond,
                quantity=position.quantity,
                valuation_date=valuation_date,
            )
            if not any(
                coupon.coupondate > valuation_date for coupon in bond.coupons
            ):
                warnings.append(
                    f"Для облигации {bond.secid} нет будущих купонных выплат; "
                    "НКД равен нулю"
                )
            if not cash_flows:
                warnings.append(
                    f"Для облигации {bond.secid} не сформированы будущие денежные потоки"
                )

            calculations.append(
                _PositionCalculation(
                    position=position,
                    bond=bond,
                    accrued=accrued,
                    dirty_price=dirty_price,
                    market_value=market_value,
                    cash_flows=cash_flows,
                )
            )
            all_cash_flows.extend(cash_flows)

        if len(currencies) > 1:
            raise PortfolioValuationError(
                "Портфель содержит облигации в разных валютах; "
                "в MVP поддерживается только одна валюта"
            )

        total_market_value = sum(
            (calculation.market_value for calculation in calculations),
            Decimal("0"),
        )
        if total_market_value <= 0:
            raise PortfolioValuationError(
                "Совокупная рыночная стоимость портфеля равна нулю; "
                "веса позиций не могут быть рассчитаны"
            )

        total_nominal_value = sum(
            (
                calculation.bond.nominal * Decimal(calculation.position.quantity)
                for calculation in calculations
            ),
            Decimal("0"),
        )

        position_dtos = [
            self._build_position_dto(
                calculation=calculation,
                total_market_value=total_market_value,
            )
            for calculation in calculations
        ]

        weighted_ytm = self._weighted_ytm(
            calculations=calculations,
            total_market_value=total_market_value,
            warnings=warnings,
        )

        consolidated = consolidate_cash_flows(all_cash_flows)
        true_ytm = calculate_portfolio_irr(
            market_value=total_market_value,
            valuation_date=valuation_date,
            cash_flows=consolidated,
        )
        if true_ytm is None:
            warnings.append(
                "Истинная доходность портфеля (IRR) не рассчитана: "
                "нет будущих положительных потоков, не установлена scipy "
                "или корень не найден в допустимом интервале"
            )

        currency = next(iter(currencies)) if len(currencies) == 1 else None

        return PortfolioValuationDTO(
            portfolio_id=request.portfolio_id,
            portfolio_name=request.portfolio_name,
            valuation_date=valuation_date,
            currency=currency,
            total_market_value=_round(total_market_value, MONEY_QUANT),
            total_nominal_value=_round(total_nominal_value, MONEY_QUANT),
            weighted_ytm=(
                _round(weighted_ytm, YTM_QUANT)
                if weighted_ytm is not None
                else None
            ),
            weighted_ytm_percent=(
                _round(weighted_ytm * Decimal("100"), PERCENT_QUANT)
                if weighted_ytm is not None
                else None
            ),
            true_ytm=(
                _round(true_ytm, YTM_QUANT) if true_ytm is not None else None
            ),
            true_ytm_percent=(
                _round(true_ytm * Decimal("100"), PERCENT_QUANT)
                if true_ytm is not None
                else None
            ),
            positions=position_dtos,
            warnings=warnings,
        )

    def _resolve_positions(
        self,
        positions: List[PortfolioPositionInputDTO],
        warnings: List[str],
    ) -> List[_ResolvedPosition]:
        """Сопоставляет входные позиции с SECID и загружает их данные."""
        resolved: List[_ResolvedPosition] = []

        for position in positions:
            if position.quantity <= 0:
                identifier = position.secid or position.isin
                warnings.append(
                    f"Позиция {identifier} с нулевым количеством облигаций пропущена"
                )
                continue

            secid = position.secid
            detail = None

            if secid:
                detail = self._data_provider.get_bond_detail_by_secid(secid)

            if detail is None and position.isin:
                detail = self._data_provider.get_bond_detail_by_isin(position.isin)
                if detail is not None:
                    resolved_secid = str(
                        _value(detail[0], "secid", "")
                    ).strip().upper()
                    if not resolved_secid:
                        raise PortfolioValuationError(
                            f"Не удалось определить SECID по ISIN {position.isin}"
                        )
                    if secid and secid != resolved_secid:
                        warnings.append(
                            f"Позиция {secid} сопоставлена с SECID {resolved_secid} "
                            f"по ISIN {position.isin}"
                        )
                    else:
                        warnings.append(
                            f"ISIN {position.isin} сопоставлен с SECID {resolved_secid}"
                        )
                    secid = resolved_secid

            if detail is None:
                identifier = position.secid or position.isin
                raise PortfolioValuationError(
                    f"Облигация {identifier} не найдена в сервисе БД",
                    status_code=404,
                )

            if not secid:
                raise PortfolioValuationError(
                    "Не удалось определить SECID позиции портфеля"
                )

            resolved.append(
                _ResolvedPosition(
                    secid=secid,
                    isin=position.isin,
                    quantity=position.quantity,
                    average_purchase_price=position.average_purchase_price,
                    detail=detail,
                )
            )

        return resolved

    @staticmethod
    def _aggregate_positions(
        positions: List[_ResolvedPosition],
        warnings: List[str],
    ) -> List[_ResolvedPosition]:
        """Объединяет повторяющиеся SECID в одну позицию."""
        grouped: Dict[str, _ResolvedPosition] = {}

        for position in positions:
            existing = grouped.get(position.secid)
            if existing is None:
                grouped[position.secid] = position
                continue

            total_quantity = existing.quantity + position.quantity
            average_price = _weighted_average_price(
                existing.average_purchase_price,
                existing.quantity,
                position.average_purchase_price,
                position.quantity,
            )
            grouped[position.secid] = replace(
                existing,
                isin=existing.isin or position.isin,
                quantity=total_quantity,
                average_purchase_price=average_price,
                detail=existing.detail or position.detail,
            )
            warnings.append(
                f"Дублирующаяся позиция {position.secid} объединена в одну"
            )

        return list(grouped.values())

    def _ensure_bond_details(self, positions: List[_ResolvedPosition]) -> None:
        """Дозагружает данные облигаций, если они не были получены при resolve."""
        for position in positions:
            if position.detail is not None:
                continue
            position.detail = self._data_provider.get_bond_detail_by_secid(
                position.secid
            )
            if position.detail is None:
                raise PortfolioValuationError(
                    f"Облигация {position.secid} не найдена в сервисе БД",
                    status_code=404,
                )

    @staticmethod
    def _build_position_dto(
        calculation: _PositionCalculation,
        total_market_value: Decimal,
    ) -> PortfolioPositionValuationDTO:
        """Формирует DTO одной позиции с округлением на выходе."""
        bond = calculation.bond
        accrued = calculation.accrued
        weight = calculation.market_value / total_market_value

        return PortfolioPositionValuationDTO(
            bond_id=bond.bond_id,
            secid=bond.secid,
            isin=bond.isin,
            name=bond.name,
            quantity=calculation.position.quantity,
            nominal=_round(bond.nominal, MONEY_QUANT),
            clean_price=_round(bond.clean_price, PRICE_QUANT),
            accrued_interest=_round(accrued.accrued_interest, MONEY_QUANT),
            accrued_interest_percent=_round(
                accrued.accrued_interest_percent,
                PERCENT_QUANT,
            ),
            dirty_price=_round(calculation.dirty_price, PRICE_QUANT),
            market_value=_round(calculation.market_value, MONEY_QUANT),
            weight=_round(weight, WEIGHT_QUANT),
            weight_percent=_round(weight * Decimal("100"), PERCENT_QUANT),
            ytm=_round(bond.ytm, YTM_QUANT) if bond.ytm is not None else None,
            ytm_percent=(
                _round(bond.ytm * Decimal("100"), PERCENT_QUANT)
                if bond.ytm is not None
                else None
            ),
            average_purchase_price=(
                _round(
                    calculation.position.average_purchase_price,
                    PRICE_QUANT,
                )
                if calculation.position.average_purchase_price is not None
                else None
            ),
            maturity_date=bond.maturity_date,
            coupon_period_start=accrued.period_start,
            coupon_period_end=accrued.period_end,
            accrued_days=accrued.days_accrued,
            period_days=accrued.days_in_period,
            day_count_convention=bond.day_count_convention.value,
            currency=bond.currency or bond.face_unit,
        )

    @staticmethod
    def _weighted_ytm(
        calculations: List[_PositionCalculation],
        total_market_value: Decimal,
        warnings: List[str],
    ) -> Optional[Decimal]:
        """Считает взвешенную доходность по доступным YTM позиций."""
        weighted_positions = [
            (calculation.market_value / total_market_value, calculation.bond.ytm)
            for calculation in calculations
            if calculation.bond.ytm is not None
        ]
        # YTM is a portfolio-wide weighted average. Renormalizing only over
        # bonds with available YTM would silently change its definition.
        if len(weighted_positions) != len(calculations):
            if weighted_positions:
                warnings.append(
                    "Взвешенная доходность не рассчитана: отсутствует YTM "
                    "для одной или нескольких позиций"
                )
            return None

        weight_sum = sum((weight for weight, _ in weighted_positions), Decimal("0"))
        if weight_sum <= 0:
            return None

        weighted_sum = sum(
            (weight * ytm for weight, ytm in weighted_positions),
            Decimal("0"),
        )
        return weighted_sum / weight_sum
