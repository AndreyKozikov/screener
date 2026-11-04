"""DTO модели данных инфляционных ожиданий."""

from pydantic import BaseModel, Field


class InflationLoadByUrlRequest(BaseModel):
    """Параметры запроса на скачивание и парсинг Excel-файла по URL."""

    url: str = Field(
        ...,
        description="Прямая ссылка (URL) на Excel-файл с данными инфляционных ожиданий",
    )