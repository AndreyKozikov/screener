"""Validated response models returned by the database service's bond API."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class BondCouponRecordDTO(BaseModel):
    model_config = ConfigDict(extra="ignore")

    coupondate: Optional[date] = None
    value: Optional[float] = None


class BondRepositoryRowDTO(BaseModel):
    model_config = ConfigDict(extra="ignore")

    secid: str
    boardid: Optional[str] = None
    isin: Optional[str] = None
    name: Optional[str] = None
    secname: Optional[str] = None
    rating: Optional[str] = None
    rating_agency: Optional[str] = None
    current_price: Optional[float] = None
    coupon_yield_to_price: Optional[float] = None
    yield_to_maturity: Optional[float] = None
    face_value: Optional[float] = None
    currency: Optional[str] = None
    face_unit: Optional[str] = None
    coupon_value: Optional[float] = None
    coupon_percent: Optional[float] = None
    coupon_frequency: Optional[float] = None
    coupon_period: Optional[int] = None
    accrued_interest: Optional[float] = None
    duration_years: Optional[float] = None
    duration: Optional[float] = None
    duration_waprice: Optional[int] = None
    maturity_date: Optional[str] = None
    listing_level: Optional[int] = None
    bond_type: Optional[int] = None
    bond_kind: Optional[int] = None
    offer_date: Optional[str] = None
    status: Optional[str] = None
    trading_status: Optional[str] = None
    next_coupon: Optional[str] = None
    board_name: Optional[str] = None
    call_option_date: Optional[str] = None
    put_option_date: Optional[str] = None
    coupons: list[BondCouponRecordDTO] = Field(default_factory=list)
