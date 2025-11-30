from pathlib import Path
from typing import Dict, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

import orjson

from app.services.data_loader import get_data_loader


class EmitentService:
    """Service for managing emitent data from MOEX API"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.emitent_file = data_dir / "bonds_emitent.json"
        self._emitent_cache: Optional[Dict[str, Dict]] = None
    
    def _load_emitent_data(self) -> Dict[str, Dict]:
        """Load emitent data from JSON file"""
        if self._emitent_cache is not None:
            return self._emitent_cache
        
        if not self.emitent_file.exists():
            # Create empty file if it doesn't exist
            self._emitent_cache = {}
            self._save_emitent_data()
            return self._emitent_cache
        
        try:
            with open(self.emitent_file, 'rb') as f:
                self._emitent_cache = orjson.loads(f.read())
        except (orjson.JSONDecodeError, IOError):
            # If file is corrupted or can't be read, start fresh
            self._emitent_cache = {}
            self._save_emitent_data()
        
        return self._emitent_cache
    
    def _save_emitent_data(self):
        """Save emitent data to JSON file"""
        if self._emitent_cache is None:
            self._emitent_cache = {}
        
        serialized = orjson.dumps(
            self._emitent_cache,
            option=orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE,
        )
        self.emitent_file.write_bytes(serialized)
    
    def get_emitent_by_secid(self, secid: str) -> Optional[Dict[str, any]]:
        """
        Get emitent data by SECID from cache.
        
        Returns:
            Full MOEX response data as dict (with all fields from MOEX API)
            or None if not found
        """
        emitent_data = self._load_emitent_data()
        return emitent_data.get(secid)
    
    def extract_required_fields(self, emitent_data: Dict[str, any]) -> Dict[str, any]:
        """
        Extract only required fields from full MOEX response.
        
        Args:
            emitent_data: Full MOEX response data
            
        Returns:
            Dict with keys: is_traded, emitent_title, emitent_inn, type
        """
        return {
            "is_traded": emitent_data.get("is_traded"),
            "emitent_title": emitent_data.get("emitent_title"),
            "emitent_inn": emitent_data.get("emitent_inn"),
            "type": emitent_data.get("type"),
        }
    
    def fetch_emitent_from_moex(self, isin: str) -> Optional[Dict[str, any]]:
        """
        Fetch emitent data from MOEX API by ISIN.
        Saves full MOEX response to file using SECID as key.
        
        Args:
            isin: ISIN code to search for
            
        Returns:
            Full MOEX response data as dict (all fields from MOEX API)
            or None if not found or error occurred
        """
        url = f"https://iss.moex.com/iss/securities.json?q={isin}"
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        
        try:
            with urlopen(request, timeout=30) as response:
                raw_payload = response.read()
        except URLError as exc:
            print(f"Failed to fetch emitent data from MOEX: {exc}")
            return None
        
        try:
            payload = orjson.loads(raw_payload)
        except orjson.JSONDecodeError as exc:
            print(f"Invalid JSON response from MOEX: {exc}")
            return None
        
        # Parse MOEX response structure
        securities = payload.get("securities", {})
        columns = securities.get("columns", [])
        data = securities.get("data", [])
        
        if not data or len(data) == 0:
            return None
        
        # Find the row that matches the ISIN
        isin_idx = columns.index("isin") if "isin" in columns else None
        if isin_idx is None:
            return None
        
        # Find matching row by ISIN
        matching_row = None
        for row in data:
            if len(row) > isin_idx and row[isin_idx] == isin:
                matching_row = row
                break
        
        if matching_row is None:
            return None
        
        # Convert row to dict with all fields from MOEX response
        # This preserves the full JSON structure
        emitent_info = {}
        for idx, column_name in enumerate(columns):
            if idx < len(matching_row):
                emitent_info[column_name] = matching_row[idx]
        
        # Extract SECID from response to use as key
        secid_idx = columns.index("secid") if "secid" in columns else None
        if secid_idx is None or secid_idx >= len(matching_row):
            return None
        
        secid = matching_row[secid_idx]
        if not secid:
            return None
        
        # Save full MOEX response to cache and file using SECID as key
        if self._emitent_cache is None:
            self._emitent_cache = {}
        
        self._emitent_cache[secid] = emitent_info
        self._save_emitent_data()
        
        return emitent_info
    
    def get_or_fetch_emitent(self, secid: str, isin: str) -> Optional[Dict[str, any]]:
        """
        Get emitent data by SECID, fetching from MOEX if not found in cache.
        
        Args:
            secid: Security ID (used as key in cache)
            isin: ISIN code (used for MOEX API request)
            
        Returns:
            Full MOEX response data as dict (all fields from MOEX API)
            or None if not found
        """
        # First try to get from cache by SECID
        emitent_data = self.get_emitent_by_secid(secid)
        if emitent_data is not None:
            return emitent_data
        
        # If not found, fetch from MOEX using ISIN
        emitent_data = self.fetch_emitent_from_moex(isin)
        return emitent_data
    
    async def get_isin_by_secid(self, secid: str) -> Optional[str]:
        """
        Get ISIN code by SECID from bonds data.
        
        Args:
            secid: Security ID
            
        Returns:
            ISIN code or None if not found
        """
        loader = get_data_loader()
        details = await loader.get_bond_details()
        
        if secid not in details:
            return None
        
        bond_data = details[secid]
        securities = bond_data.get("securities", {})
        return securities.get("ISIN")
    
    def _fetch_emitent_from_moex_by_isin(self, isin: str) -> Optional[Dict[str, any]]:
        """
        Fetch emitent data from MOEX API by ISIN without saving.
        
        Args:
            isin: ISIN code to search for
            
        Returns:
            Full MOEX response data as dict (all fields from MOEX API)
            or None if not found or error occurred
        """
        url = f"https://iss.moex.com/iss/securities.json?q={isin}"
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        
        try:
            with urlopen(request, timeout=30) as response:
                raw_payload = response.read()
        except URLError as exc:
            print(f"Failed to fetch emitent data from MOEX: {exc}")
            return None
        
        try:
            payload = orjson.loads(raw_payload)
        except orjson.JSONDecodeError as exc:
            print(f"Invalid JSON response from MOEX: {exc}")
            return None
        
        # Parse MOEX response structure
        securities = payload.get("securities", {})
        columns = securities.get("columns", [])
        data = securities.get("data", [])
        
        if not data or len(data) == 0:
            return None
        
        # Find the row that matches the ISIN
        isin_idx = columns.index("isin") if "isin" in columns else None
        if isin_idx is None:
            return None
        
        # Find matching row by ISIN
        matching_row = None
        for row in data:
            if len(row) > isin_idx and row[isin_idx] == isin:
                matching_row = row
                break
        
        if matching_row is None:
            return None
        
        # Convert row to dict with all fields from MOEX response
        emitent_info = {}
        for idx, column_name in enumerate(columns):
            if idx < len(matching_row):
                emitent_info[column_name] = matching_row[idx]
        
        return emitent_info
    
    def refresh_all_emitents(self, bonds_details: Dict[str, Dict]) -> Dict[str, int]:
        """
        Refresh emitent data for all bonds from bonds.json.
        
        Iterates through all bonds, extracts SECID and ISIN, and fetches
        emitent data from MOEX API for each bond. Saves data using bond SECID as key.
        
        Args:
            bonds_details: Dictionary with SECID as key and bond details as value
            
        Returns:
            Dictionary with refresh statistics: total, updated, errors, skipped
        """
        total_bonds = len(bonds_details)
        updated_count = 0
        error_count = 0
        skipped_count = 0
        
        # Ensure cache is loaded
        self._load_emitent_data()
        
        for secid, bond_data in bonds_details.items():
            try:
                # Extract ISIN from bond data
                securities = bond_data.get("securities", {})
                isin = securities.get("ISIN")
                
                if not isin:
                    print(f"[EMITENT REFRESH] Bond {secid}: Skipping - missing ISIN")
                    skipped_count += 1
                    continue
                
                # Fetch emitent data from MOEX (without saving)
                emitent_data = self._fetch_emitent_from_moex_by_isin(isin)
                if emitent_data is not None:
                    # Save data using bond SECID as key (not MOEX SECID)
                    if self._emitent_cache is None:
                        self._emitent_cache = {}
                    self._emitent_cache[secid] = emitent_data
                    updated_count += 1
                    print(f"[EMITENT REFRESH] Bond {secid}: Successfully updated")
                else:
                    error_count += 1
                    print(f"[EMITENT REFRESH] Bond {secid}: Failed to fetch from MOEX")
                    
            except Exception as exc:
                error_count += 1
                print(f"[EMITENT REFRESH] Bond {secid}: ERROR - {type(exc).__name__}: {str(exc)}")
                continue
        
        # Save all updated data once at the end
        if updated_count > 0:
            self._save_emitent_data()
            print(f"[EMITENT REFRESH] Saved {updated_count} updated emitent records to file")
        
        return {
            "total": total_bonds,
            "updated": updated_count,
            "errors": error_count,
            "skipped": skipped_count
        }


# Singleton instance
_emitent_service: Optional[EmitentService] = None


def init_emitent_service(data_dir: Path):
    """Initialize the emitent service singleton"""
    global _emitent_service
    _emitent_service = EmitentService(data_dir)


def get_emitent_service() -> EmitentService:
    """Get the emitent service instance"""
    if _emitent_service is None:
        raise RuntimeError("Emitent service not initialized")
    return _emitent_service

