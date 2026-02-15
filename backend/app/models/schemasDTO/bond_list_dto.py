"""DTO облигаций для ответов API: список и детали (Pydantic)."""

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class BondListItem(BaseModel):
    """Упрощенная модель облигации для отображения в списке/таблице.

    Содержит основные поля облигации для отображения в таблице на фронтенде.
    """

    SECID: str
    BOARDID: str
    SHORTNAME: str
    SECNAME: Optional[str] = None
    ISIN: Optional[str] = None
    COUPONPERCENT: Optional[float] = None
    MATDATE: Optional[date] = None
    STATUS: Optional[str] = None
    TRADINGSTATUS: Optional[str] = None
    FACEVALUE: Optional[float] = None
    PREVPRICE: Optional[float] = None
    YIELDATPREVWAPRICE: Optional[float] = None
    NEXTCOUPON: Optional[date] = None
    BOARDNAME: Optional[str] = None
    CALLOPTIONDATE: Optional[date] = None
    PUTOPTIONDATE: Optional[date] = None
    ACCRUEDINT: Optional[float] = None
    COUPONPERIOD: Optional[int] = None
    COUPONVALUE: Optional[float] = None
    DURATION: Optional[float] = None
    DURATIONWAPRICE: Optional[int] = None
    CURRENCYID: Optional[str] = None
    LISTLEVEL: Optional[int] = None
    RATING_AGENCY: Optional[str] = None
    RATING_LEVEL: Optional[str] = None
    RATINGS: Optional[List[Dict[str, Any]]] = None
    BONDTYPE: Optional[str] = None
    BONDTYPE43: Optional[str] = None
    COUPON_YIELD_TO_PRICE: Optional[float] = None
    COUPON_FREQUENCY: Optional[int] = None
    DURATION_YEARS: Optional[float] = None

    class Config:
        """Конфигурация Pydantic модели."""
        from_attributes = True


class BondDetail(BaseModel):
    """Модель полной информации об облигации со всеми секциями данных.

    Используется для детального просмотра на фронтенде.
    """

    securities: Dict[str, Any]
    marketdata: Optional[Dict[str, Any]] = None
    marketdata_yields: Optional[List[Dict[str, Any]]] = None
    emitent_inn: Optional[str] = None
