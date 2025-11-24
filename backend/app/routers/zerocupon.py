import os
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
import pandas as pd
import io
import json

router = APIRouter(prefix="/api/zerocupon", tags=["zerocupon"])


def _get_zerocupon_path() -> Path:
    """Get path to zerocupon.csv file."""
    # Script is in backend/app/routers/, need to go up to project root
    project_root = Path(__file__).parent.parent.parent.parent
    csv_path = project_root / "zerocupon" / "zerocupon.csv"
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
        
        # Parse date column
        df["Дата"] = pd.to_datetime(df["Дата"], dayfirst=True, errors="coerce")
        
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
        
        # Format date back to DD.MM.YYYY for response
        df["Дата"] = df["Дата"].dt.strftime("%d.%m.%Y")
        
        # Replace NaN with None for proper JSON serialization
        df = df.where(pd.notnull(df), None)
        
        # Convert to records (list of dicts) - use orient='records' for proper JSON
        records = df.to_dict(orient="records")
        
        return {
            "data": records,
            "count": len(records),
            "date_from": date_from,
            "date_to": date_to,
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading zerocupon data: {str(e)}")


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
        
        # Parse date column
        df["Дата"] = pd.to_datetime(df["Дата"], dayfirst=True, errors="coerce")
        
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
        
        # Format date back to DD.MM.YYYY for display
        df["Дата"] = df["Дата"].dt.strftime("%d.%m.%Y")
        
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
                    if pd.notna(value) and value is not None:
                        record["yield_curve"][str(period_years)] = float(value)
            
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
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating JSON download: {str(e)}")

