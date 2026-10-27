"""Модели данных среднесрочного прогноза Банка России для таблиц БД.

Структура соответствует миграции 015_create_forecast_tables:
forecast, forecast_indicator_name, forecast_main_indicators, forecast_balance.
"""

from datetime import date as date_type
from typing import Optional

from sqlmodel import SQLModel, Field as SQLField


class Forecast(SQLModel, table=True):
    """Метаданные прогноза: одна запись на дату выпуска (date = PK)."""

    __tablename__ = "forecast"

    date: date_type = SQLField(primary_key=True, description="Дата выпуска прогноза (ключ)")
    meeting_date: date_type = SQLField(description="Дата заседания")
    publication_date: date_type = SQLField(description="Дата публикации")


class ForecastIndicatorName(SQLModel, table=True):
    """Названия показателей для отображения (section + key = PK)."""

    __tablename__ = "forecast_indicator_name"

    section: str = SQLField(max_length=32, primary_key=True, description="основные_показатели | платёжный_баланс")
    key: str = SQLField(max_length=64, primary_key=True, description="Ключ показателя")
    title: str = SQLField(description="Человекочитаемое название")


class ForecastMainIndicators(SQLModel, table=True):
    """Основные параметры прогноза по годам (forecast_date + year = PK)."""

    __tablename__ = "forecast_main_indicators"

    forecast_date: date_type = SQLField(primary_key=True, foreign_key="forecast.date")
    year: int = SQLField(primary_key=True)
    inflation_dec_min: Optional[float] = SQLField(default=None)
    inflation_dec_max: Optional[float] = SQLField(default=None)
    inflation_avg_min: Optional[float] = SQLField(default=None)
    inflation_avg_max: Optional[float] = SQLField(default=None)
    key_rate_min: Optional[float] = SQLField(default=None)
    key_rate_max: Optional[float] = SQLField(default=None)
    gdp_min: Optional[float] = SQLField(default=None)
    gdp_max: Optional[float] = SQLField(default=None)
    gdp_q4_min: Optional[float] = SQLField(default=None)
    gdp_q4_max: Optional[float] = SQLField(default=None)
    consumption_min: Optional[float] = SQLField(default=None)
    consumption_max: Optional[float] = SQLField(default=None)
    household_consumption_min: Optional[float] = SQLField(default=None)
    household_consumption_max: Optional[float] = SQLField(default=None)
    accumulation_min: Optional[float] = SQLField(default=None)
    accumulation_max: Optional[float] = SQLField(default=None)
    capital_accumulation_min: Optional[float] = SQLField(default=None)
    capital_accumulation_max: Optional[float] = SQLField(default=None)
    export_min: Optional[float] = SQLField(default=None)
    export_max: Optional[float] = SQLField(default=None)
    import_min: Optional[float] = SQLField(default=None)
    import_max: Optional[float] = SQLField(default=None)
    money_supply_min: Optional[float] = SQLField(default=None)
    money_supply_max: Optional[float] = SQLField(default=None)
    claims_economy_min: Optional[float] = SQLField(default=None)
    claims_economy_max: Optional[float] = SQLField(default=None)
    claims_orgs_min: Optional[float] = SQLField(default=None)
    claims_orgs_max: Optional[float] = SQLField(default=None)
    claims_households_min: Optional[float] = SQLField(default=None)
    claims_households_max: Optional[float] = SQLField(default=None)
    mortgage_loans_min: Optional[float] = SQLField(default=None)
    mortgage_loans_max: Optional[float] = SQLField(default=None)


class ForecastBalance(SQLModel, table=True):
    """Показатели платёжного баланса по годам (forecast_date + year = PK)."""

    __tablename__ = "forecast_balance"

    forecast_date: date_type = SQLField(primary_key=True, foreign_key="forecast.date")
    year: int = SQLField(primary_key=True)
    account_current_operations: Optional[float] = SQLField(default=None)
    trade_balance: Optional[float] = SQLField(default=None)
    goods_export: Optional[float] = SQLField(default=None)
    goods_import: Optional[float] = SQLField(default=None)
    services_balance: Optional[float] = SQLField(default=None)
    services_export: Optional[float] = SQLField(default=None)
    services_import: Optional[float] = SQLField(default=None)
    income_balance: Optional[float] = SQLField(default=None)
    financial_account: Optional[float] = SQLField(default=None)
    liabilities_net: Optional[float] = SQLField(default=None)
    assets_net: Optional[float] = SQLField(default=None)
    errors_omissions: Optional[float] = SQLField(default=None)
    reserves_change: Optional[float] = SQLField(default=None)
    oil_price: Optional[float] = SQLField(default=None)
