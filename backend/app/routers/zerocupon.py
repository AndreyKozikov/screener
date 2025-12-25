import os
import re
import asyncio
import math
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
import pandas as pd
import io
import json
import httpx

from app.utils.logger import get_data_update_logger

router = APIRouter(prefix="/api/zerocupon", tags=["zerocupon"])


def _get_zerocupon_path() -> Path:
    """Get path to zerocupon.csv file."""
    # Script is in backend/app/routers/, data is in backend/app/data/
    data_dir = Path(__file__).parent.parent / "data"
    csv_path = data_dir / "zerocupon.csv"
    return csv_path


@router.get("/data")
async def get_zerocupon_data(
    date_from: Optional[str] = Query(None, description="Start date in DD.MM.YYYY format"),
    date_to: Optional[str] = Query(None, description="End date in DD.MM.YYYY format"),
):
    """
    Get zero-coupon yield curve data filtered by date range.
    
    Returns data as JSON array of records.
    By default returns data for the last year.
    """
    csv_path = _get_zerocupon_path()
    
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="zerocupon.csv file not found")
    
    try:
        # Read CSV with semicolon separator
        df = pd.read_csv(csv_path, sep=";", encoding="utf-8-sig", decimal=".")
        
        # Check if DataFrame is empty
        if df.empty:
            return {
                "data": [],
                "count": 0,
                "date_from": date_from,
                "date_to": date_to,
            }
        
        # Check if "Дата" column exists
        if "Дата" not in df.columns:
            raise HTTPException(status_code=500, detail="CSV file missing 'Дата' column")
        
        # Parse date column
        df["Дата"] = pd.to_datetime(df["Дата"], dayfirst=True, errors="coerce")
        
        # Remove rows with invalid dates
        df = df[df["Дата"].notna()]
        
        # Check if DataFrame is empty after date parsing
        if df.empty:
            return {
                "data": [],
                "count": 0,
                "date_from": date_from,
                "date_to": date_to,
            }
        
        # Convert all numeric columns (except Дата and Время) to float
        # This ensures proper numeric type handling
        for col in df.columns:
            if col not in ["Дата", "Время"]:
                # Try to convert to numeric, replacing commas with dots if needed
                df[col] = pd.to_numeric(
                    df[col].astype(str).str.replace(",", ".", regex=False),
                    errors="coerce"
                )
        
        # Filter by date range
        if date_from:
            try:
                date_from_dt = datetime.strptime(date_from, "%d.%m.%Y")
                df = df[df["Дата"] >= date_from_dt]
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date_from format. Use DD.MM.YYYY")
        
        if date_to:
            try:
                date_to_dt = datetime.strptime(date_to, "%d.%m.%Y")
                # Include the end date (set time to end of day)
                date_to_dt = date_to_dt.replace(hour=23, minute=59, second=59)
                df = df[df["Дата"] <= date_to_dt]
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date_to format. Use DD.MM.YYYY")
        
        # If no dates provided, default to last year
        if not date_from and not date_to:
            one_year_ago = datetime.now() - timedelta(days=365)
            df = df[df["Дата"] >= one_year_ago]
        
        # Check if DataFrame is empty after date filtering
        if df.empty:
            return {
                "data": [],
                "count": 0,
                "date_from": date_from,
                "date_to": date_to,
            }
        
        # Filter out weekends (Saturday=5, Sunday=6)
        # Only keep weekdays (Monday=0 through Friday=4)
        df = df[df["Дата"].dt.weekday < 5]
        
        # Check if DataFrame is empty after weekend filtering
        if df.empty:
            return {
                "data": [],
                "count": 0,
                "date_from": date_from,
                "date_to": date_to,
            }
        
        # Format date back to DD.MM.YYYY for response
        df["Дата"] = df["Дата"].dt.strftime("%d.%m.%Y")
        
        # Exclude 30 years column from display and calculations
        columns_to_exclude = [col for col in df.columns if "30" in col and "лет" in col]
        if columns_to_exclude:
            df = df.drop(columns=columns_to_exclude)
        
        # Convert to records (list of dicts) - use orient='records' for proper JSON
        records = df.to_dict(orient="records")
        
        # Replace all NaN, NaT, and inf values with None for proper JSON serialization
        for record in records:
            for key, value in record.items():
                if pd.isna(value):
                    record[key] = None
                elif isinstance(value, float):
                    if math.isnan(value) or math.isinf(value):
                        record[key] = None
        
        return {
            "data": records,
            "count": len(records),
            "date_from": date_from,
            "date_to": date_to,
        }
    
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log the full error for debugging
        import traceback
        error_detail = f"Error reading zerocupon data: {str(e)}\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail)


