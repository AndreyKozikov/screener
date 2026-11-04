"""Read-only coupon queries from the shared database."""

from datetime import date
from typing import Any, Dict, List, Optional

from app.repository.db.db_coupon import DBCoupon


class CouponService:
    """Provide cached coupon data to backend consumers without refreshing it."""

    def __init__(self, repository: Optional[DBCoupon] = None) -> None:
        self._repository = repository or DBCoupon()

    def get_coupons(self, secid: str) -> Dict[str, Any]:
        rows = self._repository.fetch_coupons_for_frontend(secids=[secid])
        coupons = [
            {key: value for key, value in row.items() if key != "bond_id"}
            for row in rows
        ]
        return {
            "last_updated": date.today().isoformat(),
            "coupons": coupons,
            "offers": [],
        }

    def get_coupons_batch(
        self,
        secids: List[str],
    ) -> Dict[str, Dict[str, Any]]:
        if not secids:
            return {}

        rows = self._repository.fetch_coupons_for_frontend(secids=secids)
        coupons_by_secid: Dict[str, List[Dict[str, Any]]] = {secid: [] for secid in secids}
        for row in rows:
            secid = row.get("secid")
            if secid in coupons_by_secid:
                coupons_by_secid[secid].append(
                    {key: value for key, value in row.items() if key != "bond_id"}
                )
        return {secid: {"coupons": coupons} for secid, coupons in coupons_by_secid.items()}


_coupon_service: Optional[CouponService] = None


def get_coupon_service() -> CouponService:
    global _coupon_service
    if _coupon_service is None:
        _coupon_service = CouponService()
    return _coupon_service
