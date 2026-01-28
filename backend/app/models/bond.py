"""Модели данных облигаций.

Этот модуль содержит модели данных для представления информации об облигациях
в различных форматах: упрощенный список для таблиц, детальная информация,
секции данных о ценных бумагах и рыночных данных.
"""

from datetime import date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class BondListItem(BaseModel):
    """Упрощенная модель облигации для отображения в списке/таблице.
    
    Содержит основные поля облигации, необходимые для отображения в таблице
    на фронтенде. Включает базовую информацию о ценной бумаге, купонах,
    рейтингах и вычисляемые поля для удобства отображения.
    
    Attributes:
        SECID: Идентификатор ценной бумаги (обязательное поле).
        BOARDID: Идентификатор режима торгов.
        SHORTNAME: Краткое наименование облигации.
        SECNAME: Полное наименование ценной бумаги.
        ISIN: ISIN код облигации.
        COUPONPERCENT: Процентная ставка купона.
        MATDATE: Дата погашения облигации.
        STATUS: Статус облигации.
        TRADINGSTATUS: Статус торгов.
        FACEVALUE: Номинальная стоимость облигации.
        PREVPRICE: Предыдущая цена облигации.
        YIELDATPREVWAPRICE: Доходность к погашению по предыдущей средневзвешенной цене.
        NEXTCOUPON: Дата следующей выплаты купона.
        BOARDNAME: Наименование режима торгов.
        CALLOPTIONDATE: Дата опциона на досрочный выкуп (call option).
        PUTOPTIONDATE: Дата опциона на досрочную продажу (put option).
        ACCRUEDINT: Накопленный купонный доход (НКД).
        COUPONPERIOD: Период купона в днях.
        COUPONVALUE: Сумма купона в рублях из данных о купонных выплатах.
        DURATION: Дюрация облигации в днях (из marketdata_yields).
        DURATIONWAPRICE: Дюрация по средневзвешенной цене в днях.
        CURRENCYID: Валюта торговли.
        FACEUNIT: Валюта номинала.
        LISTLEVEL: Уровень листинга (1, 2, 3 и т.д.).
        RATING_AGENCY: Название рейтингового агентства (краткое название на русском).
        RATING_LEVEL: Уровень рейтинга (наихудший рейтинг из всех доступных).
        RATINGS: Список всех рейтингов облигации.
        BONDTYPE: Тип облигации (из bonds_emitent.json).
        BONDTYPE43: Вид облигации (BONDTYPE из bonds.json, индекс 43).
        COUPON_TYPE: Тип купона (FIX или FLOAT) из coupons_data.json.
        COUPON_YIELD_TO_PRICE: Доходность купона к текущей цене в процентах (вычисляемое поле).
        COUPON_FREQUENCY: Число выплат купона в год (вычисляемое поле).
        DURATION_YEARS: Дюрация в годах (вычисляемое поле).
    
    Note:
        Вычисляемые поля (COUPON_YIELD_TO_PRICE, COUPON_FREQUENCY, DURATION_YEARS)
        рассчитываются на бэкенде в соответствии с принципами чистой архитектуры.
        Фронтенд только отображает эти значения.
    """
    SECID: str
    BOARDID: str
    SHORTNAME: str
    SECNAME: Optional[str] = None  # Полное название ценной бумаги
    ISIN: Optional[str] = None  # ISIN код
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
    ACCRUEDINT: Optional[float] = None  # НКД (накопленный купонный доход)
    COUPONPERIOD: Optional[int] = None  # Длительность купона в днях
    COUPONVALUE: Optional[float] = None  # Сумма купона в рублях из данных о купонных выплатах
    DURATION: Optional[float] = None  # Дюрация из marketdata_yields
    DURATIONWAPRICE: Optional[int] = None  # Дюрация по средневзвешенной цене в днях
    CURRENCYID: Optional[str] = None  # Валюта торговли
    FACEUNIT: Optional[str] = None  # Валюта номинала
    LISTLEVEL: Optional[int] = None  # Уровень листинга
    RATING_AGENCY: Optional[str] = None  # Название рейтингового агентства (agency_name_short_ru) - worst rating
    RATING_LEVEL: Optional[str] = None  # Уровень рейтинга (rating_level_name_short_ru) - worst rating
    RATINGS: Optional[List[Dict[str, Any]]] = None  # All ratings for the bond
    BONDTYPE: Optional[str] = None  # Тип облигации (type из bonds_emitent.json)
    BONDTYPE43: Optional[str] = None  # Вид облигации (BONDTYPE из bonds.json, индекс 43)
    COUPON_TYPE: Optional[str] = None  # Тип купона (FIX или FLOAT) из coupons_data.json
    # Вычисляемые на бэкенде поля (чистая архитектура — фронт только отображает)
    COUPON_YIELD_TO_PRICE: Optional[float] = None  # Доходность купона к текущей цене, %
    COUPON_FREQUENCY: Optional[int] = None  # Число выплат купона в год
    DURATION_YEARS: Optional[float] = None  # Дюрация в годах
    
    class Config:
        """Конфигурация Pydantic модели.
        
        Attributes:
            from_attributes: Разрешает создание модели из атрибутов объекта
                (используется для совместимости с ORM).
        """
        from_attributes = True