@router.get("/download")
async def download_zerocupon_json(
    date_from: Optional[str] = Query(None, description="Start date in DD.MM.YYYY format"),
    date_to: Optional[str] = Query(None, description="End date in DD.MM.YYYY format"),
):
    """
    Download zero-coupon yield curve data as JSON file.
    
    Returns filtered data as JSON file with LLM-friendly structure.
    By default returns data for the last year.
    """
    csv_path = _get_zerocupon_path()
    
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="zerocupon.csv file not found")
    
    try:
        # Read CSV with semicolon separator
        df = pd.read_csv(csv_path, sep=";", encoding="utf-8-sig", decimal=".")
        
        # Check if DataFrame is empty
        if df.empty:
            raise HTTPException(status_code=404, detail="CSV file is empty")
        
        # Check if "Дата" column exists
        if "Дата" not in df.columns:
            raise HTTPException(status_code=500, detail="CSV file missing 'Дата' column")
        
        # Parse date column
        df["Дата"] = pd.to_datetime(df["Дата"], dayfirst=True, errors="coerce")
        
        # Remove rows with invalid dates
        df = df[df["Дата"].notna()]
        
        # Check if DataFrame is empty after date parsing
        if df.empty:
            raise HTTPException(status_code=404, detail="No valid dates found in CSV file")
        
        # Convert all numeric columns (except Дата and Время) to float
        for col in df.columns:
            if col not in ["Дата", "Время"]:
                df[col] = pd.to_numeric(
                    df[col].astype(str).str.replace(",", ".", regex=False),
                    errors="coerce"
                )
        
        # Filter by date range
        if date_from:
            try:
                date_from_dt = datetime.strptime(date_from, "%d.%m.%Y")
                df = df[df["Дата"] >= date_from_dt]
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date_from format. Use DD.MM.YYYY")
        
        if date_to:
            try:
                date_to_dt = datetime.strptime(date_to, "%d.%m.%Y")
                date_to_dt = date_to_dt.replace(hour=23, minute=59, second=59)
                df = df[df["Дата"] <= date_to_dt]
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date_to format. Use DD.MM.YYYY")
        
        # If no dates provided, default to last year
        if not date_from and not date_to:
            one_year_ago = datetime.now() - timedelta(days=365)
            df = df[df["Дата"] >= one_year_ago]
        
        # Check if DataFrame is empty after date filtering
        if df.empty:
            raise HTTPException(status_code=404, detail="No data found for the specified date range")
        
        # Filter out weekends (Saturday=5, Sunday=6)
        # Only keep weekdays (Monday=0 through Friday=4)
        df = df[df["Дата"].dt.weekday < 5]
        
        # Check if DataFrame is empty after weekend filtering
        if df.empty:
            raise HTTPException(status_code=404, detail="No weekday data found for the specified date range")
        
        # Format date back to DD.MM.YYYY for display
        df["Дата"] = df["Дата"].dt.strftime("%d.%m.%Y")
        
        # Exclude 30 years column from display and calculations
        columns_to_exclude = [col for col in df.columns if "30" in col and "лет" in col]
        if columns_to_exclude:
            df = df.drop(columns=columns_to_exclude)
        
        # Replace NaN with None for proper JSON serialization
        df = df.where(pd.notnull(df), None)
        
        # Build LLM-friendly JSON structure
        # Extract period columns (all except Дата and Время)
        period_columns = [col for col in df.columns if col not in ["Дата", "Время"]]
        
        # Extract period values (years) from column names like "Срок 0.25 лет"
        def extract_period_years(col_name: str) -> Optional[float]:
            """Extract numeric period value from column name like 'Срок 0.25 лет'"""
            import re
            match = re.search(r'(\d+\.?\d*)', col_name)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    return None
            return None
        
        # Build data array
        data_records = []
        for _, row in df.iterrows():
            record: Dict[str, Any] = {
                "date": row["Дата"],
                "time": row["Время"] if pd.notna(row["Время"]) else None,
                "yield_curve": {}
            }
            
            # Add yield values by period (in years)
            for col in period_columns:
                period_years = extract_period_years(col)
                if period_years is not None:
                    value = row[col]
                    # Check for NaN, None, and inf values
                    if pd.notna(value) and value is not None:
                        try:
                            float_value = float(value)
                            # Check for NaN and inf
                            if not (math.isnan(float_value) or math.isinf(float_value)):
                                record["yield_curve"][str(period_years)] = float_value
                        except (ValueError, TypeError):
                            # Skip invalid values
                            pass
            
            data_records.append(record)
        
        # Build metadata
        periods_list = []
        for col in period_columns:
            period = extract_period_years(col)
            if period is not None:
                periods_list.append(period)
        
        metadata = {
            "title": "Кривая бескупонной доходности",
            "description": "Данные кривой бескупонной доходности (БКДЦТ) с различными сроками до погашения",
            "date_from": date_from or "автоматически (последний год)",
            "date_to": date_to or "автоматически (сегодня)",
            "record_count": len(data_records),
            "export_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "periods": sorted(periods_list)
        }
        
        # Build field descriptions
        field_descriptions = {
            "date": "Дата расчета кривой доходности в формате DD.MM.YYYY",
            "time": "Время расчета (если доступно)",
            "yield_curve": "Словарь значений доходности по срокам до погашения (в годах). Ключи - сроки в годах, значения - доходность в процентах годовых"
        }
        
        # Build final JSON structure
        export_data = {
            "metadata": metadata,
            "field_descriptions": field_descriptions,
            "data": data_records
        }
        
        # Convert to JSON string with proper formatting
        json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
        
        # Generate filename with date range
        filename = "zerocupon"
        if date_from or date_to:
            if date_from:
                filename += f"_{date_from.replace('.', '-')}"
            if date_to:
                filename += f"_{date_to.replace('.', '-')}"
        else:
            filename += "_last_year"
        filename += ".json"
        
        return Response(
            content=json_str,
            media_type="application/json; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log the full error for debugging
        import traceback
        error_detail = f"Error generating JSON download: {str(e)}\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail)


def _parse_jsonp_response(text: str) -> Dict[str, Any]:
    """
    Parse JSONP response from MOEX API.
    Removes JSON_CALLBACK wrapper and extracts JSON data.
    """
    # Remove JSON_CALLBACK wrapper: JSON_CALLBACK(...) -> ...
    # Match pattern: JSON_CALLBACK( ... )
    match = re.match(r'^\s*JSON_CALLBACK\s*\((.*)\)\s*$', text, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        # If no wrapper, try to parse as-is
        json_str = text
    
    # Parse JSON
    try:
        data = json.loads(json_str)
        return data
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON: {str(e)}")


def _get_last_date_from_csv(csv_path: Path) -> Optional[datetime]:
    """
    Get the last date from CSV file.
    Returns None if file is empty or doesn't exist.
    """
    if not csv_path.exists():
        return None
    
    try:
        df = pd.read_csv(csv_path, sep=";", encoding="utf-8-sig", nrows=10)
        if df.empty or "Дата" not in df.columns:
            return None
        
        # Parse first date (most recent is at the top)
        first_date_str = df.iloc[0]["Дата"]
        last_date = pd.to_datetime(first_date_str, dayfirst=True, errors="coerce")
        
        if pd.isna(last_date):
            return None
        
        return last_date.to_pydatetime()
    except Exception as e:
        print(f"Error reading last date from CSV: {e}")
        return None


def _fetch_zerocupon_data_for_date(target_date: datetime) -> Optional[List[Dict[str, Any]]]:
    """
    Fetch zero-coupon yield curve data from MOEX API for a specific date.
    Returns list of yield data items or None if request fails.
    """
    # Format date as YYYY-MM-DD
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"https://iss.moex.com/iss/engines/stock/zcyc.jsonp?iss.meta=off&iss.json=extended&callback=JSON_CALLBACK&lang=ru&iss.only=yearyields&date={date_str}"
    
    try:
        # Use httpx in sync mode for this function (will be called in thread)
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url)
            response.raise_for_status()
            
            # Parse JSONP response
            data = _parse_jsonp_response(response.text)
            
            # Extract yearyields from the nested structure
            if isinstance(data, list) and len(data) >= 2:
                # Data structure: [{"charsetinfo": ...}, {"yearyields": [...]}]
                for item in data:
                    if isinstance(item, dict) and "yearyields" in item:
                        return item["yearyields"]
            
            return None
    except Exception as e:
        print(f"Error fetching data for {date_str}: {e}")
        return None


def _add_data_to_csv(csv_path: Path, date_obj: datetime, time_str: str, yields_data: List[Dict[str, Any]]):
    """
    Add new row to CSV file with yield curve data.
    """
    # Map period values to column names
    # Note: 30 years period is excluded from calculations and display
    period_to_column = {
        0.25: "Срок 0.25 лет",
        0.50: "Срок 0.5 лет",
        0.75: "Срок 0.75 лет",
        1.00: "Срок 1.0 лет",
        2.00: "Срок 2.0 лет",
        3.00: "Срок 3.0 лет",
        5.00: "Срок 5.0 лет",
        7.00: "Срок 7.0 лет",
        10.00: "Срок 10.0 лет",
        15.00: "Срок 15.0 лет",
        20.00: "Срок 20.0 лет",
        # 30.00: "Срок 30.0 лет",  # Excluded from calculations and display
    }
    
    # Create row data with all columns initialized
    date_str = date_obj.strftime("%d.%m.%Y")
    row_data = {"Дата": date_str, "Время": time_str}
    
    # Initialize all period columns with empty strings
    for column_name in period_to_column.values():
        row_data[column_name] = ""
    
    # Add yield values for each period
    for yield_item in yields_data:
        period = yield_item.get("period")
        value = yield_item.get("value")
        
        if period in period_to_column and value is not None:
            column_name = period_to_column[period]
            # Format as number with 2 decimal places, using dot as decimal separator
            row_data[column_name] = f"{float(value):.2f}"
    
    # Read existing CSV
    if csv_path.exists():
        df = pd.read_csv(csv_path, sep=";", encoding="utf-8-sig")
    else:
        # Create new DataFrame with headers
        columns = ["Дата", "Время"] + list(period_to_column.values())
        df = pd.DataFrame(columns=columns)
    
    # Create new row DataFrame
    new_row = pd.DataFrame([row_data])
    
    # Prepend new row (most recent data at the top)
    df = pd.concat([new_row, df], ignore_index=True)
    
    # Save to CSV
    df.to_csv(csv_path, sep=";", index=False, encoding="utf-8-sig")


def refresh_zerocupon_data() -> Dict[str, Any]:
    """
    Refresh zero-coupon yield curve data from MOEX API.
    Checks last date in CSV and fetches missing data up to yesterday.
    """
    logger = get_data_update_logger()
    logger.info("[REFRESH ZEROCOUPON] Starting zerocupon data refresh")
    
    csv_path = _get_zerocupon_path()
    logger.info(f"[REFRESH ZEROCOUPON] Using CSV path: {csv_path}")
    
    # Get last date from CSV
    last_date = _get_last_date_from_csv(csv_path)
    logger.info(f"[REFRESH ZEROCOUPON] Last date in CSV: {last_date.strftime('%Y-%m-%d') if last_date else 'None'}")
    
    # Determine start date (next day after last date, or 30 days ago if no data)
    if last_date:
        start_date = last_date + timedelta(days=1)
    else:
        # If no data, start from 30 days ago
        start_date = datetime.now() - timedelta(days=30)
    
    # End date is yesterday (don't fetch today as data might not be available)
    end_date = datetime.now() - timedelta(days=1)
    
    logger.info(f"[REFRESH ZEROCOUPON] Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    # Skip if start_date is after end_date
    if start_date > end_date:
        logger.info("[REFRESH ZEROCOUPON] Data is up to date, no refresh needed")
        return {
            "status": "ok",
            "message": "Data is up to date",
            "last_date": last_date.strftime("%d.%m.%Y") if last_date else None,
            "dates_fetched": 0,
        }
    
    # Fetch data for each date
    dates_fetched = 0
    dates_failed = 0
    current_date = start_date
    
    while current_date <= end_date:
        # Skip weekends (Saturday=5, Sunday=6)
        if current_date.weekday() < 5:  # Monday=0, Friday=4
            yields_data = _fetch_zerocupon_data_for_date(current_date)
            
            if yields_data and len(yields_data) > 0:
                # Extract time from first yield item
                time_str = yields_data[0].get("tradetime", "18:49:59")
                # Extract only time part (HH:MM:SS)
                if " " in time_str:
                    time_str = time_str.split(" ")[-1]
                
                # Add to CSV
                _add_data_to_csv(csv_path, current_date, time_str, yields_data)
                dates_fetched += 1
                logger.info(f"[REFRESH ZEROCOUPON] Fetched data for {current_date.strftime('%Y-%m-%d')}")
            else:
                dates_failed += 1
                logger.warning(f"[REFRESH ZEROCOUPON] No data available for {current_date.strftime('%Y-%m-%d')}")
        
        current_date += timedelta(days=1)
    
    result = {
        "status": "ok",
        "message": f"Fetched {dates_fetched} dates, {dates_failed} failed",
        "last_date": last_date.strftime("%d.%m.%Y") if last_date else None,
        "start_date": start_date.strftime("%d.%m.%Y"),
        "end_date": end_date.strftime("%d.%m.%Y"),
        "dates_fetched": dates_fetched,
        "dates_failed": dates_failed,
    }
    
    logger.info(f"[REFRESH ZEROCOUPON] Refresh completed: {result}")
    return result


@router.post("/refresh")
async def refresh_zerocupon():
    """
    Refresh zero-coupon yield curve data from MOEX API.
    Fetches missing data from the last date in CSV up to yesterday.
    """
    logger = get_data_update_logger()
    logger.info("[API /zerocupon/refresh] Received request to refresh zerocupon data")
    
    try:
        # Run in thread to avoid blocking
        result = await asyncio.to_thread(refresh_zerocupon_data)
        logger.info(f"[API /zerocupon/refresh] Refresh completed successfully: {result}")
        return result
    except Exception as e:
        logger.error(f"[API /zerocupon/refresh] ERROR: {type(e).__name__} - {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error refreshing zerocupon data: {str(e)}")

