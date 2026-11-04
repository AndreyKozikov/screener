"""Coupon response DTOs exposed by the conversion service."""

from typing import List, Optional

from pydantic import BaseModel


class Coupon(BaseModel):
    coupondate: Optional[str] = None
    recorddate: Optional[str] = None
    startdate: Optional[str] = None
    initialfacevalue: Optional[float] = None
    facevalue: Optional[float] = None
    faceunit: Optional[str] = None
    value: Optional[float] = None
    valueprc: Optional[float] = None
    value_rub: Optional[float] = None


class CouponsListResponse(BaseModel):
    coupons: List[Coupon]


class CouponsBySecid(BaseModel):
    secid: str
    coupons: List[Coupon]


class MultipleCouponsResponse(BaseModel):
    data: List[CouponsBySecid]
