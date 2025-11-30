from datetime import date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# List item (simplified for table display)
class BondListItem(BaseModel):
    """Simplified bond data for list/table view"""
    SECID: str
    BOARDID: str
    SHORTNAME: str
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
    RATING_AGENCY: Optional[str] = None  # Название рейтингового агентства (agency_name_short_ru)
    RATING_LEVEL: Optional[str] = None  # Уровень рейтинга (rating_level_name_short_ru)
    
    class Config:
        from_attributes = True


# Securities section
class BondSecurity(BaseModel):
    """Securities section of bond data"""
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


# Market data section
class BondMarketData(BaseModel):
    """Market data section of bond"""
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


# Combined bond detail response
class BondDetail(BaseModel):
    """Complete bond information with all sections"""
    securities: Dict[str, Any]  # Flexible to accommodate all fields
    marketdata: Optional[Dict[str, Any]] = None
    marketdata_yields: Optional[List[Dict[str, Any]]] = None
