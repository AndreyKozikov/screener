from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

import orjson


class CouponLoader:
    """Helper service for loading coupon data from coupons_data.json"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.coupons_file = data_dir / "coupons_data.json"
        self._coupons_cache: Optional[Dict[str, Dict]] = None
    
    def _load_coupons_data(self) -> Dict[str, Dict]:
        """Load coupons data from JSON file"""
        if self._coupons_cache is not None:
            return self._coupons_cache
        
        if not self.coupons_file.exists():
            self._coupons_cache = {}
            return self._coupons_cache
        
        try:
            with open(self.coupons_file, 'rb') as f:
                data = orjson.loads(f.read())
            
            self._coupons_cache = data.get("bonds", {})
        except Exception as e:
            print(f"Warning: Failed to load coupons data: {e}")
            self._coupons_cache = {}
        
        return self._coupons_cache
    
    @staticmethod
    def _parse_date(date_str: str) -> Optional[date]:
        """Parse date string from various formats"""
        if not date_str or date_str == "0000-00-00":
            return None
        
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None
    
    def get_nearest_coupon_value(self, secid: str, current_date: Optional[date] = None) -> Optional[float]:
        """
        Get coupon value (value in rubles) from the nearest coupon date to current date.
        
        Args:
            secid: Security ID
            current_date: Current date (defaults to today)
            
        Returns:
            Coupon value (value) from nearest coupon in rubles, or None if not found
        """
        if current_date is None:
            current_date = date.today()
        
        coupons_data = self._load_coupons_data()
        
        if secid not in coupons_data:
            return None
        
        bond_data = coupons_data[secid]
        coupons = bond_data.get("coupons", [])
        
        if not coupons:
            return None
        
        # Find the nearest coupon date (future or past)
        nearest_coupon = None
        min_delta = None
        
        for coupon in coupons:
            coupon_date_str = coupon.get("coupondate")
            if not coupon_date_str:
                continue
            
            coupon_date = self._parse_date(coupon_date_str)
            if not coupon_date:
                continue
            
            # Calculate absolute difference in days
            delta = abs((coupon_date - current_date).days)
            
            if min_delta is None or delta < min_delta:
                min_delta = delta
                nearest_coupon = coupon
        
        if nearest_coupon is None:
            return None
        
        # Use value (coupon amount in original currency) to match what's shown in coupons tab
        coupon_value = nearest_coupon.get("value")
        
        if coupon_value is not None:
            try:
                return float(coupon_value)
            except (ValueError, TypeError):
                return None
        
        return None
    
    def get_coupon_type(self, secid: str) -> Optional[str]:
        """
        Get coupon type (FIX or FLOAT) from amortizations section.
        
        Args:
            secid: Security ID
            
        Returns:
            Coupon type (FIX or FLOAT) from amortizations, or None if not found
        """
        coupons_data = self._load_coupons_data()
        
        if secid not in coupons_data:
            return None
        
        bond_data = coupons_data[secid]
        amortizations = bond_data.get("amortizations", [])
        
        if not amortizations:
            return None
        
        # Get coupon_type from first amortization (all amortizations have the same coupon_type)
        coupon_type = amortizations[0].get("coupon_type")
        
        return coupon_type if coupon_type in ("FIX", "FLOAT") else None
    
    def clear_cache(self):
        """Clear the coupons cache"""
        self._coupons_cache = None


# Singleton instance
_coupon_loader: Optional[CouponLoader] = None


def init_coupon_loader(data_dir: Path):
    """Initialize the coupon loader singleton"""
    global _coupon_loader
    _coupon_loader = CouponLoader(data_dir)


def get_coupon_loader() -> Optional[CouponLoader]:
    """Get the coupon loader instance"""
    return _coupon_loader

