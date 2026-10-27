"""Validated input for coupon rows received from the MOEX API."""

from pydantic import BaseModel, ConfigDict


class CouponImportDTO(BaseModel):
    """The MOEX coupon fields stored by the database repository."""

    model_config = ConfigDict(extra="ignore")

    bond_id: int
    coupondate: str | None = None
    recorddate: str | None = None
    startdate: str | None = None
    initialfacevalue: int | float | None = None
    facevalue: int | float | None = None
    faceunit: str | None = None
    value: float | None = None
    valueprc: float | None = None
    value_rub: float | None = None
