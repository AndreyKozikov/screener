from db_repository.models.coupon_base import CouponBase
from decimal import Decimal


class CouponResponseDTO(CouponBase):
    model_config = {
        "from_attributes": True,
        "json_encoders": {
            Decimal: lambda v: float(v)
        }
    }
