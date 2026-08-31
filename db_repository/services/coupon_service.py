from db_repository.repository.bond_repository import get_db_repository
from db_repository.repository.coupon_repository import get_coupon_repository
from typing import List, Optional
from db_repository.models.coupon import CouponBase


class CouponService:

    def __init__(self):
        self.db_coupon_repository = get_coupon_repository()
        self.db_bond_repository = get_db_repository()

    async def get_coupons(
            self,
            bondids: List[int],
    ) -> List[CouponBase]:
        result = await self.db_coupon_repository.coupons(bondids)
        coupons = [
            CouponBase.model_validate(coupon)
            for coupon in result
        ]
        return coupons

    async def get_current_coupons(self, secids: List[str]):
        result = await self.db_coupon_repository.get_current_coupon(secids)
        return {secid: coupon_value for secid, coupon_value in result}


coupon_service: Optional[CouponService] = None

def get_coupon_service():
    global coupon_service
    if coupon_service is None:
        coupon_service = CouponService()
    return coupon_service