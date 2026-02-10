"""Модель данных индикатора RUONIA для хранения в БД.

Этот модуль содержит SQLModel-модель DBruonia для таблицы ruonia.
Структура полей соответствует данным из Excel ЦБ РФ (колонки DT, ruo, vol, T, C,
MinRate, Percentile25, Percentile75, MaxRate, StatusXML, DateUpdate).
"""

from datetime import date
from typing import Optional

from sqlmodel import SQLModel, Field as SQLField


class DBruonia(SQLModel, table=True):
    """Модель записи RUONIA для таблицы ruonia в БД.

    Хранит данные индикатора однодневной ставки межбанковского кредитования
    (RUONIA) от ЦБ РФ. Одна запись — одна дата (первичный ключ).

    Attributes:
        dt: Дата ставки (первичный ключ). Формат YYYY-MM-DD.
        ruo: Ставка RUONIA, % годовых.
        vol: Объем сделок RUONIA, млрд руб.
        T: Количество сделок, ед.
        C: Дополнительный показатель из Excel ЦБ РФ.
        MinRate: Минимальная процентная ставка, % годовых.
        Percentile25: 25-й процентиль по процентным ставкам, % годовых.
        Percentile75: 75-й процентиль по процентным ставкам, % годовых.
        MaxRate: Максимальная процентная ставка, % годовых.
        StatusXML: Статус из источника (числовой).
        DateUpdate: Дата/время обновления записи в источнике (строка).
    """

    __tablename__ = "ruonia"

    dt: date = SQLField(primary_key=True, description="Дата ставки RUONIA")
    ruo: Optional[float] = SQLField(default=None, description="Ставка RUONIA, % годовых")
    vol: Optional[float] = SQLField(default=None, description="Объем сделок RUONIA, млрд руб.")
    T: Optional[float] = SQLField(default=None, description="Количество сделок, ед.")
    C: Optional[float] = SQLField(default=None, description="Дополнительный показатель C")
    MinRate: Optional[float] = SQLField(default=None, description="Минимальная ставка, % годовых")
    Percentile25: Optional[float] = SQLField(default=None, description="25-й процентиль, % годовых")
    Percentile75: Optional[float] = SQLField(default=None, description="75-й процентиль, % годовых")
    MaxRate: Optional[float] = SQLField(default=None, description="Максимальная ставка, % годовых")
    StatusXML: Optional[float] = SQLField(default=None, description="Статус из источника")
    DateUpdate: Optional[str] = SQLField(default=None, max_length=64, description="Дата обновления в источнике")
