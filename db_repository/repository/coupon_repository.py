from db_repository.core.database_init import get_session
from typing import Optional
from typing import List
from sqlmodel import select
from datetime import date
from sqlalchemy import func

from db_repository.models.bond import Bond
from db_repository.models.coupon import Coupon


class CouponRepository:
    def __init__(self):
        pass


    async def coupons(self, bondids: List[int]):
        statement = (
            select(Coupon)
            .where(Coupon.bond_id.in_(bondids))
        )

        try:
            with get_session() as session:
                return session.exec(statement).fetchall()
        except:
            raise

    async def get_current_coupon(self, secids: List[str]):
        today = date.today()

        subquery = (
            select(
                Coupon.bond_id,
                func.max(Coupon.coupondate).label("coupondate")
            )
            .where(
                Coupon.coupondate <= today,
            )
            .group_by(Coupon.bond_id)
            .subquery()
        )
        statement = (
            select(
                Bond.secid,
                Coupon.value
            )
            .join(Coupon, Coupon.bond_id == Bond.id)
            .join(
                subquery,
                (Coupon.bond_id == subquery.c.bond_id)
                & (Coupon.coupondate == subquery.c.coupondate)
            )
            .where(Bond.secid.in_(secids))
        )
        try:
            with get_session() as session:
                return session.exec(statement).all()
        except:
            raise



coupon_repository: Optional[CouponRepository] = None

def get_coupon_repository():
    global coupon_repository
    if coupon_repository is None:
        coupon_repository = CouponRepository()
    return coupon_repository