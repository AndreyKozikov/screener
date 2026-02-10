"""Модели данных облигаций для таблиц БД (SQLModel).

Содержит Bond, BondSecurity, BondMarketData, BondMarketDataYield
для таблиц bonds, bondsecurity, bondmarketdata, bondmarketdatayield.
"""

from datetime import date
from typing import Optional

from sqlmodel import SQLModel, Field as SQLField, Relationship


class Bond(SQLModel, table=True):
    """Единая модель облигации для таблицы bonds в БД.

    Объединяет поля из исходного Bond и BondListItem. Все расчёты
    (доходность, дюрация, рейтинг, флаги оферт) выполняются в BondTransformer
    до сохранения. Все поля сохраняются в БД как обычные колонки (не computed).
    Первичный ключ — id (autoincrement).

    Attributes:
        id: Автоинкрементный первичный ключ.
        secid: Идентификатор ценной бумаги.
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
    """
    __tablename__ = "bonds"

    id: Optional[int] = SQLField(default=None, primary_key=True)
    secid: str = SQLField(max_length=64)
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
    emitent_id: Optional[int] = SQLField(default=None)


class BondSecurity(SQLModel, table=True):
    """Упрощённая SQLModel-модель данных о ценной бумаге.

    Таблица bondsecurity. Содержит расширенные поля торговых и эмиссионных параметров.
    Связана с таблицей bonds по полю bond_id (foreign key на bonds.id).

    Attributes:
        id: Автоинкрементный первичный ключ.
        bond_id: Внешний ключ на таблицу bonds (bonds.id).
        boardid: Идентификатор режима торгов.
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

    id: Optional[int] = SQLField(default=None, primary_key=True)
    bond_id: Optional[int] = SQLField(default=None, foreign_key="bonds.id")
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


class BondMarketData(SQLModel, table=True):
    """Упрощённая SQLModel-модель секции рыночных данных (marketdata).

    Таблица bondmarketdata. Содержит рыночные показатели облигации.
    Связана с таблицей bonds по полю bond_id (foreign key на bonds.id).

    Attributes:
        id: Автоинкрементный первичный ключ.
        bond_id: Внешний ключ на таблицу bonds (bonds.id).
        boardid: Идентификатор режима торгов.
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

    id: Optional[int] = SQLField(default=None, primary_key=True)
    bond_id: Optional[int] = SQLField(default=None, foreign_key="bonds.id")
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
    """SQLModel-модель расчётов доходности облигации.

    Таблица bondmarketdatayield. Содержит расчёты доходности, дюрации и спредов.
    Связана с таблицей bonds по полю bond_id (foreign key на bonds.id).

    Attributes:
        id: Автоинкрементный первичный ключ.
        bond_id: Внешний ключ на таблицу bonds (bonds.id).
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

    id: Optional[int] = SQLField(default=None, primary_key=True)
    bond_id: Optional[int] = SQLField(default=None, foreign_key="bonds.id")
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
