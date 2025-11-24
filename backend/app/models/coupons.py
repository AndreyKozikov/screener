from typing import List, Optional
from pydantic import BaseModel


class Amortization(BaseModel):
    """Amortization data model"""
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


class Coupon(BaseModel):
    """Coupon data model"""
    isin: Optional[str] = None
    name: Optional[str] = None
    issuevalue: Optional[float] = None
    coupondate: Optional[str] = None
    recorddate: Optional[str] = None
    startdate: Optional[str] = None
    initialfacevalue: Optional[float] = None
    facevalue: Optional[float] = None
    faceunit: Optional[str] = None
    value: Optional[float] = None
    valueprc: Optional[float] = None
    value_rub: Optional[float] = None
    secid: Optional[str] = None
    primary_boardid: Optional[str] = None


class Offer(BaseModel):
    """Offer data model"""
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
    """Response model for bond coupons endpoint"""
    last_updated: str
    amortizations: List[Amortization]
    coupons: List[Coupon]
    offers: List[Offer]


class CouponsListResponse(BaseModel):
    """Response model for coupons list (for table display)"""
    coupons: List[Coupon]

