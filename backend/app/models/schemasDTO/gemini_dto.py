"""DTO для валидации структурированного ответа Google Gemini.

Описывают результат анализа эмиссионной документации облигаций:
эмитент, параметры инструмента, параметры флоатера и торговые данные.
"""

from typing import Optional

from pydantic import BaseModel


class GeminiIssuerDTO(BaseModel):
    """Данные эмитента, извлечённые из документации.

    Attributes:
        name_short: Краткое наименование эмитента.
        inn: ИНН эмитента.
        rating_ru: Кредитный рейтинг (если упомянут в документах).
    """

    name_short: str
    inn: Optional[str] = None
    rating_ru: Optional[str] = None


class GeminiInstrumentDTO(BaseModel):
    """Параметры выпуска облигации.

    Attributes:
        isin: ISIN-код выпуска.
        series: Серия выпуска.
        nominal: Номинальная стоимость.
        maturity_date: Дата погашения (ISO 8601).
        days_to_maturity: Количество дней до погашения.
    """

    isin: Optional[str] = None
    series: str
    nominal: float
    maturity_date: Optional[str] = None
    days_to_maturity: Optional[int] = None


class GeminiFloatParamsDTO(BaseModel):
    """Параметры плавающей ставки (флоатера).

    Attributes:
        base_indicator_code: Код базового индикатора (KEY_RATE, RUONIA и т.д.).
        spread: Спред к базовому индикатору (в процентных пунктах).
        coupon_frequency_days: Периодичность купона в днях.
        lookback_period: Период lookback (дней).
        averaging_period: Период усреднения (дней).
        formula_raw: Математическая формула из текста (LaTeX).
        rate_determination_rule: Описание правила фиксации ставки.
        calculation_type: Тип расчёта ставки — DAILY (ежедневный акруал) или FIXED
            (фиксируется на купонный период). None если не определено.
        rounding_precision: Количество знаков после запятой при расчёте НКД и купона.
        key_rate_method: Метод применения KEY_RATE — SPOT (на дату) или MA (скользящее
            среднее). Заполняется только если base_indicator_code == KEY_RATE.
        lookback_type: Тип дней отступа — CALENDAR (календарные) или BUSINESS (рабочие).
        year_base: База года в формуле расчёта — "360", "365", "366" или "ACTUAL".
        is_daily_accrual: True если купон рассчитывается как сумма ежедневных начислений.
        floor_rate: Нижний лимит процентной ставки (минимальный купон).
        cap_rate: Верхний лимит процентной ставки (максимальный купон).
        extra_indicators: Дополнительные базовые индикаторы при формуле с несколькими индексами.
        condition_logic: Текстовое описание логических условий (пороги, зависимости от индикаторов).
        observation_type: Метод замера данных (на дату, среднее за период, макроинтервал).
        reference_period_desc: Словесное описание периода данных (напр. «за прошлый квартал»).
    """

    base_indicator_code: str = "NA"
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

    floor_rate: Optional[float] = None
    cap_rate: Optional[float] = None
    extra_indicators: Optional[str] = None
    condition_logic: Optional[str] = None
    observation_type: Optional[str] = None
    reference_period_desc: Optional[str] = None


class GeminiCalculationEngineDTO(BaseModel):
    """Технические параметры алгоритма расчёта купона.

    Нормализованные флаги для автоматического воспроизведения расчёта
    купонного дохода флоатера.

    Attributes:
        offset_days: Количество дней отступа (lookback).
        offset_calendar: Тип дней отступа — CALENDAR (календарные) или BUSINESS (рабочие).
        day_count: Конвенция базы года — ACT/365 (365 дней), ACT/366 (високосный год),
            30/360 (немецкий/американский стандарт).
        fallback: Правило подбора значения в нерабочий день —
            PRECEDING (предыдущее доступное) или FOLLOWING (следующее доступное).
        accrual_type: Тип начисления — DAILY_ACCRUAL (НКД растёт ежедневно по актуальной
            ставке) или FIXED_PERIOD (ставка фиксируется один раз на весь купонный период).
        interest_compounding: True если применяется капитализация/сложный процент.
    """

    offset_days: Optional[int] = None
    offset_calendar: Optional[str] = None
    day_count: Optional[str] = None
    fallback: Optional[str] = None
    accrual_type: Optional[str] = None
    interest_compounding: bool = False


class GeminiTradingDTO(BaseModel):
    """Торговые параметры выпуска.

    Attributes:
        listing_level: Уровень листинга.
        placement_date: Дата размещения (ISO 8601).
        underwriter: Наименование организатора размещения.
    """

    listing_level: Optional[int] = None
    placement_date: Optional[str] = None
    underwriter: Optional[str] = None


class GeminiBondAnalysisDTO(BaseModel):
    """Корневая DTO — полный результат анализа облигации через Gemini.

    Attributes:
        issuer: Данные эмитента.
        instrument: Параметры инструмента.
        float_params: Параметры плавающей ставки.
        trading: Торговые параметры.
        calculation_engine: Технические параметры алгоритма расчёта купона.
    """

    issuer: GeminiIssuerDTO
    instrument: GeminiInstrumentDTO
    float_params: GeminiFloatParamsDTO
    trading: GeminiTradingDTO
    calculation_engine: Optional[GeminiCalculationEngineDTO] = None
