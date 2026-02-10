"""Модель данных ключевой ставки ЦБ РФ для хранения в БД.

Этот модуль содержит SQLModel-модель DBkeyrate для таблицы keyrate.
Структура полей соответствует данным с HTML-страницы ЦБ РФ: дата и ставка (%)."""

from datetime import date

from sqlmodel import SQLModel, Field as SQLField


class DBkeyrate(SQLModel, table=True):
    """Модель записи ключевой ставки ЦБ РФ для таблицы keyrate в БД.

    Хранит данные ключевой ставки Центрального банка РФ по датам.
    Одна запись — одна дата (первичный ключ) и значение ставки в % годовых.

    Attributes:
        dt: Дата (первичный ключ). Формат хранения — date.
        rate: Ключевая ставка, % годовых.
    """

    __tablename__ = "keyrate"

    dt: date = SQLField(primary_key=True, description="Дата ключевой ставки")
    rate: float = SQLField(description="Ключевая ставка, % годовых")
