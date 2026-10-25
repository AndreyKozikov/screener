from sqlmodel import Field

from typing import Optional
from db_repository.models.bond_base import BondBase, BondSecurityBase, BondMarketDataBase, BondMarketDataYieldBase
from db_repository.models.coupon_response_dto import CouponResponseDTO

class BondResponseDTO(BondBase):
    id: int
    coupons: list[CouponResponseDTO] = Field(default_factory=list)
    security: Optional[BondSecurityBase] = None
    market_data: Optional[BondMarketDataBase] = None
    market_data_yields: Optional[BondMarketDataYieldBase] = None

    # ORM attributes and model_dump() use Python field names (for example,
    # ``secid``), while BondBase also defines MOEX validation aliases (``SECID``).
    # Accept both forms so DTOs can be built from ORM objects as well as MOEX data.
    model_config = {"from_attributes": True, "populate_by_name": True}
