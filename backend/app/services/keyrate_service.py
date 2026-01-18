"""
Service for loading and managing Central Bank of Russia (CBR) key rate data.

Loads key rate data from CBR HTML page, parses it using pandas.read_html,
and saves to JSON file in data directory.
"""
import json
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlencode

import pandas as pd
import requests

from app.utils.logger import get_data_update_logger


class KeyRateService:
    """Service for handling CBR key rate data"""
    
    # Base URL for CBR key rate page
    CBR_KEYRATE_URL = "https://www.cbr.ru/hd_base/keyrate/"
    
    # Default start date if file doesn't exist or is corrupted
    DEFAULT_START_DATE = date(2013, 9, 17)  # 17.09.2013
    
    # JSON file name
    KEYRATE_FILENAME = "keyrate.json"
    
    def __init__(self, data_dir: Path):
        """
        Initialize KeyRateService.
        
        Args:
            data_dir: Path to data directory where JSON file will be stored
        """
        self.data_dir = data_dir
        self.keyrate_file = data_dir / self.KEYRATE_FILENAME
        self.logger = get_data_update_logger()
    
    def _load_keyrate_data(self) -> Dict[str, float]:
        """
        Load key rate data from JSON file.
        
        Returns:
            Dictionary with date (YYYY-MM-DD) as key and rate (float) as value.
            Empty dict if file doesn't exist or is corrupted.
        """
        self.logger.info(f"[KEYRATE SERVICE] Loading key rate data from file: {self.keyrate_file}")
        
        if not self.keyrate_file.exists():
            self.logger.info("[KEYRATE SERVICE] File does not exist, returning empty dict")
            return {}
        
        try:
            file_size = self.keyrate_file.stat().st_size
            self.logger.info(f"[KEYRATE SERVICE] File exists, size: {file_size} bytes")
            
            with open(self.keyrate_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, dict):
                self.logger.warning("[KEYRATE SERVICE] Data is not a dict, returning empty dict")
                return {}
            
            entries_count = len(data)
            self.logger.info(f"[KEYRATE SERVICE] Successfully loaded {entries_count} key rate entries from file")
            return data
            
        except (json.JSONDecodeError, IOError, OSError) as exc:
            self.logger.error(
                f"[KEYRATE SERVICE] ERROR: Failed to load file - {type(exc).__name__}: {str(exc)}"
            )
            return {}
    
    def _save_keyrate_data(self, data: Dict[str, float]):
        """
        Save key rate data to JSON file.
        
        Args:
            data: Dictionary with date (YYYY-MM-DD) as key and rate (float) as value
        """
        entries_count = len(data)
        self.logger.info(
            f"[KEYRATE SERVICE] Saving {entries_count} key rate entries to file: {self.keyrate_file}"
        )
        
        # Sort by date for better readability
        sorted_data = dict(sorted(data.items()))
        
        with open(self.keyrate_file, 'w', encoding='utf-8') as f:
            json.dump(sorted_data, f, indent=2, ensure_ascii=False)
        
        file_size = self.keyrate_file.stat().st_size
        self.logger.info(f"[KEYRATE SERVICE] File saved successfully, size: {file_size} bytes")
    
    def _get_last_date_in_data(self) -> Optional[date]:
        """
        Get the last (most recent) date from existing data.
        
        Returns:
            Last date as date object, or None if no data exists
        """
        data = self._load_keyrate_data()
        
        if not data:
            return None
        
        # Get all dates and find the latest one
        dates = []
        for date_str in data.keys():
            try:
                parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                dates.append(parsed_date)
            except ValueError:
                self.logger.warning(
                    f"[KEYRATE SERVICE] Skipping invalid date format in data: {date_str}"
                )
                continue
        
        if not dates:
            return None
        
        last_date = max(dates)
        self.logger.info(
            f"[KEYRATE SERVICE] Last date in existing data: {last_date.isoformat()}"
        )
        return last_date
    
    def _build_url(self, date_from: date, date_to: date) -> str:
        """
        Build CBR key rate URL with query parameters.
        
        Args:
            date_from: Start date (format: DD.MM.YYYY)
            date_to: End date (format: DD.MM.YYYY)
        
        Returns:
            Complete URL with query parameters
        """
        params = {
            "UniDbQuery.Posted": "True",
            "UniDbQuery.From": date_from.strftime("%d.%m.%Y"),
            "UniDbQuery.To": date_to.strftime("%d.%m.%Y"),
        }
        
        url = f"{self.CBR_KEYRATE_URL}?{urlencode(params)}"
        self.logger.info(f"[KEYRATE SERVICE] Built URL: {url}")
        return url
    
    def _fetch_and_parse_keyrate(self, date_from: date, date_to: date) -> Dict[str, float]:
        """
        Fetch key rate data from CBR HTML page and parse it.
        
        Args:
            date_from: Start date for data range
            date_to: End date for data range
        
        Returns:
            Dictionary with date (YYYY-MM-DD) as key and rate (float) as value
        
        Raises:
            ValueError: If table structure doesn't match expected format
            requests.RequestException: If HTTP request fails
            Exception: For other parsing errors
        """
        url = self._build_url(date_from, date_to)
        
        self.logger.info(f"[KEYRATE SERVICE] Fetching key rate data from CBR...")
        
        try:
            # Fetch HTML page
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            self.logger.info(
                f"[KEYRATE SERVICE] HTTP response status: {response.status_code}, "
                f"content length: {len(response.content)} bytes"
            )
            
        except requests.RequestException as exc:
            self.logger.error(
                f"[KEYRATE SERVICE] ERROR: Failed to fetch page - {type(exc).__name__}: {str(exc)}"
            )
            raise RuntimeError(f"Failed to fetch key rate page: {str(exc)}") from exc
        
        # Parse HTML tables using pandas
        self.logger.info("[KEYRATE SERVICE] Parsing HTML tables with pandas.read_html...")
        
        try:
            tables = pd.read_html(
                response.text,
                decimal=",",
                thousands=" ",
            )
            
            if not tables:
                self.logger.error("[KEYRATE SERVICE] ERROR: No tables found in HTML")
                raise ValueError("No tables found on the page")
            
            self.logger.info(f"[KEYRATE SERVICE] Found {len(tables)} table(s), using first table")
            
        except Exception as exc:
            self.logger.error(
                f"[KEYRATE SERVICE] ERROR: Failed to parse HTML - {type(exc).__name__}: {str(exc)}"
            )
            raise RuntimeError(f"Failed to parse HTML tables: {str(exc)}") from exc
        
        # Get first table
        df = tables[0]
        
        self.logger.info(f"[KEYRATE SERVICE] Table shape: {df.shape}, columns: {list(df.columns)}")
        
        # Normalize column names (lowercase, strip whitespace)
        df.columns = df.columns.str.lower().str.strip()
        
        # Check for required columns
        required_columns = {"дата", "ставка"}
        actual_columns = set(df.columns)
        
        if not required_columns.issubset(actual_columns):
            missing = required_columns - actual_columns
            error_msg = (
                f"Table columns don't match expected format. "
                f"Required columns: {required_columns}, "
                f"Actual columns: {actual_columns}, "
                f"Missing: {missing}"
            )
            self.logger.error(f"[KEYRATE SERVICE] ERROR: {error_msg}")
            raise ValueError(error_msg)
        
        # Rename columns to more convenient names
        df = df.rename(columns={"дата": "date", "ставка": "key_rate"})
        
        # Convert date column to datetime
        try:
            df["date"] = pd.to_datetime(df["date"], format="%d.%m.%Y")
        except Exception as exc:
            self.logger.error(
                f"[KEYRATE SERVICE] ERROR: Failed to parse dates - {type(exc).__name__}: {str(exc)}"
            )
            raise ValueError(f"Failed to parse date column: {str(exc)}") from exc
        
        # Convert key_rate to float (handles comma as decimal separator)
        try:
            df["key_rate"] = pd.to_numeric(df["key_rate"], errors="coerce")
        except Exception as exc:
            self.logger.error(
                f"[KEYRATE SERVICE] ERROR: Failed to parse rates - {type(exc).__name__}: {str(exc)}"
            )
            raise ValueError(f"Failed to parse key_rate column: {str(exc)}") from exc
        
        # Check for NaN values
        nan_count = df["key_rate"].isna().sum()
        if nan_count > 0:
            self.logger.warning(
                f"[KEYRATE SERVICE] WARNING: Found {nan_count} NaN values in key_rate column"
            )
        
        # Drop rows with NaN values
        df = df.dropna(subset=["date", "key_rate"])
        
        # Convert to dictionary: date (YYYY-MM-DD) -> rate (float)
        result = {}
        for _, row in df.iterrows():
            date_obj = row["date"].date()
            rate = float(row["key_rate"])
            date_str = date_obj.isoformat()
            result[date_str] = rate
        
        self.logger.info(
            f"[KEYRATE SERVICE] Successfully parsed {len(result)} key rate entries"
        )
        
        return result
    
    def load_keyrate_data(self) -> Dict[str, float]:
        """
        Load key rate data from CBR and update local file.
        
        This method:
        1. Loads existing data from JSON file
        2. Determines date_from (last date in file or default)
        3. Sets date_to to current date
        4. Fetches new data from CBR
        5. Merges new data with existing data
        6. Saves updated data to file
        
        Returns:
            Dictionary with all key rate data (date -> rate)
        
        Raises:
            RuntimeError: If data cannot be fetched or parsed
        """
        self.logger.info("[KEYRATE SERVICE] Starting key rate data load...")
        
        # Load existing data
        existing_data = self._load_keyrate_data()
        
        # Determine date_from
        last_date = self._get_last_date_in_data()
        if last_date is None:
            date_from = self.DEFAULT_START_DATE
            self.logger.info(
                f"[KEYRATE SERVICE] No existing data, using default start date: "
                f"{date_from.strftime('%d.%m.%Y')}"
            )
        else:
            date_from = last_date
            self.logger.info(
                f"[KEYRATE SERVICE] Using last date from existing data: "
                f"{date_from.strftime('%d.%m.%Y')}"
            )
        
        # Set date_to to current date
        date_to = date.today()
        self.logger.info(
            f"[KEYRATE SERVICE] Using current date as end date: {date_to.strftime('%d.%m.%Y')}"
        )
        
        # Fetch new data
        new_data = self._fetch_and_parse_keyrate(date_from, date_to)
        
        # Merge with existing data (new data overwrites old data for same dates)
        existing_data.update(new_data)
        
        # Save updated data
        self._save_keyrate_data(existing_data)
        
        self.logger.info(
            f"[KEYRATE SERVICE] Key rate data load completed. "
            f"Total entries: {len(existing_data)}, New entries: {len(new_data)}"
        )
        
        return existing_data


# Global service instance
_keyrate_service: Optional[KeyRateService] = None


def init_keyrate_service(data_dir: Path):
    """
    Initialize global keyrate service instance.
    
    Args:
        data_dir: Path to data directory
    """
    global _keyrate_service
    _keyrate_service = KeyRateService(data_dir)


def get_keyrate_service() -> KeyRateService:
    """
    Get global keyrate service instance.
    
    Returns:
        KeyRateService instance
    
    Raises:
        RuntimeError: If service not initialized
    """
    if _keyrate_service is None:
        raise RuntimeError("KeyRateService not initialized. Call init_keyrate_service() first.")
    return _keyrate_service
