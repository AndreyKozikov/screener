"""Модели данных облигаций.

Этот модуль содержит модели данных для представления информации об облигациях:
объединённая SQLModel-модель Bond для таблицы bonds (исходные и расчётные поля),
Pydantic BondListItem для ответов API, детальная информация и секции данных.
"""

from datetime import date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from sqlmodel import SQLModel, Field as SQLField, Relationship, ForeignKey


class Bond(SQLModel, table=True):
    """Единая модель облигации для таблицы bonds в БД.

    Объединяет поля из исходного Bond и BondListItem. Все расчёты
    (доходность, дюрация, рейтинг, флаги оферт) выполняются в BondTransformer
    до сохранения. Все поля сохраняются в БД как обычные колонки (не computed).
    Первичный ключ — secid.

    Attributes:
        secid: Идентификатор ценной бумаги (первичный ключ).
        boardid: Идентификатор режима торгов.
        isin: ISIN код облигации.
        name: Краткое наименование облигации.
        secname: Полное наименование ценной бумаги.
        rating: Стандартизированный рейтинг (наихудший из доступных).
        rating_agency: Название рейтингового агентства (краткое на русском).
        current_price: Текущая цена.
        coupon_yield_to_price: Доходность купона к текущей цене (%).
        yield_to_maturity: Доходность к погашению (%).
        face_value: Номинальная стоимость.
        currency: Валюта расчётов (CURRENCYID из securities).
        face_unit: Валюта номинала (FACEUNIT из securities).
        coupon_value: Сумма купона.
        coupon_percent: Процентная ставка купона.
        coupon_frequency: Число выплат купона в год.
        coupon_period: Период купона в днях.
        accrued_interest: Накопленный купонный доход.
        duration_years: Дюрация в годах.
        duration: Дюрация в днях (из marketdata).
        duration_waprice: Дюрация по средневзвешенной цене в днях.
        has_put_option: Наличие оферты на продажу (1/0).
        has_call_option: Наличие оферты на выкуп (1/0).
        maturity_date: Дата погашения (YYYY-MM-DD).
        listing_level: Уровень листинга.
        bond_type: ID типа облигации (маппинг).
        bond_kind: ID вида облигации (маппинг).
        offer_date: Дата оферты (YYYY-MM-DD).
        status: Статус облигации.
        trading_status: Статус торгов.
        next_coupon: Дата следующей выплаты купона (YYYY-MM-DD).
        board_name: Наименование режима торгов.
        call_option_date: Дата опциона на досрочный выкуп (YYYY-MM-DD).
        put_option_date: Дата опциона на досрочную продажу (YYYY-MM-DD).
        ratings: JSON-строка списка рейтингов (сериализованный список словарей).
    """
    __tablename__ = "bonds"

    secid: str = SQLField(primary_key=True, max_length=64)
    boardid: Optional[str] = SQLField(default=None, max_length=32)
    isin: Optional[str] = SQLField(default=None, max_length=32)
    name: Optional[str] = SQLField(default=None)
    secname: Optional[str] = SQLField(default=None)
    rating: Optional[str] = SQLField(default=None, max_length=32)
    rating_agency: Optional[str] = SQLField(default=None, max_length=64)
    current_price: Optional[float] = SQLField(default=None)
    coupon_yield_to_price: Optional[float] = SQLField(default=None)
    yield_to_maturity: Optional[float] = SQLField(default=None)
    face_value: Optional[float] = SQLField(default=None)
    currency: Optional[str] = SQLField(default=None, max_length=16)
    face_unit: Optional[str] = SQLField(default=None, max_length=16)
    coupon_value: Optional[float] = SQLField(default=None)
    coupon_percent: Optional[float] = SQLField(default=None)
    coupon_frequency: Optional[float] = SQLField(default=None)
    coupon_period: Optional[int] = SQLField(default=None)
    accrued_interest: Optional[float] = SQLField(default=None)
    duration_years: Optional[float] = SQLField(default=None)
    duration: Optional[float] = SQLField(default=None)
    duration_waprice: Optional[int] = SQLField(default=None)
    has_put_option: Optional[int] = SQLField(default=None)
    has_call_option: Optional[int] = SQLField(default=None)
    maturity_date: Optional[str] = SQLField(default=None, max_length=10)
    listing_level: Optional[int] = SQLField(default=None)
    bond_type: Optional[int] = SQLField(default=None)
    bond_kind: Optional[int] = SQLField(default=None)
    offer_date: Optional[str] = SQLField(default=None, max_length=10)
    status: Optional[str] = SQLField(default=None, max_length=32)
    trading_status: Optional[str] = SQLField(default=None, max_length=32)
    next_coupon: Optional[str] = SQLField(default=None, max_length=10)
    board_name: Optional[str] = SQLField(default=None, max_length=128)
    call_option_date: Optional[str] = SQLField(default=None, max_length=10)
    put_option_date: Optional[str] = SQLField(default=None, max_length=10)
    ratings: Optional[str] = SQLField(default=None)


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


