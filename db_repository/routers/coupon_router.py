from decimal import Decimal
from typing import List, Dict
from fastapi import Body
from db_repository.models.coupon import CouponBase
from fastapi import APIRouter
from db_repository.services.coupon_service import get_coupon_service

coupon_router = APIRouter(prefix='/api/coupons', tags=['coupons'])

@coupon_router.post("/", tags=["coupons"], response_model=List[CouponBase])
async def get_coupons(secids: List[str] = Body(...)):
    service = get_coupon_service()
    coupons = await service.get_coupons(secids)
    return coupons


@coupon_router.post("/current_coupon", tags=["coupons"])
async def get_current_coupon(bond_ids: List[str] = Body(...)) -> Dict[str, Decimal]:
    service = get_coupon_service()
    current_coupon = await service.get_current_coupons(bond_ids)
    return current_coupon