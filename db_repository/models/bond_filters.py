"""Модели фильтров для поиска и фильтрации облигаций.

Этот модуль содержит модели данных для параметров фильтрации облигаций
при запросах к API. Используется для валидации query-параметров запросов
и передачи фильтров в сервисный слой для выполнения поиска.
"""

from datetime import date
from typing import Optional, List
from pydantic import BaseModel, Field


class BondFilters(BaseModel):
    """Модель параметров фильтрации облигаций.
    
    Содержит все возможные параметры фильтрации для поиска облигаций
    в системе. Используется для валидации query-параметров HTTP-запросов
    и передачи фильтров в сервисный слой для выполнения поиска в базе данных.
    
    Все параметры опциональны, что позволяет гибко комбинировать различные
    фильтры для точного поиска нужных облигаций.
    """
    # Coupon rate range
    coupon_min: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Минимальная процентная ставка купона (от 0 до 100)"
    )

    coupon_max: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Максимальная процентная ставка купона (от 0 до 100)"
    )

    # Yield to maturity range
    yield_min: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Минимальная доходность к погашению в процентах (от 0 до 100)"
    )

    yield_max: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Максимальная доходность к погашению в процентах (от 0 до 100)"
    )

    # Coupon yield to price range
    coupon_yield_min: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Минимальная доходность купона к текущей цене в процентах (от 0 до 100)"
    )

    coupon_yield_max: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Максимальная доходность купона к текущей цене в процентах (от 0 до 100)"
    )

    # Maturity date range
    matdate_from: Optional[date] = Field(
        None,
        description="Начальная дата погашения облигации в формате YYYY-MM-DD"
    )

    matdate_to: Optional[date] = Field(
        None,
        description="Конечная дата погашения облигации в формате YYYY-MM-DD"
    )

    # List level filter
    listlevel: Optional[List[int]] = Field(
        None,
        description="Список уровней листинга для фильтрации (например, [1, 2, 3])"
    )

    # Currency filter (face unit)
    faceunit: Optional[List[str]] = Field(
        None,
        description="Список валют номинала для фильтрации (например, ['RUB', 'USD', 'EUR'])"
    )

    # Bond type filter (ID из bond_type_mapping)
    bondtype: Optional[List[int]] = Field(
        None,
        description="Cписок идентификаторов типов облигаций из bond_type_mapping."
                    "Возможные значения:"
                    "- 1: exchange_bond (биржевые облигации)"
                    "- 2: ofz_bond (облигации федерального займа)"
                    "- 3: corporate_bond (корпоративные облигации)"
                    "- 4: municipal_bond (муниципальные облигации)"
                    "- 5: subfederal_bond (субфедеральные облигации)"
    )

    # Bond type 43 filter (ID из bond_type43_mapping)
    bondtype43: Optional[List[int]] = Field(
        None,
        description="Список идентификаторов видов облигаций из bond_type43_mapping."
                    "Возможные значения:"
                    "- 1: Амортизируемые облигации"
                    "- 2: Валютные облигации"
                    "- 3: Конвертируемые облигации"
                    "- 4: Линкер/облигации с индексируемым купоном"
                    "- 5: Структурная облигация"
                    "- 6: Фикс с известным купоном"
                    "- 7: Фикс с неизвестным купоном"
                    "- 8: Флоатер (облигации с плавающей ставкой)"
    )

    # Rating range filter
    rating_min: Optional[str] = Field(
        None,
        description="Минимальный рейтинг облигации из шкалы рейтингов"
    )

    rating_max: Optional[str] = Field(
        None,
        description="Максимальный рейтинг облигации из шкалы рейтингов"
    )

    # Search
    search: Optional[str] = Field(
        None,
        description="Строка поиска для фильтрации по SECID, SHORTNAME или SECNAME."
                    "Поиск выполняется без учета регистра и частично совпадающих подстрок"
    )

    # Pagination
    skip: int = Field(
        default=0,
        ge=0,
        description="Количество записей для пропуска (для пагинации). По умолчанию 0."
                    "Минимальное значение: 0"
    )

    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Максимальное количество записей для возврата (для пагинации)."
                    "По умолчанию 100. Диапазон: от 1 до 1000"
    )