# class BondSecurity(BaseModel):
#     """Модель секции данных о ценной бумаге (securities).
#
#     Содержит полную информацию о ценной бумаге из секции "securities"
#     файла bonds.json. Включает все основные параметры облигации:
#     идентификаторы, цены, купоны, даты и дополнительные характеристики.
#
#     Attributes:
#         SECID: Идентификатор ценной бумаги (обязательное поле).
#         BOARDID: Идентификатор режима торгов (обязательное поле).
#         SHORTNAME: Краткое наименование облигации (обязательное поле).
#         SECNAME: Полное наименование ценной бумаги.
#         PREVWAPRICE: Предыдущая средневзвешенная цена.
#         YIELDATPREVWAPRICE: Доходность к погашению по предыдущей средневзвешенной цене.
#         COUPONVALUE: Сумма купона в валюте номинала.
#         COUPONPERCENT: Процентная ставка купона.
#         NEXTCOUPON: Дата следующей выплаты купона.
#         ACCRUEDINT: Накопленный купонный доход (НКД).
#         PREVPRICE: Предыдущая цена облигации.
#         LOTSIZE: Размер лота.
#         FACEVALUE: Номинальная стоимость облигации.
#         BOARDNAME: Наименование режима торгов.
#         STATUS: Статус облигации.
#         MATDATE: Дата погашения облигации.
#         ISIN: ISIN код облигации.
#         REGNUMBER: Регистрационный номер.
#         CURRENCYID: Валюта торговли.
#         DECIMALS: Количество знаков после запятой для цены.
#         COUPONPERIOD: Период купона в днях.
#         ISSUESIZE: Объем выпуска.
#         PREVLEGALCLOSEPRICE: Предыдущая официальная цена закрытия.
#         PREVDATE: Предыдущая дата торгов.
#         REMARKS: Примечания.
#         MARKETCODE: Код рынка.
#         INSTRID: Идентификатор инструмента.
#         SECTORID: Идентификатор сектора.
#         MINSTEP: Минимальный шаг цены.
#         FACEUNIT: Валюта номинала.
#         BUYBACKPRICE: Цена обратного выкупа.
#         BUYBACKDATE: Дата обратного выкупа.
#         LATNAME: Латинское наименование.
#         ISSUESIZEPLACED: Размещенный объем выпуска.
#         LISTLEVEL: Уровень листинга.
#         SECTYPE: Тип ценной бумаги.
#         OFFERDATE: Дата оферты.
#         SETTLEDATE: Дата расчетов.
#         LOTVALUE: Стоимость лота.
#         FACEVALUEONSETTLEDATE: Номинальная стоимость на дату расчетов.
#         CALLOPTIONDATE: Дата опциона на досрочный выкуп.
#         PUTOPTIONDATE: Дата опциона на досрочную продажу.
#         DATEYIELDFROMISSUER: Дата доходности от эмитента.
#     """
#     SECID: str = Field(..., description="Security ID")
#     BOARDID: str = Field(..., description="Board ID")
#     SHORTNAME: str = Field(..., description="Short name")
#     SECNAME: Optional[str] = Field(None, description="Full security name")
#     PREVWAPRICE: Optional[float] = Field(None, description="Previous weighted average price")
#     YIELDATPREVWAPRICE: Optional[float] = Field(None, description="Yield at prev WA price")
#     COUPONVALUE: Optional[float] = Field(None, description="Coupon value in currency")
#     COUPONPERCENT: Optional[float] = Field(None, description="Coupon rate %")
#     NEXTCOUPON: Optional[date] = Field(None, description="Next coupon payment date")
#     ACCRUEDINT: Optional[float] = Field(None, description="Accrued interest")
#     PREVPRICE: Optional[float] = Field(None, description="Previous price")
#     LOTSIZE: Optional[int] = Field(None, description="Lot size")
#     FACEVALUE: Optional[float] = Field(None, description="Face value")
#     BOARDNAME: Optional[str] = Field(None, description="Board name")
#     STATUS: Optional[str] = Field(None, description="Status")
#     MATDATE: Optional[date] = Field(None, description="Maturity date")
#     ISIN: Optional[str] = Field(None, description="ISIN code")
#     REGNUMBER: Optional[str] = Field(None, description="Registration number")
#     CURRENCYID: Optional[str] = Field(None, description="Currency")
#     # Additional fields from bonds.json
#     DECIMALS: Optional[int] = None
#     COUPONPERIOD: Optional[int] = None
#     ISSUESIZE: Optional[int] = None
#     PREVLEGALCLOSEPRICE: Optional[float] = None
#     PREVDATE: Optional[date] = None
#     REMARKS: Optional[str] = None
#     MARKETCODE: Optional[str] = None
#     INSTRID: Optional[str] = None
#     SECTORID: Optional[str] = None
#     MINSTEP: Optional[float] = None
#     FACEUNIT: Optional[str] = None
#     BUYBACKPRICE: Optional[float] = None
#     BUYBACKDATE: Optional[date] = None
#     LATNAME: Optional[str] = None
#     ISSUESIZEPLACED: Optional[int] = None
#     LISTLEVEL: Optional[int] = None
#     SECTYPE: Optional[str] = None
#     OFFERDATE: Optional[date] = None
#     SETTLEDATE: Optional[date] = None
#     LOTVALUE: Optional[float] = None
#     FACEVALUEONSETTLEDATE: Optional[float] = None
#     CALLOPTIONDATE: Optional[date] = None
#     PUTOPTIONDATE: Optional[date] = None
#     DATEYIELDFROMISSUER: Optional[date] = None


