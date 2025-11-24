import json
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


def _get_forecast_path() -> Path:
    """Get path to forecast JSON file."""
    project_root = Path(__file__).parent.parent.parent.parent
    json_path = project_root / "data" / "forecast_251024.json"
    return json_path


def _load_forecast_data() -> dict:
    """Load forecast data from JSON file."""
    json_path = _get_forecast_path()
    
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="forecast_251024.json file not found")
    
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"Error reading forecast data: {str(e)}")


@router.get("/dates")
async def get_available_dates():
    """
    Get list of available forecast dates.
    Returns dates sorted in descending order (newest first).
    """
    data = _load_forecast_data()
    
    # Extract all date keys (excluding "названия")
    dates = [key for key in data.keys() if key != "названия" and key.startswith("20")]
    dates.sort(reverse=True)  # Newest first
    
    return {"dates": dates}


@router.get("/data")
async def get_forecast_data(
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format. If not provided, returns latest available date.")
):
    """
    Get forecast data for a specific date.
    If date is not provided, returns data for the latest available date.
    """
    data = _load_forecast_data()
    
    # If no date provided, get the latest
    if not date:
        dates = [key for key in data.keys() if key != "названия" and key.startswith("20")]
        if not dates:
            raise HTTPException(status_code=404, detail="No forecast data available")
        dates.sort(reverse=True)
        date = dates[0]
    
    # Check if date exists
    if date not in data:
        raise HTTPException(status_code=404, detail=f"Forecast data for date {date} not found")
    
    # Get names mapping
    names = data.get("названия", {})
    
    # Get data for the date
    date_data = data[date]
    
    return {
        "date": date,
        "names": names,
        "data": date_data,
    }


@router.get("/export/json")
async def export_forecast_json(
    dates: Optional[str] = Query(None, description="Comma-separated dates in YYYY-MM-DD format. If not provided, exports latest available date.")
):
    """
    Export forecast data as JSON.
    Returns JSON with dates as top-level keys and Russian field names as keys.
    """
    data = _load_forecast_data()
    names = data.get("названия", {})
    main_names = names.get("основные_показатели", {})
    balance_names = names.get("платёжный_баланс", {})
    
    # Parse dates parameter
    if dates:
        date_list = [d.strip() for d in dates.split(",") if d.strip()]
    else:
        # If no dates provided, get the latest
        available_dates = [key for key in data.keys() if key != "названия" and key.startswith("20")]
        if not available_dates:
            raise HTTPException(status_code=404, detail="No forecast data available")
        available_dates.sort(reverse=True)
        date_list = [available_dates[0]]
    
    # Validate all dates exist
    for date in date_list:
        if date not in data:
            raise HTTPException(status_code=404, detail=f"Forecast data for date {date} not found")
    
    # Build export structure
    export_data = {}
    
    for date in date_list:
        date_data = data[date]
        date_export = {
            "дата_заседания": date_data.get("дата_заседания"),
            "дата_публикации": date_data.get("дата_публикации"),
            "основные_показатели": {},
            "платёжный_баланс": {},
        }
        
        # Process main indicators
        main_indicators = date_data.get("основные_показатели", [])
        if main_indicators:
            years = sorted(set([ind["год"] for ind in main_indicators]))
            for year in years:
                year_data = next((ind for ind in main_indicators if ind["год"] == year), None)
                if year_data:
                    year_dict = {}
                    for key, value in year_data.items():
                        if key == "год":
                            continue
                        if key in main_names:
                            field_name = main_names[key]
                            year_dict[field_name] = value
                    if year_dict:
                        date_export["основные_показатели"][str(year)] = year_dict
        
        # Process balance indicators
        balance_indicators = date_data.get("платёжный_баланс", [])
        if balance_indicators:
            years = sorted(set([ind["год"] for ind in balance_indicators]))
            for year in years:
                year_data = next((ind for ind in balance_indicators if ind["год"] == year), None)
                if year_data:
                    year_dict = {}
                    for key, value in year_data.items():
                        if key == "год":
                            continue
                        if key in balance_names:
                            field_name = balance_names[key]
                            year_dict[field_name] = value
                    if year_dict:
                        date_export["платёжный_баланс"][str(year)] = year_dict
        
        export_data[date] = date_export
    
    # Convert to JSON string
    json_text = json.dumps(export_data, ensure_ascii=False, indent=2)
    
    # Return as downloadable file
    if len(date_list) == 1:
        filename = f"forecast_{date_list[0].replace('-', '_')}.json"
    else:
        filename = f"forecast_{len(date_list)}_dates.json"
    
    return Response(
        content=json_text,
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )

