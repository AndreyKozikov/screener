"""DTO для параметров плавающей ставки облигации (float params).

Содержит BondFloatParamsDTO — все поля из BondFloatParams плюс
ключевые данные из Bond (secid, name_short, maturity_date, nominal,
days_to_maturity) для отображения карточки флоатера на фронтенде.
"""

from typing import Optional

from pydantic import BaseModel


class BondFloatParamsDTO(BaseModel):
    """DTO параметров плавающей ставки с данными облигации.

    Attributes:
        secid: Идентификатор ценной бумаги (из Bond).
        name_short: Краткое наименование облигации (Bond.name).
        maturity_date: Дата погашения (YYYY-MM-DD, из Bond).
        nominal: Номинальная стоимость (Bond.face_value).
        days_to_maturity: Количество дней до погашения (вычисляемое).
        is_find: 1 — данные найдены, 0 — не найдены.
        base_indicator_code: Код базового индикатора (KEY_RATE, RUONIA и т.д.).
        spread: Спред к базовому индикатору (п.п.).
        coupon_frequency_days: Периодичность купона в днях.
        lookback_period: Период lookback (дней).
        averaging_period: Период усреднения (дней).
        formula_raw: Математическая формула из текста (LaTeX).
        rate_determination_rule: Описание правила фиксации ставки.
        calculation_type: Тип расчёта ставки — DAILY или FIXED.
        rounding_precision: Знаков после запятой при округлении.
        key_rate_method: Метод применения KEY_RATE — SPOT или MA.
        lookback_type: Тип дней отступа — CALENDAR или BUSINESS.
        year_base: База года — 360, 365, 366 или ACTUAL.
        is_daily_accrual: True если купон — сумма ежедневных начислений.
        offset_days: Количество дней отступа (lookback).
        offset_calendar: Тип дней отступа — CALENDAR или BUSINESS.
        day_count: Конвенция базы года — ACT/365, ACT/366, 30/360.
        fallback: Правило нерабочего дня — PRECEDING или FOLLOWING.
        accrual_type: Тип начисления — DAILY_ACCRUAL или FIXED_PERIOD.
        interest_compounding: True если применяется капитализация.
        placement_date: Дата размещения (ISO 8601).
        underwriter: Наименование организатора размещения.
        floor_rate: Нижний лимит процентной ставки.
        cap_rate: Верхний лимит процентной ставки.
        extra_indicators: Дополнительные базовые индикаторы.
        condition_logic: Текстовое описание логических условий.
        observation_type: Метод замера данных.
        reference_period_desc: Словесное описание периода данных.
    """

    secid: str
    name_short: Optional[str] = None
    maturity_date: Optional[str] = None
    nominal: Optional[float] = None
    days_to_maturity: Optional[int] = None

    is_find: int
    base_indicator_code: str
    spread: Optional[float] = None
    coupon_frequency_days: Optional[int] = None
    lookback_period: Optional[int] = None
    averaging_period: Optional[int] = None
    formula_raw: Optional[str] = None
    rate_determination_rule: Optional[str] = None
    calculation_type: Optional[str] = None
    rounding_precision: Optional[int] = None
    key_rate_method: Optional[str] = None
    lookback_type: Optional[str] = None
    year_base: Optional[str] = None
    is_daily_accrual: bool = False
    offset_days: Optional[int] = None
    offset_calendar: Optional[str] = None
    day_count: Optional[str] = None
    fallback: Optional[str] = None
    accrual_type: Optional[str] = None
    interest_compounding: bool = False
    placement_date: Optional[str] = None
    underwriter: Optional[str] = None
    floor_rate: Optional[float] = None
    cap_rate: Optional[float] = None
    extra_indicators: Optional[str] = None
    condition_logic: Optional[str] = None
    observation_type: Optional[str] = None
    reference_period_desc: Optional[str] = None

    model_config = {"from_attributes": True}