class BondSecurity(SQLModel, table=True):
    """Упрощённая SQLModel-модель секции данных о ценной бумаге (securities).

    Таблица bondsecurity. Содержит сокращённый набор полей из секции "securities".
    Связана с таблицей bonds по полю secid (primary key и foreign key).

    Attributes:
        secid: Идентификатор ценной бумаги (primary key, FK на bonds.secid).
        boardid: Идентификатор режима торгов (BOARDID из секции securities).
        prev_waprice: Предыдущая средневзвешенная цена.
        yield_at_prev_waprice: Доходность к погашению по предыдущей средневзвешенной цене.
        prev_price: Предыдущая цена облигации.
        lot_size: Размер лота.
        reg_number: Регистрационный номер.
        decimals: Количество знаков после запятой для цены.
        issue_size: Объем выпуска.
        prev_legal_close_price: Предыдущая официальная цена закрытия.
        prev_date: Предыдущая дата торгов.
        remarks: Примечания.
        market_code: Код рынка.
        instr_id: Идентификатор инструмента.
        sector_id: Идентификатор сектора.
        min_step: Минимальный шаг цены.
        face_unit: Валюта номинала.
        buyback_price: Цена обратного выкупа.
        buyback_date: Дата обратного выкупа.
        lat_name: Латинское наименование.
        issue_size_placed: Размещенный объем выпуска.
        sec_type: Тип ценной бумаги.
        settle_date: Дата расчетов.
        lot_value: Стоимость лота.
        face_value_on_settle_date: Номинальная стоимость на дату расчетов.
        date_yield_from_issuer: Дата доходности от эмитента.
    """
    __tablename__ = "bondsecurity"

    secid: str = SQLField(
        primary_key=True,
        foreign_key="bonds.secid",
        max_length=64
    )
    boardid: Optional[str] = SQLField(default=None, max_length=32)
    prev_waprice: Optional[float] = SQLField(default=None)
    yield_at_prev_waprice: Optional[float] = SQLField(default=None)
    prev_price: Optional[float] = SQLField(default=None)
    lot_size: Optional[int] = SQLField(default=None)
    reg_number: Optional[str] = SQLField(default=None)
    decimals: Optional[int] = SQLField(default=None)
    issue_size: Optional[int] = SQLField(default=None)
    prev_legal_close_price: Optional[float] = SQLField(default=None)
    prev_date: Optional[date] = SQLField(default=None)
    remarks: Optional[str] = SQLField(default=None)
    market_code: Optional[str] = SQLField(default=None)
    instr_id: Optional[str] = SQLField(default=None)
    sector_id: Optional[str] = SQLField(default=None)
    min_step: Optional[float] = SQLField(default=None)
    face_unit: Optional[str] = SQLField(default=None)
    buyback_price: Optional[float] = SQLField(default=None)
    buyback_date: Optional[date] = SQLField(default=None)
    lat_name: Optional[str] = SQLField(default=None)
    issue_size_placed: Optional[int] = SQLField(default=None)
    sec_type: Optional[str] = SQLField(default=None)
    settle_date: Optional[date] = SQLField(default=None)
    lot_value: Optional[float] = SQLField(default=None)
    face_value_on_settle_date: Optional[float] = SQLField(default=None)
    date_yield_from_issuer: Optional[date] = SQLField(default=None)

    bond: Optional["Bond"] = Relationship()


