from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

import orjson

# Path to store coupons data
COUPONS_DATA_FILE = Path(__file__).parent.parent / "data" / "coupons_data.json"


class CouponService:
    """Service for handling bond coupon data from MOEX API"""
    
    # Number of days after which data is considered stale
    STALE_DAYS = 14
    
    def __init__(self, data_file: Path = COUPONS_DATA_FILE):
        self.data_file = data_file
        self._ensure_data_file_exists()
    
    def _ensure_data_file_exists(self):
        """Create coupons data file if it doesn't exist"""
        if not self.data_file.exists():
            initial_data = {
                "bonds": {}
            }
            self._write_data(initial_data)
    
    def _read_data(self) -> Dict:
        """Read coupons data from JSON file"""
        if not self.data_file.exists():
            return {"bonds": {}}
        
        with open(self.data_file, 'rb') as f:
            return orjson.loads(f.read())
    
    def _write_data(self, data: Dict):
        """Write coupons data to JSON file"""
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        
        serialized = orjson.dumps(
            data,
            option=orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE,
        )
        
        self.data_file.write_bytes(serialized)
    
    def _is_data_stale(self, last_updated: str) -> bool:
        """Check if data is older than STALE_DAYS"""
        try:
            last_date = datetime.strptime(last_updated, "%Y-%m-%d").date()
            days_ago = (date.today() - last_date).days
            return days_ago > self.STALE_DAYS
        except (ValueError, TypeError):
            return True
    
    def detect_coupon_type(self, coupons: List[Dict]) -> str:
        """
        Определение типа купона только по фактическим купонным выплатам (поле value):
        - "FIX"   — купон по сути постоянный (почти все выплаты одинаковые, изменения редки)
        - "FLOAT" — купон переменный (выплаты систематически меняются)

        Анализируется весь ряд выплат, а не только минимум и максимум.
        """
        payments = [c.get("value") for c in coupons if c.get("value") is not None]

        # Недостаточно данных для осмысленного вывода
        if len(payments) < 4:
            return "FIX"

        # Округляем до 2 знаков, чтобы убрать мелкие погрешности округления
        rounded = [round(v, 2) for v in payments]

        counter = Counter(rounded)
        unique_values = list(counter.keys())
        unique_count = len(unique_values)
        total = len(rounded)

        # Все выплаты по одному уровню
        if unique_count == 1:
            return "FIX"

        # Основной (самый частый) уровень выплат и его доля
        most_common_value, most_common_count = counter.most_common(1)[0]
        share_most_common = most_common_count / total

        # Считаем число реальных переходов между выплатами
        threshold = 0.10  # изменение выплаты менее 10 копеек считаем шумом
        changes = 0
        for prev, cur in zip(rounded, rounded[1:]):
            if abs(cur - prev) > threshold:
                changes += 1

        # Если большинство выплат одинаковые и изменений мало — считаем FIX
        if share_most_common >= 0.8 and changes <= 2:
            return "FIX"

        # В любом другом случае — переменный купон
        return "FLOAT"
    
    def _download_coupons_from_moex(self, secid: str) -> Dict:
        """
        Download bond coupon data from MOEX API
        
        Args:
            secid: Security ID
            
        Returns:
            Dictionary with coupons, amortizations, and offers data
        """
        url = f"https://iss.moex.com/iss/securities/{secid}/bondization.json"
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        
        try:
            with urlopen(request, timeout=30) as response:
                raw_payload = response.read()
        except URLError as exc:
            raise RuntimeError(f"Failed to download coupons data for {secid}: {exc}") from exc
        
        try:
            payload = orjson.loads(raw_payload)
        except orjson.JSONDecodeError as exc:
            raise RuntimeError(f"Received invalid JSON for {secid}") from exc
        
        # Parse the response structure
        result = {
            "amortizations": [],
            "coupons": [],
            "offers": []
        }
        
        # Parse amortizations
        amortizations = payload.get("amortizations", {})
        amort_columns = amortizations.get("columns", [])
        amort_data = amortizations.get("data", [])
        
        for row in amort_data:
            if len(row) == len(amort_columns):
                amort_dict = dict(zip(amort_columns, row))
                result["amortizations"].append(amort_dict)
        
        # Parse coupons
        coupons = payload.get("coupons", {})
        coupon_columns = coupons.get("columns", [])
        coupon_data = coupons.get("data", [])
        
        for row in coupon_data:
            if len(row) == len(coupon_columns):
                coupon_dict = dict(zip(coupon_columns, row))
                result["coupons"].append(coupon_dict)
        
        # Parse offers
        offers = payload.get("offers", {})
        offer_columns = offers.get("columns", [])
        offer_data = offers.get("data", [])
        
        for row in offer_data:
            if len(row) == len(offer_columns):
                offer_dict = dict(zip(offer_columns, row))
                result["offers"].append(offer_dict)
        
        return result
    
    def get_coupons(self, secid: str, force_refresh: bool = False) -> Dict:
        """
        Get coupon data for a specific bond
        
        Args:
            secid: Security ID
            force_refresh: If True, force download from MOEX API
            
        Returns:
            Dictionary with last_updated, amortizations, coupons, and offers
        """
        data = self._read_data()
        bonds = data.get("bonds", {})
        
        # Check if data exists and is not stale
        if secid in bonds and not force_refresh:
            bond_data = bonds[secid]
            last_updated = bond_data.get("last_updated", "")
            
            if last_updated and not self._is_data_stale(last_updated):
                # Load coupon_type from file ONLY - no recalculation
                # Coupon type is calculated and saved only during data refresh from MOEX API
                coupons = bond_data.get("coupons", [])
                amortizations = bond_data.get("amortizations", [])
                
                # For old data structure: one-time in-memory migration for backward compatibility
                # This only affects the returned data, does NOT save to file
                if coupons and len(coupons) > 0 and amortizations and len(amortizations) > 0:
                    # Check if amortizations already have coupon_type
                    has_coupon_type_in_amort = any(
                        amort.get("coupon_type") is not None 
                        for amort in amortizations
                    )
                    
                    # Only migrate in-memory if amortizations don't have coupon_type but coupons do (old structure)
                    if not has_coupon_type_in_amort:
                        coupon_type_from_coupons = coupons[0].get("coupon_type")
                        if coupon_type_from_coupons:
                            # In-memory migration only (for reading old data structure)
                            # This does NOT save to file - actual migration happens only on refresh
                            for amort in amortizations:
                                if "coupon_type" not in amort:
                                    amort["coupon_type"] = coupon_type_from_coupons
                
                # Clean duplicate fields from coupons (for old data structure)
                bond_data["coupons"] = [self._clean_coupon_fields(c) for c in coupons]
                
                return bond_data
        
        # Download fresh data
        try:
            fresh_data = self._download_coupons_from_moex(secid)
        except Exception as exc:
            # If download fails and we have cached data, return it (with cleaned coupons)
            if secid in bonds:
                cached_data = bonds[secid].copy()
                cached_coupons = cached_data.get("coupons", [])
                cached_data["coupons"] = [self._clean_coupon_fields(c) for c in cached_coupons]
                return cached_data
            raise exc
        
        # Detect coupon type
        coupon_type = self.detect_coupon_type(fresh_data["coupons"])
        
        # Add coupon_type to each amortization entry
        for amort in fresh_data["amortizations"]:
            amort["coupon_type"] = coupon_type
        
        # Remove duplicate fields from coupons using helper method
        fresh_data["coupons"] = [self._clean_coupon_fields(c) for c in fresh_data["coupons"]]
        
        # Save to file
        bond_entry = {
            "last_updated": date.today().isoformat(),
            "amortizations": fresh_data["amortizations"],
            "coupons": fresh_data["coupons"],
            "offers": fresh_data["offers"]
        }
        
        bonds[secid] = bond_entry
        data["bonds"] = bonds
        self._write_data(data)
        
        # Clear CouponLoader cache so it picks up the new data
        from app.services.coupon_loader import get_coupon_loader
        coupon_loader = get_coupon_loader()
        if coupon_loader is not None:
            coupon_loader.clear_cache()
        
        # Clear DataLoader cache so bonds list is reloaded with new coupon data
        from app.services.data_loader import get_data_loader
        try:
            data_loader = get_data_loader()
            data_loader.clear_bonds_cache()  # Clear bonds cache to force reload
        except RuntimeError:
            # DataLoader not initialized yet, that's ok
            pass
        
        return bond_entry
    
    def _clean_coupon_fields(self, coupon: Dict) -> Dict:
        """
        Remove duplicate fields from coupon that should not be in coupons section.
        
        Args:
            coupon: Coupon dictionary
            
        Returns:
            Cleaned coupon dictionary
        """
        # Fields to remove from coupons (these are duplicated and moved to amortizations)
        fields_to_remove = ["isin", "name", "issuevalue", "primary_boardid", "coupon_type", "secid"]
        cleaned = {k: v for k, v in coupon.items() if k not in fields_to_remove}
        return cleaned
    
    def get_coupons_only(self, secid: str, force_refresh: bool = False) -> List[Dict]:
        """
        Get only coupons data (for frontend display)
        
        Args:
            secid: Security ID
            force_refresh: If True, force download from MOEX API
            
        Returns:
            List of coupon dictionaries (with duplicate fields removed)
        """
        bond_data = self.get_coupons(secid, force_refresh)
        coupons = bond_data.get("coupons", [])
        # Clean old fields from coupons for backward compatibility with old data structure
        return [self._clean_coupon_fields(c) for c in coupons]


# Singleton instance
_coupon_service: Optional[CouponService] = None


def get_coupon_service() -> CouponService:
    """Get the coupon service instance"""
    global _coupon_service
    if _coupon_service is None:
        _coupon_service = CouponService()
    return _coupon_service

