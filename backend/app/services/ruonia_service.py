import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Any
from urllib.parse import urlencode
import requests

import orjson
import pandas as pd

from app.utils.logger import get_data_update_logger


class RuoniaService:
    """Service for handling RUONIA rate data from CBR"""
    
    # Base URL for CBR RUONIA Excel download
    CBR_RUONIA_BASE_URL = "https://www.cbr.ru/Queries/UniDbQuery/DownloadExcel/14315"
    
    # Default start date if no data exists yet
    DEFAULT_START_DATE = date(2010, 1, 11)
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.ruonia_file = data_dir / "ruonia.json"
        self.logger = get_data_update_logger()
    
    def _load_ruonia_data(self) -> Dict[str, Dict[str, Any]]:
        """Load RUONIA data from JSON file"""
        self.logger.info(f"[RUONIA SERVICE] Loading RUONIA data from file: {self.ruonia_file}")
        
        if not self.ruonia_file.exists():
            self.logger.info("[RUONIA SERVICE] File does not exist, creating empty file")
            empty_data: Dict[str, Dict[str, Any]] = {}
            self._save_ruonia_data(empty_data)
            return empty_data
        
        try:
            file_size = self.ruonia_file.stat().st_size
            self.logger.info(f"[RUONIA SERVICE] File exists, size: {file_size} bytes")
            
            with open(self.ruonia_file, 'rb') as f:
                data = orjson.loads(f.read())
            
            if not isinstance(data, dict):
                self.logger.warning("[RUONIA SERVICE] Data is not a dictionary, initializing empty dict")
                empty_data: Dict[str, Dict[str, Any]] = {}
                self._save_ruonia_data(empty_data)
                return empty_data
            
            entries_count = len(data)
            self.logger.info(f"[RUONIA SERVICE] Successfully loaded {entries_count} RUONIA entries from file")
            return data
            
        except (orjson.JSONDecodeError, IOError) as exc:
            self.logger.error(f"[RUONIA SERVICE] ERROR: Failed to load file - {type(exc).__name__}: {str(exc)}")
            self.logger.info("[RUONIA SERVICE] Creating fresh empty file")
            empty_data: Dict[str, Dict[str, Any]] = {}
            self._save_ruonia_data(empty_data)
            return empty_data
    
    def _save_ruonia_data(self, data: Dict[str, Dict[str, Any]]):
        """Save RUONIA data to JSON file"""
        entries_count = len(data)
        self.logger.info(f"[RUONIA SERVICE] Saving {entries_count} RUONIA entries to file: {self.ruonia_file}")
        
        serialized = orjson.dumps(
            data,
            option=orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE,
        )
        
        file_size = len(serialized)
        self.ruonia_file.write_bytes(serialized)
        self.logger.info(f"[RUONIA SERVICE] File saved successfully, size: {file_size} bytes")
    
    def _get_last_date_from_data(self, ruonia_data: Dict[str, Dict[str, Any]]) -> Optional[date]:
        """Get the latest date from existing RUONIA data"""
        if not ruonia_data:
            return None
        
        dates = []
        for date_str in ruonia_data.keys():
            try:
                parsed_date = datetime.fromisoformat(date_str).date()
                dates.append(parsed_date)
            except (ValueError, TypeError):
                continue
        
        if not dates:
            return None
        
        last_date = max(dates)
        self.logger.info(f"[RUONIA SERVICE] Last date in existing data: {last_date.isoformat()}")
        return last_date
    
    def _format_date_for_url(self, date_obj: date, format_type: str = "ddmmyyyy") -> str:
        """Format date for URL parameters
        
        Args:
            date_obj: Date object to format
            format_type: "ddmmyyyy" for From/To (DD.MM.YYYY) or "mmddyyyy" for FromDate/ToDate (MM/DD/YYYY)
        """
        if format_type == "ddmmyyyy":
            return date_obj.strftime("%d.%m.%Y")
        elif format_type == "mmddyyyy":
            return date_obj.strftime("%m/%d/%Y")
        else:
            raise ValueError(f"Unknown format_type: {format_type}")
    
    def _build_download_url(self, from_date: date, to_date: date) -> str:
        """Build URL for downloading RUONIA Excel file from CBR"""
        params = {
            "Posted": "True",
            "From": self._format_date_for_url(from_date, "ddmmyyyy"),
            "To": self._format_date_for_url(to_date, "ddmmyyyy"),
            "FromDate": self._format_date_for_url(from_date, "mmddyyyy"),
            "ToDate": self._format_date_for_url(to_date, "mmddyyyy"),
            "backUrl": "/hd_base/ruonia/dynamics/?UniDbQuery.Posted=True"
        }
        
        url = self.CBR_RUONIA_BASE_URL + "?" + urlencode(params)
        self.logger.info(f"[RUONIA SERVICE] Built download URL: {url}")
        return url
    
    def _download_excel_file(self, url: str) -> Path:
        """Download Excel file from URL and save to temporary file"""
        self.logger.info(f"[RUONIA SERVICE] Downloading Excel file from: {url}")
        
        try:
            response = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=60
            )
            
            self.logger.info(f"[RUONIA SERVICE] Download response: status_code={response.status_code}")
            response.raise_for_status()
            
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
            temp_path = Path(temp_file.name)
            
            # Write content to temporary file
            temp_file.write(response.content)
            temp_file.close()
            
            file_size = temp_path.stat().st_size
            self.logger.info(f"[RUONIA SERVICE] Excel file saved to temporary file: {temp_path}, size: {file_size} bytes")
            
            return temp_path
            
        except requests.RequestException as exc:
            error_type = type(exc).__name__
            self.logger.error(f"[RUONIA SERVICE] ERROR: Download failed - {error_type}: {str(exc)}")
            raise RuntimeError(f"Failed to download RUONIA Excel file from CBR: {exc}") from exc
        except Exception as exc:
            error_type = type(exc).__name__
            self.logger.error(f"[RUONIA SERVICE] ERROR: Unexpected error during download - {error_type}: {str(exc)}")
            raise RuntimeError(f"Failed to download RUONIA Excel file: {exc}") from exc
    
    def _parse_excel_file(self, excel_path: Path) -> Dict[str, Dict[str, Any]]:
        """Parse Excel file and convert to dictionary with DT as key"""
        self.logger.info(f"[RUONIA SERVICE] Parsing Excel file: {excel_path}")
        
        try:
            # Read Excel file
            df = pd.read_excel(excel_path, engine='openpyxl')
            
            self.logger.info(f"[RUONIA SERVICE] Excel file loaded, rows: {len(df)}, columns: {df.columns.tolist()}")
            
            # Check if DT column exists
            if 'DT' not in df.columns:
                raise ValueError("Column 'DT' not found in Excel file")
            
            # Convert to dictionary where key is DT (date) and value is the row data
            result = {}
            
            for _, row in df.iterrows():
                dt_value = row['DT']
                
                # Handle different date formats
                if pd.isna(dt_value):
                    continue
                
                # Convert date to ISO format string
                if isinstance(dt_value, datetime):
                    date_str = dt_value.date().isoformat()
                elif isinstance(dt_value, date):
                    date_str = dt_value.isoformat()
                elif isinstance(dt_value, pd.Timestamp):
                    date_str = dt_value.date().isoformat()
                else:
                    # Try to parse as date string
                    try:
                        parsed_date = pd.to_datetime(dt_value).date()
                        date_str = parsed_date.isoformat()
                    except (ValueError, TypeError):
                        self.logger.warning(f"[RUONIA SERVICE] WARNING: Could not parse date: {dt_value}")
                        continue
                
                # Convert row to dictionary, handling NaN values
                row_dict = {}
                for col in df.columns:
                    value = row[col]
                    # Convert NaN to None for JSON serialization
                    if pd.isna(value):
                        row_dict[col] = None
                    else:
                        # Keep original type for numbers
                        if isinstance(value, (int, float)):
                            row_dict[col] = value
                        elif isinstance(value, (datetime, pd.Timestamp)):
                            row_dict[col] = value.isoformat()
                        elif isinstance(value, date):
                            row_dict[col] = value.isoformat()
                        else:
                            row_dict[col] = str(value)
                
                result[date_str] = row_dict
            
            parsed_count = len(result)
            self.logger.info(f"[RUONIA SERVICE] Successfully parsed {parsed_count} entries from Excel file")
            
            return result
            
        except Exception as exc:
            error_type = type(exc).__name__
            self.logger.error(f"[RUONIA SERVICE] ERROR: Failed to parse Excel file - {error_type}: {str(exc)}")
            raise RuntimeError(f"Failed to parse RUONIA Excel file: {exc}") from exc
        finally:
            # Clean up temporary file
            try:
                if excel_path.exists():
                    excel_path.unlink()
                    self.logger.info(f"[RUONIA SERVICE] Temporary file deleted: {excel_path}")
            except Exception as exc:
                self.logger.warning(f"[RUONIA SERVICE] WARNING: Could not delete temporary file: {exc}")
    
    def update_ruonia_data(self) -> Dict[str, Any]:
        """
        Update RUONIA data by downloading from CBR and merging with existing data.
        
        Checks if data file exists before starting. If file doesn't exist,
        sets start date to 11.01.2010.
        
        Returns:
            Dictionary with update result
        """
        self.logger.info("[RUONIA SERVICE] Starting RUONIA data update")
        
        try:
            # Check if data file exists before starting
            file_exists = self.ruonia_file.exists()
            self.logger.info(f"[RUONIA SERVICE] Data file exists: {file_exists}")
            
            # Load existing data
            existing_data = self._load_ruonia_data()
            
            # Determine date range for download
            last_date = self._get_last_date_from_data(existing_data)
            
            if last_date:
                # Start from next day after last date
                from_date = last_date + timedelta(days=1)
                self.logger.info(f"[RUONIA SERVICE] Using date range from existing data: {from_date.isoformat()}")
            else:
                # File doesn't exist or is empty - start from default date 11.01.2010
                from_date = self.DEFAULT_START_DATE
                if not file_exists:
                    self.logger.info(f"[RUONIA SERVICE] Data file does not exist, using default start date: {from_date.isoformat()}")
                else:
                    self.logger.info(f"[RUONIA SERVICE] No data in file, using default start date: {from_date.isoformat()}")
            
            # End date is today
            to_date = date.today()
            self.logger.info(f"[RUONIA SERVICE] End date: {to_date.isoformat()}")
            
            # Check if we need to download anything
            if from_date > to_date:
                self.logger.info("[RUONIA SERVICE] No new data to download (from_date > to_date)")
                return {
                    'status': 'ok',
                    'message': 'No new data to download',
                    'entries_count': len(existing_data),
                    'updated': False
                }
            
            # Build download URL
            download_url = self._build_download_url(from_date, to_date)
            
            # Download Excel file
            excel_path = self._download_excel_file(download_url)
            
            # Parse Excel file
            new_data = self._parse_excel_file(excel_path)
            
            # Merge with existing data (new data overwrites existing if same date)
            updated_count = 0
            new_count = 0
            
            for date_str, row_data in new_data.items():
                if date_str in existing_data:
                    updated_count += 1
                else:
                    new_count += 1
                existing_data[date_str] = row_data
            
            # Save merged data
            self._save_ruonia_data(existing_data)
            
            total_count = len(existing_data)
            
            self.logger.info(f"[RUONIA SERVICE] Update completed: {new_count} new entries, {updated_count} updated entries, total: {total_count}")
            
            return {
                'status': 'ok',
                'message': 'RUONIA data updated successfully',
                'from_date': from_date.isoformat(),
                'to_date': to_date.isoformat(),
                'new_entries': new_count,
                'updated_entries': updated_count,
                'total_entries': total_count,
                'updated': True
            }
            
        except Exception as exc:
            error_type = type(exc).__name__
            self.logger.error(f"[RUONIA SERVICE] ERROR: Failed to update RUONIA data - {error_type}: {str(exc)}")
            return {
                'status': 'error',
                'error': str(exc),
                'updated': False
            }
    
    def get_ruonia_data(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all RUONIA data.
        
        Returns:
            Dictionary with dates as keys and row data as values
        """
        return self._load_ruonia_data()


# Singleton instance
_ruonia_service: Optional[RuoniaService] = None


def init_ruonia_service(data_dir: Path):
    """Initialize the RUONIA service singleton"""
    global _ruonia_service
    _ruonia_service = RuoniaService(data_dir)


def get_ruonia_service() -> RuoniaService:
    """Get the RUONIA service instance"""
    if _ruonia_service is None:
        raise RuntimeError("RUONIA service not initialized")
    return _ruonia_service