# class BondMarketData(BaseModel):
#     """Модель секции рыночных данных (marketdata).
#
#     Содержит информацию о текущих рыночных показателях облигации:
#     цены покупки/продажи, объемы торгов, изменения цен и другие
#     рыночные метрики из секции "marketdata" файла bonds.json.
#
#     Attributes:
#         SECID: Идентификатор ценной бумаги (обязательное поле).
#         BOARDID: Идентификатор режима торгов (обязательное поле).
#         BID: Цена покупки (bid).
#         OFFER: Цена продажи (offer).
#         SPREAD: Спред между ценой покупки и продажи.
#         BIDDEPTH: Глубина стакана по покупке (количество заявок).
#         OFFERDEPTH: Глубина стакана по продаже (количество заявок).
#         OPEN: Цена открытия торгов.
#         LOW: Минимальная цена за торговую сессию.
#         HIGH: Максимальная цена за торговую сессию.
#         LAST: Последняя цена сделки.
#         LASTCHANGE: Изменение последней цены в абсолютных единицах.
#         LASTCHANGEPRCNT: Изменение последней цены в процентах.
#         QTY: Количество в последней сделке.
#         VALUE: Объем сделок в валюте инструмента.
#         VALUE_USD: Объем сделок в долларах США.
#         WAPRICE: Средневзвешенная цена.
#         LASTCNGTOLASTWAPRICE: Изменение последней цены относительно средневзвешенной.
#         WAPTOPREVWAPRICEPRCNT: Изменение средневзвешенной цены относительно предыдущей в процентах.
#         WAPTOPREVWAPRICE: Изменение средневзвешенной цены относительно предыдущей в абсолютных единицах.
#         CLOSEPRICE: Цена закрытия.
#         MARKETPRICETODAY: Рыночная цена на сегодня.
#         MARKETPRICE: Текущая рыночная цена.
#         LASTTOPREVPRICE: Изменение последней цены относительно предыдущей.
#         NUMTRADES: Количество сделок за торговую сессию.
#         VOLTODAY: Объем торгов за сегодня в штуках.
#         VALTODAY: Объем торгов за сегодня в валюте инструмента.
#         VALTODAY_USD: Объем торгов за сегодня в долларах США.
#         ETFSETTLEPRICE: Расчетная цена для ETF.
#         TRADINGSTATUS: Статус торгов.
#         UPDATETIME: Время последнего обновления данных.
#     """
#     SECID: str
#     BOARDID: str
#     BID: Optional[float] = None
#     OFFER: Optional[float] = None
#     SPREAD: Optional[float] = None
#     BIDDEPTH: Optional[int] = None
#     OFFERDEPTH: Optional[int] = None
#     OPEN: Optional[float] = None
#     LOW: Optional[float] = None
#     HIGH: Optional[float] = None
#     LAST: Optional[float] = None
#     LASTCHANGE: Optional[float] = None
#     LASTCHANGEPRCNT: Optional[float] = None
#     QTY: Optional[int] = None
#     VALUE: Optional[float] = None
#     VALUE_USD: Optional[float] = None
#     WAPRICE: Optional[float] = None
#     LASTCNGTOLASTWAPRICE: Optional[float] = None
#     WAPTOPREVWAPRICEPRCNT: Optional[float] = None
#     WAPTOPREVWAPRICE: Optional[float] = None
#     CLOSEPRICE: Optional[float] = None
#     MARKETPRICETODAY: Optional[float] = None
#     MARKETPRICE: Optional[float] = None
#     LASTTOPREVPRICE: Optional[float] = None
#     NUMTRADES: Optional[int] = None
#     VOLTODAY: Optional[int] = None
#     VALTODAY: Optional[float] = None
#     VALTODAY_USD: Optional[float] = None
#     ETFSETTLEPRICE: Optional[float] = None
#     TRADINGSTATUS: Optional[str] = None
#     UPDATETIME: Optional[str] = None


