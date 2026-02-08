"""DTO для передачи описаний полей на фронтенд.

Используется эндпоинтом GET /api/descriptions. Структура совместима
с прежним форматом из describe.json: секция -> имя поля -> текст описания.
"""

from typing import Dict, Optional

from pydantic import BaseModel, Field


class DescribeDTO(BaseModel):
    """Описания полей по секциям для отображения подсказок на фронтенде.

    Ключи верхнего уровня — секции (securities, marketdata). Значения —
    словари «имя поля» -> «текст описания». Фронт ожидает такую же структуру
    при вызове GET /api/descriptions.

    Attributes:
        securities: Описания полей секции securities (опционально).
        marketdata: Описания полей секции marketdata (опционально).
    """

    securities: Optional[Dict[str, str]] = Field(default=None, description="Описания полей секции securities")
    marketdata: Optional[Dict[str, str]] = Field(default=None, description="Описания полей секции marketdata")

    class Config:
        """Конфигурация Pydantic модели."""

        extra = "allow"  # допускаем дополнительные секции при расширении
