"""Модель эмитента для таблицы emitents в БД (SQLModel)."""

from typing import Optional

from sqlmodel import SQLModel, Field as SQLField


class Emitent(SQLModel, table=True):
    """Модель эмитента для таблицы emitents в БД.

    Attributes:
        id: Первичный ключ (autoincrement).
        moex_id: ID эмитента в MOEX (emitent_id из JSON), UNIQUE.
        inn: ИНН эмитента (emitent_inn из JSON), UNIQUE.
        okpo: ОКПО эмитента (emitent_okpo из JSON).
        title: Наименование эмитента (emitent_title из JSON).
        type: Тип ценной бумаги эмитента (type из API MOEX, напр. ofz_bond, exchange_bond).
    """

    __tablename__ = "emitents"

    id: Optional[int] = SQLField(default=None, primary_key=True)
    moex_id: Optional[int] = SQLField(default=None, unique=True)
    inn: Optional[str] = SQLField(default=None, max_length=32, unique=True)
    okpo: Optional[str] = SQLField(default=None, max_length=32)
    title: Optional[str] = SQLField(default=None)
    type: Optional[str] = SQLField(default=None, max_length=64)