class BondSecurity(BaseModel):
    """Модель секции данных о ценной бумаге (securities).
    
    Содержит полную информацию о ценной бумаге из секции "securities"
    файла bonds.json. Включает все основные параметры облигации:
    идентификаторы, цены, купоны, даты и дополнительные характеристики.
    
    Attributes:
        SECID: Идентификатор ценной бумаги (обязательное поле).
        BOARDID: Идентификатор режима торгов (обязательное поле).
        SHORTNAME: Краткое наименование облигации (обязательное поле).
        SECNAME: Полное наименование ценной бумаги.
        PREVWAPRICE: Предыдущая средневзвешенная цена.
        YIELDATPREVWAPRICE: Доходность к погашению по предыдущей средневзвешенной цене.
        COUPONVALUE: Сумма купона в валюте номинала.
        COUPONPERCENT: Процентная ставка купона.
        NEXTCOUPON: Дата следующей выплаты купона.
        ACCRUEDINT: Накопленный купонный доход (НКД).
        PREVPRICE: Предыдущая цена облигации.
        LOTSIZE: Размер лота.
        FACEVALUE: Номинальная стоимость облигации.
        BOARDNAME: Наименование режима торгов.
        STATUS: Статус облигации.
        MATDATE: Дата погашения облигации.
        ISIN: ISIN код облигации.
        REGNUMBER: Регистрационный номер.
        CURRENCYID: Валюта торговли.
        DECIMALS: Количество знаков после запятой для цены.
        COUPONPERIOD: Период купона в днях.
        ISSUESIZE: Объем выпуска.
        PREVLEGALCLOSEPRICE: Предыдущая официальная цена закрытия.
        PREVDATE: Предыдущая дата торгов.
        REMARKS: Примечания.
        MARKETCODE: Код рынка.
        INSTRID: Идентификатор инструмента.
        SECTORID: Идентификатор сектора.
        MINSTEP: Минимальный шаг цены.
        FACEUNIT: Валюта номинала.
        BUYBACKPRICE: Цена обратного выкупа.
        BUYBACKDATE: Дата обратного выкупа.
        LATNAME: Латинское наименование.
        ISSUESIZEPLACED: Размещенный объем выпуска.
        LISTLEVEL: Уровень листинга.
        SECTYPE: Тип ценной бумаги.
        OFFERDATE: Дата оферты.
        SETTLEDATE: Дата расчетов.
        LOTVALUE: Стоимость лота.
        FACEVALUEONSETTLEDATE: Номинальная стоимость на дату расчетов.
        CALLOPTIONDATE: Дата опциона на досрочный выкуп.
        PUTOPTIONDATE: Дата опциона на досрочную продажу.
        DATEYIELDFROMISSUER: Дата доходности от эмитента.
    """
    SECID: str = Field(..., description="Security ID")
    BOARDID: str = Field(..., description="Board ID")
    SHORTNAME: str = Field(..., description="Short name")
    SECNAME: Optional[str] = Field(None, description="Full security name")
    PREVWAPRICE: Optional[float] = Field(None, description="Previous weighted average price")
    YIELDATPREVWAPRICE: Optional[float] = Field(None, description="Yield at prev WA price")
    COUPONVALUE: Optional[float] = Field(None, description="Coupon value in currency")
    COUPONPERCENT: Optional[float] = Field(None, description="Coupon rate %")
    NEXTCOUPON: Optional[date] = Field(None, description="Next coupon payment date")
    ACCRUEDINT: Optional[float] = Field(None, description="Accrued interest")
    PREVPRICE: Optional[float] = Field(None, description="Previous price")
    LOTSIZE: Optional[int] = Field(None, description="Lot size")
    FACEVALUE: Optional[float] = Field(None, description="Face value")
    BOARDNAME: Optional[str] = Field(None, description="Board name")
    STATUS: Optional[str] = Field(None, description="Status")
    MATDATE: Optional[date] = Field(None, description="Maturity date")
    ISIN: Optional[str] = Field(None, description="ISIN code")
    REGNUMBER: Optional[str] = Field(None, description="Registration number")
    CURRENCYID: Optional[str] = Field(None, description="Currency")
    # Additional fields from bonds.json
    DECIMALS: Optional[int] = None
    COUPONPERIOD: Optional[int] = None
    ISSUESIZE: Optional[int] = None
    PREVLEGALCLOSEPRICE: Optional[float] = None
    PREVDATE: Optional[date] = None
    REMARKS: Optional[str] = None
    MARKETCODE: Optional[str] = None
    INSTRID: Optional[str] = None
    SECTORID: Optional[str] = None
    MINSTEP: Optional[float] = None
    FACEUNIT: Optional[str] = None
    BUYBACKPRICE: Optional[float] = None
    BUYBACKDATE: Optional[date] = None
    LATNAME: Optional[str] = None
    ISSUESIZEPLACED: Optional[int] = None
    LISTLEVEL: Optional[int] = None
    SECTYPE: Optional[str] = None
    OFFERDATE: Optional[date] = None
    SETTLEDATE: Optional[date] = None
    LOTVALUE: Optional[float] = None
    FACEVALUEONSETTLEDATE: Optional[float] = None
    CALLOPTIONDATE: Optional[date] = None
    PUTOPTIONDATE: Optional[date] = None
    DATEYIELDFROMISSUER: Optional[date] = None


