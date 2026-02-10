"""Модель исторических торгов по облигациям.

Хранит данные истории торгов из API Мосбиржи в отдельной БД history_db.db.
Составной первичный ключ: (SECID, TRADEDATE, BOARDID).
"""

from datetime import date
from typing import Optional

from sqlmodel import Field, SQLModel


class TradingHistoryRecord(SQLModel, table=True):
    """Запись истории торгов по облигации за одну дату.

    Соответствует одной строке из секции history API Мосбиржи.
    Таблица хранится в отдельной БД history_db.db.

    Attributes:
        boardid: Идентификатор режима торгов (макс. 12 символов).
        tradedate: Дата торгов.
        secid: Идентификатор ценной бумаги (макс. 36 символов).
        numtrades: Количество сделок.
        value: Оборот в рублях.
        legalcloseprice: Официальная цена закрытия.
        accint: Накопленный купонный доход.
        yieldclose: Доходность к закрытию.
        open: Цена открытия.
        volume: Объём торгов.
        duration: Дюрация в днях.
        yieldatwap: Доходность по средневзвешенной цене.
        iricpiclose: Показатель IR CPI на закрытие.
        couponpercent: Процентная ставка купона.
        couponvalue: Сумма купона.
        facevalue: Номинал.
        yieldtooffer: Доходность к оферте.
        yieldlastcoupon: Доходность к последнему купону.
        calloptionyield: Доходность по опциону выкупа.
        calloptionduration: Дюрация до опциона выкупа.
        zspread: Z-spread.
        buybackdate: Дата выкупа.
        lasttradedate: Дата последней сделки.
        putoptiondate: Дата оферты на продажу.
        dateyieldfromissuer: Дата доходности от эмитента.
        trade_session_date: Дата торговой сессии.
    """

    __tablename__ = "bond_trading_history"
    __table_args__ = {"extend_existing": True}

    secid: str = Field(max_length=36, primary_key=True)
    tradedate: date = Field(primary_key=True)
    boardid: str = Field(max_length=12, primary_key=True)
    numtrades: Optional[float] = Field(default=None)
    value: Optional[float] = Field(default=None)
    legalcloseprice: Optional[float] = Field(default=None)
    accint: Optional[float] = Field(default=None)
    yieldclose: Optional[float] = Field(default=None)
    open: Optional[float] = Field(default=None)
    volume: Optional[float] = Field(default=None)
    duration: Optional[float] = Field(default=None)
    yieldatwap: Optional[float] = Field(default=None)
    iricpiclose: Optional[float] = Field(default=None)
    couponpercent: Optional[float] = Field(default=None)
    couponvalue: Optional[float] = Field(default=None)
    facevalue: Optional[float] = Field(default=None)
    yieldtooffer: Optional[float] = Field(default=None)
    yieldlastcoupon: Optional[float] = Field(default=None)
    calloptionyield: Optional[float] = Field(default=None)
    calloptionduration: Optional[float] = Field(default=None)
    zspread: Optional[float] = Field(default=None)
    buybackdate: Optional[date] = Field(default=None)
    lasttradedate: Optional[date] = Field(default=None)
    putoptiondate: Optional[date] = Field(default=None)
    dateyieldfromissuer: Optional[date] = Field(default=None)
    trade_session_date: Optional[date] = Field(default=None)
