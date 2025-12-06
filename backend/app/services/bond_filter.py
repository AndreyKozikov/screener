import re
from typing import List, Optional
from app.models.bond import BondListItem
from app.models.filters import BondFilters


# Rating scale - from highest to lowest
RATINGS = [
    'AAA',
    'AA+', 'AA', 'AA-',
    'A+', 'A', 'A-',
    'BBB+', 'BBB', 'BBB-',
    'BB+', 'BB', 'BB-',
    'B+', 'B', 'B-',
    'CCC+', 'CCC', 'CCC-',
    'CC', 'C',
    'D'
]


def get_rating_index(rating: Optional[str]) -> Optional[int]:
    """
    Get rating index in the rating scale. Returns None if rating is not found.
    Supports partial matching - e.g., 'ruAA', 'BB(ru)', 'AA+' will match 'AA', 'BB', 'AA+' from RATINGS list.
    """
    if rating is None or not rating:
        return None
    rating_upper = rating.strip().upper()
    
    # First try exact match
    try:
        return RATINGS.index(rating_upper)
    except ValueError:
        pass
    
    # Try to find any rating from RATINGS list within the bond rating string
    # Check longer ratings first to avoid false matches (e.g., 'AAA' before 'AA')
    for i, rating_value in enumerate(RATINGS):
        if rating_value in rating_upper:
            return i
    
    return None


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
    
    # Yield to maturity range
    if filters.yield_min is not None:
        filtered = [b for b in filtered if b.YIELDATPREVWAPRICE and b.YIELDATPREVWAPRICE >= filters.yield_min]
    
    if filters.yield_max is not None:
        filtered = [b for b in filtered if b.YIELDATPREVWAPRICE and b.YIELDATPREVWAPRICE <= filters.yield_max]
    
    # Coupon yield to price range (calculated: (COUPONVALUE / (PREVPRICE × FACEVALUE / 100)) × payments_per_year × 100)
    if filters.coupon_yield_min is not None or filters.coupon_yield_max is not None:
        def calc_coupon_yield(bond: BondListItem) -> Optional[float]:
            """
            Calculate coupon yield to current price.
            Formula: (COUPONVALUE / (PREVPRICE × FACEVALUE / 100)) × (number of payments per year) × 100
            """
            if (bond.COUPONVALUE is not None and 
                bond.PREVPRICE is not None and 
                bond.FACEVALUE is not None and
                bond.COUPONPERIOD is not None and
                bond.PREVPRICE > 0 and
                bond.FACEVALUE > 0 and
                bond.COUPONPERIOD > 0):
                # Calculate number of coupon payments per year
                payments_per_year = 365 / bond.COUPONPERIOD
                # Coupon yield = (COUPONVALUE / (PREVPRICE × FACEVALUE / 100)) × payments_per_year × 100
                # Simplified: (COUPONVALUE × 10000 / (PREVPRICE × FACEVALUE)) × payments_per_year
                return (bond.COUPONVALUE * 10000 / (bond.PREVPRICE * bond.FACEVALUE)) * payments_per_year
            return None
        
        if filters.coupon_yield_min is not None:
            filtered = [b for b in filtered if (cy := calc_coupon_yield(b)) is not None and cy >= filters.coupon_yield_min]
        
        if filters.coupon_yield_max is not None:
            filtered = [b for b in filtered if (cy := calc_coupon_yield(b)) is not None and cy <= filters.coupon_yield_max]
    
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
    
    # Bond type filter
    if filters.bondtype:
        before_count = len(filtered)
        filtered = [b for b in filtered if b.BONDTYPE is not None and b.BONDTYPE in filters.bondtype]
        after_count = len(filtered)
        print(f"DEBUG filter_bonds: bondtype filter - before={before_count}, after={after_count}, filtering by={filters.bondtype}")
    
    # Coupon type filter
    if filters.coupon_type:
        before_count = len(filtered)
        filtered = [b for b in filtered if b.COUPON_TYPE is not None and b.COUPON_TYPE in filters.coupon_type]
        after_count = len(filtered)
        print(f"DEBUG filter_bonds: coupon_type filter - before={before_count}, after={after_count}, filtering by={filters.coupon_type}")
    
    # Rating range filter
    if filters.rating_min is not None or filters.rating_max is not None:
        before_count = len(filtered)
        
        # Get rating indices for min and max
        min_rating_index = 0 if filters.rating_min is None else RATINGS.index(filters.rating_min.upper())
        max_rating_index = len(RATINGS) - 1 if filters.rating_max is None else RATINGS.index(filters.rating_max.upper())
        
        # Filter bonds by rating range
        # Check if any rating from selected range matches in bond's RATING_LEVEL as a complete rating
        # E.g., filter "A+" should match "A+(RU)" but filter "A" should NOT match "AAA" or "A+"
        def is_rating_in_range(bond: BondListItem) -> bool:
            if bond.RATING_LEVEL is None or not bond.RATING_LEVEL:
                return False
            
            bond_rating_upper = bond.RATING_LEVEL.upper()
            
            # Check if any rating from the selected range matches as a complete rating
            for rating_index in range(min_rating_index, max_rating_index + 1):
                rating_value = RATINGS[rating_index]
                
                # Use regex to match whole rating, not as part of another rating
                # Rating can be preceded by: start of string, space, opening parenthesis, or lowercase letters (prefix)
                # Rating can be followed by: end of string, space, closing parenthesis, opening parenthesis (suffix)
                # Pattern ensures "A" matches "A(RU)" but not "AAA" or "A+"
                pattern = rf'(?:^|[^A-Z])({re.escape(rating_value)})(?:[^A-Z+\-]|$)'
                if re.search(pattern, bond_rating_upper):
                    return True
            
            return False
        
        filtered = [b for b in filtered if is_rating_in_range(b)]
        after_count = len(filtered)
        print(f"DEBUG filter_bonds: rating filter - before={before_count}, after={after_count}, filtering by={filters.rating_min} to {filters.rating_max}")
    
    # Search filter is handled on client side - NOT on server
    # No server-side search filtering
    
    return filtered