class BondMarketData(BaseModel):
    """Модель секции рыночных данных (marketdata).
    
    Содержит информацию о текущих рыночных показателях облигации:
    цены покупки/продажи, объемы торгов, изменения цен и другие
    рыночные метрики из секции "marketdata" файла bonds.json.
    
    Attributes:
        SECID: Идентификатор ценной бумаги (обязательное поле).
        BOARDID: Идентификатор режима торгов (обязательное поле).
        BID: Цена покупки (bid).
        OFFER: Цена продажи (offer).
        SPREAD: Спред между ценой покупки и продажи.
        BIDDEPTH: Глубина стакана по покупке (количество заявок).
        OFFERDEPTH: Глубина стакана по продаже (количество заявок).
        OPEN: Цена открытия торгов.
        LOW: Минимальная цена за торговую сессию.
        HIGH: Максимальная цена за торговую сессию.
        LAST: Последняя цена сделки.
        LASTCHANGE: Изменение последней цены в абсолютных единицах.
        LASTCHANGEPRCNT: Изменение последней цены в процентах.
        QTY: Количество в последней сделке.
        VALUE: Объем сделок в валюте инструмента.
        VALUE_USD: Объем сделок в долларах США.
        WAPRICE: Средневзвешенная цена.
        LASTCNGTOLASTWAPRICE: Изменение последней цены относительно средневзвешенной.
        WAPTOPREVWAPRICEPRCNT: Изменение средневзвешенной цены относительно предыдущей в процентах.
        WAPTOPREVWAPRICE: Изменение средневзвешенной цены относительно предыдущей в абсолютных единицах.
        CLOSEPRICE: Цена закрытия.
        MARKETPRICETODAY: Рыночная цена на сегодня.
        MARKETPRICE: Текущая рыночная цена.
        LASTTOPREVPRICE: Изменение последней цены относительно предыдущей.
        NUMTRADES: Количество сделок за торговую сессию.
        VOLTODAY: Объем торгов за сегодня в штуках.
        VALTODAY: Объем торгов за сегодня в валюте инструмента.
        VALTODAY_USD: Объем торгов за сегодня в долларах США.
        ETFSETTLEPRICE: Расчетная цена для ETF.
        TRADINGSTATUS: Статус торгов.
        UPDATETIME: Время последнего обновления данных.
    """
    SECID: str
    BOARDID: str
    BID: Optional[float] = None
    OFFER: Optional[float] = None
    SPREAD: Optional[float] = None
    BIDDEPTH: Optional[int] = None
    OFFERDEPTH: Optional[int] = None
    OPEN: Optional[float] = None
    LOW: Optional[float] = None
    HIGH: Optional[float] = None
    LAST: Optional[float] = None
    LASTCHANGE: Optional[float] = None
    LASTCHANGEPRCNT: Optional[float] = None
    QTY: Optional[int] = None
    VALUE: Optional[float] = None
    VALUE_USD: Optional[float] = None
    WAPRICE: Optional[float] = None
    LASTCNGTOLASTWAPRICE: Optional[float] = None
    WAPTOPREVWAPRICEPRCNT: Optional[float] = None
    WAPTOPREVWAPRICE: Optional[float] = None
    CLOSEPRICE: Optional[float] = None
    MARKETPRICETODAY: Optional[float] = None
    MARKETPRICE: Optional[float] = None
    LASTTOPREVPRICE: Optional[float] = None
    NUMTRADES: Optional[int] = None
    VOLTODAY: Optional[int] = None
    VALTODAY: Optional[float] = None
    VALTODAY_USD: Optional[float] = None
    ETFSETTLEPRICE: Optional[float] = None
    TRADINGSTATUS: Optional[str] = None
    UPDATETIME: Optional[str] = None


class BondDetail(BaseModel):
    """Модель полной информации об облигации со всеми секциями данных.
    
    Объединяет данные из всех секций файла bonds.json: securities,
    marketdata и marketdata_yields. Используется для детального просмотра
    информации об облигации на фронтенде.
    
    Attributes:
        securities: Словарь со всеми полями секции "securities".
            Используется гибкая структура для размещения всех возможных полей.
        marketdata: Словарь с данными секции "marketdata" (опционально).
            Содержит текущие рыночные показатели облигации.
        marketdata_yields: Список словарей с данными секции "marketdata_yields" (опционально).
            Содержит данные о доходностях по различным ценам и срокам.
    
    Note:
        Используются словари Dict[str, Any] вместо строгих моделей для гибкости,
        так как структура данных из MOEX API может изменяться и содержать
        дополнительные поля, не описанные в моделях.
    """
    securities: Dict[str, Any]  # Flexible to accommodate all fields
    marketdata: Optional[Dict[str, Any]] = None
    marketdata_yields: Optional[List[Dict[str, Any]]] = None
