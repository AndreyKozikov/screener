"""DTO запроса и ответа для оценки портфеля облигаций."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import List, Optional

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class PortfolioPositionInputDTO(BaseModel):
    """Позиция портфеля, переданная с фронтенда.

    Фронтенд хранит облигацию в формате ``PortfolioBond`` и может передать
    SECID, ISIN, количество и среднюю цену покупки. Для совместимости
    принимаются как snake_case, так и исходные имена полей фронтенда.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    secid: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("secid", "SECID"),
    )
    isin: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("isin", "ISIN"),
    )
    quantity: int = Field(..., ge=0, description="Количество облигаций в позиции")
    average_purchase_price: Optional[Decimal] = Field(
        default=None,
        validation_alias=AliasChoices(
            "average_purchase_price",
            "averagePurchasePrice",
        ),
        description="Средняя цена покупки в процентах от номинала",
    )

    @field_validator("secid", "isin", mode="before")
    @classmethod
    def _normalize_identifier(cls, value: object) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip().upper()
        return text or None

    @field_validator("average_purchase_price", mode="before")
    @classmethod
    def _to_decimal(cls, value: object) -> Optional[Decimal]:
        if value is None or value == "":
            return None
        if isinstance(value, Decimal):
            if not value.is_finite():
                raise ValueError("average_purchase_price должен быть конечным числом")
            if value <= 0:
                raise ValueError("average_purchase_price должен быть больше нуля")
            return value
        try:
            result = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError("average_purchase_price должен быть числом") from exc
        if not result.is_finite():
            raise ValueError("average_purchase_price должен быть конечным числом")
        if result <= 0:
            raise ValueError("average_purchase_price должен быть больше нуля")
        return result

    @model_validator(mode="after")
    def _validate_identifier(self) -> "PortfolioPositionInputDTO":
        if not self.secid and not self.isin:
            raise ValueError("Для позиции портфеля необходимо указать secid или isin")
        return self


class PortfolioValuationRequestDTO(BaseModel):
    """Запрос на оценку портфеля, состав которого передан с фронтенда."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    positions: List[PortfolioPositionInputDTO] = Field(
        ...,
        min_length=1,
        validation_alias=AliasChoices("positions", "bonds", "portfolio"),
        description="Позиции портфеля",
    )
    valuation_date: Optional[date] = Field(
        default=None,
        validation_alias=AliasChoices("valuation_date", "valuationDate"),
        description="Дата оценки; если не передана, используется текущая дата",
    )
    portfolio_id: Optional[int] = Field(
        default=None,
        description="Идентификатор портфеля (резерв для будущего хранения портфелей)",
    )
    portfolio_name: Optional[str] = Field(
        default=None,
        description="Отображаемое имя портфеля",
    )


class SavedPortfolioValuationRequestDTO(BaseModel):
    """Параметры оценки сохранённого на сервере портфеля."""

    valuation_date: Optional[date] = Field(
        default=None,
        validation_alias=AliasChoices("valuation_date", "valuationDate"),
        description="Дата оценки; если не передана, используется текущая дата",
    )


class PortfolioDealDTO(BaseModel):
    """Одна сохранённая сделка по облигации, остающейся в портфеле."""

    id: int
    portfolio_id: int
    security_id: Optional[int] = None
    trade_date: str
    settlement_date: Optional[str] = None
    trade_time: Optional[str] = None
    operation_type: str
    quantity: int
    price_percent_scaled: Optional[int] = None
    amount_ex_nkd_minor: Optional[int] = None
    nkd_minor: Optional[int] = None
    broker_fee_minor: Optional[int] = None
    exchange_fee_minor: Optional[int] = None
    currency_code: Optional[str] = None
    trade_number: Optional[str] = None
    status: Optional[str] = None
    comment: Optional[str] = None
    source_row_number: Optional[int] = None
    raw_data_json: Optional[str] = None
    isin: Optional[str] = None
    security_code: Optional[str] = None
    security_name: Optional[str] = None
    security_currency_code: Optional[str] = None
    asset_type: Optional[str] = None
    security_category: Optional[str] = None
    issuer: Optional[str] = None
    security_raw_data_json: Optional[str] = None
    current_quantity: Optional[int] = None


class PortfolioDealsDTO(BaseModel):
    """Все сделки по облигациям, которые входят в текущий снимок портфеля."""

    portfolio_id: int
    portfolio_name: str
    base_currency: str
    deals: List[PortfolioDealDTO] = Field(default_factory=list)


class PortfolioPositionValuationDTO(BaseModel):
    """Результат оценки одной позиции портфеля."""

    bond_id: Optional[int] = None
    secid: str
    isin: Optional[str] = None
    name: Optional[str] = None

    quantity: int
    nominal: Decimal

    clean_price: Decimal
    accrued_interest: Decimal
    accrued_interest_percent: Decimal
    dirty_price: Decimal

    market_value: Decimal
    weight: Decimal
    weight_percent: Decimal

    ytm: Optional[Decimal] = None
    ytm_percent: Optional[Decimal] = None
    average_purchase_price: Optional[Decimal] = None

    maturity_date: Optional[date] = None
    coupon_period_start: Optional[date] = None
    coupon_period_end: Optional[date] = None
    accrued_days: int = 0
    period_days: int = 0
    day_count_convention: str
    currency: Optional[str] = None


class PortfolioValuationDTO(BaseModel):
    """Итоговый DTO оценки портфеля."""

    portfolio_id: Optional[int] = None
    portfolio_name: Optional[str] = None
    valuation_date: date
    currency: Optional[str] = None

    total_market_value: Decimal
    total_nominal_value: Decimal

    weighted_ytm: Optional[Decimal] = None
    weighted_ytm_percent: Optional[Decimal] = None
    true_ytm: Optional[Decimal] = None
    true_ytm_percent: Optional[Decimal] = None

    positions: List[PortfolioPositionValuationDTO] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
