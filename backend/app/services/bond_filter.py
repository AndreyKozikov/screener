from typing import List
from app.models.bond import BondListItem
from app.models.filters import BondFilters


def filter_bonds(bonds: List[BondListItem], filters: BondFilters) -> List[BondListItem]:
    """
    Apply filters to bond list.
    
    Translates Streamlit filtering logic to backend service.
    """
    filtered = bonds
    
    # Coupon rate range
    if filters.coupon_min is not None:
        filtered = [b for b in filtered if b.COUPONPERCENT and b.COUPONPERCENT >= filters.coupon_min]
    
    if filters.coupon_max is not None:
        filtered = [b for b in filtered if b.COUPONPERCENT and b.COUPONPERCENT <= filters.coupon_max]
    
    # Maturity date range
    if filters.matdate_from is not None:
        filtered = [b for b in filtered if b.MATDATE and b.MATDATE >= filters.matdate_from]
    
    if filters.matdate_to is not None:
        filtered = [b for b in filtered if b.MATDATE and b.MATDATE <= filters.matdate_to]
    
    # List level filter
    if filters.listlevel:
        before_count = len(filtered)
        filtered = [b for b in filtered if b.LISTLEVEL is not None and b.LISTLEVEL in filters.listlevel]
        after_count = len(filtered)
        print(f"DEBUG filter_bonds: listlevel filter - before={before_count}, after={after_count}, filtering by={filters.listlevel}")
    
    # Currency filter (face unit)
    if filters.faceunit:
        before_count = len(filtered)
        filtered = [b for b in filtered if b.FACEUNIT is not None and b.FACEUNIT in filters.faceunit]
        after_count = len(filtered)
        print(f"DEBUG filter_bonds: faceunit filter - before={before_count}, after={after_count}, filtering by={filters.faceunit}")
    
    # Search filter is handled on client side - NOT on server
    # No server-side search filtering
    
    return filtered
