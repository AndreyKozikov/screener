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


def standardize_rating(rating: Optional[str]) -> Optional[str]:
    """
    Standardizes rating notation by removing Russian market indicators.
    
    Removes:
    - (RU) suffix (with or without space): "AAA (RU)" -> "AAA"
    - .ru suffix: "AAA.ru" -> "AAA"
    - ru prefix (case-insensitive): "ruAAA" -> "AAA"
    
    Preserves the core rating value (e.g., AAA, AA+, BBB-) including modifiers (+ and -).
    
    Examples:
        "AAA (RU)" -> "AAA"
        "AA+ (RU)" -> "AA+"
        "AAA.ru" -> "AAA"
        "AA+.ru" -> "AA+"
        "ruAAA" -> "AAA"
        "ruAA+" -> "AA+"
        "BBB-" -> "BBB-"
        "BBB- (RU)" -> "BBB-"
        "ruBBB-" -> "BBB-"
    
    Args:
        rating: Rating string that may contain Russian market indicators
    
    Returns:
        Standardized rating string containing only the core rating value, or None if input is None/empty
    """
    if not rating or not isinstance(rating, str):
        return None
    
    # Strip whitespace
    normalized = rating.strip()
    
    if not normalized:
        return None
    
    # Remove (RU) suffix - handles both "AAA (RU)" and "AAA(RU)" formats
    # Case-insensitive, with optional spaces
    normalized = re.sub(r'\s*\(RU\)\s*$', '', normalized, flags=re.IGNORECASE)
    
    # Remove .ru suffix - handles "AAA.ru" format
    # Case-insensitive
    normalized = re.sub(r'\.ru\s*$', '', normalized, flags=re.IGNORECASE)
    
    # Remove ru prefix - handles "ruAAA" format
    # Case-insensitive, with optional spaces after
    normalized = re.sub(r'^ru\s*', '', normalized, flags=re.IGNORECASE)
    
    # Remove any remaining ru indicators that might be embedded (e.g., "BB+|ru|")
    # This handles edge cases like "BB+|ru|" -> "BB+"
    normalized = re.sub(r'\|ru\|', '', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\|RU\|', '', normalized, flags=re.IGNORECASE)
    
    # Clean up any extra whitespace
    normalized = normalized.strip()
    
    # Return None if result is empty, otherwise return the standardized rating
    return normalized if normalized else None


def is_rating_in_range(
    rating_level: Optional[str],
    rating_min: Optional[str],
    rating_max: Optional[str],
) -> bool:
    """
    Проверяет, входит ли рейтинг облигации (RATING_LEVEL) в диапазон [rating_min, rating_max].
    Используется для фильтрации по рейтингу в сервисном слое.
    """
    if not rating_level or not str(rating_level).strip():
        return False
    if rating_min is None and rating_max is None:
        return True
    try:
        min_rating_index = 0 if rating_min is None else RATINGS.index(rating_min.upper())
        max_rating_index = len(RATINGS) - 1 if rating_max is None else RATINGS.index(rating_max.upper())
    except ValueError:
        return True  # неверные границы — не отфильтровываем
    bond_rating_upper = str(rating_level).upper()
    for rating_index in range(min_rating_index, max_rating_index + 1):
        rating_value = RATINGS[rating_index]
        pattern = rf'(?:^|[^A-Z])({re.escape(rating_value)})(?:[^A-Z+\-]|$)'
        if re.search(pattern, bond_rating_upper):
            return True
    return False


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
    # Supports all bond types from bonds_emitent.json:
    # - exchange_bond (Биржевая облигация)
    # - ofz_bond (ОФЗ - Государственная облигация)
    # - corporate_bond (Корпоративная облигация)
    # - municipal_bond (Муниципальная облигация)
    # - subfederal_bond (Региональная облигация)
    if filters.bondtype:
        before_count = len(filtered)
        filtered = [b for b in filtered if b.BONDTYPE is not None and b.BONDTYPE in filters.bondtype]
        after_count = len(filtered)
        print(f"DEBUG filter_bonds: bondtype filter - before={before_count}, after={after_count}, filtering by={filters.bondtype}")
    
    # Bond type 43 filter (вид облигации из bonds.json)
    # Supports bond types from bonds.json index 43:
    # - Амортизируемые облигации
    # - Валютные облигации
    # - Конвертируемые облигации
    # - Линкер/облигации с индексируемым
    # - Структурная облигация
    # - Фикс с известным купоном
    # - Фикс с неизвестным купоном
    # - Флоатер
    if filters.bondtype43:
        before_count = len(filtered)
        filtered = [b for b in filtered if b.BONDTYPE43 is not None and b.BONDTYPE43 in filters.bondtype43]
        after_count = len(filtered)
        print(f"DEBUG filter_bonds: bondtype43 filter - before={before_count}, after={after_count}, filtering by={filters.bondtype43}")
    
    # Rating range filter (использует общий helper is_rating_in_range)
    if filters.rating_min is not None or filters.rating_max is not None:
        before_count = len(filtered)
        filtered = [b for b in filtered if is_rating_in_range(b.RATING_LEVEL, filters.rating_min, filters.rating_max)]
        after_count = len(filtered)
        print(f"DEBUG filter_bonds: rating filter - before={before_count}, after={after_count}, filtering by={filters.rating_min} to {filters.rating_max}")
    
    # Search filter is handled on client side - NOT on server
    # No server-side search filtering
    
    return filtered
