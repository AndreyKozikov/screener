"""DTO для кривой бескупонной доходности (КБД).

Этот модуль содержит модели для передачи данных кривой бескупонной доходности
на фронтенд. KbdDTO описывает одну запись кривой (дата, время, доходности по срокам);
KbdDataResponse — обёртка ответа эндпоинта GET /api/zerocupon/data.
Структура полей и сериализация в JSON совместимы с ожиданиями фронтенда
(русские названия полей, формат даты DD.MM.YYYY).
"""

from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


class KbdDTO(BaseModel):
    """DTO одной записи кривой бескупонной доходности (КБД) для фронтенда.

    Содержит дату и время расчёта и доходности по срокам до погашения (в процентах годовых).
    Поля сериализуются в JSON с русскими ключами (Дата, Время, Срок X.Y лет)
    для совместимости с фронтендом.

    Attributes:
        date: Дата расчёта в формате DD.MM.YYYY (сериализуется как «Дата»).
        time: Время расчёта, например HH:MM:SS (сериализуется как «Время»).
        term_0_25 .. term_20_0: Доходности по срокам до погашения, % годовых.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
        from_attributes=True,
    )

    date: str = Field(alias="Дата", description="Дата расчёта КБД в формате DD.MM.YYYY")
    time: Optional[str] = Field(default=None, alias="Время", description="Время расчёта")
    term_0_25: Optional[float] = Field(default=None, alias="Срок 0.25 лет")
    term_0_5: Optional[float] = Field(default=None, alias="Срок 0.5 лет")
    term_0_75: Optional[float] = Field(default=None, alias="Срок 0.75 лет")
    term_1_0: Optional[float] = Field(default=None, alias="Срок 1.0 лет")
    term_2_0: Optional[float] = Field(default=None, alias="Срок 2.0 лет")
    term_3_0: Optional[float] = Field(default=None, alias="Срок 3.0 лет")
    term_5_0: Optional[float] = Field(default=None, alias="Срок 5.0 лет")
    term_7_0: Optional[float] = Field(default=None, alias="Срок 7.0 лет")
    term_10_0: Optional[float] = Field(default=None, alias="Срок 10.0 лет")
    term_15_0: Optional[float] = Field(default=None, alias="Срок 15.0 лет")
    term_20_0: Optional[float] = Field(default=None, alias="Срок 20.0 лет")


class KbdDataResponse(BaseModel):
    """Ответ API с данными кривой бескупонной доходности.

    Используется для эндпоинта GET /api/zerocupon/data. Совместим с форматом,
    ожидаемым фронтендом: data — список записей КБД, count, date_from, date_to.

    Attributes:
        data: Список записей кривой бескупонной доходности (KbdDTO).
        count: Количество записей после фильтрации.
        date_from: Начальная дата фильтра (DD.MM.YYYY).
        date_to: Конечная дата фильтра (DD.MM.YYYY).
    """

    data: List[KbdDTO]
    count: int
    date_from: str
    date_to: str
