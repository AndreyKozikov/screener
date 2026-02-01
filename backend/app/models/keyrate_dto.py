"""DTO для отдачи данных ключевой ставки ЦБ РФ на фронтенд.

Модуль содержит модель KeyrateDTO для ответа API ключевой ставки.
Структура полей соответствует интерфейсу KeyRateRecord на фронтенде:
«Дата» (YYYY-MM-DD), «Ключевая ставка, % годовых».
"""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class KeyrateDTO(BaseModel):
    """DTO одной записи ключевой ставки для отображения в таблице на фронтенде.

    Структура и имена полей (через alias) совпадают с интерфейсом KeyRateRecord
    на фронтенде. Сериализация в JSON использует русские ключи (by_alias=True).

    Attributes:
        dt: Дата ключевой ставки (в БД — date; при сериализации — строка YYYY-MM-DD).
        rate: Ключевая ставка, % годовых.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )

    dt: date = Field(alias="Дата", description="Дата ключевой ставки (YYYY-MM-DD)")
    rate: float = Field(alias="Ключевая ставка, % годовых", description="Ключевая ставка, % годовых")
