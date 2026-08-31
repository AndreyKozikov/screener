
from typing import Optional
from sqlmodel import SQLModel, Field as SQLField
from datetime import date
from pydantic import field_validator, model_validator


class BondBase(SQLModel):
    """Единая модель облигации для таблицы bonds в БД.

    Объединяет поля из исходного Bond и BondListItem. Все расчёты
    (доходность, дюрация, рейтинг, флаги оферт) выполняются в BondTransformer
    до сохранения. Все поля сохраняются в БД как обычные колонки (не computed).
    Первичный ключ — id (autoincrement).

    Attributes:
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
    # Вычисляемые поля см. transform_to_bond в файле D:\Andrew\GeekBrains\Python\BondsScreener\backend\app\core\bond_transformer.py
    secid: str = SQLField(max_length=64, validation_alias="SECID")
    boardid: Optional[str] = SQLField(default=None, max_length=32, validation_alias="BOARDID")
    isin: Optional[str] = SQLField(default=None, max_length=32, validation_alias="ISIN")
    name: Optional[str] = SQLField(default=None, validation_alias="SHORTNAME")
    secname: Optional[str] = SQLField(default=None, validation_alias="SECNAME")
    rating: Optional[str] = SQLField(default=None, max_length=32, validation_alias="RATING_LEVEL") #
    rating_agency: Optional[str] = SQLField(default=None, max_length=64, validation_alias="RATING_AGENCY")
    current_price: Optional[float] = SQLField(default=None, validation_alias="LCURRENTPRICE")
    coupon_yield_to_price: Optional[float] = SQLField(default=None, validation_alias="COUPONYIELDTOPRICE")
    yield_to_maturity: Optional[float] = SQLField(default=None, validation_alias="YIELDATPREVWAPRICE")
    face_value: Optional[float] = SQLField(default=None, validation_alias="FACEVALUE")
    currency: Optional[str] = SQLField(default=None, max_length=16, validation_alias="CURRENCYID")
    face_unit: Optional[str] = SQLField(default=None, max_length=16, validation_alias="FACEUNIT")
    coupon_value: Optional[float] = SQLField(default=None, validation_alias="COUPONVALUE")
    coupon_percent: Optional[float] = SQLField(default=None, validation_alias="COUPONPERCENT")
    coupon_frequency: Optional[float] = SQLField(default=None)
    coupon_period: Optional[int] = SQLField(default=None, validation_alias="COUPONPERIOD")
    accrued_interest: Optional[float] = SQLField(default=None, validation_alias="ACCRUEDINT`")
    duration_years: Optional[float] = SQLField(default=None)
    duration: Optional[float] = SQLField(default=None, validation_alias="DURATION")
    duration_waprice: Optional[int] = SQLField(default=None)
    has_put_option: Optional[int] = SQLField(default=None)
    has_call_option: Optional[int] = SQLField(default=None)
    maturity_date: Optional[str] = SQLField(default=None, max_length=10, validation_alias="MATDATE")
    listing_level: Optional[int] = SQLField(default=None, validation_alias="LISTLEVEL")
    bond_type: Optional[int] = SQLField(default=None, validation_alias="BONDTYPE")
    bond_kind: Optional[int] = SQLField(default=None, validation_alias="BONDTYPE43")
    offer_date: Optional[str] = SQLField(default=None, max_length=10, validation_alias="OFFERDATE")
    status: Optional[str] = SQLField(default=None, max_length=32, validation_alias="STATUS")
    trading_status: Optional[str] = SQLField(default=None, max_length=32, validation_alias="TRADINGSTATUS")
    next_coupon: Optional[str] = SQLField(default=None, max_length=10, validation_alias="NEXTCOUPON")
    board_name: Optional[str] = SQLField(default=None, max_length=128, validation_alias="BOARDNAME")
    call_option_date: Optional[str] = SQLField(default=None, max_length=10, validation_alias="CALLOPTIONDATE")
    put_option_date: Optional[str] = SQLField(default=None, max_length=10, validation_alias="PUTOPTIONDATE")

    @model_validator(mode="before")
    @classmethod
    def calculate_fields(cls, values):
        if not isinstance(values, dict):
            return values

        values["has_call_option"] = (
            1 if values.get("call_option_date") else 0
        )

        values["has_put_option"] = (
            1 if values.get("put_option_date") else 0
        )

        duration = values.get("duration")
        if duration is not None:
            values["duration_years"] = round(duration / 365, 2)
        else:
            values["duration_years"] = None

        coupon_period = values.get("coupon_period")
        if coupon_period:
            values["coupon_frequency"] = round(365 / coupon_period)
        else:
            values["coupon_frequency"] = None

        return values

    @field_validator(
        "bond_type",
        mode="before",
    )
    @classmethod
    def validate_bond_type(cls, val):
        if not isinstance(val, int):
            return None
        return val


    @field_validator(
        "offer_date",
        "call_option_date",
        "put_option_date",
        "maturity_date",
        mode="before"
    )
    @classmethod
    def validate_date(cls, val):
        if val is None:
            return None

        if isinstance(val, date):
            return val.strftime("%Y-%m-%d")

        if isinstance(val, str) and val and val != "0000-00-00":
            return val

        return None

    @field_validator("duration_waprice", mode="before")
    @classmethod
    def validate_duration_waprice(cls, val):
        if val is not None and not isinstance(val, int):
            try:
                return int(val)
            except (TypeError, ValueError):
                return None



class BondSecurityBase(SQLModel):
    """Упрощённая SQLModel-модель данных о ценной бумаге.

    Таблица bondsecurity. Содержит расширенные поля торговых и эмиссионных параметров.
    Связана с таблицей bonds по полю bond_id (foreign key на bonds.id).

    Attributes:
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
    bond_id: Optional[int] = SQLField(
        default=None,
        foreign_key="bonds.id",
        unique=True
    )
    boardid: Optional[str] = SQLField(default=None, max_length=32, validation_alias="BOARDID")
    prev_waprice: Optional[float] = SQLField(default=None, validation_alias="PREVWAPRICE")
    yield_at_prev_waprice: Optional[float] = SQLField(default=None, validation_alias="YIELDATPREVWAPRICE")
    prev_price: Optional[float] = SQLField(default=None, validation_alias="PREVPRICE")
    lot_size: Optional[int] = SQLField(default=None, validation_alias="LOTSIZE")
    reg_number: Optional[str] = SQLField(default=None, validation_alias="REGNUMBER")
    decimals: Optional[int] = SQLField(default=None, validation_alias="DECIMALS")
    issue_size: Optional[int] = SQLField(default=None, validation_alias="ISSUESIZE")
    prev_legal_close_price: Optional[float] = SQLField(default=None, validation_alias="PREVLEGALCLOSEPRICE")
    prev_date: Optional[date] = SQLField(default=None, validation_alias="PREVDATE")
    remarks: Optional[str] = SQLField(default=None, validation_alias="REMARKS")
    market_code: Optional[str] = SQLField(default=None, validation_alias="MARKETCODE")
    instr_id: Optional[str] = SQLField(default=None, validation_alias="INSTRID")
    sector_id: Optional[str] = SQLField(default=None, validation_alias="SECTORID")
    min_step: Optional[float] = SQLField(default=None, validation_alias="MINSTEP")
    face_unit: Optional[str] = SQLField(default=None, validation_alias="FACEUNIT")
    buyback_price: Optional[float] = SQLField(default=None, validation_alias="BUYBACKPRICE")
    buyback_date: Optional[date] = SQLField(default=None, validation_alias="BUYBACKDATE")
    lat_name: Optional[str] = SQLField(default=None, validation_alias="LATNAME")
    issue_size_placed: Optional[int] = SQLField(default=None, validation_alias="ISSUESIZEPLACED")
    sec_type: Optional[str] = SQLField(default=None, validation_alias="SECTYPE")
    settle_date: Optional[date] = SQLField(default=None, validation_alias="SETTLEDATE")
    lot_value: Optional[float] = SQLField(default=None, validation_alias="LOTVALUE")
    face_value_on_settle_date: Optional[float] = SQLField(default=None, validation_alias="FACEVALUEONSETTLEDATE")
    date_yield_from_issuer: Optional[date] = SQLField(default=None, validation_alias="DATEYIELDFROMISSUER")

    @field_validator(
        "buyback_date",
        "settle_date",
        "prev_date",
        mode="before"
    )
    @classmethod
    def validate_date(cls, val):
        if val is None:
            return None

        if isinstance(val, date):
            return val.strftime("%Y-%m-%d")

        if isinstance(val, str) and val and val != "0000-00-00":
            return val

        return None

