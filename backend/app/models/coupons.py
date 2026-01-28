"""Модели данных купонов облигаций.

Этот модуль содержит модели данных для представления информации о купонах,
амортизациях и офертах облигаций. Используется для валидации и сериализации
данных из coupons_data.json и формирования ответов API.
"""

from typing import List, Optional
from pydantic import BaseModel


class Amortization(BaseModel):
    """Модель данных амортизации облигации.
    
    Содержит информацию об амортизационных выплатах облигации, включая
    даты выплат, номинальные стоимости и типы купонов. Данные берутся
    из секции "amortizations" файла coupons_data.json.
    
    Attributes:
        isin: ISIN код облигации.
        name: Наименование облигации.
        issuevalue: Объем выпуска.
        amortdate: Дата амортизации в формате строки (YYYY-MM-DD).
        facevalue: Номинальная стоимость на дату амортизации.
        initialfacevalue: Начальная номинальная стоимость.
        faceunit: Валюта номинала (RUB, USD, EUR и т.д.).
        valueprc: Процентное значение амортизации.
        value: Значение амортизации в валюте номинала.
        value_rub: Значение амортизации в рублях.
        data_source: Источник данных (для отладки и логирования).
        secid: Идентификатор ценной бумаги.
        primary_boardid: Основной идентификатор режима торгов.
        coupon_type: Тип купона (FIX или FLOAT). Перенесено из секции coupons.
    
    Note:
        Поле coupon_type было перенесено из секции coupons, так как тип купона
        одинаков для всех амортизаций одной облигации.
    """
    isin: Optional[str] = None
    name: Optional[str] = None
    issuevalue: Optional[float] = None
    amortdate: Optional[str] = None
    facevalue: Optional[float] = None
    initialfacevalue: Optional[float] = None
    faceunit: Optional[str] = None
    valueprc: Optional[float] = None
    value: Optional[float] = None
    value_rub: Optional[float] = None
    data_source: Optional[str] = None
    secid: Optional[str] = None
    primary_boardid: Optional[str] = None
    coupon_type: Optional[str] = None  # Moved from coupons section (FIX or FLOAT)


class Coupon(BaseModel):
    """Модель данных купона облигации.
    
    Содержит информацию об отдельной купонной выплате облигации.
    Данные берутся из секции "coupons" файла coupons_data.json.
    
    Attributes:
        coupondate: Дата выплаты купона в формате строки (YYYY-MM-DD).
        recorddate: Дата фиксации списка владельцев для выплаты купона.
        startdate: Дата начала купонного периода.
        initialfacevalue: Начальная номинальная стоимость на начало купонного периода.
        facevalue: Номинальная стоимость на дату выплаты купона.
        faceunit: Валюта номинала (RUB, USD, EUR и т.д.).
        value: Сумма купона в валюте номинала.
        valueprc: Процентная ставка купона.
        value_rub: Сумма купона в рублях (рассчитанное значение).
    
    Note:
        Поля isin, name, issuevalue, primary_boardid, secid и coupon_type
        были удалены из этой модели, так как они теперь присутствуют только
        в секции amortizations для избежания дублирования данных.
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


class BondCouponsResponse(BaseModel):
    """Модель ответа API для эндпоинта получения купонов облигации.
    
    Используется для возврата полной информации о купонах, амортизациях
    и офертах конкретной облигации. Содержит все данные из файла
    coupons_data.json для указанной облигации.
    
    Attributes:
        last_updated: Дата и время последнего обновления данных в формате строки.
        amortizations: Список данных об амортизационных выплатах облигации.
        coupons: Список данных о купонных выплатах облигации.
        offers: Список данных об офертах облигации.
    """
    last_updated: str
    amortizations: List[Amortization]
    coupons: List[Coupon]
    offers: List[Offer]


class CouponsListResponse(BaseModel):
    """Модель ответа API для списка купонов (для отображения в таблице).
    
    Упрощенная модель для отображения списка купонов в таблице на фронтенде.
    Содержит только данные о купонах и тип купона для удобства отображения.
    
    Attributes:
        coupons: Список данных о купонных выплатах облигации.
        coupon_type: Тип купона (FIX или FLOAT) из секции amortizations.
            Используется для отображения типа купона в интерфейсе.
    """
    coupons: List[Coupon]
    coupon_type: Optional[str] = None  # FIX or FLOAT from amortizations section


class CouponsBySecid(BaseModel):
    """Модель данных купонов для конкретной облигации по SECID.
    
    Используется для группировки купонов по идентификатору ценной бумаги
    в ответах API, когда запрашиваются купоны для нескольких облигаций.
    
    Attributes:
        secid: Идентификатор ценной бумаги (обязательное поле).
        coupons: Список данных о купонных выплатах для данной облигации.
        coupon_type: Тип купона (FIX или FLOAT) из секции amortizations.
            Используется для отображения типа купона в интерфейсе.
    """
    secid: str
    coupons: List[Coupon]
    coupon_type: Optional[str] = None  # FIX or FLOAT from amortizations section


class MultipleCouponsResponse(BaseModel):
    """Модель ответа API для купонов нескольких облигаций.
    
    Используется для возврата данных о купонах для нескольких облигаций
    в одном запросе. Данные группируются по идентификатору ценной бумаги.
    
    Attributes:
        data: Список объектов CouponsBySecid, каждый из которых содержит
            данные о купонах для одной облигации, сгруппированные по SECID.
    """
    data: List[CouponsBySecid]  # List of coupons grouped by secid

