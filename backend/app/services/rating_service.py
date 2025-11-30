import re
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.error import URLError

import orjson
import requests


class RatingService:
    """Service for handling bond rating data from MOEX website"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.rating_file = data_dir / "bonds_rating.json"
        self._rating_cache: Optional[Dict[str, Dict]] = None
    
    def _load_rating_data(self) -> Dict[str, Dict]:
        """Load rating data from JSON file"""
        if self._rating_cache is not None:
            print(f"[RATING SERVICE] Using cached rating data (in-memory cache)")
            return self._rating_cache
        
        print(f"[RATING SERVICE] Loading rating data from file: {self.rating_file}")
        
        if not self.rating_file.exists():
            print(f"[RATING SERVICE] File does not exist, creating empty file")
            # Create empty file if it doesn't exist
            self._rating_cache = {}
            self._save_rating_data()
            print(f"[RATING SERVICE] Empty file created")
            return self._rating_cache
        
        try:
            file_size = self.rating_file.stat().st_size
            print(f"[RATING SERVICE] File exists, size: {file_size} bytes")
            
            with open(self.rating_file, 'rb') as f:
                self._rating_cache = orjson.loads(f.read())
            
            cached_count = len(self._rating_cache)
            print(f"[RATING SERVICE] Successfully loaded {cached_count} rating entries from file")
        except (orjson.JSONDecodeError, IOError) as exc:
            print(f"[RATING SERVICE] ERROR: Failed to load file - {type(exc).__name__}: {str(exc)}")
            print(f"[RATING SERVICE] Creating fresh empty file")
            # If file is corrupted or can't be read, start fresh
            self._rating_cache = {}
            self._save_rating_data()
        
        return self._rating_cache
    
    def _filter_rating_keys(self, rating_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter rating item to keep only required keys.
        
        Args:
            rating_item: Rating dictionary with all fields
            
        Returns:
            Filtered dictionary with only required keys
        """
        required_keys = [
            "agency_id",
            "agency_name_short_ru",
            "rating_level_id",
            "rating_date",
            "rating_level_name_short_ru"
        ]
        
        return {key: rating_item.get(key) for key in required_keys if key in rating_item}
    
    def _create_empty_rating(self) -> List[Dict[str, Any]]:
        """
        Create empty rating entry with default values.
        
        Returns:
            List with one empty rating dictionary
        """
        return [
            {
                "agency_id": 0,
                "agency_name_short_ru": "",
                "rating_level_id": 0,
                "rating_date": "",
                "rating_level_name_short_ru": ""
            }
        ]
    
    def _is_data_stale(self, last_updated: str) -> bool:
        """
        Check if data is older than one month.
        
        Args:
            last_updated: Date string in ISO format (YYYY-MM-DD)
            
        Returns:
            True if data is older than one month, False otherwise
        """
        try:
            last_date = date.fromisoformat(last_updated)
            today = date.today()
            days_diff = (today - last_date).days
            is_stale = days_diff > 30  # More than 30 days (one month)
            
            print(f"[RATING SERVICE] Data age check: last_updated={last_updated}, days_diff={days_diff}, is_stale={is_stale}")
            return is_stale
        except (ValueError, TypeError) as exc:
            print(f"[RATING SERVICE] ERROR: Could not parse last_updated date '{last_updated}': {exc}")
            # If date is invalid, consider data stale to force update
            return True
    
    def _save_rating_data(self):
        """Save rating data to JSON file"""
        if self._rating_cache is None:
            self._rating_cache = {}
        
        entries_count = len(self._rating_cache)
        print(f"[RATING SERVICE] Saving {entries_count} rating entries to file: {self.rating_file}")
        
        serialized = orjson.dumps(
            self._rating_cache,
            option=orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE,
        )
        
        file_size = len(serialized)
        self.rating_file.write_bytes(serialized)
        print(f"[RATING SERVICE] File saved successfully, size: {file_size} bytes")
    
    def _extract_emitent_id_from_html(self, html_content: str) -> Optional[str]:
        """
        Extract emitent ID from HTML page by finding emidocs.aspx?id=XXXX link.
        
        Args:
            html_content: HTML content from MOEX page
            
        Returns:
            Emitent ID (XXXX) or None if not found
        """
        print(f"[RATING SERVICE] Searching for emitent ID in HTML (emidocs.aspx?id=...)")
        
        # Pattern to find emidocs.aspx?id=XXXX
        # This can appear in various formats:
        # - emidocs.aspx?id=12345
        # - /ru/emidocs.aspx?id=12345
        # - https://www.moex.com/ru/emidocs.aspx?id=12345
        # - href="emidocs.aspx?id=12345"
        
        patterns = [
            # Pattern 1: Direct emidocs.aspx?id=XXXX
            r'emidocs\.aspx\?id=(\d+)',
            # Pattern 2: In href attribute
            r'href=["\']([^"\']*emidocs\.aspx\?id=(\d+))["\']',
            # Pattern 3: Full URL
            r'https?://[^"\s]+emidocs\.aspx\?id=(\d+)',
        ]
        
        for pattern_idx, pattern in enumerate(patterns):
            print(f"[RATING SERVICE] Trying pattern {pattern_idx + 1} for emitent ID")
            matches = list(re.finditer(pattern, html_content, re.IGNORECASE))
            
            for match in matches:
                # Extract ID from match groups
                emitent_id = None
                if match.lastindex:
                    # Use the last group which should be the ID
                    emitent_id = match.group(match.lastindex)
                else:
                    # Single group pattern
                    emitent_id = match.group(1)
                
                if emitent_id and emitent_id.isdigit():
                    print(f"[RATING SERVICE] Found emitent ID: {emitent_id}")
                    return emitent_id
        
        print(f"[RATING SERVICE] ERROR: Could not find emitent ID in HTML")
        return None
    
    def _fetch_rating_via_api(self, secid: str, emitent_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch rating data from MOEX API using emitent ID.
        
        Args:
            secid: Security ID
            emitent_id: Emitent ID extracted from HTML
            
        Returns:
            List of rating dictionaries or None if not found
        """
        # Construct API URL
        api_url = (
            f"https://iss.moex.com/iss/cci/rating/companies/ecbd_{emitent_id}/"
            f"securities/isin_{secid}.json?iss.json=extended&iss.meta=off"
        )
        
        print(f"[RATING SERVICE] Fetching rating via MOEX API")
        print(f"[RATING SERVICE] API URL: {api_url}")
        
        try:
            print(f"[RATING SERVICE] Sending HTTP GET request to API...")
            response = requests.get(
                api_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=30
            )
            
            print(f"[RATING SERVICE] API response: status_code={response.status_code}")
            response.raise_for_status()
            
            # Parse JSON response
            try:
                json_data = response.json()
                print(f"[RATING SERVICE] JSON parsed successfully, type: {type(json_data).__name__}")
                
                # Handle different response formats and extract ratings list
                ratings_list = []
                
                # Format 1: List that may contain charsetinfo and cci_rating_securities
                if isinstance(json_data, list):
                    print(f"[RATING SERVICE] Response is a list with {len(json_data)} elements")
                    # Search for element containing cci_rating_securities
                    for item in json_data:
                        if isinstance(item, dict):
                            # Check if this item has cci_rating_securities
                            if "cci_rating_securities" in item:
                                ratings_data = item["cci_rating_securities"]
                                if isinstance(ratings_data, list):
                                    ratings_list = ratings_data
                                    print(f"[RATING SERVICE] Found cci_rating_securities in list element: {len(ratings_list)} entries")
                                    break
                            # Skip charsetinfo objects
                            elif "charsetinfo" in item:
                                print(f"[RATING SERVICE] Skipping charsetinfo element")
                                continue
                    
                    # If not found in nested structure, treat as direct list of ratings
                    if not ratings_list:
                        # Check if all items are rating objects (have agency_id or similar)
                        potential_ratings = [item for item in json_data if isinstance(item, dict) and "agency_id" in item]
                        if potential_ratings:
                            ratings_list = potential_ratings
                            print(f"[RATING SERVICE] Found {len(ratings_list)} rating entries (direct list format)")
                
                # Format 2: Dict with cci_rating_securities key
                elif isinstance(json_data, dict):
                    # Check for direct cci_rating_securities array
                    if "cci_rating_securities" in json_data:
                        ratings_data = json_data["cci_rating_securities"]
                        
                        # If it's a dict with columns/data structure (MOEX format)
                        if isinstance(ratings_data, dict) and "data" in ratings_data:
                            columns = ratings_data.get("columns", [])
                            data_rows = ratings_data.get("data", [])
                            
                            print(f"[RATING SERVICE] Found MOEX format: {len(columns)} columns, {len(data_rows)} rows")
                            
                            # Convert to list of dicts
                            for row in data_rows:
                                if len(row) == len(columns):
                                    rating_dict = dict(zip(columns, row))
                                    ratings_list.append(rating_dict)
                            
                            print(f"[RATING SERVICE] Converted to {len(ratings_list)} rating entries")
                        
                        # If it's already a list
                        elif isinstance(ratings_data, list):
                            ratings_list = ratings_data
                            print(f"[RATING SERVICE] Found {len(ratings_list)} rating entries")
                
                # Format 3: Nested structure - search recursively
                if not ratings_list and isinstance(json_data, dict):
                    print(f"[RATING SERVICE] Searching recursively in JSON structure...")
                    for key, value in json_data.items():
                        if isinstance(value, dict) and "cci_rating_securities" in value:
                            ratings_data = value["cci_rating_securities"]
                            if isinstance(ratings_data, dict) and "data" in ratings_data:
                                columns = ratings_data.get("columns", [])
                                data_rows = ratings_data.get("data", [])
                                
                                for row in data_rows:
                                    if len(row) == len(columns):
                                        rating_dict = dict(zip(columns, row))
                                        ratings_list.append(rating_dict)
                                
                                print(f"[RATING SERVICE] Found in nested structure: {len(ratings_list)} rating entries")
                                break
                            elif isinstance(ratings_data, list):
                                ratings_list = ratings_data
                                print(f"[RATING SERVICE] Found in nested structure: {len(ratings_list)} rating entries")
                                break
                
                # Filter ratings to keep only required keys
                if ratings_list:
                    print(f"[RATING SERVICE] Processing {len(ratings_list)} rating entries from API")
                    
                    # Filter each rating and collect valid ones
                    filtered_ratings = []
                    for idx, rating in enumerate(ratings_list):
                        if not isinstance(rating, dict):
                            print(f"[RATING SERVICE] WARNING: Rating entry {idx} is not a dict, skipping")
                            continue
                        
                        filtered = self._filter_rating_keys(rating)
                        # Only add non-empty dictionaries
                        if filtered and len(filtered) > 0:
                            filtered_ratings.append(filtered)
                            agency_name = filtered.get("agency_name_short_ru", "unknown")
                            print(f"[RATING SERVICE] Rating {idx + 1}/{len(ratings_list)}: {agency_name} - filtered successfully")
                        else:
                            print(f"[RATING SERVICE] WARNING: Rating entry {idx} filtered to empty, skipping")
                    
                    print(f"[RATING SERVICE] Successfully filtered {len(filtered_ratings)} rating entries (from {len(ratings_list)} total)")
                    
                    if not filtered_ratings:
                        print(f"[RATING SERVICE] WARNING: All ratings were filtered out, returning empty rating")
                        return self._create_empty_rating()
                    
                    # Return just the list, not wrapped in cci_rating_securities
                    return filtered_ratings
            
            except json.JSONDecodeError as exc:
                print(f"[RATING SERVICE] ERROR: Failed to parse JSON response - {str(exc)}")
                raise RuntimeError(f"Invalid JSON response from API: {exc}") from exc
            
        except requests.RequestException as exc:
            error_type = type(exc).__name__
            print(f"[RATING SERVICE] ERROR: API request failed - {error_type}: {str(exc)}")
            raise RuntimeError(f"Failed to fetch rating from API for {secid}: {exc}") from exc
        
        print(f"[RATING SERVICE] ERROR: Could not extract cci_rating_securities from API response")
        return None
    
    def _fetch_rating_from_moex(self, secid: str, boardid: str) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch rating data from MOEX website by SECID and BOARDID.
        
        Strategy:
        1. Load HTML page
        2. Extract emitent ID from HTML (emidocs.aspx?id=XXXX)
        3. Fetch rating data via MOEX API using emitent ID
        
        Args:
            secid: Security ID
            boardid: Board ID
            
        Returns:
            List of rating dictionaries or None if not found
        """
        url = f"https://www.moex.com/ru/issue.aspx?board={boardid}&code={secid}"
        print(f"[RATING SERVICE] Fetching rating data from MOEX")
        print(f"[RATING SERVICE] URL: {url}")
        print(f"[RATING SERVICE] SECID: {secid}, BOARDID: {boardid}")
        
        # Step 1: Load HTML page
        try:
            print(f"[RATING SERVICE] Step 1: Loading HTML page...")
            response = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=30
            )
            
            print(f"[RATING SERVICE] HTML response: status_code={response.status_code}")
            response.raise_for_status()
            
            html_content = response.text
            html_size = len(html_content)
            print(f"[RATING SERVICE] HTML content size: {html_size} bytes")
            
        except requests.RequestException as exc:
            error_type = type(exc).__name__
            print(f"[RATING SERVICE] ERROR: HTTP request failed - {error_type}: {str(exc)}")
            raise RuntimeError(f"Failed to download rating data for {secid}: {exc}") from exc
        except URLError as exc:
            print(f"[RATING SERVICE] ERROR: URL error - {str(exc)}")
            raise RuntimeError(f"Failed to download rating data for {secid}: {exc}") from exc
        
        # Step 2: Extract emitent ID from HTML
        print(f"[RATING SERVICE] Step 2: Extracting emitent ID from HTML...")
        emitent_id = self._extract_emitent_id_from_html(html_content)
        
        if not emitent_id:
            print(f"[RATING SERVICE] WARNING: Could not find emitent ID in HTML for {secid}")
            print(f"[RATING SERVICE] No rating data available for this bond, returning empty rating")
            # Return empty rating instead of raising error
            return self._create_empty_rating()
        
        # Step 3: Fetch rating via API
        print(f"[RATING SERVICE] Step 3: Fetching rating via API...")
        rating_data = self._fetch_rating_via_api(secid, emitent_id)
        
        if rating_data is None:
            print(f"[RATING SERVICE] WARNING: Could not extract rating data from API response for {secid}")
            print(f"[RATING SERVICE] Returning empty rating")
            return self._create_empty_rating()
        
        print(f"[RATING SERVICE] Successfully fetched rating data via API")
        return rating_data
    
    def get_rating(self, secid: str, boardid: str, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Get rating data for a specific bond by SECID and BOARDID.
        
        First checks local file. If force_refresh is True, fetches from MOEX website
        when data is missing or stale. If force_refresh is False, only returns cached data.
        
        Args:
            secid: Security ID
            boardid: Board ID
            force_refresh: If True, fetch from MOEX when data is missing or stale.
                          If False, only return cached data (no network requests).
            
        Returns:
            List of rating dictionaries with keys: agency_id, agency_name_short_ru,
            rating_level_id, rating_date, rating_level_name_short_ru
            
        Raises:
            RuntimeError: If data cannot be fetched or parsed (only when force_refresh=True)
        """
        print(f"[RATING SERVICE] Getting rating for SECID={secid}, BOARDID={boardid}, force_refresh={force_refresh}")
        
        rating_data = self._load_rating_data()
        
        # Check if data exists in local file
        if secid in rating_data:
            cached_entry = rating_data[secid]
            # Handle different formats
            if isinstance(cached_entry, dict):
                # New format with last_updated and ratings
                if "ratings" in cached_entry:
                    ratings_list = cached_entry["ratings"]
                    last_updated = cached_entry.get("last_updated", "")
                    ratings_count = len(ratings_list) if isinstance(ratings_list, list) else 0
                    print(f"[RATING SERVICE] Found cached data for {secid} with {ratings_count} rating entries (last updated: {last_updated})")
                    
                    # Check if data needs to be refreshed (older than one month)
                    if last_updated and not self._is_data_stale(last_updated):
                        print(f"[RATING SERVICE] Cached data is fresh, returning cached data (no MOEX fetch needed)")
                        # Ensure we return a list
                        if not isinstance(ratings_list, list):
                            print(f"[RATING SERVICE] WARNING: ratings_list is not a list, converting...")
                            ratings_list = []
                        return ratings_list
                    else:
                        if force_refresh:
                            print(f"[RATING SERVICE] Cached data is stale (older than one month), fetching fresh data from MOEX...")
                            # Continue to fetch fresh data below
                        else:
                            print(f"[RATING SERVICE] Cached data is stale, but force_refresh=False, returning cached data anyway")
                            # Ensure we return a list
                            if not isinstance(ratings_list, list):
                                print(f"[RATING SERVICE] WARNING: ratings_list is not a list, converting...")
                                ratings_list = []
                            return ratings_list
                # Old format with cci_rating_securities (no date, consider stale)
                elif "cci_rating_securities" in cached_entry:
                    ratings_list = cached_entry.get("cci_rating_securities", [])
                    ratings_count = len(ratings_list) if isinstance(ratings_list, list) else 0
                    print(f"[RATING SERVICE] Found cached data for {secid} with {ratings_count} rating entries (old format, no date)")
                    if force_refresh:
                        print(f"[RATING SERVICE] force_refresh=True, fetching fresh data from MOEX...")
                        # Continue to fetch fresh data below
                    else:
                        print(f"[RATING SERVICE] force_refresh=False, returning cached data (old format)")
                        # Ensure we return a list
                        if not isinstance(ratings_list, list):
                            print(f"[RATING SERVICE] WARNING: ratings_list is not a list, converting...")
                            ratings_list = []
                        return ratings_list
            # Old format: direct array (no date, consider stale)
            elif isinstance(cached_entry, list):
                ratings_count = len(cached_entry)
                print(f"[RATING SERVICE] Found cached data for {secid} with {ratings_count} rating entries (old format - direct array, no date)")
                if force_refresh:
                    print(f"[RATING SERVICE] force_refresh=True, fetching fresh data from MOEX...")
                    # Continue to fetch fresh data below
                else:
                    print(f"[RATING SERVICE] force_refresh=False, returning cached data (old format)")
                    # Ensure we return a list
                    if not isinstance(cached_entry, list):
                        print(f"[RATING SERVICE] WARNING: cached_entry is not a list, converting...")
                        cached_entry = []
                    return cached_entry
        
        # No cached data found or force_refresh is True
        if not force_refresh:
            print(f"[RATING SERVICE] No cached data found for {secid}, but force_refresh=False, returning empty rating")
            return self._create_empty_rating()
        
        print(f"[RATING SERVICE] No cached data found for {secid}, fetching from MOEX...")
        
        # Fetch from MOEX website
        try:
            fresh_data = self._fetch_rating_from_moex(secid, boardid)
            print(f"[RATING SERVICE] Successfully processed data from MOEX")
        except Exception as exc:
            error_type = type(exc).__name__
            print(f"[RATING SERVICE] ERROR: Failed to fetch from MOEX - {error_type}: {str(exc)}")
            # On error, save empty rating instead of raising exception
            print(f"[RATING SERVICE] Saving empty rating due to error")
            fresh_data = self._create_empty_rating()
        
        # Ensure we have data (should always be the case now)
        if fresh_data is None:
            print(f"[RATING SERVICE] WARNING: No data received, using empty rating")
            fresh_data = self._create_empty_rating()
        
        # Save to file (save with last_updated date)
        print(f"[RATING SERVICE] Saving data to cache...")
        if self._rating_cache is None:
            self._rating_cache = {}
        
        # Save with last_updated date
        today = date.today().isoformat()
        self._rating_cache[secid] = {
            "last_updated": today,
            "ratings": fresh_data
        }
        print(f"[RATING SERVICE] Saving with last_updated date: {today}")
        self._save_rating_data()
        
        print(f"[RATING SERVICE] Data saved successfully, returning to caller")
        # Ensure we return a list
        if not isinstance(fresh_data, list):
            print(f"[RATING SERVICE] WARNING: fresh_data is not a list, converting...")
            fresh_data = []
        return fresh_data


# Singleton instance
_rating_service: Optional[RatingService] = None


def init_rating_service(data_dir: Path):
    """Initialize the rating service singleton"""
    global _rating_service
    _rating_service = RatingService(data_dir)


def get_rating_service() -> RatingService:
    """Get the rating service instance"""
    if _rating_service is None:
        raise RuntimeError("Rating service not initialized")
    return _rating_service

