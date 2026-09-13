"""DTO модели данных ИПЦ (Индекс потребительских цен)."""

from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class IpcMonthItem(BaseModel):
    """Показатели ИПЦ за конкретный месяц для кода территории 643."""

    ipc: str = Field(..., alias="ипц", description="Индекс потребительских цен")
    food_products: str = Field(..., alias="продовольстенные товары", description="Продовольственные товары")
    non_food_products: str = Field(..., alias="непродовольственные товары", description="Непродовольственные товары")
    services: str = Field(..., alias="услуги", description="Услуги")

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )


class IpcLoadRequest(BaseModel):
    """Параметры запроса на скачивание, парсинг и сохранение данных ИПЦ."""

    url: Optional[str] = Field(
        default=None,
        description="Внешний URL для загрузки Excel-файла с индексами ИПЦ",
    )
    file_path: Optional[str] = Field(
        default=None,
        description="Путь к локальному Excel-файлу (если файл уже загружен)",
    )
    output_path: Optional[str] = Field(
        default=None,
        description="Путь для сохранения результирующего JSON-файла",
    )


class IpcLoadResponse(BaseModel):
    """Ответ сервиса после загрузки и парсинга ИПЦ."""

    status: str = Field(..., description="Статус операции (ok / error)")
    output_path: str = Field(..., description="Путь к сохранённому JSON-файлу")
    years_count: int = Field(..., description="Количество обработанных годов")
    total_months_count: int = Field(..., description="Общее количество обработанных месяцев")
    data: Dict[str, Dict[str, Dict[str, str]]] = Field(
        ...,
        description="Собранные данные ИПЦ в формате {год: {месяц: {...}}}",
    )
