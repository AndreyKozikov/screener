"""Модель данных параметров флоатера для таблицы bond_float_params.

Содержит BondFloatParams — результат анализа эмиссионной документации
через Gemini: параметры плавающей ставки, настройки расчётного движка
и торговые данные. Одна запись на облигацию (bond_id UNIQUE).
"""

from typing import Optional

from sqlmodel import SQLModel, Field as SQLField, Relationship


class BondFloatParams(SQLModel, table=True):
    """Параметры плавающей ставки облигации (таблица bond_float_params).

    Хранит результат анализа эмиссионной документации: параметры флоатера
    (base_indicator_code, spread, lookback и т.д.), настройки расчётного
    движка (offset_days, day_count, fallback) и торговые параметры
    (placement_date, underwriter). Связана с bonds по bond_id (FK).

    Attributes:
        id: Автоинкрементный первичный ключ.
        bond_id: Внешний ключ на таблицу bonds (bonds.id), UNIQUE.
        base_indicator_code: Код базового индикатора (KEY_RATE, RUONIA и т.д.).
        spread: Спред к базовому индикатору (в процентных пунктах).
        coupon_frequency_days: Периодичность купона в днях.
        lookback_period: Период lookback (дней).
        averaging_period: Период усреднения (дней).
        formula_raw: Математическая формула из текста (LaTeX).
        rate_determination_rule: Описание правила фиксации ставки.
        calculation_type: Тип расчёта ставки — DAILY или FIXED.
        rounding_precision: Знаков после запятой при расчёте НКД и купона.
        key_rate_method: Метод применения KEY_RATE — SPOT или MA.
        lookback_type: Тип дней отступа — CALENDAR или BUSINESS.
        year_base: База года — "360", "365", "366" или "ACTUAL".
        is_daily_accrual: True если купон — сумма ежедневных начислений.
        offset_days: Количество дней отступа (lookback) из calculation_engine.
        offset_calendar: Тип дней отступа — CALENDAR или BUSINESS.
        day_count: Конвенция базы года — ACT/365, ACT/366, 30/360.
        fallback: Правило нерабочего дня — PRECEDING или FOLLOWING.
        accrual_type: Тип начисления — DAILY_ACCRUAL или FIXED_PERIOD.
        interest_compounding: True если применяется капитализация/сложный процент.
        placement_date: Дата размещения (ISO 8601).
        underwriter: Наименование организатора размещения.
        bond: Навигационное свойство — связанный объект Bond.
        is_find: 1 — данные найдены и сохранены, 0 — пайплайн обработан, данные не найдены.
        floor_rate: Нижний лимит процентной ставки (минимальный купон).
        cap_rate: Верхний лимит процентной ставки (максимальный купон).
        extra_indicators: Дополнительные базовые индикаторы при формуле с несколькими индексами.
        condition_logic: Текстовое описание логических условий (пороги, зависимости от индикаторов).
        observation_type: Метод замера данных (на дату, среднее за период, макроинтервал).
        reference_period_desc: Словесное описание периода данных (напр. «за прошлый квартал»).
    """

    __tablename__ = "bond_float_params"

    id: Optional[int] = SQLField(default=None, primary_key=True)
    bond_id: int = SQLField(foreign_key="bonds.id", nullable=False, index=True, unique=True)

    # Признак результата пайплайна: 1 — данные найдены, 0 — не найдены (остальные поля NULL).
    is_find: int = SQLField(default=1, nullable=False)

    # float_params fields
    base_indicator_code: str = SQLField(max_length=64)
    spread: Optional[float] = SQLField(default=None)
    coupon_frequency_days: Optional[int] = SQLField(default=None)
    lookback_period: Optional[int] = SQLField(default=None)
    averaging_period: Optional[int] = SQLField(default=None)
    formula_raw: Optional[str] = SQLField(default=None)
    rate_determination_rule: Optional[str] = SQLField(default=None)
    calculation_type: Optional[str] = SQLField(default=None, max_length=32)
    rounding_precision: Optional[int] = SQLField(default=None)
    key_rate_method: Optional[str] = SQLField(default=None, max_length=32)
    lookback_type: Optional[str] = SQLField(default=None, max_length=32)
    year_base: Optional[str] = SQLField(default=None, max_length=16)
    is_daily_accrual: bool = SQLField(default=False)

    # calculation_engine fields
    offset_days: Optional[int] = SQLField(default=None)
    offset_calendar: Optional[str] = SQLField(default=None, max_length=32)
    day_count: Optional[str] = SQLField(default=None, max_length=32)
    fallback: Optional[str] = SQLField(default=None, max_length=32)
    accrual_type: Optional[str] = SQLField(default=None, max_length=32)
    interest_compounding: bool = SQLField(default=False)

    # trading fields
    placement_date: Optional[str] = SQLField(default=None, max_length=10)
    underwriter: Optional[str] = SQLField(default=None)

    # Сложные флоатеры: лимиты ставки, доп. индикаторы, условия, период наблюдения
    floor_rate: Optional[float] = SQLField(default=None)
    cap_rate: Optional[float] = SQLField(default=None)
    extra_indicators: Optional[str] = SQLField(default=None)
    condition_logic: Optional[str] = SQLField(default=None)
    observation_type: Optional[str] = SQLField(default=None, max_length=64)
    reference_period_desc: Optional[str] = SQLField(default=None)

    bond: Optional["Bond"] = Relationship()