class BondMarketDataBase(SQLModel):
    """Упрощённая SQLModel-модель секции рыночных данных (marketdata).

    Таблица bondmarketdata. Содержит рыночные показатели облигации.
    Связана с таблицей bonds по полю bond_id (foreign key на bonds.id).

    Attributes:
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

    bond_id: Optional[int] = SQLField(
        default=None,
        foreign_key="bonds.id",
        unique=True
    )
    boardid: Optional[str] = SQLField(default=None, max_length=32, validation_alias="BOARDID")
    bid: Optional[float] = SQLField(default=None, validation_alias="BID")
    offer: Optional[float] = SQLField(default=None, validation_alias="OFFER")
    spread: Optional[float] = SQLField(default=None, validation_alias="SPREAD")
    bid_depth: Optional[int] = SQLField(default=None, validation_alias="BIDDEPTH")
    offer_depth: Optional[int] = SQLField(default=None, validation_alias="OFFERDEPTH")
    open_price: Optional[float] = SQLField(default=None, validation_alias="OPENPRICE")
    low: Optional[float] = SQLField(default=None, validation_alias="LOW")
    high: Optional[float] = SQLField(default=None, validation_alias="HIGH")
    last_price: Optional[float] = SQLField(default=None, validation_alias="LAST")
    last_change: Optional[float] = SQLField(default=None, validation_alias="LASTCHANGE")
    last_change_prcnt: Optional[float] = SQLField(default=None, validation_alias="LASTCHANGEPRCNT")
    qty: Optional[int] = SQLField(default=None, validation_alias="QTY")
    value: Optional[float] = SQLField(default=None, validation_alias="VALUE")
    value_usd: Optional[float] = SQLField(default=None, validation_alias="VALUE_USD")
    waprice: Optional[float] = SQLField(default=None, validation_alias="WAPRICE")
    last_cnt_to_last_waprice: Optional[float] = SQLField(default=None, validation_alias="LASTCNGTOLASTWAPRICE")
    wap_to_prev_waprice_prcnt: Optional[float] = SQLField(default=None, validation_alias="WAPTOPREVWAPRICEPRCNT")
    wap_to_prev_waprice: Optional[float] = SQLField(default=None, validation_alias="WAPTOPREVWAPRICE")
    close_price: Optional[float] = SQLField(default=None, validation_alias="CLOSEPRICE")
    market_price_today: Optional[float] = SQLField(default=None, validation_alias="MARKETPRICETODAY")
    market_price: Optional[float] = SQLField(default=None, validation_alias="MARKETPRICE")
    last_to_prev_price: Optional[float] = SQLField(default=None, validation_alias="LASTTOPREVPRICE")
    num_trades: Optional[int] = SQLField(default=None, validation_alias="NUMTRADES")
    vol_today: Optional[int] = SQLField(default=None, validation_alias="VOLTODAY")
    val_today: Optional[float] = SQLField(default=None, validation_alias="VALTODAY")
    val_today_usd: Optional[float] = SQLField(default=None, validation_alias="VALTODAY_USD")
    etf_settle_price: Optional[float] = SQLField(default=None, validation_alias="ETFSETTLEPRICE")
    update_time: Optional[str] = SQLField(default=None, validation_alias="UPDATETIME")


class BondMarketDataYieldBase(SQLModel):
    """SQLModel-модель расчётов доходности облигации.

    Таблица bondmarketdatayield. Содержит расчёты доходности, дюрации и спредов.
    Связана с таблицей bonds по полю bond_id (foreign key на bonds.id).

    Attributes:
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
    bond_id: Optional[int] = SQLField(
        default=None,
        foreign_key="bonds.id",
        unique=True
    )
    boardid: Optional[str] = SQLField(default=None, max_length=32, validation_alias="BOARDID")
    price: Optional[float] = SQLField(default=None, validation_alias="PRICE")
    yield_date: Optional[str] = SQLField(default=None, max_length=10, validation_alias="YIELDDATE")
    zcyc_moment: Optional[str] = SQLField(default=None, max_length=32, validation_alias="ZCYCMOMENT")
    yield_date_type: Optional[str] = SQLField(default=None, max_length=32, validation_alias="YIELDDATETYPE")
    effective_yield: Optional[float] = SQLField(default=None, validation_alias="EFFECTIVEYIELD")
    duration: Optional[int] = SQLField(default=None, validation_alias="DURATION")
    zspread_bp: Optional[int] = SQLField(default=None, validation_alias="ZSPREADBP")
    gspread_bp: Optional[int] = SQLField(default=None, validation_alias="GSPREADBP")
    waprice: Optional[float] = SQLField(default=None, validation_alias="WAPRICE")
    effective_yield_waprice: Optional[float] = SQLField(default=None, validation_alias="EFFECTIVEYIELDWAPRICE")
    duration_waprice: Optional[int] = SQLField(default=None, validation_alias="DURATIONWAPRICE")
    ir: Optional[float] = SQLField(default=None, validation_alias="IR")
    icpi: Optional[float] = SQLField(default=None, validation_alias="ICPI")
    bei: Optional[float] = SQLField(default=None, validation_alias="BEI")
    cbr: Optional[float] = SQLField(default=None, validation_alias="CBR")
    yield_to_offer: Optional[float] = SQLField(default=None, validation_alias="YIELDTOOFFER")
    yield_last_coupon: Optional[float] = SQLField(default=None, validation_alias="YIELDLASTCOUPON")
    trade_moment: Optional[str] = SQLField(default=None, max_length=32, validation_alias="TRADEMOMENT")
    seqnum: Optional[int] = SQLField(default=None, validation_alias="SEQNUM")
    systime: Optional[str] = SQLField(default=None, max_length=32, validation_alias="SYSTIME")