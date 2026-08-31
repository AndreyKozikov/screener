from datetime import date
from typing import Optional
from decimal import Decimal
from sqlmodel import SQLModel, Field



class CouponBase(SQLModel):

    bond_id: int = Field(
        foreign_key="bonds.id",
        primary_key=True,
        nullable=False,
    )

    coupondate: Optional[date] = Field(
        default=None,
        primary_key=True,
    )

    recorddate: Optional[date] = Field(
        default=None,
    )

    startdate: Optional[date] = Field(
        default=None,
    )

    initialfacevalue: Optional[Decimal] = Field(
        default=None,
    )

    facevalue: Optional[Decimal] = Field(
        default=None,
    )

    faceunit: Optional[str] = Field(
        default=None,
    )

    value: Optional[Decimal] = Field(
        default=None,
    )

    valueprc: Optional[Decimal] = Field(
        default=None,
    )

    value_rub: Optional[Decimal] = Field(
        default=None,
    )