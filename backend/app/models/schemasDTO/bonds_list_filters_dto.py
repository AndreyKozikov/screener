from typing import Optional, List
from datetime import date
from pydantic import BaseModel, Field


class BondsListFiltersDTO(BaseModel):
    coupon_min: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Минимальный процент купона (0-100)"
    )

    coupon_max: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Максимальный процент купона (0-100)"
    )

    yield_min: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Минимальная доходность к погашению (0-100)"
    )

    yield_max: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Максимальная доходность к погашению (0-100)"
    )

    coupon_yield_min: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Минимальная доходность купона к цене (0-100)"
    )

    coupon_yield_max: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Максимальная доходность купона к цене (0-100)"
    )

    matdate_from: Optional[date] = Field(
        None,
        description="Начальная дата погашения (включительно)"
    )

    matdate_to: Optional[date] = Field(
        None,
        description="Конечная дата погашения (включительно)"
    )

    listlevel: Optional[List[int]] = Field(
        None,
        description="Список уровней листинга для фильтрации"
    )

    faceunit: Optional[List[str]] = Field(
        None,
        description="Список валют для фильтрации (например, SUR, USD)"
    )

    bondtype: Optional[List[int]] = Field(
        None,
        description=("Список ID типов облигаций из bond_type_mapping"
                     "(1=exchange_bond, 2=ofz_bond, и т.д.)"
                     )
    )

    bondtype43: Optional[List[int]] = Field(
        None,
        description=("Список ID видов облигаций из bond_type43_mapping"
                     "(1=Амортизируемые облигации, 6=Фикс с известным купоном, и т.д.)"
                     )
    )

    rating_min: Optional[str] = Field(
        None,
        description="Минимальный рейтинг для фильтрации (из шкалы рейтингов)"
    )

    rating_max: Optional[str] = Field(
        None,
        description="Максимальный рейтинг для фильтрации (из шкалы рейтингов)"
    )

    emitent_title: Optional[str] = Field(
        None,
        description="Название эмитента для фильтрации облигаций"
    )

    exclude_spob: bool = Field(
        True,
        description="Если True, исключает облигации с режимом торгов SPOB"
    )

    skip: int = Field(
        default=0,
        description="Смещение для пагинации (всегда 0)"
    )

    limit: int = Field(
        default=1000,
        description="Лимит записей (равен filtered)"
    )