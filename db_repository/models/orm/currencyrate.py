"""Модель данных курсов валют ЦБ РФ для хранения в БД.

Этот модуль содержит SQLModel-модель DBcurrencyrate для таблицы currencyrate.
Структура полей соответствует данным из API ЦБ РФ: дата, source_date и курсы
EUR, USD, CNY (code, rate, nominal, original_value).
"""

from datetime import date
from typing import Optional

from sqlmodel import SQLModel, Field as SQLField


class DBcurrencyrate(SQLModel, table=True):
    """Модель записи курсов валют ЦБ РФ для таблицы currencyrate в БД.

    Хранит данные курсов валют (EUR, USD, CNY) от ЦБ РФ по датам.
    Одна запись — одна дата (первичный ключ) и курсы за эту дату.

    Attributes:
        dt: Дата курсов (первичный ключ). Формат хранения — date.
        source_date: Дата из ответа API ЦБ РФ (строка, например "31.12.2025").
        usd_rate: Курс USD за 1 единицу в рублях.
        usd_nominal: Номинал USD из API.
        usd_original_value: Исходное значение курса USD из API (строка).
        eur_rate: Курс EUR за 1 единицу в рублях.
        eur_nominal: Номинал EUR из API.
        eur_original_value: Исходное значение курса EUR из API (строка).
        cny_rate: Курс CNY за 1 единицу в рублях.
        cny_nominal: Номинал CNY из API.
        cny_original_value: Исходное значение курса CNY из API (строка).
    """

    __tablename__ = "currencyrate"

    dt: date = SQLField(primary_key=True, description="Дата курсов валют")
    source_date: str = SQLField(default="", max_length=32, description="Дата из ответа API ЦБ РФ")

    usd_rate: Optional[float] = SQLField(default=None, description="Курс USD за 1 ед. в рублях")
    usd_nominal: Optional[int] = SQLField(default=None, description="Номинал USD")
    usd_original_value: Optional[str] = SQLField(default=None, max_length=32, description="Исходное значение курса USD из API")

    eur_rate: Optional[float] = SQLField(default=None, description="Курс EUR за 1 ед. в рублях")
    eur_nominal: Optional[int] = SQLField(default=None, description="Номинал EUR")
    eur_original_value: Optional[str] = SQLField(default=None, max_length=32, description="Исходное значение курса EUR из API")

    cny_rate: Optional[float] = SQLField(default=None, description="Курс CNY за 1 ед. в рублях")
    cny_nominal: Optional[int] = SQLField(default=None, description="Номинал CNY")
    cny_original_value: Optional[str] = SQLField(default=None, max_length=32, description="Исходное значение курса CNY из API")
