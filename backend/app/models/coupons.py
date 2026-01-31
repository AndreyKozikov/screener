"""Модели данных купонов облигаций.

Используется для валидации и сериализации данных купонов и формирования ответов API.
"""

from typing import List, Optional
from pydantic import BaseModel


class Coupon(BaseModel):
    """Модель данных купона облигации.
    
    Attributes:
        coupondate: Дата выплаты купона (YYYY-MM-DD).
        recorddate: Дата фиксации списка владельцев.
        startdate: Дата начала купонного периода.
        initialfacevalue: Начальная номинальная стоимость.
        facevalue: Номинальная стоимость на дату выплаты.
        faceunit: Валюта номинала.
        value: Сумма купона в валюте номинала.
        valueprc: Процентная ставка купона.
        value_rub: Сумма купона в рублях.
    """
    coupondate: Optional[str] = None
    recorddate: Optional[str] = None
    startdate: Optional[str] = None
    initialfacevalue: Optional[float] = None
    facevalue: Optional[float] = None
    faceunit: Optional[str] = None
    value: Optional[float] = None
    valueprc: Optional[float] = None
    value_rub: Optional[float] = None


class Offer(BaseModel):
    """Модель данных оферты облигации.
    
    Содержит информацию об оферте (досрочном погашении) облигации.
    Данные берутся из секции "offers" файла coupons_data.json.
    
    Attributes:
        isin: ISIN код облигации.
        name: Наименование облигации.
        issuevalue: Объем выпуска.
        offerdate: Дата оферты в формате строки (YYYY-MM-DD).
        offerdatestart: Дата начала периода оферты.
        offerdateend: Дата окончания периода оферты.
        facevalue: Номинальная стоимость на дату оферты.
        faceunit: Валюта номинала (RUB, USD, EUR и т.д.).
        price: Цена выкупа при оферте.
        value: Сумма выкупа в валюте номинала.
        agent: Агент по оферте (наименование организации).
        offertype: Тип оферты (например, "PUT", "CALL").
        secid: Идентификатор ценной бумаги.
        primary_boardid: Основной идентификатор режима торгов.
    """
    isin: Optional[str] = None
    name: Optional[str] = None
    issuevalue: Optional[float] = None
    offerdate: Optional[str] = None
    offerdatestart: Optional[str] = None
    offerdateend: Optional[str] = None
    facevalue: Optional[float] = None
    faceunit: Optional[str] = None
    price: Optional[float] = None
    value: Optional[float] = None
    agent: Optional[str] = None
    offertype: Optional[str] = None
    secid: Optional[str] = None
    primary_boardid: Optional[str] = None


class CouponsListResponse(BaseModel):
    """Модель ответа API для списка купонов."""
    coupons: List[Coupon]


class CouponsBySecid(BaseModel):
    """Модель данных купонов для облигации по SECID."""
    secid: str
    coupons: List[Coupon]


class MultipleCouponsResponse(BaseModel):
    """Модель ответа API для купонов нескольких облигаций.
    
    Используется для возврата данных о купонах для нескольких облигаций
    в одном запросе. Данные группируются по идентификатору ценной бумаги.
    
    Attributes:
        data: Список объектов CouponsBySecid, каждый из которых содержит
            данные о купонах для одной облигации, сгруппированные по SECID.
    """
    data: List[CouponsBySecid]  # List of coupons grouped by secid