class BondMarketData(SQLModel, table=True):
    """Упрощённая SQLModel-модель секции рыночных данных (marketdata).

    Таблица bondmarketdata. Содержит рыночные показатели облигации.
    Связана с таблицей bonds по полю secid (primary key и foreign key).

    Attributes:
        secid: Идентификатор ценной бумаги (primary key, FK на bonds.secid).
        boardid: Идентификатор режима торгов (BOARDID из секции marketdata).
        bid: Цена покупки (bid).
        offer: Цена продажи (offer).
        spread: Спред между ценой покупки и продажи.
        bid_depth: Глубина стакана по покупке (количество заявок).
        offer_depth: Глубина стакана по продаже (количество заявок).
        open_price: Цена открытия торгов.
        low: Минимальная цена за торговую сессию.
        high: Максимальная цена за торговую сессию.
        last_price: Последняя цена сделки.
        last_change: Изменение последней цены в абсолютных единицах.
        last_change_prcnt: Изменение последней цены в процентах.
        qty: Количество в последней сделке.
        value: Объем сделок в валюте инструмента.
        value_usd: Объем сделок в долларах США.
        waprice: Средневзвешенная цена.
        last_cnt_to_last_waprice: Изменение последней цены относительно средневзвешенной.
        wap_to_prev_waprice_prcnt: Изменение средневзвешенной цены относительно предыдущей в %.
        wap_to_prev_waprice: Изменение средневзвешенной цены относительно предыдущей в абс. ед.
        close_price: Цена закрытия.
        market_price_today: Рыночная цена на сегодня.
        market_price: Текущая рыночная цена.
        last_to_prev_price: Изменение последней цены относительно предыдущей.
        num_trades: Количество сделок за торговую сессию.
        vol_today: Объем торгов за сегодня в штуках.
        val_today: Объем торгов за сегодня в валюте инструмента.
        val_today_usd: Объем торгов за сегодня в долларах США.
        etf_settle_price: Расчетная цена для ETF.
        update_time: Время последнего обновления данных.
    """
    __tablename__ = "bondmarketdata"

    secid: str = SQLField(
        primary_key=True,
        foreign_key="bonds.secid",
        max_length=64
    )
    boardid: Optional[str] = SQLField(default=None, max_length=32)
    bid: Optional[float] = SQLField(default=None)
    offer: Optional[float] = SQLField(default=None)
    spread: Optional[float] = SQLField(default=None)
    bid_depth: Optional[int] = SQLField(default=None)
    offer_depth: Optional[int] = SQLField(default=None)
    open_price: Optional[float] = SQLField(default=None)
    low: Optional[float] = SQLField(default=None)
    high: Optional[float] = SQLField(default=None)
    last_price: Optional[float] = SQLField(default=None)
    last_change: Optional[float] = SQLField(default=None)
    last_change_prcnt: Optional[float] = SQLField(default=None)
    qty: Optional[int] = SQLField(default=None)
    value: Optional[float] = SQLField(default=None)
    value_usd: Optional[float] = SQLField(default=None)
    waprice: Optional[float] = SQLField(default=None)
    last_cnt_to_last_waprice: Optional[float] = SQLField(default=None)
    wap_to_prev_waprice_prcnt: Optional[float] = SQLField(default=None)
    wap_to_prev_waprice: Optional[float] = SQLField(default=None)
    close_price: Optional[float] = SQLField(default=None)
    market_price_today: Optional[float] = SQLField(default=None)
    market_price: Optional[float] = SQLField(default=None)
    last_to_prev_price: Optional[float] = SQLField(default=None)
    num_trades: Optional[int] = SQLField(default=None)
    vol_today: Optional[int] = SQLField(default=None)
    val_today: Optional[float] = SQLField(default=None)
    val_today_usd: Optional[float] = SQLField(default=None)
    etf_settle_price: Optional[float] = SQLField(default=None)
    update_time: Optional[str] = SQLField(default=None)

    bond: Optional["Bond"] = Relationship()


