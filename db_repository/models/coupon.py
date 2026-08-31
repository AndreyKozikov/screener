from db_repository.models.coupon_base import CouponBase
from sqlmodel import SQLModel

class Coupon(CouponBase, table=True):

    __tablename__ = "coupons"
