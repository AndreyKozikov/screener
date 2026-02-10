"""DTO для отдачи данных RUONIA на фронтенд.

Этот модуль содержит модели для ответа API индикатора RUONIA.
RuoniaDTO — одна запись таблицы (дата ставки и показатели); имена полей и типы
полностью соответствуют ожиданиям фронтенда (RuoniaRecord, RuoniaDataResponse).
"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RuoniaDTO(BaseModel):
    """DTO одной записи RUONIA для отображения в таблице на фронтенде.

    Структура и имена полей совпадают с интерфейсом RuoniaRecord на фронтенде.
    Сериализация в JSON использует русские ключи (serialize_by_alias=True).

    Attributes:
        date_stavki: Дата ставки в формате YYYY-MM-DD (alias «Дата ставки»).
        stavka_ruonia: Ставка RUONIA, % годовых.
        volume_ruonia: Объем сделок RUONIA, млрд руб.
        count_deals: Количество сделок, ед.
        min_rate: Минимальная процентная ставка, % годовых.
        percentile_25: 25-й процентиль по процентным ставкам, % годовых.
        percentile_75: 75-й процентиль по процентным ставкам, % годовых.
        max_rate: Максимальная процентная ставка, % годовых.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
        from_attributes=True,
    )

    date_stavki: str = Field(alias="Дата ставки", description="Дата ставки RUONIA (YYYY-MM-DD)")
    stavka_ruonia: Optional[float] = Field(None, alias="Ставка RUONIA, % годовых")
    volume_ruonia: Optional[float] = Field(None, alias="Объем сделок RUONIA, млрд руб.")
    count_deals: Optional[float] = Field(None, alias="Количество сделок, ед.")
    min_rate: Optional[float] = Field(None, alias="Минимальная процентная ставка, % годовых")
    percentile_25: Optional[float] = Field(None, alias="25-й процентиль по процентным ставкам, % годовых")
    percentile_75: Optional[float] = Field(None, alias="75-й процентиль по процентным ставкам, % годовых")
    max_rate: Optional[float] = Field(None, alias="Максимальная процентная ставка, % годовых")


class RuoniaDataResponse(BaseModel):
    """Ответ API с данными RUONIA для таблицы на фронтенде.

    Используется для эндпоинта GET /api/ruonia/data. Совместим с форматом
    RuoniaDataResponse на фронтенде: data, count, date_from, date_to.

    Attributes:
        data: Список записей RUONIA (RuoniaDTO).
        count: Количество записей после фильтрации.
        date_from: Начальная дата фильтра (DD.MM.YYYY) или None.
        date_to: Конечная дата фильтра (DD.MM.YYYY) или None.
    """

    data: List[RuoniaDTO]
    count: int
    date_from: Optional[str] = None
    date_to: Optional[str] = None
