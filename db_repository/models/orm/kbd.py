"""Модель SQLModel для таблицы kbd (кривая бескупонной доходности).

Структура полей соответствует таблице kbd в БД. Составной первичный ключ: (date, time).
"""

from typing import Optional

from sqlmodel import Field, SQLModel


class DBkbd(SQLModel, table=True):
    """Модель записи кривой бескупонной доходности (КБД).

    Соответствует таблице kbd в БД. Дата и время — составной первичный ключ.
    Доходности по срокам хранятся в процентах годовых (REAL).

    Attributes:
        date: Дата расчёта (YYYY-MM-DD).
        time: Время расчёта (HH:MM:SS).
        term_0_25 .. term_30_0: Доходность для срока до погашения в годах, % годовых.
    """

    __tablename__ = "kbd"

    date: str = Field(primary_key=True, max_length=10)
    time: str = Field(primary_key=True, max_length=12)
    term_0_25: Optional[float] = Field(default=None)
    term_0_5: Optional[float] = Field(default=None)
    term_0_75: Optional[float] = Field(default=None)
    term_1_0: Optional[float] = Field(default=None)
    term_2_0: Optional[float] = Field(default=None)
    term_3_0: Optional[float] = Field(default=None)
    term_5_0: Optional[float] = Field(default=None)
    term_7_0: Optional[float] = Field(default=None)
    term_10_0: Optional[float] = Field(default=None)
    term_15_0: Optional[float] = Field(default=None)
    term_20_0: Optional[float] = Field(default=None)
    term_30_0: Optional[float] = Field(default=None)
