from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

import orjson

from app.models.bond import BondListItem
from app.services.coupon_loader import get_coupon_loader


class DataLoader:
    """Handles loading and caching of JSON data files"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self._bonds_cache: Optional[List[BondListItem]] = None
        self._details_cache: Optional[Dict[str, Dict]] = None
        self._columns_cache: Optional[Dict[str, str]] = None
        self._descriptions_cache: Optional[Dict] = None
    
    async def get_bonds(self) -> List[BondListItem]:
        """Load all bonds (cached)"""
        if self._bonds_cache is None:
            self._load_bonds_data()
        return self._bonds_cache
    
    async def get_bond_details(self) -> Dict[str, Dict]:
        """Load detailed bond information (cached)"""
        if self._details_cache is None:
            self._load_bonds_data()
        return self._details_cache
    
    async def get_column_mapping(self) -> Dict[str, str]:
        """Load column name mappings (cached)"""
        if self._columns_cache is None:
            self._columns_cache = self._load_column_mapping()
        return self._columns_cache
    
    async def get_descriptions(self) -> Dict:
        """Load field descriptions (cached)"""
        if self._descriptions_cache is None:
            self._descriptions_cache = self._load_descriptions()
        return self._descriptions_cache
    
    def refresh_bonds_dataset(self, source_url: str) -> Dict[str, int]:
        """
        Download the latest bonds dataset from an external source and refresh caches.
        
        Args:
            source_url: URL to fetch the bonds JSON payload from.
        
        Returns:
            Summary information about the downloaded dataset.
        """
        request = Request(source_url, headers={"User-Agent": "Mozilla/5.0"})
        
        try:
            with urlopen(request, timeout=30) as response:
                raw_payload = response.read()
        except URLError as exc:
            raise RuntimeError(f"Failed to download bonds data: {exc}") from exc
        
        try:
            payload = orjson.loads(raw_payload)
        except orjson.JSONDecodeError as exc:
            raise RuntimeError("Received invalid JSON while refreshing bonds data") from exc
        
        serialized = orjson.dumps(
            payload,
            option=orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE,
        )
        
        bonds_path = self.data_dir / "bonds.json"
        bonds_path.write_bytes(serialized)
        
        # Keep root-level bonds.json in sync for auxiliary tools (e.g., Streamlit app)
        root_bonds_path = self.data_dir.parents[2] / "bonds.json"
        try:
            root_bonds_path.write_bytes(serialized)
        except OSError:
            # If we fail to write the auxiliary file, continue without interrupting the refresh flow
            pass
        
        # Reset caches and reload data from disk
        self._bonds_cache = None
        self._details_cache = None
        self._load_bonds_data()
        
        securities = len(payload.get("securities", {}).get("data", []))
        marketdata = len(payload.get("marketdata", {}).get("data", []))
        yields = len(payload.get("marketdata_yields", {}).get("data", []))
        
        return {
            "securities": securities,
            "marketdata": marketdata,
            "marketdata_yields": yields,
        }
    
    def _load_bonds_data(self):
        """Load bonds.json and parse into structures"""
        bonds_path = self.data_dir / "bonds.json"
        
        with open(bonds_path, 'rb') as f:
            data = orjson.loads(f.read())
        
        # Parse securities section
        securities = data.get("securities", {})
        sec_columns = securities.get("columns", [])
        sec_data = securities.get("data", [])
        
        # Parse marketdata section
        marketdata = data.get("marketdata", {})
        md_columns = marketdata.get("columns", [])
        md_data = marketdata.get("data", [])
        
        # Parse marketdata_yields section
        yields = data.get("marketdata_yields", {})
        yields_columns = yields.get("columns", [])
        yields_data = yields.get("data", [])
        
        # Build lookup dictionaries
        bonds_list = []
        details_map = {}
        
        for row in sec_data:
            bond_dict = dict(zip(sec_columns, row))
            
            # Convert date strings to date objects
            for date_field in ["NEXTCOUPON", "MATDATE", "BUYBACKDATE", "PREVDATE", 
                             "OFFERDATE", "SETTLEDATE", "CALLOPTIONDATE", 
                             "PUTOPTIONDATE", "DATEYIELDFROMISSUER"]:
                if date_field in bond_dict and bond_dict[date_field]:
                    bond_dict[date_field] = self._parse_date(bond_dict[date_field])
            
            # Create list item (simplified) for table view
            try:
                # Extract fields needed for BondListItem
                list_item_data = {
                    "SECID": bond_dict.get("SECID"),
                    "BOARDID": bond_dict.get("BOARDID"),
                    "SHORTNAME": bond_dict.get("SHORTNAME"),
                    "COUPONPERCENT": bond_dict.get("COUPONPERCENT"),
                    "MATDATE": bond_dict.get("MATDATE"),
                    "STATUS": bond_dict.get("STATUS"),
                    "FACEVALUE": bond_dict.get("FACEVALUE"),
                    "PREVPRICE": bond_dict.get("PREVPRICE"),
                    "YIELDATPREVWAPRICE": bond_dict.get("YIELDATPREVWAPRICE"),
                    "NEXTCOUPON": bond_dict.get("NEXTCOUPON"),
                    "BOARDNAME": bond_dict.get("BOARDNAME"),
                    "CALLOPTIONDATE": bond_dict.get("CALLOPTIONDATE"),
                    "PUTOPTIONDATE": bond_dict.get("PUTOPTIONDATE"),
                    "ACCRUEDINT": bond_dict.get("ACCRUEDINT"),
                    "COUPONPERIOD": bond_dict.get("COUPONPERIOD"),
                    "DURATION": None,  # Will be set from marketdata
                    "DURATIONWAPRICE": None,  # Will be set from marketdata_yields
                    "CURRENCYID": bond_dict.get("CURRENCYID"),
                    "FACEUNIT": bond_dict.get("FACEUNIT"),
                    "LISTLEVEL": self._parse_int(bond_dict.get("LISTLEVEL")),
                }
                
                list_item = BondListItem(**list_item_data)
                
                # Try to get coupon value and coupon_type from coupons data if available
                coupon_loader = get_coupon_loader()
                if coupon_loader is not None:
                    nearest_coupon_value = coupon_loader.get_nearest_coupon_value(
                        list_item.SECID
                    )
                    # Set COUPONVALUE with coupon value from coupons data if found
                    if nearest_coupon_value is not None:
                        list_item.COUPONVALUE = nearest_coupon_value
                    
                    # Get coupon_type from coupons data
                    coupon_type = coupon_loader.get_coupon_type(list_item.SECID)
                    if coupon_type is not None:
                        list_item.COUPON_TYPE = coupon_type
                
                bonds_list.append(list_item)
            except Exception as e:
                # Log validation errors but continue
                print(f"Error parsing bond {bond_dict.get('SECID')}: {e}")
                continue
            
            # Store detailed info (raw dict for flexibility)
            secid = bond_dict.get("SECID")
            if secid:
                details_map[secid] = {
                    "securities": bond_dict,
                    "marketdata": {},
                    "marketdata_yields": []
                }
        
        # Add marketdata
        for row in md_data:
            md_dict = dict(zip(md_columns, row))
            secid = md_dict.get("SECID")
            boardid = md_dict.get("BOARDID")
            
            if secid and secid in details_map:
                details_map[secid]["marketdata"] = md_dict
                
                # Add TRADINGSTATUS and DURATION to list items (DURATION ONLY from marketdata)
                # Match by both SECID and BOARDID for accurate mapping
                if secid:
                    matched_bond = None
                    
                    # First, try to find exact match by SECID + BOARDID
                    if boardid:
                        for bond in bonds_list:
                            if bond.SECID == secid and bond.BOARDID == boardid:
                                matched_bond = bond
                                break
                    
                    # If no exact match found, find first bond with matching SECID
                    if matched_bond is None:
                        for bond in bonds_list:
                            if bond.SECID == secid:
                                matched_bond = bond
                                break
                    
                    if matched_bond:
                        if md_dict.get("TRADINGSTATUS"):
                            matched_bond.TRADINGSTATUS = md_dict.get("TRADINGSTATUS")
                        
                        # Load DURATION exclusively from marketdata section
                        duration_raw = md_dict.get("DURATION")
                        
                        # Always try to set DURATION from marketdata if it exists
                        # Check if DURATION key exists in the dictionary (even if value is None/0)
                        if "DURATION" in md_dict:
                            try:
                                if duration_raw is None:
                                    # Explicitly set to None if key exists but value is None
                                    matched_bond.DURATION = None
                                elif isinstance(duration_raw, (int, float)):
                                    # Convert to float (including 0, which is valid)
                                    matched_bond.DURATION = float(duration_raw)
                                elif isinstance(duration_raw, str):
                                    duration_str = duration_raw.strip()
                                    if duration_str and duration_str.lower() not in ('', 'nan', 'none', 'null', 'n/a'):
                                        try:
                                            parsed = float(duration_str)
                                            matched_bond.DURATION = parsed
                                        except (ValueError, TypeError):
                                            matched_bond.DURATION = None
                                    else:
                                        matched_bond.DURATION = None
                                else:
                                    matched_bond.DURATION = None
                            except (ValueError, TypeError, AttributeError) as e:
                                # If parsing fails, set to None
                                matched_bond.DURATION = None
                        # If DURATION key doesn't exist in marketdata, leave bond.DURATION as is (None or previously set)
        
        # Add yields data and extract DURATIONWAPRICE for list items (DURATION is loaded only from marketdata)
        for row in yields_data:
            yields_dict = dict(zip(yields_columns, row))
            secid = yields_dict.get("SECID")
            if secid and secid in details_map:
                details_map[secid]["marketdata_yields"].append(yields_dict)
                
                # Add DURATIONWAPRICE to list item if available (use first yield record)
                # NOTE: DURATION is loaded exclusively from marketdata, not from marketdata_yields
                durationwaprice = yields_dict.get("DURATIONWAPRICE")
                if durationwaprice is not None:
                    for bond in bonds_list:
                        if bond.SECID == secid:
                            if bond.DURATIONWAPRICE is None:
                                bond.DURATIONWAPRICE = durationwaprice
                            break
        
        # Load and add ratings data
        ratings_map = self._load_ratings_map()
        self._add_ratings_to_bonds(bonds_list, ratings_map)
        
        # Also add ratings to details_map for BondDetail
        for secid, rating_info in ratings_map.items():
            if secid in details_map:
                # Add rating to securities section in details_map
                details_map[secid]["securities"]["RATING_AGENCY"] = rating_info["agency"]
                details_map[secid]["securities"]["RATING_LEVEL"] = rating_info["level"]
        
        # Load and add bond types from bonds_emitent.json
        bondtype_map = self._load_bondtype_map()
        self._add_bondtypes_to_bonds(bonds_list, bondtype_map)
        
        # Also add bondtype to details_map for BondDetail
        for secid, bondtype in bondtype_map.items():
            if secid in details_map:
                # Add bondtype to securities section in details_map
                details_map[secid]["securities"]["BONDTYPE"] = bondtype
        
        self._bonds_cache = bonds_list
        self._details_cache = details_map
    
    def _load_column_mapping(self) -> Dict[str, str]:
        """Load columns.json and build field -> display name mapping"""
        columns_path = self.data_dir / "columns.json"
        
        with open(columns_path, 'rb') as f:
            data = orjson.loads(f.read())
        
        mapping = {}
        
        for section_name in ["securities", "marketdata", "marketdata_yields"]:
            section = data.get(section_name, {})
            columns = section.get("columns", [])
            rows = section.get("data", [])
            
            try:
                name_idx = columns.index("name")
                short_title_idx = columns.index("short_title")
            except ValueError:
                continue
            
            for row in rows:
                if len(row) > max(name_idx, short_title_idx):
                    field_name = row[name_idx]
                    display_name = row[short_title_idx]
                    if field_name and display_name:
                        mapping[str(field_name)] = str(display_name)
        
        return mapping
    
    def _load_descriptions(self) -> Dict:
        """Load describe.json"""
        desc_path = self.data_dir / "describe.json"
        
        with open(desc_path, 'rb') as f:
            return orjson.loads(f.read())
    
    def clear_bonds_cache(self):
        """Clear bonds cache to force reload with updated coupon data"""
        self._bonds_cache = None
        self._details_cache = None
    
    def clear_metadata_cache(self):
        """Clear metadata cache (columns and descriptions) to force reload"""
        self._columns_cache = None
        self._descriptions_cache = None
    
    @staticmethod
    def _parse_int(value: any) -> Optional[int]:
        """Parse integer value from various formats"""
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except (ValueError, TypeError):
                return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    
    def _load_ratings_map(self) -> Dict[str, Dict[str, Optional[str]]]:
        """Load ratings from bonds_rating.json and return as a map"""
        ratings_path = self.data_dir / "bonds_rating.json"
        ratings_map = {}
        
        if not ratings_path.exists():
            print(f"[DATA LOADER] Ratings file not found: {ratings_path}, skipping ratings")
            return ratings_map
        
        try:
            with open(ratings_path, 'rb') as f:
                ratings_data = orjson.loads(f.read())
            
            print(f"[DATA LOADER] Loaded ratings for {len(ratings_data)} bonds")
            
            # Create a lookup map for quick access
            for secid, rating_entry in ratings_data.items():
                if isinstance(rating_entry, dict):
                    # New format: {last_updated: "...", ratings: [...]}
                    if "ratings" in rating_entry:
                        ratings_list = rating_entry["ratings"]
                        if isinstance(ratings_list, list) and len(ratings_list) > 0:
                            # Get first rating (most recent or primary)
                            first_rating = ratings_list[0]
                            if isinstance(first_rating, dict):
                                agency_name = first_rating.get("agency_name_short_ru", "")
                                rating_level = first_rating.get("rating_level_name_short_ru", "")
                                # Only add if rating is not empty
                                if agency_name and agency_name.strip():
                                    ratings_map[secid] = {
                                        "agency": agency_name.strip(),
                                        "level": rating_level.strip() if rating_level else None
                                    }
                    # Old format: {cci_rating_securities: [...]}
                    elif "cci_rating_securities" in rating_entry:
                        ratings_list = rating_entry["cci_rating_securities"]
                        if isinstance(ratings_list, list) and len(ratings_list) > 0:
                            first_rating = ratings_list[0]
                            if isinstance(first_rating, dict):
                                agency_name = first_rating.get("agency_name_short_ru", "")
                                rating_level = first_rating.get("rating_level_name_short_ru", "")
                                if agency_name and agency_name.strip():
                                    ratings_map[secid] = {
                                        "agency": agency_name.strip(),
                                        "level": rating_level.strip() if rating_level else None
                                    }
                # Old format: direct array
                elif isinstance(rating_entry, list) and len(rating_entry) > 0:
                    first_rating = rating_entry[0]
                    if isinstance(first_rating, dict):
                        agency_name = first_rating.get("agency_name_short_ru", "")
                        rating_level = first_rating.get("rating_level_name_short_ru", "")
                        if agency_name and agency_name.strip():
                            ratings_map[secid] = {
                                "agency": agency_name.strip(),
                                "level": rating_level.strip() if rating_level else None
                            }
            
        except (orjson.JSONDecodeError, IOError) as exc:
            print(f"[DATA LOADER] ERROR: Failed to load ratings file - {type(exc).__name__}: {str(exc)}")
            # Continue without ratings if file is corrupted or can't be read
        
        return ratings_map
    
    def _add_ratings_to_bonds(self, bonds_list: List[BondListItem], ratings_map: Dict[str, Dict[str, Optional[str]]]):
        """Add ratings from ratings_map to bonds"""
        ratings_added = 0
        for bond in bonds_list:
            if bond.SECID in ratings_map:
                rating_info = ratings_map[bond.SECID]
                bond.RATING_AGENCY = rating_info["agency"]
                bond.RATING_LEVEL = rating_info["level"]
                ratings_added += 1
        
        print(f"[DATA LOADER] Added ratings to {ratings_added} bonds")
    
    def _load_bondtype_map(self) -> Dict[str, Optional[str]]:
        """Load bond types from bonds_emitent.json and return as a map"""
        emitent_path = self.data_dir / "bonds_emitent.json"
        bondtype_map = {}
        
        if not emitent_path.exists():
            print(f"[DATA LOADER] Emitent file not found: {emitent_path}, skipping bond types")
            return bondtype_map
        
        try:
            with open(emitent_path, 'rb') as f:
                emitent_data = orjson.loads(f.read())
            
            print(f"[DATA LOADER] Loaded emitent data for {len(emitent_data)} bonds")
            
            # Create a lookup map for quick access
            for secid, emitent_entry in emitent_data.items():
                if isinstance(emitent_entry, dict):
                    bondtype = emitent_entry.get("type")
                    if bondtype and isinstance(bondtype, str):
                        bondtype_map[secid] = bondtype.strip()
            
            print(f"[DATA LOADER] Extracted bond types for {len(bondtype_map)} bonds")
            
        except (orjson.JSONDecodeError, IOError) as exc:
            print(f"[DATA LOADER] ERROR: Failed to load emitent file - {type(exc).__name__}: {str(exc)}")
            # Continue without bond types if file is corrupted or can't be read
        
        return bondtype_map
    
    def _add_bondtypes_to_bonds(self, bonds_list: List[BondListItem], bondtype_map: Dict[str, Optional[str]]):
        """Add bond types from bondtype_map to bonds"""
        bondtypes_added = 0
        for bond in bonds_list:
            if bond.SECID in bondtype_map:
                bond.BONDTYPE = bondtype_map[bond.SECID]
                bondtypes_added += 1
        
        print(f"[DATA LOADER] Added bond types to {bondtypes_added} bonds")
    
    @staticmethod
    def _parse_date(date_str: str) -> Optional[date]:
        """Parse date string from various formats"""
        if not date_str or date_str == "0000-00-00":
            return None
        
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None


# Singleton instance
_data_loader: Optional[DataLoader] = None


def init_data_loader(data_dir: Path):
    """Initialize the data loader singleton"""
    global _data_loader
    _data_loader = DataLoader(data_dir)


def get_data_loader() -> DataLoader:
    """Get the data loader instance"""
    if _data_loader is None:
        raise RuntimeError("Data loader not initialized")
    return _data_loader
