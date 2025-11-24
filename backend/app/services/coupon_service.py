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
                return bond_data
        
        # Download fresh data
        try:
            fresh_data = self._download_coupons_from_moex(secid)
        except Exception as exc:
            # If download fails and we have cached data, return it
            if secid in bonds:
                return bonds[secid]
            raise exc
        
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
    
    def get_coupons_only(self, secid: str, force_refresh: bool = False) -> List[Dict]:
        """
        Get only coupons data (for frontend display)
        
        Args:
            secid: Security ID
            force_refresh: If True, force download from MOEX API
            
        Returns:
            List of coupon dictionaries
        """
        bond_data = self.get_coupons(secid, force_refresh)
        return bond_data.get("coupons", [])


# Singleton instance
_coupon_service: Optional[CouponService] = None


def get_coupon_service() -> CouponService:
    """Get the coupon service instance"""
    global _coupon_service
    if _coupon_service is None:
        _coupon_service = CouponService()
    return _coupon_service

