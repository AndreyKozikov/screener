"""Получение данных облигаций и купонов через микросервис БД."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from app.portfolio.exceptions import PortfolioValuationError
from app.portfolio.models import (
    BondValuationInput,
    CouponScheduleItem,
    DayCountConvention,
)
from app.repository.db.bonds_repository import BondsRepository
from app.repository.db.db_coupon import DBCoupon
from app.repository.db.remote_repository import RemoteRepositoryError


def _field(obj: Any, name: str, default: Any = None) -> Any:
    """Читает поле из AttrDict, обычного словаря или ORM-подобного объекта."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _to_decimal(value: Any) -> Optional[Decimal]:
    """Преобразует значение в Decimal без потери десятичного представления."""
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value if value.is_finite() else None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() else None


def _first_decimal(*values: Any) -> Optional[Decimal]:
    """Возвращает первое корректное Decimal-значение из переданных."""
    for value in values:
        decimal_value = _to_decimal(value)
        if decimal_value is not None:
            return decimal_value
    return None


def _parse_date(value: Any) -> Optional[date]:
    """Разбирает дату из строки или date/datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text or text in {"0000-00-00", "None"}:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _normalize_currency(value: Any) -> Optional[str]:
    """Нормализует обозначение валюты для проверки единства портфеля."""
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text:
        return None
    if text in {"SUR", "RUB", "RUR"}:
        return "RUB"
    return text


class PortfolioDataProvider:
    """Загружает рыночные данные и графики купонов из сервиса БД."""

    def __init__(
        self,
        bonds_repository: Optional[BondsRepository] = None,
        coupon_repository: Optional[DBCoupon] = None,
    ) -> None:
        self._bonds = bonds_repository or BondsRepository()
        self._coupons = coupon_repository or DBCoupon()

    def get_bond_detail_by_secid(self, secid: str) -> Any:
        """Возвращает Bond, BondSecurity, BondMarketData и BondMarketDataYield."""
        try:
            return self._bonds.get_bond_detail_by_secid(secid)
        except RemoteRepositoryError as exc:
            raise PortfolioValuationError(
                f"Не удалось получить данные облигации {secid} из сервиса БД: {exc}",
                status_code=502,
            ) from exc

    def get_bond_detail_by_isin(self, isin: str) -> Any:
        """Возвращает данные облигации по ISIN через сервис БД."""
        try:
            return self._bonds.get_bond_detail_by_isin(isin)
        except RemoteRepositoryError as exc:
            raise PortfolioValuationError(
                f"Не удалось получить данные облигации по ISIN {isin} из сервиса БД: {exc}",
                status_code=502,
            ) from exc

    def get_coupons(self, secids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """Загружает все записи графика купонов для указанных SECID."""
        if not secids:
            return {}

        try:
            rows = self._coupons.fetch_coupons_raw(secids=secids)
        except RemoteRepositoryError as exc:
            raise PortfolioValuationError(
                f"Не удалось получить график купонов из сервиса БД: {exc}",
                status_code=502,
            ) from exc

        coupons_by_secid: Dict[str, List[Dict[str, Any]]] = {secid: [] for secid in secids}
        for row in rows or []:
            secid = str(_field(row, "secid", "")).strip().upper()
            if secid in coupons_by_secid:
                coupons_by_secid[secid].append(row)
        return coupons_by_secid

    def build_bond_input(
        self,
        secid: str,
        detail: Any,
        coupon_rows: List[Dict[str, Any]],
        valuation_date: date,
    ) -> BondValuationInput:
        """Собирает и валидирует данные одной облигации для расчёта."""
        if not detail or len(detail) < 4:
            raise PortfolioValuationError(f"Облигация {secid} не найдена в сервисе БД")

        bond, security, market_data, market_data_yield = detail
        warnings: List[str] = []

        raw_maturity = _parse_date(_field(bond, "maturity_date"))
        parsed_coupons = self._parse_coupons(
            secid=secid,
            rows=coupon_rows,
            fallback_coupon_value=_to_decimal(_field(bond, "coupon_value")),
        )
        if not any(coupon.value > 0 for coupon in parsed_coupons):
            coupon_percent = _to_decimal(_field(bond, "coupon_percent"))
            if coupon_percent is not None and coupon_percent > 0:
                raise PortfolioValuationError(
                    f"Не удалось определить размер купона для облигации {secid}"
                )
            warnings.append(
                f"Для облигации {secid} не найдены ненулевые купонные выплаты"
            )

        maturity_date = raw_maturity
        if maturity_date is None and parsed_coupons:
            maturity_date = parsed_coupons[-1].coupondate
            warnings.append(
                f"Для облигации {secid} не указана дата погашения; "
                "использована дата последнего купона"
            )
        if maturity_date is None:
            raise PortfolioValuationError(
                f"Не удалось определить дату погашения облигации {secid}"
            )
        if maturity_date <= valuation_date:
            raise PortfolioValuationError(
                f"Облигация {secid} погашена или погашается на дату оценки"
            )

        nominal = _first_decimal(_field(bond, "face_value"))
        if nominal is None or nominal <= 0:
            current_coupon = self._current_coupon(parsed_coupons, valuation_date)
            if current_coupon is not None:
                nominal = current_coupon.facevalue
        if nominal is None or nominal <= 0:
            raise PortfolioValuationError(
                f"Не удалось определить номинал облигации {secid}"
            )

        clean_price = _first_decimal(
            _field(bond, "current_price"),
            _field(market_data, "market_price"),
            _field(market_data, "last_price"),
            _field(market_data, "close_price"),
            _field(market_data, "waprice"),
            _field(security, "prev_price"),
        )
        if clean_price is None or clean_price <= 0:
            raise PortfolioValuationError(
                f"Не удалось определить чистую рыночную цену облигации {secid}"
            )

        ytm_percent = _first_decimal(
            _field(bond, "yield_to_maturity"),
            _field(market_data_yield, "effective_yield"),
            _field(market_data_yield, "effective_yield_waprice"),
            _field(security, "yield_at_prev_waprice"),
        )
        ytm = ytm_percent / Decimal("100") if ytm_percent is not None else None
        if ytm is None:
            warnings.append(
                f"Для облигации {secid} не найдена индивидуальная доходность к погашению"
            )

        coupon_period_days = self._coupon_period_days(
            _field(bond, "coupon_period"),
            parsed_coupons,
        )
        coupon_frequency = _to_decimal(_field(bond, "coupon_frequency"))
        if coupon_frequency is None and coupon_period_days:
            coupon_frequency = Decimal("365") / Decimal(coupon_period_days)

        convention_value = None
        for attribute in (
            "day_count_convention",
            "daycount",
            "day_count",
            "day_count_basis",
        ):
            convention_value = _field(bond, attribute)
            if convention_value:
                break
        day_count_convention = DayCountConvention.from_value(convention_value)

        face_unit = _normalize_currency(_field(bond, "face_unit"))
        currency = face_unit or _normalize_currency(_field(bond, "currency"))

        bond_id_value = _field(bond, "id")
        try:
            bond_id = int(bond_id_value) if bond_id_value is not None else None
        except (TypeError, ValueError):
            bond_id = None

        return BondValuationInput(
            bond_id=bond_id,
            secid=str(_field(bond, "secid") or secid).strip().upper(),
            isin=(str(_field(bond, "isin")).strip() if _field(bond, "isin") else None),
            name=_field(bond, "name"),
            nominal=nominal,
            clean_price=clean_price,
            ytm=ytm,
            maturity_date=maturity_date,
            coupon_frequency=coupon_frequency,
            coupon_period_days=coupon_period_days,
            day_count_convention=day_count_convention,
            coupons=tuple(parsed_coupons),
            currency=currency,
            face_unit=face_unit,
            warnings=tuple(warnings),
        )

    @staticmethod
    def _parse_coupons(
        secid: str,
        rows: List[Dict[str, Any]],
        fallback_coupon_value: Optional[Decimal],
    ) -> List[CouponScheduleItem]:
        """Преобразует строки графика купонов в типизированные записи."""
        coupons: List[CouponScheduleItem] = []
        for row in rows:
            coupondate = _parse_date(_field(row, "coupondate"))
            if coupondate is None:
                continue

            facevalue = _to_decimal(_field(row, "facevalue"))
            value = _to_decimal(_field(row, "value"))
            valueprc = _to_decimal(_field(row, "valueprc"))

            if (value is None or value == 0) and fallback_coupon_value is not None:
                value = fallback_coupon_value
            if value is None:
                value = Decimal("0")

            coupons.append(
                CouponScheduleItem(
                    coupondate=coupondate,
                    startdate=_parse_date(_field(row, "startdate")),
                    value=value,
                    facevalue=facevalue,
                    valueprc=valueprc,
                )
            )

        coupons.sort(key=lambda item: item.coupondate)
        if not coupons:
            raise PortfolioValuationError(
                f"Не удалось получить график купонных выплат для облигации {secid}"
            )
        return coupons

    @staticmethod
    def _coupon_period_days(
        raw_period: Any,
        coupons: List[CouponScheduleItem],
    ) -> Optional[int]:
        """Определяет длину купонного периода в днях."""
        if raw_period is not None:
            try:
                period = int(raw_period)
                if period > 0:
                    return period
            except (TypeError, ValueError):
                pass

        intervals = [
            (coupons[index + 1].coupondate - coupons[index].coupondate).days
            for index in range(len(coupons) - 1)
        ]
        intervals = [interval for interval in intervals if interval > 0]
        if not intervals:
            return None
        return int(round(sum(intervals) / len(intervals)))

    @staticmethod
    def _current_coupon(
        coupons: List[CouponScheduleItem],
        valuation_date: date,
    ) -> Optional[CouponScheduleItem]:
        """Возвращает ближайший будущий купон для оценки номинала."""
        for coupon in coupons:
            if coupon.coupondate > valuation_date:
                return coupon
        return None
