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
        
        try:
            with open(self.data_file, 'rb') as f:
                raw_data = f.read()
                return orjson.loads(raw_data)
        except (orjson.JSONDecodeError, UnicodeDecodeError) as exc:
            # If file is corrupted, log error and return empty structure
            # This will force refresh from MOEX API
            print(f"[КУПОНЫ] ВНИМАНИЕ: Файл {self.data_file} поврежден (ошибка: {type(exc).__name__}: {exc})")
            print(f"[КУПОНЫ] Файл будет пересоздан при следующем обновлении данных")
            # Try to backup corrupted file
            try:
                backup_path = self.data_file.with_suffix('.json.corrupted')
                if not backup_path.exists():
                    import shutil
                    shutil.copy2(self.data_file, backup_path)
                    print(f"[КУПОНЫ] Создана резервная копия поврежденного файла: {backup_path}")
            except Exception:
                pass  # Ignore backup errors
            return {"bonds": {}}
    
    def _write_data(self, data: Dict):
        """Write coupons data to JSON file"""
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Clean data before serialization to ensure valid UTF-8
        cleaned_data = self._clean_string_value(data)
        
        try:
            serialized = orjson.dumps(
                cleaned_data,
                option=orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE,
            )
            self.data_file.write_bytes(serialized)
        except (TypeError, ValueError) as exc:
            # If serialization fails, try to clean data more aggressively
            print(f"[КУПОНЫ] ВНИМАНИЕ: Ошибка при сериализации данных: {exc}")
            print(f"[КУПОНЫ] Попытка дополнительной очистки данных...")
            # Additional cleaning pass
            cleaned_data = self._clean_string_value(cleaned_data)
            serialized = orjson.dumps(
                cleaned_data,
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
            
        Note:
            New API format returns array: [{"charsetinfo": {...}}, {"coupons": [...]}]
            Only coupons are returned, amortizations and offers are empty.
            A minimal amortization entry is created from the first coupon.
        """
        url = f"https://iss.moex.com/iss/securities/{secid}/bondization.json?iss.json=extended&iss.meta=off&iss.only=coupons&lang=ru&limit=unlimited"
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        
        try:
            with urlopen(request, timeout=30) as response:
                raw_payload = response.read()
        except URLError as exc:
            raise RuntimeError(f"Failed to download coupons data for {secid}: {exc}") from exc
        
        try:
            payload = orjson.loads(raw_payload)
        except orjson.JSONDecodeError as exc:
            raise RuntimeError(f"Received invalid JSON for {secid}: {exc}") from exc
        
        # Parse the response structure
        result = {
            "amortizations": [],
            "coupons": [],
            "offers": []
        }
        
        # New API format: payload is an array, second element contains coupons
        # Format: [{"charsetinfo": {"name": "utf-8"}}, {"coupons": [...]}]
        if not isinstance(payload, list) or len(payload) < 2:
            raise RuntimeError(f"Unexpected API response format for {secid}: expected array with at least 2 elements")
        
        # Get coupons array from second element
        coupons_data = payload[1].get("coupons", [])
        if not isinstance(coupons_data, list):
            raise RuntimeError(f"Unexpected coupons format for {secid}: expected array, got {type(coupons_data).__name__}")
        
        # Parse coupons - they come as objects already in new API format
        first_coupon_raw = None
        for coupon_dict in coupons_data:
            # Create a copy to avoid modifying original data, then clean string values
            coupon_dict_copy = coupon_dict.copy() if isinstance(coupon_dict, dict) else coupon_dict
            coupon_dict_cleaned = self._clean_string_value(coupon_dict_copy)
            result["coupons"].append(coupon_dict_cleaned)
            # Save first coupon raw data (before cleaning duplicate fields) for amortization creation
            if first_coupon_raw is None:
                first_coupon_raw = coupon_dict_cleaned
        
        # Create a minimal amortization entry from first coupon data
        # Use first coupon raw data (already cleaned for UTF-8, but before removing duplicate fields)
        if first_coupon_raw is not None:
            # Create amortization entry with common fields from coupon
            amort_entry = {
                "isin": first_coupon_raw.get("isin"),
                "name": first_coupon_raw.get("name"),
                "issuevalue": first_coupon_raw.get("issuevalue"),
                "secid": first_coupon_raw.get("secid") or secid,
                "primary_boardid": first_coupon_raw.get("primary_boardid"),
                "facevalue": first_coupon_raw.get("facevalue"),
                "initialfacevalue": first_coupon_raw.get("initialfacevalue"),
                "faceunit": first_coupon_raw.get("faceunit"),
            }
            # Clean and add to result (already cleaned, but double-check)
            amort_entry = self._clean_string_value(amort_entry)
            result["amortizations"].append(amort_entry)
        
        # Offers are not returned by new API, leaving empty array
        
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
                # Clean cached data to ensure valid UTF-8 (in case it was saved before fix)
                try:
                    bond_data = self._clean_string_value(bond_data)
                except Exception as exc:
                    # If cleaning fails, force refresh by breaking out of this block
                    print(f"[КУПОНЫ] ВНИМАНИЕ: Не удалось очистить кэшированные данные для {secid}: {exc}")
                    print(f"[КУПОНЫ] Будет выполнена загрузка свежих данных с MOEX")
                    # bond_data will be None, so we'll skip this block and download fresh data
                    bond_data = None
                
                if bond_data:
                    coupons = bond_data.get("coupons", [])
                    
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
        
        # Data is already cleaned in _download_coupons_from_moex, but clean again to be safe
        # Remove duplicate fields from coupons using helper method
        fresh_data["coupons"] = [self._clean_coupon_fields(c) for c in fresh_data["coupons"]]
        
        # Save to file (data is already cleaned)
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
    
    def _clean_string_value(self, value: any) -> any:
        """
        Clean string values to ensure valid UTF-8 encoding.
        Removes surrogate pairs that cause UTF-8 encoding errors.
        
        Args:
            value: Value to clean (can be string, dict, list, or other types)
            
        Returns:
            Cleaned value with valid UTF-8 strings
        """
        if value is None:
            return None
        elif isinstance(value, str):
            # Remove surrogate pairs by encoding/decoding with error handling
            try:
                # Try to encode and decode to validate UTF-8
                value.encode('utf-8').decode('utf-8')
                return value
            except (UnicodeEncodeError, UnicodeDecodeError):
                # If encoding fails, remove invalid characters
                # Replace surrogates with replacement character
                cleaned = value.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                return cleaned
        elif isinstance(value, dict):
            return {k: self._clean_string_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._clean_string_value(item) for item in value]
        else:
            # For other types (int, float, bool, etc.), return as-is
            return value
    
    def _clean_coupon_fields(self, coupon: Dict) -> Dict:
        """
        Remove duplicate fields from coupon that should not be in coupons section.
        
        Args:
            coupon: Coupon dictionary
            
        Returns:
            Cleaned coupon dictionary
        """
        # Fields to remove from coupons (these are duplicated and moved to amortizations)
        fields_to_remove = ["isin", "name", "issuevalue", "primary_boardid", "secid"]
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