class BondMarketDataYield(SQLModel, table=True):
    """SQLModel-модель секции marketdata_yields из bonds.json.

    Таблица bondmarketdatayield. Содержит расчёты доходности облигации.
    Связана с таблицей bonds по полю secid (primary key и foreign key).
    Структура соответствует секции marketdata_yields, собираемой в DataLoader._load_bonds_data().

    Attributes:
        secid: Идентификатор ценной бумаги (primary key, FK на bonds.secid).
        boardid: Идентификатор режима торгов.
        price: Цена.
        yield_date: Дата доходности (YIELDDATE).
        zcyc_moment: Момент кривой БКЗ (ZCYCMOMENT).
        yield_date_type: Тип даты доходности (YIELDDATETYPE).
        effective_yield: Эффективная доходность.
        duration: Дюрация в днях.
        zspread_bp: Z-spread в базисных пунктах.
        gspread_bp: G-spread в базисных пунктах.
        waprice: Средневзвешенная цена.
        effective_yield_waprice: Эффективная доходность по средневзвешенной цене.
        duration_waprice: Дюрация по средневзвешенной цене в днях.
        ir: Показатель IR.
        icpi: Показатель ICPI.
        bei: Показатель BEI.
        cbr: Показатель CBR.
        yield_to_offer: Доходность до оферты.
        yield_last_coupon: Доходность последнего купона.
        trade_moment: Момент сделки.
        seqnum: Порядковый номер.
        systime: Системное время.
    """
    __tablename__ = "bondmarketdatayield"

    secid: str = SQLField(
        primary_key=True,
        foreign_key="bonds.secid",
        max_length=64
    )
    boardid: Optional[str] = SQLField(default=None, max_length=32)
    price: Optional[float] = SQLField(default=None)
    yield_date: Optional[str] = SQLField(default=None, max_length=10)
    zcyc_moment: Optional[str] = SQLField(default=None, max_length=32)
    yield_date_type: Optional[str] = SQLField(default=None, max_length=32)
    effective_yield: Optional[float] = SQLField(default=None)
    duration: Optional[int] = SQLField(default=None)
    zspread_bp: Optional[int] = SQLField(default=None)
    gspread_bp: Optional[int] = SQLField(default=None)
    waprice: Optional[float] = SQLField(default=None)
    effective_yield_waprice: Optional[float] = SQLField(default=None)
    duration_waprice: Optional[int] = SQLField(default=None)
    ir: Optional[float] = SQLField(default=None)
    icpi: Optional[float] = SQLField(default=None)
    bei: Optional[float] = SQLField(default=None)
    cbr: Optional[float] = SQLField(default=None)
    yield_to_offer: Optional[float] = SQLField(default=None)
    yield_last_coupon: Optional[float] = SQLField(default=None)
    trade_moment: Optional[str] = SQLField(default=None, max_length=32)
    seqnum: Optional[int] = SQLField(default=None)
    systime: Optional[str] = SQLField(default=None, max_length=32)

    bond: Optional["Bond"] = Relationship()


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
