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
    
    Attributes:
        coupon_min: Минимальная процентная ставка купона (от 0 до 100).
        coupon_max: Максимальная процентная ставка купона (от 0 до 100).
        yield_min: Минимальная доходность к погашению в процентах (от 0 до 100).
        yield_max: Максимальная доходность к погашению в процентах (от 0 до 100).
        coupon_yield_min: Минимальная доходность купона к текущей цене в процентах (от 0 до 100).
        coupon_yield_max: Максимальная доходность купона к текущей цене в процентах (от 0 до 100).
        matdate_from: Начальная дата погашения облигации в формате YYYY-MM-DD.
            Фильтр применяется включительно (>=).
        matdate_to: Конечная дата погашения облигации в формате YYYY-MM-DD.
            Фильтр применяется включительно (<=).
        listlevel: Список уровней листинга для фильтрации (например, [1, 2, 3]).
            Уровень листинга определяет категорию облигации на бирже.
        faceunit: Список валют номинала для фильтрации (например, ["RUB", "USD", "EUR"]).
            Фильтрует облигации по валюте номинальной стоимости.
        bondtype: Список идентификаторов типов облигаций из bond_type_mapping.
            Возможные значения:
            - 1: exchange_bond (биржевые облигации)
            - 2: ofz_bond (облигации федерального займа)
            - 3: corporate_bond (корпоративные облигации)
            - 4: municipal_bond (муниципальные облигации)
            - 5: subfederal_bond (субфедеральные облигации)
        bondtype43: Список идентификаторов видов облигаций из bond_type43_mapping.
            Возможные значения:
            - 1: Амортизируемые облигации
            - 2: Валютные облигации
            - 3: Конвертируемые облигации
            - 4: Линкер/облигации с индексируемым купоном
            - 5: Структурная облигация
            - 6: Фикс с известным купоном
            - 7: Фикс с неизвестным купоном
            - 8: Флоатер (облигации с плавающей ставкой)
        rating_min: Минимальный рейтинг облигации из шкалы рейтингов.
            Возможные значения: "AAA", "AA+", "AA", "AA-", "A+", "A", "A-",
            "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-", "B+", "B", "B-",
            "CCC", "CC", "C", "D".
        rating_max: Максимальный рейтинг облигации из шкалы рейтингов.
            Используется для определения диапазона рейтингов.
        search: Строка поиска для фильтрации по SECID, SHORTNAME или SECNAME.
            Поиск выполняется без учета регистра и частично совпадающих подстрок.
        skip: Количество записей для пропуска (для пагинации). По умолчанию 0.
            Минимальное значение: 0.
        limit: Максимальное количество записей для возврата (для пагинации).
            По умолчанию 100. Диапазон: от 1 до 1000.
    
    Examples:
        Пример использования для поиска корпоративных облигаций с купоном от 5% до 10%:
        
        >>> filters = BondFilters(
        ...     coupon_min=5.0,
        ...     coupon_max=10.0,
        ...     bondtype=[3],  # corporate_bond
        ...     limit=50
        ... )
        
        Пример поиска облигаций с рейтингом от AA до AAA:
        
        >>> filters = BondFilters(
        ...     rating_min="AA",
        ...     rating_max="AAA",
        ...     faceunit=["RUB"]
        ... )
    
    Note:
        Фильтры по рейтингу применяются с учетом иерархии рейтингов.
        Если указаны rating_min и rating_max, выбираются все рейтинги в диапазоне
        между ними включительно, независимо от порядка указания границ.
    """
    # Coupon rate range
    coupon_min: Optional[float] = Field(None, ge=0, le=100, description="Min coupon rate %")
    coupon_max: Optional[float] = Field(None, ge=0, le=100, description="Max coupon rate %")
    
    # Yield to maturity range
    yield_min: Optional[float] = Field(None, ge=0, le=100, description="Min yield to maturity %")
    yield_max: Optional[float] = Field(None, ge=0, le=100, description="Max yield to maturity %")
    
    # Coupon yield to price range
    coupon_yield_min: Optional[float] = Field(None, ge=0, le=100, description="Min coupon yield to price %")
    coupon_yield_max: Optional[float] = Field(None, ge=0, le=100, description="Max coupon yield to price %")
    
    # Maturity date range
    matdate_from: Optional[date] = Field(None, description="Maturity date from (YYYY-MM-DD)")
    matdate_to: Optional[date] = Field(None, description="Maturity date to (YYYY-MM-DD)")
    
    # List level filter
    listlevel: Optional[List[int]] = Field(None, description="List levels (1, 2, 3, etc.)")
    
    # Currency filter (face unit)
    faceunit: Optional[List[str]] = Field(None, description="Currency face units (RUB, USD, EUR, etc.)")
    
    # Bond type filter (ID из bond_type_mapping)
    bondtype: Optional[List[int]] = Field(None, description="Bond type IDs (from bond_type_mapping: 1=exchange_bond, 2=ofz_bond, 3=corporate_bond, 4=municipal_bond, 5=subfederal_bond)")
    
    # Bond type 43 filter (ID из bond_type43_mapping)
    bondtype43: Optional[List[int]] = Field(None, description="Bond type43 IDs (from bond_type43_mapping: 1=Амортизируемые облигации, 2=Валютные облигации, 3=Конвертируемые облигации, 4=Линкер/облигации с индексируемым, 5=Структурная облигация, 6=Фикс с известным купоном, 7=Фикс с неизвестным купоном, 8=Флоатер)")
    
    # Rating range filter
    rating_min: Optional[str] = Field(None, description="Minimum rating (AAA, AA+, AA, AA-, A+, etc.)")
    rating_max: Optional[str] = Field(None, description="Maximum rating (AAA, AA+, AA, AA-, A+, etc.)")
    
    # Search
    search: Optional[str] = Field(None, description="Search in SECID, SHORTNAME, SECNAME")
    
    # Pagination
    skip: int = Field(0, ge=0, description="Number of records to skip")
    limit: int = Field(100, ge=1, le=1000, description="Max records to return")
